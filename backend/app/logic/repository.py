"""Thin read-only queries that feed `app/logic/positions.py` plain data."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FplPlayer, Gameweek, PlayerIdMap, PlayerMatchPosition, SyncRun
from app.logic.depth import outfield_pool
from app.logic.positions import MatchPosition


def load_sofascore_ids(session: Session, fpl_ids: Iterable[int]) -> dict[int, int]:
    """FPL ID → Sofascore ID for the mapped players among `fpl_ids`."""
    rows = session.execute(
        select(PlayerIdMap.fpl_id, PlayerIdMap.sofascore_id).where(
            PlayerIdMap.fpl_id.in_(list(fpl_ids))
        )
    )
    return {fpl_id: sofascore_id for fpl_id, sofascore_id in rows}


def load_match_positions(
    session: Session, sofascore_ids: Iterable[int]
) -> dict[int, list[MatchPosition]]:
    """Every stored match of each player, most recent kickoff first, keyed by
    Sofascore ID. Filters on the player only, so SQLite uses the
    (player, kickoff) index; the logic picks the gameweeks (a season is at
    most ~40 rows per player)."""
    ids = list(sofascore_ids)
    result: dict[int, list[MatchPosition]] = {i: [] for i in ids}
    if not ids:
        return result
    query = (
        select(PlayerMatchPosition)
        .where(PlayerMatchPosition.sofascore_player_id.in_(ids))
        .order_by(PlayerMatchPosition.sofascore_player_id, PlayerMatchPosition.kickoff.desc())
    )
    for row in session.scalars(query):
        result[row.sofascore_player_id].append(
            MatchPosition(
                sofascore_player_id=row.sofascore_player_id,
                match_id=row.match_id,
                gw=row.gw,
                kickoff=row.kickoff,
                x=row.avg_x,
                y=row.avg_y,
                points_count=row.points_count,
                minutes=row.minutes,
            )
        )
    return result


def load_depth_pool(session: Session, min_minutes: int) -> list[float]:
    """Sorted depth of every stored match of a mapped outfield player who
    played at least `min_minutes` (~1,150 rows for six gameweeks)."""
    rows = session.execute(
        select(FplPlayer.role, PlayerMatchPosition.avg_y)
        .join(PlayerIdMap, PlayerIdMap.sofascore_id == PlayerMatchPosition.sofascore_player_id)
        .join(FplPlayer, FplPlayer.id == PlayerIdMap.fpl_id)
        .where(PlayerMatchPosition.minutes >= min_minutes)
    )
    return outfield_pool((role, y) for role, y in rows)


def load_positions_synced(session: Session, gw: int) -> bool:
    """Whether every match of `gw` has its positions in the database."""
    synced = session.scalar(select(Gameweek.positions_synced).where(Gameweek.id == gw))
    return bool(synced)


def load_data_as_of(session: Session) -> datetime | None:
    """When the latest finished sync ended: the site's "data as of"."""
    return session.scalar(select(func.max(SyncRun.finished_at)))
