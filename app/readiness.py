"""Règle de préparation au déploiement (voir PRD, « Règle de préparation »).

L'état n'est jamais stocké : il est recalculé à partir des problèmes et des étapes.
"""

from datetime import date

from .business_days import first_business_day_from, next_business_day

# Hypothèse à valider (voir README, « Hypothèses et validation ») : 3 niveaux seulement.
SEVERITIES = ("Critique", "Moyenne", "Faible")
ISSUE_STATES = ("Ouvert", "En cours", "Résolu")
MILESTONE_STATES = ("À faire", "En cours", "Terminé", "Bloqué")
FEATURE_STATES = ("Planifiée", "En développement", "Livrée")

NOT_READY, AT_RISK, READY, IN_PROGRESS = "Non prêt", "À risque", "Prêt", "En cours"


def is_late(milestone: dict, today: str) -> bool:
    return milestone["status"] != "Terminé" and bool(milestone["dueDate"]) and milestone["dueDate"] < today


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


def _names(items: list[dict], key: str) -> str:
    return ", ".join(x[key] for x in items)


def affects(issue: dict, client_id: str) -> bool:
    return issue.get("allClients", False) or client_id in issue["clientIds"]


def _issue_names(issues: list[dict], milestones: list[dict]) -> str:
    """Titres des problèmes, avec l'étape qu'ils retardent quand elle appartient à ce client."""
    steps = {m["id"]: m["name"] for m in milestones}
    return ", ".join(f"{i['title']}, étape « {steps[i['milestoneId']]} »" if i.get("milestoneId") in steps else i["title"] for i in issues)


def untriaged_critical(state: dict) -> list[dict]:
    """Critiques ouverts liés à aucun client (« À trier »).

    On ne sait pas encore qui est touché : par prudence, ils bloquent TOUS les clients
    jusqu'au tri. Aucun Critique ouvert ne peut donc laisser passer un client.
    """
    return [i for i in state["issues"] if i["severity"] == "Critique" and i["state"] != "Résolu" and not i["clientIds"] and not i.get("allClients")]


def triage_deadline(created_at: str) -> date:
    """Dernier jour pour trier : le jour ouvré de création (le suivant si créé un week-end ou un jour férié)."""
    return first_business_day_from(date.fromisoformat(created_at))


def is_overdue_for_triage(issue: dict, today: str) -> bool:
    """Critique ouvert, toujours sans client, après la fin de son jour ouvré de création.

    Règle d'équipe : un Critique est trié le jour ouvré même. Le signal apparaît le jour
    ouvré suivant : créé le vendredi, il est en retard le lundi, jamais pendant le week-end
    ni un jour férié (voir business_days). Les dates sont celles du fuseau de l'agence.
    Le serveur calcule ce signal, l'interface l'affiche.
    """
    if issue["severity"] != "Critique" or issue["state"] == "Résolu":
        return False
    if issue["clientIds"] or issue.get("allClients"):
        return False
    created_at = issue.get("createdAt", "")
    if not created_at:
        return False
    return date.fromisoformat(today) >= next_business_day(triage_deadline(created_at[:10]))


def compute_readiness(client: dict, state: dict, today: str) -> dict:
    issues = [i for i in state["issues"] if affects(i, client["id"]) and i["state"] != "Résolu"]
    milestones = [m for m in state["milestones"] if m["clientId"] == client["id"]]

    critical = [i for i in issues if i["severity"] == "Critique"]
    untriaged = untriaged_critical(state)
    blocked = [m for m in milestones if m["status"] == "Bloqué"]
    late = [m for m in milestones if is_late(m, today)]

    if critical or blocked or untriaged:
        reasons = []
        if critical:
            s = "s" if len(critical) > 1 else ""
            reasons.append(f"{len(critical)} problème{s} critique{s} ouvert{s} ({_issue_names(critical, milestones)})")
        if blocked:
            s = "s" if len(blocked) > 1 else ""
            reasons.append(f"{len(blocked)} étape{s} bloquée{s} ({_names(blocked, 'name')})")
        if untriaged:
            s = "s" if len(untriaged) > 1 else ""
            reasons.append(f"{len(untriaged)} problème{s} critique{s} non trié{s}, à relier aux clients touchés ({_names(untriaged, 'title')})")
        return {"status": NOT_READY, "reasons": reasons}

    if late:
        return {"status": AT_RISK, "reasons": [f"{_plural(len(late), 'étape')} en retard ({_names(late, 'name')})"]}

    if milestones and all(m["status"] == "Terminé" for m in milestones):
        return {"status": READY, "reasons": ["Toutes les étapes sont terminées et aucun problème critique n'est ouvert"]}

    remaining = sum(m["status"] != "Terminé" for m in milestones)
    reason = f"{_plural(remaining, 'étape')} restante{'s' if remaining > 1 else ''}" if milestones else "Aucune étape définie"
    return {"status": IN_PROGRESS, "reasons": [reason]}


def compute_all(state: dict, today: str) -> dict:
    return {c["id"]: compute_readiness(c, state, today) for c in state["clients"]}
