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
    "severity": "Medium",
    "state": "In Progress",
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
        assert created["severity"] == "Medium" and created["state"] == "In Progress"

        # 2. Enregistré dans la base SQLite (lecture directe, sans passer par l'API).
        conn = sqlite3.connect(db.db_path())
        row = conn.execute("SELECT title, severity, state FROM issues WHERE id = ?", (created["id"],)).fetchone()
        conn.close()
        assert row == (TICKET["title"], "Medium", "In Progress")

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
        assert res.json()["state"] == "Open"
        assert res.json()["severity"] == "Medium"


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
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Ready"
        client.post("/api/issues", json={"title": "Panne EVV", "severity": "Critical", "clientIds": ["c3"]})
        readiness = client.get("/api/state").json()["readiness"]["c3"]
        assert readiness["status"] == "Not Ready"
        assert "Panne EVV" in readiness["reasons"][0]


def test_probleme_sans_client_accepte_a_trier():
    """Un problème peut être signalé sans client (« À trier ») ; les clients indiqués doivent exister."""
    with TestClient(app) as client:
        res = client.post("/api/issues", json={"title": "Bug général", "severity": "Low"})
        assert res.status_code == 201
        assert res.json()["clientIds"] == []
        for client_ids in (["inconnu"], ["c3", "inconnu"]):
            res = client.post("/api/issues", json={"title": "X", "severity": "Critical", "clientIds": client_ids})
            assert res.status_code == 400
            assert res.json()["error"] == "Unknown client."


def test_critique_non_trie_bloque_tous_les_clients():
    """Promesse : aucun client ne passe en production avec un Critique ouvert, même non trié."""
    with TestClient(app) as client:
        def readiness():
            return client.get("/api/state").json()["readiness"]

        assert readiness()["c3"]["status"] == "Ready"
        issue = client.post("/api/issues", json={"title": "Panne de synchronisation", "severity": "Critical"}).json()
        for cid, r in readiness().items():
            assert r["status"] == "Not Ready", cid
            assert any("untriaged" in reason and "Panne de synchronisation" in reason for reason in r["reasons"]), cid

        # Tri : relié à Horizon (c1) seulement → Bien-Être Queens (c3) redevient Prêt.
        client.put(f"/api/issues/{issue['id']}", json={"clientIds": ["c1"]})
        assert readiness()["c3"]["status"] == "Ready"
        assert "Panne de synchronisation" in readiness()["c1"]["reasons"][0]


def test_critique_non_trie_bloque_aussi_un_client_cree_apres():
    """Demandé par Sarah : un nouveau client ne passe pas « Prêt » tant qu'un Critique attend le tri."""
    with TestClient(app) as client:
        issue = client.post("/api/issues", json={"title": "Faille de sécurité", "severity": "Critical"}).json()

        new = client.post("/api/clients", json={"name": "Clinique Nouvelle"}).json()
        step = client.post("/api/milestones", json={"clientId": new["id"], "name": "Formation"}).json()
        client.put(f"/api/milestones/{step['id']}", json={"status": "Done"})

        r = client.get("/api/state").json()["readiness"][new["id"]]
        assert r["status"] == "Not Ready"
        assert any("untriaged" in reason and "Faille de sécurité" in reason for reason in r["reasons"])

        # Seule la résolution lève le blocage : le nouveau client, toutes étapes terminées, passe Prêt.
        client.put(f"/api/issues/{issue['id']}", json={"state": "Resolved"})
        assert client.get("/api/state").json()["readiness"][new["id"]]["status"] == "Ready"


def test_non_trie_moyen_ou_resolu_ne_bloque_personne():
    with TestClient(app) as client:
        client.post("/api/issues", json={"title": "Libellé tronqué", "severity": "Medium"})
        client.post("/api/issues", json={"title": "Ancienne panne", "severity": "Critical", "state": "Resolved"})
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Ready"


