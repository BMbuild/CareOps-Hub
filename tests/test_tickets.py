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
        res = client.post("/api/issues", json={"title": "Sans statut", "clientIds": ["c2"]})
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


def test_probleme_sans_client_accepte_a_trier():
    """Un problème peut être signalé sans client (« À trier ») ; les clients indiqués doivent exister."""
    with TestClient(app) as client:
        res = client.post("/api/issues", json={"title": "Bug général", "severity": "Faible"})
        assert res.status_code == 201
        assert res.json()["clientIds"] == []
        for client_ids in (["inconnu"], ["c3", "inconnu"]):
            res = client.post("/api/issues", json={"title": "X", "severity": "Critique", "clientIds": client_ids})
            assert res.status_code == 400
            assert res.json()["error"] == "Client inconnu."


def test_critique_non_trie_bloque_tous_les_clients():
    """Promesse : aucun client ne passe en production avec un Critique ouvert, même non trié."""
    with TestClient(app) as client:
        def readiness():
            return client.get("/api/state").json()["readiness"]

        assert readiness()["c3"]["status"] == "Prêt"
        issue = client.post("/api/issues", json={"title": "Panne de synchronisation", "severity": "Critique"}).json()
        for cid, r in readiness().items():
            assert r["status"] == "Non prêt", cid
            assert any("non trié" in reason and "Panne de synchronisation" in reason for reason in r["reasons"]), cid

        # Tri : relié à Horizon (c1) seulement → Bien-Être Queens (c3) redevient Prêt.
        client.put(f"/api/issues/{issue['id']}", json={"clientIds": ["c1"]})
        assert readiness()["c3"]["status"] == "Prêt"
        assert "Panne de synchronisation" in readiness()["c1"]["reasons"][0]


def test_non_trie_moyen_ou_resolu_ne_bloque_personne():
    with TestClient(app) as client:
        client.post("/api/issues", json={"title": "Libellé tronqué", "severity": "Moyenne"})
        client.post("/api/issues", json={"title": "Ancienne panne", "severity": "Critique", "state": "Résolu"})
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Prêt"


def test_retirer_tous_les_clients_dun_critique_bloque_tout_le_monde():
    """Décocher le dernier client ne fait pas disparaître le blocage : le Critique redevient « À trier »."""
    with TestClient(app) as client:
        issue = client.post("/api/issues", json={"title": "Lenteur", "severity": "Moyenne", "clientIds": ["c2"]}).json()
        res = client.put(f"/api/issues/{issue['id']}", json={"severity": "Critique", "state": "En cours", "clientIds": ["c2", "c3"]})
        assert res.status_code == 200
        saved = next(i for i in client.get("/api/issues").json() if i["id"] == issue["id"])
        assert (saved["severity"], saved["state"], sorted(saved["clientIds"])) == ("Critique", "En cours", ["c2", "c3"])

        assert client.put(f"/api/issues/{issue['id']}", json={"clientIds": []}).status_code == 200
        assert all(r["status"] == "Non prêt" for r in client.get("/api/state").json()["readiness"].values())


def test_supprimer_le_seul_client_dun_critique_bloque_les_autres():
    """Supprimer un client ne doit pas effacer un Critique ouvert : il devient « À trier » et bloque tout le monde."""
    with TestClient(app) as client:
        client.post("/api/issues", json={"title": "Panne", "severity": "Critique", "clientIds": ["c3"]})
        assert client.delete("/api/clients/c3").status_code == 204
        issue = next(i for i in client.get("/api/issues").json() if i["title"] == "Panne")
        assert issue["clientIds"] == []
        assert all(r["status"] == "Non prêt" for r in client.get("/api/state").json()["readiness"].values())


def test_bout_en_bout_critique_puis_resolution():
    """Scénario du plan : Critique → Non prêt ; résolu → Prêt seulement si toutes les étapes sont terminées."""
    with TestClient(app) as client:
        def status(cid):
            return client.get("/api/state").json()["readiness"][cid]["status"]

        # Bien-Être Queens (c3) : toutes ses étapes sont terminées.
        # Horizon (c1) : des étapes restent à faire ; on résout d'abord son problème critique existant (i1).
        assert status("c3") == "Prêt"
        issue = client.post("/api/issues", json={"title": "Export EVV rejeté", "severity": "Critique", "clientIds": ["c1", "c3"]}).json()
        assert status("c3") == "Non prêt" and status("c1") == "Non prêt"

        client.put(f"/api/issues/{issue['id']}", json={"state": "Résolu"})
        client.put("/api/issues/i1", json={"state": "Résolu"})
        assert status("c3") == "Prêt"
        assert status("c1") != "Prêt"  # étapes non terminées : pas prêt malgré zéro problème critique

        # Le résultat est recalculé à partir des données enregistrées, après un « rechargement ».
    with TestClient(app) as client:
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Prêt"
