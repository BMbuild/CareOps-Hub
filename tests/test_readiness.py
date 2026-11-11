import copy
import json

from app.db import SEED_FILE
from app.readiness import compute_readiness

SEED = json.loads(SEED_FILE.read_text(encoding="utf-8"))
TODAY = "2026-11-04"


def status(state: dict, client_id: str) -> str:
    client = next(c for c in state["clients"] if c["id"] == client_id)
    return compute_readiness(client, state, TODAY)["status"]


def test_probleme_critique_ouvert_rend_non_pret():
    assert status(SEED, "c1") == "Not Ready"


def test_resoudre_le_critique_ne_suffit_pas_si_une_etape_est_bloquee():
    state = copy.deepcopy(SEED)
    next(i for i in state["issues"] if i["id"] == "i1")["state"] = "Resolved"
    assert status(state, "c1") == "Not Ready"
    next(m for m in state["milestones"] if m["id"] == "m3")["status"] = "In Progress"
    assert status(state, "c1") == "In Progress"


def test_etape_en_retard_donne_a_risque():
    assert status(SEED, "c2") == "At Risk"


def test_probleme_moyen_ne_bloque_pas():
    state = copy.deepcopy(SEED)
    next(m for m in state["milestones"] if m["id"] == "m6")["status"] = "Done"
    assert status(state, "c2") == "In Progress"


def test_tout_termine_donne_pret():
    assert status(SEED, "c3") == "Ready"


def test_raisons_au_pluriel():
    state = copy.deepcopy(SEED)
    state["issues"].append({"id": "x", "title": "Autre", "severity": "Critical", "state": "Open", "clientIds": ["c1"]})
    client = next(c for c in state["clients"] if c["id"] == "c1")
    reason = compute_readiness(client, state, TODAY)["reasons"][0]
    assert reason.startswith("2 open critical issues")


def test_en_retard_de_tri():
    """Signal de Sarah : un Critique ouvert sans client, non trié à la fin de son jour ouvré, est en retard de tri."""
    from app.readiness import is_overdue_for_triage

    base = {"severity": "Critical", "state": "Open", "clientIds": [], "allClients": False, "createdAt": "2026-11-03"}
    assert is_overdue_for_triage(base, TODAY)  # créé la veille, toujours sans client
    for change in (
        {"createdAt": TODAY},  # créé aujourd'hui : encore dans le délai
        {"clientIds": ["c1"]},  # trié
        {"allClients": True},  # trié : touche tout le monde
        {"state": "Resolved"},
        {"severity": "Medium"},
        {"createdAt": ""},
    ):
        assert not is_overdue_for_triage({**base, **change}, TODAY), change


def test_retard_de_tri_en_jours_ouvres():
    """Demande de Sarah : un Critique créé le vendredi n'est pas en retard pendant le week-end."""
    from app.readiness import is_overdue_for_triage

    def overdue(created, today):
        issue = {"severity": "Critical", "state": "Open", "clientIds": [], "allClients": False, "createdAt": created}
        return is_overdue_for_triage(issue, today)

    friday, saturday, sunday, monday, tuesday = "2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09", "2026-11-10"
    assert not overdue(friday, friday)
    assert not overdue(friday, saturday)
    assert not overdue(friday, sunday)
    assert overdue(friday, monday)  # pas trié vendredi : en retard le jour ouvré suivant
    # Créé le week-end : à trier le lundi, en retard le mardi.
    assert not overdue(saturday, monday)
    assert overdue(saturday, tuesday)
    assert not overdue(sunday, monday)
    # En semaine, rien ne change : en retard le lendemain.
    assert not overdue(monday, monday)
    assert overdue(monday, tuesday)


def _overdue(created, today):
    from app.readiness import is_overdue_for_triage

    issue = {"severity": "Critical", "state": "Open", "clientIds": [], "allClients": False, "createdAt": created}
    return is_overdue_for_triage(issue, today)


def test_retard_de_tri_saute_les_jours_feries(monkeypatch):
    monkeypatch.delenv("CAREOPS_HOLIDAYS", raising=False)  # réglage par défaut : jours fériés fédéraux
    # Thanksgiving, jeudi 26 novembre 2026 : créé le mercredi, en retard le vendredi, pas le jeudi.
    assert not _overdue("2026-11-25", "2026-11-26")
    assert _overdue("2026-11-25", "2026-11-27")
    # Créé le jour férié : à trier le vendredi, en retard le lundi.
    assert not _overdue("2026-11-26", "2026-11-27")
    assert _overdue("2026-11-26", "2026-11-30")
    # Vendredi 28 mai 2027, avant le Memorial Day (lundi 31) : en retard le mardi, pas le lundi.
    assert not _overdue("2027-05-28", "2027-05-29")
    assert not _overdue("2027-05-28", "2027-05-31")
    assert _overdue("2027-05-28", "2027-06-01")
    # Samedi avant ce lundi férié : à trier le mardi, en retard le mercredi.
    assert not _overdue("2027-05-29", "2027-06-01")
    assert _overdue("2027-05-29", "2027-06-02")


