"""Where each player's dot goes: the shared frame, "most recent match
played" and ghosts. Pure functions on plain data: rows come from
`app/logic/repository.py`, nothing here touches the database or HTTP.

Frame
-----
This module is the single place the frame is defined in code (the positions
adapter, `app/positions/base.py`, returns positions in it and the database
stores them unchanged). Pitch seen from behind the player's own goal, his
team attacking upward:

- **x**: 0 = left touchline, 100 = right touchline. `CENTER_X` = 50.
- **y**: 0 = own goal line, 100 = opponent's goal line.

Placement
---------
For a target gameweek, a player's dot comes from his usable matches in that
gameweek (all of them: a double gameweek has two, combined in task 11). If he
has none, it comes from his most recent usable match in an earlier gameweek,
and `from_gw` says which ("from GW4"). Matches in later gameweeks, or not yet
linked to a gameweek, are never used. A player with no Sofascore mapping, or
no usable match up to the target gameweek, is a ghost (drawn greyed on the
sideline, so he has no x / y).

A match is usable when its average is built from at least
`POSITION_MIN_POINTS_COUNT` on-ball actions.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.config import get_settings

X_MIN = Y_MIN = 0.0
X_MAX = Y_MAX = 100.0
CENTER_X = (X_MIN + X_MAX) / 2


class FrameError(ValueError):
    """A position outside the shared frame."""


def validate_point(x: float, y: float) -> None:
    if not (X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX):
        raise FrameError(f"position ({x}, {y}) is outside the {X_MIN:g}-{X_MAX:g} frame")


@dataclass(frozen=True)
class MatchPosition:
    """One stored `player_match_positions` row, in the frame above."""

    sofascore_player_id: int
    match_id: int
    gw: int | None  # None = match not linked to an FPL gameweek yet
    kickoff: datetime
    x: float
    y: float
    points_count: int
    minutes: int

    def __post_init__(self) -> None:
        validate_point(self.x, self.y)


class GhostReason(StrEnum):
    NO_MAPPING = "no_mapping"  # no Sofascore player linked to the FPL player
    NO_MATCH = "no_match"  # no usable match up to the target gameweek


@dataclass(frozen=True)
class Placement:
    fpl_id: int
    target_gw: int
    # Gameweek the matches come from; None for a ghost.
    source_gw: int | None
    # Every usable match of `source_gw` for the target gameweek itself; the
    # single most recent one for an earlier gameweek. Empty for a ghost.
    matches: tuple[MatchPosition, ...]
    ghost_reason: GhostReason | None = None

    @property
    def is_ghost(self) -> bool:
        return self.ghost_reason is not None

    @property
    def from_gw(self) -> int | None:
        """The "from GWx" label: set only when the dot is from an earlier gameweek."""
        if self.source_gw is None or self.source_gw == self.target_gw:
            return None
        return self.source_gw


def is_usable(row: MatchPosition, min_points_count: int) -> bool:
    return row.points_count >= min_points_count


def place_player(
    fpl_id: int,
    sofascore_id: int | None,
    rows: Iterable[MatchPosition],
    target_gw: int,
    *,
    min_points_count: int | None = None,
) -> Placement:
    """Place one player for `target_gw` from his stored rows (any order,
    any gameweeks; rows of other Sofascore players are ignored)."""
    if sofascore_id is None:
        return Placement(fpl_id, target_gw, None, (), GhostReason.NO_MAPPING)
    if min_points_count is None:
        min_points_count = get_settings().position_min_points_count

    candidates = [
        r
        for r in rows
        if r.sofascore_player_id == sofascore_id
        and r.gw is not None
        and r.gw <= target_gw
        and is_usable(r, min_points_count)
    ]
    in_target = sorted((r for r in candidates if r.gw == target_gw), key=lambda r: r.kickoff)
    if in_target:
        return Placement(fpl_id, target_gw, target_gw, tuple(in_target))
    if candidates:
        latest = max(candidates, key=lambda r: r.kickoff)
        return Placement(fpl_id, target_gw, latest.gw, (latest,))
    return Placement(fpl_id, target_gw, None, (), GhostReason.NO_MATCH)


def place_players(
    fpl_ids: Iterable[int],
    sofascore_ids: Mapping[int, int],
    rows_by_sofascore_id: Mapping[int, list[MatchPosition]],
    target_gw: int,
    *,
    min_points_count: int | None = None,
) -> dict[int, Placement]:
    """`place_player` for each FPL ID, keyed by FPL ID. `sofascore_ids` maps
    FPL ID → Sofascore ID (a missing key = no mapping)."""
    if min_points_count is None:
        min_points_count = get_settings().position_min_points_count
    placements = {}
    for fpl_id in fpl_ids:
        sofascore_id = sofascore_ids.get(fpl_id)
        rows = rows_by_sofascore_id.get(sofascore_id, []) if sofascore_id is not None else []
        placements[fpl_id] = place_player(
            fpl_id, sofascore_id, rows, target_gw, min_points_count=min_points_count
        )
    return placements
