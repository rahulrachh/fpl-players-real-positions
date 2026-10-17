"""A team's gameweek → the final list of dots: gameweek state (preview /
locked), whose dots are drawn (picked XI or XI after auto-subs) and the
double gameweek rule. Pure functions on plain data, like
`app/logic/positions.py` which places each player.

States
------
- **locked**: the gameweek is finished in FPL *and* `gameweeks.positions_synced`
  (every match of it is in the deployed database). Dots are the XI after
  FPL's auto-subs (a sub-in takes the starter's slot), each from his matches
  of that gameweek only. A starter with none is a ghost.
- **preview**: anything else, including finished but not yet synced. Dots are
  the XI as picked (auto-subs undone), each from his most recent match in the
  database, labelled "from GWx" unless it is from the previous gameweek (or
  the target gameweek itself).

Double gameweek
---------------
Every usable match of the gameweek counts (also a rescheduled match FPL moved
into it). They give **two linked dots** when they are on opposite flanks:
some on each side of `CENTER_X`, each of those beyond `DGW_FLANK_MARGIN`
from it. Otherwise one dot, the plain average of the matches.

Captain
-------
The armband goes to the picked captain in preview, and in locked to the
player whose points FPL multiplied (the vice when the captain did not play;
that captain is on the bench, so not drawn). Bench players are never dots.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.config import get_settings
from app.fpl.team import GameweekStatus, TeamGameweek, TeamPick
from app.logic.positions import (
    CENTER_X,
    GhostReason,
    MatchPosition,
    Placement,
    place_player,
)


class GameweekState(StrEnum):
    PREVIEW = "preview"
    LOCKED = "locked"


def gameweek_state(finished: bool, positions_synced: bool) -> GameweekState:
    if finished and positions_synced:
        return GameweekState.LOCKED
    return GameweekState.PREVIEW


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def combine_matches(matches: Sequence[MatchPosition], flank_margin: float) -> list[Point]:
    """One point per dot: two (left flank first) for opposite flanks, else
    one average. Empty for no matches."""
    if not matches:
        return []
    left = [m for m in matches if m.x < CENTER_X - flank_margin]
    right = [m for m in matches if m.x > CENTER_X + flank_margin]
    if left and right:
        # Matches near the center join the side they are on.
        return [
            _average([m for m in matches if m.x < CENTER_X]),
            _average([m for m in matches if m.x >= CENTER_X]),
        ]
    return [_average(matches)]


def _average(matches: Sequence[MatchPosition]) -> Point:
    return Point(
        x=sum(m.x for m in matches) / len(matches),
        y=sum(m.y for m in matches) / len(matches),
    )


@dataclass(frozen=True)
class Dot:
    fpl_id: int
    # XI slot 1-11 (FPL's formation order); a sub-in has the starter's slot.
    slot: int
    role: str
    is_captain: bool
    # None for a ghost (drawn on the sideline).
    x: float | None
    y: float | None
    ghost_reason: GhostReason | None
    # "from GWx" label; None when the dot is from the expected gameweek.
    from_gw: int | None
    # Shared by the two linked dots of a double gameweek on opposite flanks
    # (the player's FPL ID); None for a single dot.
    link_group: int | None
    # Locked only: the picked starter this auto-sub replaced.
    replaces: int | None
    match_ids: tuple[int, ...]

    @property
    def is_ghost(self) -> bool:
        return self.ghost_reason is not None


def team_state(team: TeamGameweek, positions_synced: bool) -> GameweekState:
    return gameweek_state(team.status is GameweekStatus.FINISHED, positions_synced)


def plotted_picks(team: TeamGameweek, state: GameweekState) -> list[tuple[int, TeamPick]]:
    """(slot, pick) for the XI drawn in this state, in slot order."""
    if state is GameweekState.LOCKED:
        return [(p.position, p) for p in team.picks if p.starter]
    # Preview: undo FPL's auto-subs; a subbed-out starter gets the slot of the
    # bench player who replaced them.
    position_of = {p.player.id: p.position for p in team.picks}
    sub_in_for = {s.player_out: s.player_in for s in team.automatic_subs}
    picked = []
    for p in team.picks:
        if not p.picked_starter:
            continue
        slot = position_of[sub_in_for[p.player.id]] if p.auto_sub == "out" else p.position
        picked.append((slot, p))
    return sorted(picked, key=lambda sp: sp[0])


def build_dots(
    team: TeamGameweek,
    state: GameweekState,
    sofascore_ids: Mapping[int, int],
    rows_by_sofascore_id: Mapping[int, list[MatchPosition]],
    *,
    min_points_count: int | None = None,
    flank_margin: float | None = None,
) -> list[Dot]:
    """The dots for `team`'s gameweek, in slot order. `sofascore_ids` /
    `rows_by_sofascore_id` as for `place_players`."""
    settings = get_settings()
    if min_points_count is None:
        min_points_count = settings.position_min_points_count
    if flank_margin is None:
        flank_margin = settings.dgw_flank_margin
    gw = team.gameweek
    if state is GameweekState.LOCKED:
        captain_id = team.effective_captain_id
    else:
        captain_id = team.captain_id
    replaced = {s.player_in: s.player_out for s in team.automatic_subs}

    dots: list[Dot] = []
    for slot, pick in plotted_picks(team, state):
        fpl_id = pick.player.id
        sofascore_id = sofascore_ids.get(fpl_id)
        rows = rows_by_sofascore_id.get(sofascore_id, []) if sofascore_id is not None else []
        placement = place_player(fpl_id, sofascore_id, rows, gw, min_points_count=min_points_count)
        if state is GameweekState.LOCKED:
            matches, ghost_reason, from_gw = _locked(placement)
        else:
            matches, ghost_reason, from_gw = _preview(placement)

        common = dict(
            fpl_id=fpl_id,
            slot=slot,
            role=pick.role,
            is_captain=fpl_id == captain_id,
            from_gw=from_gw,
            replaces=replaced.get(fpl_id) if state is GameweekState.LOCKED else None,
            match_ids=tuple(m.match_id for m in matches),
        )
        points = combine_matches(matches, flank_margin)
        if not points:
            dots.append(Dot(**common, x=None, y=None, ghost_reason=ghost_reason, link_group=None))
            continue
        link_group = fpl_id if len(points) > 1 else None
        for point in points:
            dots.append(
                Dot(**common, x=point.x, y=point.y, ghost_reason=None, link_group=link_group)
            )
    return dots


def _locked(
    placement: Placement,
) -> tuple[tuple[MatchPosition, ...], GhostReason | None, int | None]:
    """Only the gameweek's own matches; none = ghost."""
    if placement.is_ghost:
        return (), placement.ghost_reason, None
    if placement.source_gw != placement.target_gw:
        return (), GhostReason.NO_MATCH, None
    return placement.matches, None, None


def _preview(
    placement: Placement,
) -> tuple[tuple[MatchPosition, ...], GhostReason | None, int | None]:
    """The single most recent match; labelled unless it is from the target
    or the previous gameweek."""
    if placement.is_ghost:
        return (), placement.ghost_reason, None
    latest = max(placement.matches, key=lambda m: m.kickoff)
    source = placement.source_gw
    from_gw = None if source in (placement.target_gw, placement.target_gw - 1) else source
    return (latest,), None, from_gw
