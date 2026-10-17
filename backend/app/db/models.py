"""MVP tables. Written only by offline scripts; the web app reads them
read-only. Described in `docs/data-model.md`.

Conventions:
- Datetimes are stored as naive UTC.
- Primary keys are the source's own IDs (FPL or Sofascore), except
  `sync_runs`.
- Positions are on Sofascore's normalized 0-100 frame: x 0 = own goal,
  100 = opponent's goal; y high = left side (attacking team's view).
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

FPL_ROLES = ("GK", "DEF", "MID", "FWD")
MATCH_METHODS = ("exact", "short_name", "surname_initial", "fuzzy", "override")
SYNC_TRIGGERS = ("run", "backfill")

# Full match length used to derive minutes; stoppage time is ignored.
MATCH_MINUTES = 90


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class FplClub(Base):
    __tablename__ = "fpl_clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(64))
    short_name: Mapped[str] = mapped_column(String(8))
    # Set from the owner's list; used to fetch the club's matches.
    sofascore_team_id: Mapped[int | None] = mapped_column(Integer, unique=True)

    players: Mapped[list["FplPlayer"]] = relationship(back_populates="club")


class FplPlayer(Base):
    """Refreshed from FPL on every sync. Holds no mapping data
    (see `PlayerIdMap`), so a refresh never touches the mapping."""

    __tablename__ = "fpl_players"
    __table_args__ = (CheckConstraint(_in("role", FPL_ROLES), name="role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(128))
    second_name: Mapped[str] = mapped_column(String(128))
    web_name: Mapped[str] = mapped_column(String(128))
    club_id: Mapped[int] = mapped_column(ForeignKey("fpl_clubs.id"), index=True)
    role: Mapped[str] = mapped_column(String(3))
    # FPL `now_cost`: tenths of £m (55 = £5.5m).
    price: Mapped[int] = mapped_column(Integer)
    # FPL availability code: a (available), d (doubtful), i, s, u, n.
    status: Mapped[str] = mapped_column(String(1))
    news: Mapped[str] = mapped_column(Text, default="")

    club: Mapped[FplClub] = relationship(back_populates="players")
    mapping: Mapped["PlayerIdMap | None"] = relationship(back_populates="fpl_player")


class SofascorePlayer(Base):
    """Source side of the ID mapping."""

    __tablename__ = "sofascore_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(128))
    short_name: Mapped[str | None] = mapped_column(String(128))
    slug: Mapped[str | None] = mapped_column(String(128))
    # Club the player was last seen for (not an FK: Sofascore team IDs live
    # on `fpl_clubs.sofascore_team_id` and may not be set yet).
    sofascore_team_id: Mapped[int | None] = mapped_column(Integer, index=True)

    mapping: Mapped["PlayerIdMap | None"] = relationship(back_populates="sofascore_player")


class PlayerIdMap(Base):
    """FPL player ↔ Sofascore player. One row per matched FPL player;
    unmatched players have no row. The UNIQUE on `sofascore_id` stops two
    FPL players mapping to the same Sofascore player."""

    __tablename__ = "player_id_map"
    __table_args__ = (
        CheckConstraint(_in("match_method", MATCH_METHODS), name="match_method"),
        CheckConstraint("match_confidence BETWEEN 0 AND 1", name="match_confidence"),
    )

    fpl_id: Mapped[int] = mapped_column(
        ForeignKey("fpl_players.id"), primary_key=True, autoincrement=False
    )
    sofascore_id: Mapped[int] = mapped_column(
        ForeignKey("sofascore_players.id"), unique=True
    )
    match_method: Mapped[str] = mapped_column(String(16))
    match_confidence: Mapped[float] = mapped_column(Float)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime)

    fpl_player: Mapped[FplPlayer] = relationship(back_populates="mapping")
    sofascore_player: Mapped[SofascorePlayer] = relationship(back_populates="mapping")


class Gameweek(Base):
    __tablename__ = "gameweeks"

    # FPL gameweek number (1-38).
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    deadline: Mapped[datetime] = mapped_column(DateTime)
    # FPL `finished` / `data_checked`: all fixtures done / points final.
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    data_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Every match of the gameweek has its positions stored.
    positions_synced: Mapped[bool] = mapped_column(Boolean, default=False)


class Match(Base):
    __tablename__ = "matches"

    # Sofascore event ID.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    fpl_fixture_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    # From FPL's fixture list, not Sofascore's round number. Null until the
    # match is linked to an FPL fixture.
    gw: Mapped[int | None] = mapped_column(ForeignKey("gameweeks.id"), index=True)
    home_club_id: Mapped[int] = mapped_column(ForeignKey("fpl_clubs.id"))
    away_club_id: Mapped[int] = mapped_column(ForeignKey("fpl_clubs.id"))
    # Sofascore `startTimestamp`.
    kickoff: Mapped[datetime] = mapped_column(DateTime)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    # Null = average positions not downloaded yet.
    positions_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)

    positions: Mapped[list["PlayerMatchPosition"]] = relationship(back_populates="match")


class PlayerMatchPosition(Base):
    """One player's average position in one match. `kickoff` and `gw` are
    copied from `matches` so the website reads only this table."""

    __tablename__ = "player_match_positions"
    __table_args__ = (
        CheckConstraint("avg_x BETWEEN 0 AND 100", name="avg_x"),
        CheckConstraint("avg_y BETWEEN 0 AND 100", name="avg_y"),
        CheckConstraint("points_count >= 0", name="points_count"),
        CheckConstraint("minutes >= 0", name="minutes"),
        # "Most recent match played" lookup.
        Index("ix_player_match_positions_player_kickoff", "sofascore_player_id", "kickoff"),
        # Gameweek view.
        Index("ix_player_match_positions_player_gw", "sofascore_player_id", "gw"),
    )

    # The composite primary key is the unique (match, player) constraint.
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    sofascore_player_id: Mapped[int] = mapped_column(
        ForeignKey("sofascore_players.id"), primary_key=True
    )
    # Normalized: own goal (0) to opponent goal (100); y high = left side.
    avg_x: Mapped[float] = mapped_column(Float)
    avg_y: Mapped[float] = mapped_column(Float)
    # Sofascore `pointsCount`: on-ball actions behind the average. Low = noisy dot.
    points_count: Mapped[int] = mapped_column(Integer)
    # Set = came on as a sub / was taken off.
    sub_on_minute: Mapped[int | None] = mapped_column(Integer)
    sub_off_minute: Mapped[int | None] = mapped_column(Integer)
    # Derived on write from the sub minutes (see `minutes_played`).
    minutes: Mapped[int] = mapped_column(Integer)
    kickoff: Mapped[datetime] = mapped_column(DateTime)
    gw: Mapped[int | None] = mapped_column(Integer)

    match: Mapped[Match] = relationship(back_populates="positions")


def minutes_played(sub_on_minute: int | None, sub_off_minute: int | None) -> int:
    """Approximate minutes: stoppage time and red cards are ignored."""
    end = MATCH_MINUTES if sub_off_minute is None else sub_off_minute
    start = 0 if sub_on_minute is None else sub_on_minute
    return max(0, end - start)


@event.listens_for(PlayerMatchPosition, "before_insert")
@event.listens_for(PlayerMatchPosition, "before_update")
def _derive_minutes(_mapper, _connection, row: PlayerMatchPosition) -> None:
    row.minutes = minutes_played(row.sub_on_minute, row.sub_off_minute)


class SyncRun(Base):
    """One offline sync. The latest finished run is the site's "data as of"."""

    __tablename__ = "sync_runs"
    __table_args__ = (CheckConstraint(_in("trigger", SYNC_TRIGGERS), name="trigger"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    # Null = still running or crashed.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    trigger: Mapped[str] = mapped_column(String(16))
    matches_fetched: Mapped[int] = mapped_column(Integer, default=0)
    # Error messages, one per failure (JSON list of strings).
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)
