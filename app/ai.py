"""Les trois fonctions IA du PRD. La clé reste côté serveur (ANTHROPIC_API_KEY dans .env).

Claude ne modifie jamais les données : il renvoie une suggestion que l'utilisateur valide.
"""

import json
from functools import cache

import anthropic

from .readiness import SEVERITIES, is_late

MODEL = "claude-opus-5-5"

SYSTEM = """Tu es l'assistant de CareOps Hub, un outil qui suit les implémentations clients d'un éditeur de logiciels pour les soins à domicile.
Tu réponds en français, de façon brève, factuelle et professionnelle.
Tu t'appuies uniquement sur les données fournies ; si une information manque, dis-le au lieu de l'inventer."""


class AIError(Exception):
    pass


@cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _ask(prompt: str, fmt: dict | None = None) -> str:
    output_config = {"effort": "low"}  # tâches courtes : un effort bas suffit et coûte moins
    if fmt:
        output_config["format"] = fmt
    try:
        response = _client().beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            output_config=output_config,
            # Si un filtre de sécurité refuse la demande, l'API relance sur un modèle de repli.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise AIError("Clé API Anthropic invalide : vérifiez le fichier .env.") from e
    except anthropic.RateLimitError as e:
        raise AIError("Trop de demandes à Claude, réessayez dans un instant.") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Erreur de l'API Anthropic ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Impossible de joindre l'API Anthropic.") from e

    if response.stop_reason == "refusal":
        raise AIError("Claude a refusé cette demande.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise AIError("Claude n'a renvoyé aucune réponse.")
    return text


def _client_context(client: dict, state: dict, readiness: dict, today: str) -> str:
    issues = [i for i in state["issues"] if client["id"] in i["clientIds"]]
    milestones = [m for m in state["milestones"] if m["clientId"] == client["id"]]
    features = {f["id"]: f["name"] for f in state["features"]}

    lines = [
        f"Client : {client['name']}",
        f"Date de go-live prévue : {client['goLiveDate'] or 'non définie'}",
        f"Date du jour : {today}",
        f"État de préparation calculé : {readiness['status']} — {' ; '.join(readiness['reasons'])}",
        "",
        "Étapes :",
    ]
    for m in milestones:
        late = " (en retard)" if is_late(m, today) else ""
        blocker = f" | blocage : {m['blocker']}" if m["blocker"] else ""
        lines.append(f"- {m['name']} | statut : {m['status']}{late} | échéance : {m['dueDate'] or '—'} | responsable : {m['owner'] or '—'}{blocker}")
    if not milestones:
        lines.append("- aucune")
    lines += ["", "Problèmes techniques qui touchent ce client :"]
    for i in issues:
        lines.append(f"- {i['title']} | gravité : {i['severity']} | état : {i['state']} | fonctionnalité : {features.get(i['featureId'], '—')}")
    if not issues:
        lines.append("- aucun")
    return "\n".join(lines)


def summarize_readiness(client: dict, state: dict, readiness: dict, today: str) -> str:
    return _ask(f"""{_client_context(client, state, readiness, today)}

Rédige un résumé de préparation au déploiement pour la cheffe de projet, en 3 à 5 phrases :
1. l'état actuel et sa raison principale ;
2. les risques pour la date de go-live ;
3. la prochaine action concrète, avec son responsable si on le connaît.
Pas de titre, pas de liste : un seul paragraphe.""")


SEVERITY_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": list(SEVERITIES)},
            "justification": {"type": "string"},
        },
        "required": ["severity", "justification"],
        "additionalProperties": False,
    },
}


def suggest_severity(title: str, description: str, feature_name: str | None) -> dict:
    text = _ask(
        f"""Propose une gravité pour ce problème technique.

Échelle :
- Critique : bloque une fonction essentielle (visites, EVV, facturation, conformité) sans contournement, ou risque réglementaire.
- Moyenne : gêne réelle ; un contournement existe, même s'il est coûteux.
- Faible : défaut mineur ou esthétique.

Titre : {title}
Fonctionnalité : {feature_name or 'non précisée'}
Description : {description or 'aucune'}

La justification tient en une ou deux phrases.""",
        SEVERITY_FORMAT,
    )
    result = json.loads(text)
    if result.get("severity") not in SEVERITIES:
        raise AIError("Gravité proposée invalide.")
    return result


def draft_client_email(client: dict, state: dict, readiness: dict, today: str, summary: str) -> str:
    validated = f"\nRésumé de préparation déjà validé :\n{summary}\n" if summary else ""
    return _ask(f"""{_client_context(client, state, readiness, today)}
{validated}
Rédige un brouillon d'e-mail de mise à jour pour l'interlocuteur du client {client['name']}.
- Commence par une ligne « Objet : ... ».
- Ton rassurant mais honnête : n'annonce pas de date que les données ne permettent pas de garantir.
- N'emploie pas de jargon interne (gravité, identifiants) ; décris l'impact pour le client.
- Termine par la prochaine étape et une formule de politesse, signée « L'équipe Implémentation ».
- 150 mots maximum.""")
