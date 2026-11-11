"""Les trois fonctions IA du PRD. La clé reste côté serveur (ANTHROPIC_API_KEY dans .env).

Claude ne modifie jamais les données : il renvoie une suggestion que l'utilisateur valide.
"""

import json
import os
from functools import cache

import anthropic

from .readiness import SEVERITIES, affects, is_late

DEFAULT_MODEL = "claude-opus-5-5"


def model() -> str:
    """Modèle lu à chaque appel : .env est chargé par main.py après l'import de ce module."""
    return os.getenv("CAREOPS_MODEL") or DEFAULT_MODEL

SYSTEM = """You are the assistant in CareOps Hub, a tool that tracks client implementations for a home-care software vendor.
Answer in English, briefly, factually and professionally.
Use only the data provided; if something is missing, say so instead of making it up.
Your text is shown in plain-text boxes: never use Markdown (no asterisks, no hash signs, no bullet lists).
Write dates in words, for example "November 20, 2026", never as 2026-11-20."""


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
            model=model(),
            max_tokens=16000,
            output_config=output_config,
            # Si un filtre de sécurité refuse la demande, l'API relance sur un modèle de repli.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise AIError("Invalid Anthropic API key: check the .env file.") from e
    except anthropic.RateLimitError as e:
        raise AIError("Too many requests to Claude, try again in a moment.") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Anthropic API error ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Could not reach the Anthropic API.") from e

    if response.stop_reason == "refusal":
        raise AIError("Claude declined this request.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise AIError("Claude returned no answer.")
    return text


def _client_context(client: dict, state: dict, readiness: dict, today: str) -> str:
    issues = [i for i in state["issues"] if affects(i, client["id"])]
    milestones = [m for m in state["milestones"] if m["clientId"] == client["id"]]
    features = {f["id"]: f["name"] for f in state["features"]}

    lines = [
        f"Client: {client['name']}",
        f"Planned go-live date: {client['goLiveDate'] or 'not set'}",
        f"Today: {today}",
        f"Computed readiness: {readiness['status']} — {'; '.join(readiness['reasons'])}",
        "",
        "Milestones:",
    ]
    for m in milestones:
        late = " (late)" if is_late(m, today) else ""
        blocker = f" | blocker: {m['blocker']}" if m["blocker"] else ""
        lines.append(f"- {m['name']} | status: {m['status']}{late} | due: {m['dueDate'] or '—'} | owner: {m['owner'] or '—'}{blocker}")
    if not milestones:
        lines.append("- none")
    lines += ["", "Technical issues affecting this client:"]
    for i in issues:
        lines.append(f"- {i['title']} | severity: {i['severity']} | state: {i['state']} | feature: {features.get(i['featureId'], '—')}")
    if not issues:
        lines.append("- none")
    return "\n".join(lines)


def summarize_readiness(client: dict, state: dict, readiness: dict, today: str) -> str:
    return _ask(f"""{_client_context(client, state, readiness, today)}

Write a go-live readiness summary for the implementation project manager, in 3 to 5 sentences:
1. the current status and its main reason;
2. the risks to the go-live date;
3. the next concrete action, with its owner if known.
No title, no list: a single paragraph.""")


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
        f"""Suggest a severity for this technical issue.

Scale:
- Critical: blocks an essential function (visits, EVV, billing, compliance) with no workaround, or creates a regulatory risk.
- Medium: a real problem; a workaround exists, even a costly one.
- Low: a minor or cosmetic defect.

Title: {title}
Feature: {feature_name or 'not specified'}
Description: {description or 'none'}

Keep the justification to one or two sentences.""",
        SEVERITY_FORMAT,
    )
    result = json.loads(text)
    if result.get("severity") not in SEVERITIES:
        raise AIError("Claude suggested an invalid severity.")
    return result


def draft_client_email(client: dict, state: dict, readiness: dict, today: str, summary: str) -> str:
    validated = f"\nReadiness summary already approved:\n{summary}\n" if summary else ""
    return _ask(f"""{_client_context(client, state, readiness, today)}
{validated}
Draft an update email to the contact person at {client['name']}.
- Start with a line "Subject: ...".
- Reassuring but honest tone: do not promise a date the data cannot guarantee.
- No internal jargon (severity, IDs); describe the impact for the client.
- End with the next step and a polite closing, signed "The Implementation Team".
- 150 words at most.""")