def test_retirer_tous_les_clients_dun_critique_bloque_tout_le_monde():
    """Décocher le dernier client ne fait pas disparaître le blocage : le Critique redevient « À trier »."""
    with TestClient(app) as client:
        issue = client.post("/api/issues", json={"title": "Lenteur", "severity": "Medium", "clientIds": ["c2"]}).json()
        res = client.put(f"/api/issues/{issue['id']}", json={"severity": "Critical", "state": "In Progress", "clientIds": ["c2", "c3"]})
        assert res.status_code == 200
        saved = next(i for i in client.get("/api/issues").json() if i["id"] == issue["id"])
        assert (saved["severity"], saved["state"], sorted(saved["clientIds"])) == ("Critical", "In Progress", ["c2", "c3"])

        assert client.put(f"/api/issues/{issue['id']}", json={"clientIds": []}).status_code == 200
        assert all(r["status"] == "Not Ready" for r in client.get("/api/state").json()["readiness"].values())


def test_supprimer_le_seul_client_dun_critique_bloque_les_autres():
    """Supprimer un client ne doit pas effacer un Critique ouvert : il devient « À trier » et bloque tout le monde."""
    with TestClient(app) as client:
        client.post("/api/issues", json={"title": "Panne", "severity": "Critical", "clientIds": ["c3"]})
        assert client.delete("/api/clients/c3").status_code == 204
        issue = next(i for i in client.get("/api/issues").json() if i["title"] == "Panne")
        assert issue["clientIds"] == []
        assert all(r["status"] == "Not Ready" for r in client.get("/api/state").json()["readiness"].values())


def test_bout_en_bout_critique_puis_resolution():
    """Scénario du plan : Critique → Non prêt ; résolu → Prêt seulement si toutes les étapes sont terminées."""
    with TestClient(app) as client:
        def status(cid):
            return client.get("/api/state").json()["readiness"][cid]["status"]

        # Bien-Être Queens (c3) : toutes ses étapes sont terminées.
        # Horizon (c1) : des étapes restent à faire ; on résout d'abord son problème critique existant (i1).
        assert status("c3") == "Ready"
        issue = client.post("/api/issues", json={"title": "Export EVV rejeté", "severity": "Critical", "clientIds": ["c1", "c3"]}).json()
        assert status("c3") == "Not Ready" and status("c1") == "Not Ready"

        client.put(f"/api/issues/{issue['id']}", json={"state": "Resolved"})
        client.put("/api/issues/i1", json={"state": "Resolved"})
        assert status("c3") == "Ready"
        assert status("c1") != "Ready"  # étapes non terminées : pas prêt malgré zéro problème critique

        # Le résultat est recalculé à partir des données enregistrées, après un « rechargement ».
    with TestClient(app) as client:
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Ready"


def test_tous_les_clients_bloque_aussi_les_clients_ajoutes_plus_tard():
    """« Tous les clients » : bloque chaque client, y compris un client créé après le problème."""
    with TestClient(app) as client:
        issue = client.post("/api/issues", json={"title": "Panne de connexion", "severity": "Critical", "allClients": True, "clientIds": ["c1"]}).json()
        assert issue["allClients"] is True
        assert issue["clientIds"] == []  # la liste individuelle est remplacée

        new = client.post("/api/clients", json={"name": "Nouveau client"}).json()
        readiness = client.get("/api/state").json()["readiness"]
        for cid in ("c1", "c2", "c3", new["id"]):
            assert readiness[cid]["status"] == "Not Ready", cid
            assert "Panne de connexion" in readiness[cid]["reasons"][0], cid
            assert "untriaged" not in " ".join(readiness[cid]["reasons"]), cid  # trié : il touche tout le monde

        # Une mise à jour partielle (ex. l'état) garde l'option ; une fois résolu, plus aucun blocage.
        client.put(f"/api/issues/{issue['id']}", json={"state": "In Progress"})
        assert next(i for i in client.get("/api/issues").json() if i["id"] == issue["id"])["allClients"] is True
        client.put(f"/api/issues/{issue['id']}", json={"state": "Resolved"})
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Ready"


def test_tous_les_clients_peut_etre_retire():
    with TestClient(app) as client:
        issue = client.post("/api/issues", json={"title": "Lenteur", "severity": "Critical", "allClients": True}).json()
        client.put(f"/api/issues/{issue['id']}", json={"allClients": False, "clientIds": ["c1"]})
        saved = next(i for i in client.get("/api/issues").json() if i["id"] == issue["id"])
        assert (saved["allClients"], saved["clientIds"]) == (False, ["c1"])
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Ready"


