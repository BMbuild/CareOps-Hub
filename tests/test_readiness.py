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
    assert status(SEED, "c1") == "Non prêt"


def test_resoudre_le_critique_ne_suffit_pas_si_une_etape_est_bloquee():
    state = copy.deepcopy(SEED)
    next(i for i in state["issues"] if i["id"] == "i1")["state"] = "Résolu"
    assert status(state, "c1") == "Non prêt"
    next(m for m in state["milestones"] if m["id"] == "m3")["status"] = "En cours"
    assert status(state, "c1") == "En cours"


def test_etape_en_retard_donne_a_risque():
    assert status(SEED, "c2") == "À risque"


def test_probleme_moyen_ne_bloque_pas():
    state = copy.deepcopy(SEED)
    next(m for m in state["milestones"] if m["id"] == "m6")["status"] = "Terminé"
    assert status(state, "c2") == "En cours"


def test_tout_termine_donne_pret():
    assert status(SEED, "c3") == "Prêt"


def test_raisons_au_pluriel():
    state = copy.deepcopy(SEED)
    state["issues"].append({"id": "x", "title": "Autre", "severity": "Critique", "state": "Ouvert", "clientIds": ["c1"]})
    client = next(c for c in state["clients"] if c["id"] == "c1")
    reason = compute_readiness(client, state, TODAY)["reasons"][0]
    assert reason.startswith("2 problèmes critiques ouverts")


def test_en_retard_de_tri():
    """Signal de Sarah : un Critique ouvert sans client, non trié à la fin de son jour ouvré, est en retard de tri."""
    from app.readiness import is_overdue_for_triage

    base = {"severity": "Critique", "state": "Ouvert", "clientIds": [], "allClients": False, "createdAt": "2026-11-03"}
    assert is_overdue_for_triage(base, TODAY)  # créé la veille, toujours sans client
    for change in (
        {"createdAt": TODAY},  # créé aujourd'hui : encore dans le délai
        {"clientIds": ["c1"]},  # trié
        {"allClients": True},  # trié : touche tout le monde
        {"state": "Résolu"},
        {"severity": "Moyenne"},
        {"createdAt": ""},
    ):
        assert not is_overdue_for_triage({**base, **change}, TODAY), change


def test_retard_de_tri_en_jours_ouvres():
    """Demande de Sarah : un Critique créé le vendredi n'est pas en retard pendant le week-end."""
    from app.readiness import is_overdue_for_triage

    def overdue(created, today):
        issue = {"severity": "Critique", "state": "Ouvert", "clientIds": [], "allClients": False, "createdAt": created}
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
