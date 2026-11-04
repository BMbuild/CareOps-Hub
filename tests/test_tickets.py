"""Test de bout en bout du premier composant : création d'un ticket dans l'espace Produit.

Critère de succès : le ticket est créé, enregistré en base, affiché dans la liste
et retrouvé après un rechargement, sans doublon.
"""

import sqlite3

from fastapi.testclient import TestClient

from app import db
from app.main import app

TICKET = {
    "title": "Pointage refusé hors zone GPS",
    "description": "Les aides ne peuvent pas pointer à moins de 50 m du domicile.",
    "severity": "Moyenne",
    "state": "En cours",
    "featureId": "f4",
    "clientIds": ["c2"],
}


def tickets_titled(client: TestClient, title: str) -> list[dict]:
    return [i for i in client.get("/api/issues").json() if i["title"] == title]


def test_ticket_cree_enregistre_affiche_et_persistant():
    with TestClient(app) as client:
        before = len(client.get("/api/issues").json())

        # 1. Création, comme le formulaire du front.
        res = client.post("/api/issues", json=TICKET)
        assert res.status_code == 201
        created = res.json()
        assert created["id"]
        assert created["severity"] == "Moyenne" and created["state"] == "En cours"

        # 2. Enregistré dans la base SQLite (lecture directe, sans passer par l'API).
        conn = sqlite3.connect(db.db_path())
        row = conn.execute("SELECT title, severity, state FROM issues WHERE id = ?", (created["id"],)).fetchone()
        conn.close()
        assert row == (TICKET["title"], "Moyenne", "En cours")

        # 3. Affiché dans la liste, une seule fois.
        assert len(tickets_titled(client, TICKET["title"])) == 1
        assert len(client.get("/api/issues").json()) == before + 1

    # 4. « Rechargement » : nouveau client et nouveau démarrage du serveur sur la même base.
    with TestClient(app) as client:
        found = tickets_titled(client, TICKET["title"])
        assert len(found) == 1
        assert found[0]["id"] == created["id"]
        assert found[0]["clientIds"] == ["c2"]


def test_statut_initial_par_defaut_ouvert():
    with TestClient(app) as client:
        res = client.post("/api/issues", json={"title": "Sans statut"})
        assert res.status_code == 201
        assert res.json()["state"] == "Ouvert"
        assert res.json()["severity"] == "Moyenne"


def test_valeurs_invalides_refusees():
    with TestClient(app) as client:
        assert client.post("/api/issues", json={"title": ""}).status_code == 400
        # « Élevée » n'existe plus : 3 niveaux seulement (Critique, Moyenne, Faible).
        res = client.post("/api/issues", json={"title": "X", "severity": "Élevée"})
        assert res.status_code == 400
        assert "severity" in res.json()["error"]
        assert client.post("/api/issues", json={"title": "X", "state": "Fermé"}).status_code == 400


def test_ticket_critique_bloque_le_deploiement():
    with TestClient(app) as client:
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Prêt"
        client.post("/api/issues", json={"title": "Panne EVV", "severity": "Critique", "clientIds": ["c3"]})
        readiness = client.get("/api/state").json()["readiness"]["c3"]
        assert readiness["status"] == "Non prêt"
        assert "Panne EVV" in readiness["reasons"][0]
