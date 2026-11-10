"""Calendrier de l'agence : fuseau horaire de référence et jours ouvrés.

Les dates (création d'un problème, « aujourd'hui ») sont prises dans le fuseau de
l'agence, pas dans celui du serveur : sur Render, le serveur tourne en UTC.
"""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/New_York"

# Jours fériés fédéraux américains (dates observées). À confirmer avec Sarah :
# une agence de soins à domicile ne s'arrête pas forcément ces jours-là.
HOLIDAYS = frozenset(date.fromisoformat(d) for d in (
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


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in HOLIDAYS


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
