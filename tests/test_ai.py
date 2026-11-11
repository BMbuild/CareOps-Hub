"""Fonctions Claude testées avec un faux client : aucun appel réel, aucun coût.

Ce qu'on vérifie : ce qui entre dans les données (la gravité) est contrôlé, chaque panne
donne un message lisible, et Claude reçoit l'état calculé par l'application.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai, db
from app.main import app, today
from app.readiness import compute_readiness

REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def reply(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class FakeClaude:
    """Remplace anthropic.Anthropic() : renvoie une réponse prévue ou lève une erreur."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def claude(monkeypatch):
    """Installe un faux Claude ; le test choisit sa réponse avec claude(outcome)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    def install(outcome):
        fake = FakeClaude(outcome)
        monkeypatch.setattr(ai, "_client", lambda: fake)
        return fake

    return install


def test_gravite_proposee_valide(claude):
    claude(reply(json.dumps({"severity": "Critical", "justification": "Blocks EVV with no workaround."})))
    with TestClient(app) as client:
        res = client.post("/api/ai/severity", json={"title": "EVV export rejected", "featureId": "f1"})
    assert res.status_code == 200
    assert res.json() == {"severity": "Critical", "justification": "Blocks EVV with no workaround."}


def test_gravite_inventee_par_claude_est_refusee(claude):
    """Seul endroit où une réponse de Claude entre dans les données : une valeur hors liste est bloquée."""
    claude(reply(json.dumps({"severity": "High", "justification": "Looks serious."})))
    with TestClient(app) as client:
        res = client.post("/api/ai/severity", json={"title": "EVV export rejected"})
    assert res.status_code == 502
    assert res.json()["error"] == "Claude suggested an invalid severity."


@pytest.mark.parametrize("outcome, message", [
    (reply("", stop_reason="refusal"), "Claude declined this request."),
    (reply("   "), "Claude returned no answer."),
    (anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=REQUEST), body=None),
     "Invalid Anthropic API key: check the .env file."),
    (anthropic.RateLimitError("slow down", response=httpx.Response(429, request=REQUEST), body=None),
     "Too many requests to Claude, try again in a moment."),
    (anthropic.InternalServerError("oops", response=httpx.Response(500, request=REQUEST), body=None),
     "Anthropic API error (500)."),
    (anthropic.APIConnectionError(request=REQUEST), "Could not reach the Anthropic API."),
])
def test_chaque_panne_donne_un_message_lisible(claude, outcome, message):
    claude(outcome)
    with TestClient(app) as client:
        res = client.post("/api/ai/summary", json={"clientId": "c1"})
    assert res.status_code == 502
    assert res.json()["error"] == message


def test_sans_cle_les_trois_routes_repondent_503(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(app) as client:
        for route, body in [("summary", {"clientId": "c1"}), ("severity", {"title": "X"}), ("email", {"clientId": "c1"})]:
            res = client.post(f"/api/ai/{route}", json=body)
            assert res.status_code == 503, route
            assert "ANTHROPIC_API_KEY" in res.json()["error"]


def test_entrees_invalides_refusees_sans_appeler_claude(claude):
    fake = claude(reply("unused"))
    with TestClient(app) as client:
        assert client.post("/api/ai/severity", json={"title": "  "}).status_code == 400
        assert client.post("/api/ai/summary", json={"clientId": "unknown"}).status_code == 400
    assert fake.calls == []


def test_claude_recoit_l_etat_calcule_par_l_application(claude):
    fake = claude(reply("Horizon is not ready."))
    with TestClient(app) as client:
        res = client.post("/api/ai/summary", json={"clientId": "c1"})
        assert res.json() == {"text": "Horizon is not ready."}
    prompt = fake.calls[0]["messages"][0]["content"]
    state = db.load_state()
    client_c1 = next(c for c in state["clients"] if c["id"] == "c1")
    readiness = compute_readiness(client_c1, state, today())
    assert "Client: Horizon Home Care" in prompt
    assert f"Computed readiness: {readiness['status']}" in prompt
    assert readiness["reasons"][0] in prompt
    assert "State EVV test" in prompt and "blocker:" in prompt  # étape bloquée et sa cause
    assert "English" in fake.calls[0]["system"]


def test_email_recoit_le_resume_valide(claude):
    fake = claude(reply("Subject: Update\n\nHello."))
    with TestClient(app) as client:
        res = client.post("/api/ai/email", json={"clientId": "c1", "summary": "Approved summary text."})
    assert res.status_code == 200
    assert "Readiness summary already approved:\nApproved summary text." in fake.calls[0]["messages"][0]["content"]


def test_modele_reglable_avec_careops_model(claude, monkeypatch):
    """Le modèle est lu à chaque appel, donc la valeur de .env (chargé après l'import) est bien prise."""
    fake = claude(reply("ok"))
    monkeypatch.delenv("CAREOPS_MODEL", raising=False)
    with TestClient(app) as client:
        client.post("/api/ai/summary", json={"clientId": "c1"})
        monkeypatch.setenv("CAREOPS_MODEL", "claude-sonnet-5-5")
        client.post("/api/ai/summary", json={"clientId": "c1"})
    assert [c["model"] for c in fake.calls] == ["claude-opus-5-5", "claude-sonnet-5-5"]
