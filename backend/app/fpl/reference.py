"""Copy FPL's stable reference data (clubs, players, gameweeks) into the
database. Offline scripts only (read-write session); the sync script (task 07)
calls `refresh_fpl_reference_data()` on every run.

Upserts in place by FPL ID. Columns FPL does not own are left alone:
`fpl_clubs.sofascore_team_id` and `gameweeks.positions_synced`. Players that
disappear from FPL are kept, since the mapping and history may refer to them.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import FplClub, FplPlayer, Gameweek
from app.fpl.client import FplClient
from app.fpl.schemas import BootstrapStatic

# FPL `element_type` ID → our role code. FPL's own short name for 1 is "GKP".
ROLE_BY_ELEMENT_TYPE = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


@dataclass(frozen=True)
class RefreshCounts:
    clubs: int
    players: int
    gameweeks: int


def refresh_fpl_reference_data(session: Session, client: FplClient) -> RefreshCounts:
    """Fetch `bootstrap-static/` and upsert clubs, players and gameweeks.
    Does not commit: the caller owns the transaction."""
    return apply_bootstrap(session, client.bootstrap_static())


def apply_bootstrap(session: Session, data: BootstrapStatic) -> RefreshCounts:
    for team in data.teams:
        club = session.get(FplClub, team.id) or FplClub(id=team.id)
        club.name = team.name
        club.short_name = team.short_name
        session.add(club)
    # Players reference clubs; make sure new clubs exist first.
    session.flush()

    for element in data.elements:
        role = ROLE_BY_ELEMENT_TYPE.get(element.element_type)
        if role is None:
            raise ValueError(
                f"FPL player {element.id} has unknown element_type {element.element_type}"
            )
        player = session.get(FplPlayer, element.id) or FplPlayer(id=element.id)
        player.first_name = element.first_name
        player.second_name = element.second_name
        player.web_name = element.web_name
        player.club_id = element.team
        player.role = role
        player.price = element.now_cost
        player.status = element.status
        player.news = element.news
        player.minutes = element.minutes
        session.add(player)

    for event in data.events:
        gameweek = session.get(Gameweek, event.id) or Gameweek(id=event.id)
        gameweek.deadline = _naive_utc(event.deadline_time)
        gameweek.finished = event.finished
        gameweek.data_checked = event.data_checked
        session.add(gameweek)

    session.flush()
    return RefreshCounts(
        clubs=len(data.teams), players=len(data.elements), gameweeks=len(data.events)
    )


def _naive_utc(value: datetime) -> datetime:
    """The database stores naive UTC."""
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value
