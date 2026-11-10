"""Calendrier de l'agence : fuseau horaire de référence et jours ouvrés.

Les dates (création d'un problème, « aujourd'hui ») sont prises dans le fuseau de
l'agence, pas dans celui du serveur : sur Render, le serveur tourne en UTC.
"""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/New_York"

# Jours fériés fédéraux américains (dates observées), utilisés par défaut. À confirmer
# avec Sarah : une agence de soins à domicile ne s'arrête pas forcément ces jours-là.
FEDERAL_HOLIDAYS = frozenset(date.fromisoformat(d) for d in (
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-10-12", "2026-11-11", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-10-11", "2027-11-11", "2027-11-25", "2027-12-24", "2027-12-31",
))


def agency_tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("CAREOPS_TZ") or DEFAULT_TZ)


def local_today(now: datetime | None = None) -> str:
    """Date du jour dans le fuseau de l'agence (AAAA-MM-JJ), quel que soit le fuseau du serveur."""
    now = now or datetime.now(tz=agency_tz())
    return now.astimezone(agency_tz()).date().isoformat()


def holidays() -> frozenset[date]:
    """Jours fériés sautés par le délai de tri, réglables avec CAREOPS_HOLIDAYS.

    - non définie : jours fériés fédéraux américains (2026-2027) ;
    - vide : aucun jour férié, seuls les week-ends sont sautés ;
    - dates AAAA-MM-JJ séparées par des virgules : seulement ces jours-là.
    """
    raw = os.getenv("CAREOPS_HOLIDAYS")
    if raw is None:
        return FEDERAL_HOLIDAYS
    days = set()
    for item in filter(None, (part.strip() for part in raw.split(","))):
        try:
            days.add(date.fromisoformat(item))
        except ValueError:
            raise ValueError(f"CAREOPS_HOLIDAYS : date invalide « {item} » (format attendu AAAA-MM-JJ).") from None
    return frozenset(days)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in holidays()


def next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def first_business_day_from(day: date) -> date:
    """Le jour même s'il est ouvré, sinon le prochain jour ouvré."""
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def triage_calendar() -> dict:
    """Règle de calendrier active, renvoyée par /api/state : tout le monde voit la même."""
    raw = os.getenv("CAREOPS_HOLIDAYS")
    days = holidays()
    if raw is None:
        mode, label = "federal", "jours fériés fédéraux US"
    elif not days:
        mode, label = "none", "aucun jour férié"
    else:
        mode, label = "custom", "jours fériés de l'agence (" + ", ".join(d.isoformat() for d in sorted(days)) + ")"
    return {
        "holidays": mode,
        "holidayDates": sorted(d.isoformat() for d in days),
        "timeZone": agency_tz().key,
        "label": f"week-ends et {label} exclus ; dates à l'heure de {agency_tz().key}",
    }
