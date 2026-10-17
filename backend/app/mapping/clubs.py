"""FPL club ↔ Sofascore team. A static table for the current season, keyed
by FPL short name (stable across seasons, unlike FPL club IDs, which follow
alphabetical order). Pulled forward from task 08: the sync needs it to fetch
each club's matches. IDs checked against Sofascore's 2026/27 round 6.

A promoted club missing here is reported by `apply_club_mapping()` and its
matches are skipped until it is added.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FplClub

SOFASCORE_TEAM_ID_BY_SHORT_NAME = {
    "ARS": 42,  # Arsenal
    "AVL": 40,  # Aston Villa
    "BOU": 60,  # Bournemouth
    "BRE": 50,  # Brentford
    "BHA": 30,  # Brighton & Hove Albion
    "CHE": 38,  # Chelsea
    "COV": 11,  # Coventry City
    "CRY": 7,  # Crystal Palace
    "EVE": 48,  # Everton
    "FUL": 43,  # Fulham
    "HUL": 96,  # Hull City
    "IPS": 32,  # Ipswich Town
    "LEE": 34,  # Leeds United
    "LIV": 44,  # Liverpool
    "MCI": 17,  # Manchester City
    "MUN": 35,  # Manchester United
    "NEW": 39,  # Newcastle United
    "NFO": 14,  # Nottingham Forest
    "TOT": 33,  # Tottenham Hotspur
    "SUN": 41,  # Sunderland
}


def apply_club_mapping(session: Session) -> list[str]:
    """Set `fpl_clubs.sofascore_team_id` from the table. Returns the short
    names of clubs with no entry. Flushes, caller commits."""
    clubs = session.scalars(select(FplClub)).all()
    wanted = {c.id: SOFASCORE_TEAM_ID_BY_SHORT_NAME.get(c.short_name) for c in clubs}
    # Clear changed IDs first so the UNIQUE never trips mid-update.
    for club in clubs:
        if club.sofascore_team_id != wanted[club.id]:
            club.sofascore_team_id = None
    session.flush()
    for club in clubs:
        club.sofascore_team_id = wanted[club.id]
    session.flush()
    return sorted(c.short_name for c in clubs if wanted[c.id] is None)