def test_dates_dans_le_fuseau_de_l_agence(monkeypatch):
    """Le serveur (Render) tourne en UTC ; les dates restent celles de New York."""
    from datetime import datetime, timezone

    from app.business_days import local_today

    monkeypatch.delenv("CAREOPS_TZ", raising=False)
    # Jeudi 5 novembre, 23 h 59 à New York = vendredi 6, 04 h 59 UTC : c'est encore jeudi.
    assert local_today(datetime(2026, 11, 6, 4, 59, tzinfo=timezone.utc)) == "2026-11-05"
    assert local_today(datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc)) == "2026-11-06"
    # Jeudi 19 h à New York (vendredi minuit UTC) : un problème du jeudi matin n'est pas encore en retard.
    assert not _overdue("2026-11-05", local_today(datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc)))
    # Le fuseau se règle avec CAREOPS_TZ.
    monkeypatch.setenv("CAREOPS_TZ", "UTC")
    assert local_today(datetime(2026, 11, 6, 4, 59, tzinfo=timezone.utc)) == "2026-11-06"


def test_api_date_les_problemes_dans_le_fuseau_de_l_agence(monkeypatch):
    """La date de création et « aujourd'hui » viennent du même fuseau, pas de celui du serveur."""
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient

    from app import business_days
    from app.main import app

    evening_ny = datetime(2026, 11, 6, 0, 30, tzinfo=timezone.utc)  # jeudi 5, 19 h 30 à New York
    real = business_days.datetime

    class FrozenClock(real):
        @classmethod
        def now(cls, tz=None):
            return evening_ny.astimezone(tz)

    monkeypatch.setattr(business_days, "datetime", FrozenClock)
    with TestClient(app) as client:
        issue = client.post("/api/issues", json={"title": "Bug du soir", "severity": "Critical"}).json()
        assert issue["createdAt"] == "2026-11-05"
        flags = {i["id"]: i["overdueForTriage"] for i in client.get("/api/state").json()["issues"]}
        assert flags[issue["id"]] is False


def test_jours_feries_reglables(monkeypatch):
    """CAREOPS_HOLIDAYS : la réponse de Sarah s'applique par un réglage, sans toucher au code."""
    import pytest

    from app.business_days import FEDERAL_HOLIDAYS, holidays

    monkeypatch.delenv("CAREOPS_HOLIDAYS", raising=False)
    assert holidays() == FEDERAL_HOLIDAYS
    assert not _overdue("2027-05-28", "2027-05-31")  # Memorial Day sauté par défaut

    # L'agence travaille les jours fériés : seuls les week-ends sont sautés.
    monkeypatch.setenv("CAREOPS_HOLIDAYS", "")
    assert holidays() == frozenset()
    assert _overdue("2027-05-28", "2027-05-31")  # vendredi : en retard dès le lundi
    assert _overdue("2026-11-25", "2026-11-26")  # mercredi : en retard le jeudi de Thanksgiving
    assert not _overdue("2026-11-06", "2026-11-08")  # le week-end reste sauté

    # L'agence ne ferme que Thanksgiving et Noël.
    monkeypatch.setenv("CAREOPS_HOLIDAYS", "2026-11-26, 2026-12-25")
    assert not _overdue("2026-11-25", "2026-11-26")  # Thanksgiving sauté
    assert _overdue("2026-11-10", "2026-11-11")  # Veterans Day travaillé

    monkeypatch.setenv("CAREOPS_HOLIDAYS", "2026-13-01")
    with pytest.raises(ValueError, match="CAREOPS_HOLIDAYS"):
        holidays()


def test_tableau_de_decision_du_readme():
    """Le tableau « How readiness works » du README, ligne par ligne, dans son ordre."""
    today = "2026-11-11"
    client = {"id": "c1", "name": "A"}

    def status(milestones=(), issues=()):
        state = {"clients": [client], "milestones": list(milestones), "issues": list(issues)}
        return compute_readiness(client, state, today)["status"]

    def step(st, due="2026-12-01", blocker=""):
        return {"id": st, "clientId": "c1", "name": st, "dueDate": due, "owner": "", "status": st, "blocker": blocker}

    def issue(severity, state="Open", client_ids=("c1",)):
        return {"id": "i", "title": "Bug", "severity": severity, "state": state, "clientIds": list(client_ids), "allClients": False, "createdAt": today}

    late = step("To Do", due="2026-11-01")
    # Not Ready : un Critique non résolu (Open ou In Progress) touche le client, ou une étape est Blocked.
    assert status([step("Done")], [issue("Critical")]) == "Not Ready"
    assert status([step("Done")], [issue("Critical", "In Progress")]) == "Not Ready"
    assert status([step("Blocked", blocker="X"), late]) == "Not Ready"  # prioritaire sur At Risk
    assert status([step("Done")], [issue("Critical", client_ids=())]) == "Not Ready"  # To triage : bloque tout le monde
    # At Risk : sinon, une étape est en retard (même si un Medium est ouvert).
    assert status([late, step("Done")], [issue("Medium")]) == "At Risk"
    # Ready : sinon, toutes les étapes sont Done (un Critique résolu ne compte plus).
    assert status([step("Done")], [issue("Critical", "Resolved"), issue("Low")]) == "Ready"
    # In Progress : tout le reste, y compris aucune étape.
    assert status([step("To Do"), step("Done")]) == "In Progress"
    assert status([]) == "In Progress"