def test_ancienne_base_sans_colonne_all_clients_est_migree(tmp_path, monkeypatch):
    import sqlite3

    from app import db

    path = tmp_path / "ancienne.db"
    monkeypatch.setenv("CAREOPS_DB", str(path))
    old_schema = db.SCHEMA.replace(",\n    -- 1 = touche tous les clients, y compris ceux ajoutés plus tard (issue_clients reste vide).\n    all_clients  INTEGER NOT NULL DEFAULT 0 CHECK (all_clients IN (0, 1))", "")
    assert "all_clients" not in old_schema
    with sqlite3.connect(path) as conn:
        conn.executescript(old_schema)
    db.init_db()
    assert all(i["allClients"] is False for i in db.load_state()["issues"])


def test_etape_bloquee_exige_une_cause():
    """Une étape Bloquée rend le client « Non prêt » : sa cause doit être écrite, à la création comme en modification."""
    with TestClient(app) as client:
        expected = "A blocked milestone needs a cause: describe what is blocking it."
        for blocker in ("", "   "):
            res = client.post("/api/milestones", json={"clientId": "c3", "name": "Formation", "status": "Blocked", "blocker": blocker})
            assert res.status_code == 400
            assert res.json()["error"] == expected
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Ready"  # rien n'a été enregistré

        step = client.post("/api/milestones", json={"clientId": "c3", "name": "Formation", "status": "Done"}).json()
        assert client.put(f"/api/milestones/{step['id']}", json={"status": "Blocked"}).status_code == 400

        res = client.put(f"/api/milestones/{step['id']}", json={"status": "Blocked", "blocker": "Accès VPN refusé par le client"})
        assert res.status_code == 200
        r = client.get("/api/state").json()["readiness"]["c3"]
        assert r["status"] == "Not Ready"
        assert "Formation" in r["reasons"][0]

        # Effacer la cause d'une étape encore bloquée est refusé ; débloquer sans cause est permis.
        assert client.put(f"/api/milestones/{step['id']}", json={"blocker": ""}).status_code == 400
        assert client.put(f"/api/milestones/{step['id']}", json={"status": "Done", "blocker": ""}).status_code == 200


def test_api_signale_le_retard_de_tri():
    """Le serveur calcule le signal ; un Critique non trié de la veille l'a, celui du jour non."""
    with TestClient(app) as client:
        old = client.post("/api/issues", json={"title": "Ancien bug", "severity": "Critical"}).json()
        new = client.post("/api/issues", json={"title": "Nouveau bug", "severity": "Critical"}).json()
        with sqlite3.connect(db.db_path()) as conn:
            conn.execute("UPDATE issues SET created_at = '2000-01-01' WHERE id = ?", (old["id"],))

        flags = {i["id"]: i["overdueForTriage"] for i in client.get("/api/state").json()["issues"]}
        assert flags[old["id"]] is True
        assert flags[new["id"]] is False
        assert not any(flags[i] for i in flags if i not in (old["id"], new["id"]))  # données de démo : aucun

        client.put(f"/api/issues/{old['id']}", json={"clientIds": ["c1"]})  # trié
        issues = client.get("/api/state").json()["issues"]
        assert next(i for i in issues if i["id"] == old["id"])["overdueForTriage"] is False


def test_probleme_lie_a_une_etape_plan_en_quatre_tests():
    """Plan du 10 novembre : un Critique lié à une étape du client A bloque A, pas B ; résolu, A redevient Prêt ; tout persiste."""
    def readiness(client):
        return client.get("/api/state").json()["readiness"]

    with TestClient(app) as client:
        # Client A = Bien-Être Queens (c3, toutes étapes terminées) ; client B = CareFirst Brooklyn (c2).
        before_b = readiness(client)["c2"]
        assert readiness(client)["c3"]["status"] == "Ready"

        # Test 1 : Critique ouvert lié à l'étape « Test EVV avec l'État » (m10) de A → A Non prêt, étape nommée.
        issue = client.post("/api/issues", json={"title": "Export EVV refusé", "severity": "Critical", "milestoneId": "m10"}).json()
        assert issue["milestoneId"] == "m10"
        assert issue["clientIds"] == ["c3"]  # l'étape relie automatiquement son client
        a = readiness(client)["c3"]
        assert a["status"] == "Not Ready"
        assert "Export EVV refusé, milestone “State EVV test”" in a["reasons"][0]

        # Test 2 : B ne change pas.
        assert readiness(client)["c2"] == before_b

        # Test 3 : résolu → A Prêt (toutes ses étapes sont terminées).
        client.put(f"/api/issues/{issue['id']}", json={"state": "Resolved"})
        assert readiness(client)["c3"]["status"] == "Ready"
        client.put(f"/api/issues/{issue['id']}", json={"state": "Open"})

    # Test 4 : après « actualisation » (nouveau démarrage), problème, lien d'étape et états sont conservés.
    with TestClient(app) as client:
        saved = next(i for i in client.get("/api/issues").json() if i["id"] == issue["id"])
        assert (saved["milestoneId"], saved["clientIds"], saved["state"]) == ("m10", ["c3"], "Open")
        assert readiness(client)["c3"]["status"] == "Not Ready"
        assert readiness(client)["c2"] == before_b


def test_lien_etape_invalide_ou_supprimee():
    with TestClient(app) as client:
        res = client.post("/api/issues", json={"title": "X", "severity": "Critical", "milestoneId": "inconnue"})
        assert res.status_code == 400
        assert res.json()["error"] == "Unknown milestone."

        # Supprimer l'étape ne fait pas disparaître le blocage : le problème reste lié au client.
        step = client.post("/api/milestones", json={"clientId": "c3", "name": "Audit"}).json()
        client.put(f"/api/milestones/{step['id']}", json={"status": "Done"})
        issue = client.post("/api/issues", json={"title": "Audit bloqué", "severity": "Critical", "milestoneId": step["id"]}).json()
        assert client.delete(f"/api/milestones/{step['id']}").status_code == 204
        saved = next(i for i in client.get("/api/issues").json() if i["id"] == issue["id"])
        assert (saved["milestoneId"], saved["clientIds"]) == ("", ["c3"])
        assert client.get("/api/state").json()["readiness"]["c3"]["status"] == "Not Ready"


def test_ancienne_base_sans_colonne_milestone_id_est_migree(tmp_path, monkeypatch):
    path = tmp_path / "ancienne.db"
    monkeypatch.setenv("CAREOPS_DB", str(path))
    old_schema = db.SCHEMA.replace(
        ",\n    -- Étape retardée par le problème (facultatif). Son client est toujours ajouté aux clients touchés.\n    milestone_id TEXT REFERENCES milestones(id) ON DELETE SET NULL", "")
    assert "milestone_id" not in old_schema
    with sqlite3.connect(path) as conn:
        conn.executescript(old_schema)
    db.init_db()
    links = {i["id"]: i["milestoneId"] for i in db.load_state()["issues"]}
    assert links.pop("i1") == "m3"  # données de démo : la colonne ajoutée reçoit bien le lien
    assert set(links.values()) == {""}


def test_demo_de_presentation():
    """Scénario de la démo (README, « Presentation Demo ») : les deux espaces travaillent ensemble."""
    with TestClient(app) as client:
        client.post("/api/reset")
        readiness = lambda: client.get("/api/state").json()["readiness"]["c3"]
        assert readiness()["status"] == "Ready"

        # 1. Sarah ajoute une étape à Bien-Être Queens.
        step = client.post("/api/milestones", json={
            "clientId": "c3", "name": "Final go-live check",
            "dueDate": "2099-12-31", "owner": "Sarah", "status": "To Do"}).json()
        assert readiness()["status"] == "In Progress"

        # 2. Brahim crée un Critique et choisit cette étape : le client est relié tout seul.
        issue = client.post("/api/issues", json={
            "title": "Duplicate clock-ins in the caregiver portal", "severity": "Critical",
            "featureId": "f4", "milestoneId": step["id"]}).json()
        assert issue["clientIds"] == ["c3"]
        # 3. Sarah voit Non prêt, avec le problème et l'étape dans la raison.
        assert readiness()["status"] == "Not Ready"
        assert "milestone “Final go-live check”" in readiness()["reasons"][0]

        # 4. Brahim résout le problème, puis Sarah termine l'étape.
        client.put(f"/api/issues/{issue['id']}", json={"state": "Resolved"})
        assert readiness()["status"] == "In Progress"
        client.put(f"/api/milestones/{step['id']}", json={"status": "Done"})

    # 5. Après un redémarrage (même base), tout est conservé.
    with TestClient(app) as client:
        state = client.get("/api/state").json()
        assert state["readiness"]["c3"]["status"] == "Ready"
        saved = next(i for i in state["issues"] if i["id"] == issue["id"])
        assert (saved["state"], saved["milestoneId"]) == ("Resolved", step["id"])


def test_api_affiche_le_calendrier_de_tri_actif(monkeypatch):
    """Les jours fériés et le fuseau appliqués sont visibles : deux postes réglés différemment se voient."""
    with TestClient(app) as client:
        monkeypatch.delenv("CAREOPS_HOLIDAYS", raising=False)
        monkeypatch.delenv("CAREOPS_TZ", raising=False)
        calendar = client.get("/api/state").json()["triageCalendar"]
        assert calendar["holidays"] == "federal"
        assert "2026-11-26" in calendar["holidayDates"]
        assert calendar["timeZone"] == "America/New_York"
        assert "US federal holidays" in calendar["label"]

        monkeypatch.setenv("CAREOPS_HOLIDAYS", "")
        calendar = client.get("/api/state").json()["triageCalendar"]
        assert (calendar["holidays"], calendar["holidayDates"]) == ("none", [])
        assert "no holidays" in calendar["label"]

        monkeypatch.setenv("CAREOPS_HOLIDAYS", "2026-12-25,2026-11-26")
        monkeypatch.setenv("CAREOPS_TZ", "America/Chicago")
        calendar = client.get("/api/state").json()["triageCalendar"]
        assert calendar["holidayDates"] == ["2026-11-26", "2026-12-25"]
        assert calendar["label"] == ("weekends and agency holidays (2026-11-26, 2026-12-25) skipped; "
                                     "dates in America/Chicago time")


def test_ancienne_base_en_francais_est_convertie_en_anglais(tmp_path, monkeypatch):
    """Une base créée avant l'interface anglaise (Critique, Bloqué…) est convertie au démarrage."""
    path = tmp_path / "francaise.db"
    monkeypatch.setenv("CAREOPS_DB", str(path))
    french_schema = db.SCHEMA
    for fr_values, en_values in [
        ("'Planifiée', 'En développement', 'Livrée'", "'Planned', 'In Development', 'Shipped'"),
        ("'Critique', 'Moyenne', 'Faible'", "'Critical', 'Medium', 'Low'"),
        ("'Ouvert', 'En cours', 'Résolu'", "'Open', 'In Progress', 'Resolved'"),
        ("'À faire', 'En cours', 'Terminé', 'Bloqué'", "'To Do', 'In Progress', 'Done', 'Blocked'"),
    ]:
        french_schema = french_schema.replace(en_values, fr_values)
    assert "'Critique'" in french_schema
    with sqlite3.connect(path) as conn:
        conn.executescript(french_schema)
        conn.execute("INSERT INTO clients (id, name) VALUES ('c1', 'Horizon')")
        conn.execute("INSERT INTO features (id, name, status) VALUES ('f1', 'Export EVV', 'Livrée')")
        conn.execute("INSERT INTO milestones (id, client_id, name, status, blocker) VALUES ('m1', 'c1', 'Test EVV', 'Bloqué', 'Rejeté')")
        conn.execute("INSERT INTO issues (id, title, severity, state, feature_id, created_at, milestone_id) "
                     "VALUES ('i1', 'Export rejeté', 'Critique', 'En cours', 'f1', '2026-11-02', 'm1')")
        conn.execute("INSERT INTO issue_clients (issue_id, client_id) VALUES ('i1', 'c1')")

    db.init_db()

    state = db.load_state()
    assert state["features"][0]["status"] == "Shipped"
    assert state["milestones"][0]["status"] == "Blocked"
    issue = state["issues"][0]
    assert (issue["severity"], issue["state"], issue["title"]) == ("Critical", "In Progress", "Export rejeté")
    assert (issue["clientIds"], issue["milestoneId"], issue["featureId"]) == (["c1"], "m1", "f1")  # liens conservés
    assert db.migrate_french_values(path) is False  # déjà convertie : rien à refaire
    with TestClient(app) as client:  # les valeurs anglaises sont acceptées par la nouvelle contrainte
        assert client.put("/api/issues/i1", json={"state": "Resolved"}).status_code == 200
        assert client.get("/api/state").json()["readiness"]["c1"]["status"] == "Not Ready"  # étape toujours Bloquée
