"""A team's gameweek → the JSON the frontend draws (`GET /api/team/{id}/plot/{gw}`,
documented in `docs/api.md`). Joins the dots from `app/logic/gameweek.py`
with the player details and the navigation around the gameweek.

Reads only the bundled database and the already-loaded FPL team; never
Sofascore.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.fpl.team import GameweekStatus, PickMatch, TeamGameweek, TeamPick
from app.logic.depth import POOL_MIN_MINUTES, rank_depth
from app.logic.gameweek import (
    GameweekState,
    bench_picks,
    build_dots,
    captain_multiplier,
    team_state,
)
from app.logic.positions import GhostReason
from app.logic.repository import (
    load_data_as_of,
    load_depth_pool,
    load_fixture_ids,
    load_match_positions,
    load_positions_synced,
    load_sofascore_ids,
)


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class PlotDot(_Model):
    fpl_id: int
    # Full name ("Bukayo Saka") and FPL's short name ("Saka").
    name: str
    web_name: str
    role: str
    # Club short name ("ARS").
    club: str
    # XI slot 1-11; an auto-sub has the starter's slot.
    slot: int
    # 0-100, attacking upward (see `docs/data-model.md`), 2 decimals; None
    # for a ghost.
    x: float | None
    y: float | None
    is_captain: bool
    is_ghost: bool
    ghost_reason: GhostReason | None
    from_gw: int | None
    # Same value on the two linked dots of a double gameweek.
    link_group: int | None
    # Locked only: FPL ID of the picked starter this auto-sub replaced.
    replaces: int | None
    # Percentile (0-100) of y among every outfield player-match
    # (`app/logic/depth.py`); the pitch draws it as the dot's height. None for
    # a goalkeeper or a ghost.
    depth_pct: float | None
    # The points the player scored for the team this gameweek (live while in
    # progress): his own, doubled for the captain (tripled with Triple
    # Captain). The dots of the XI add up to the gameweek score before hits.
    points: int
    # 2 for the captain (3 with Triple Captain), else 1: `points` is his own
    # points times this.
    multiplier: int
    # A bench player drawn because of Bench Boost (slot 12-15).
    from_bench: bool
    # His matches of the gameweek with the points breakdown (the hover box).
    # A linked double-gameweek dot has only the match its position came from;
    # every other dot has all of them.
    matches: list[PickMatch]


class BenchPlayer(_Model):
    """Points are his own (they did not count for the team)."""

    fpl_id: int
    name: str
    web_name: str
    role: str
    club: str
    points: int
    # Locked only: a picked starter FPL auto-subbed off (did not play).
    subbed_off: bool
    matches: list[PickMatch]


class Plot(_Model):
    team_id: int
    team_name: str
    manager_name: str
    gw: int
    state: GameweekState
    # FPL's status: in_progress or finished. A finished gameweek in the
    # preview state is waiting for its positions (next sync + deploy).
    status: GameweekStatus
    # bboost / 3xc / freehit / wildcard / manager; None = no chip.
    chip: str | None
    # The team's gameweek score before hits, and the hit (FPL `entry_history`).
    points: int
    transfers_cost: int
    # Neighbouring gameweeks the team can be shown for; None at an edge.
    prev_gw: int | None
    next_gw: int | None
    # End of the latest finished sync; None if the database was never synced.
    data_as_of: datetime | None
    dots: list[PlotDot]
    # In bench order (see `app/logic/gameweek.py`); empty under Bench Boost,
    # when the bench is drawn on the pitch.
    bench: list[BenchPlayer]


# Decimals kept in x / y: a hundredth of the pitch is ~1 m.
COORD_DECIMALS = 2


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, COORD_DECIMALS)


def neighbour_gameweeks(
    gw: int, started_event: int, latest_gw: int | None
) -> tuple[int | None, int | None]:
    """(prev, next): prev stops at the team's first gameweek (and GW1), next
    at the newest gameweek whose deadline has passed (and so GW38)."""
    prev_gw = gw - 1 if gw - 1 >= max(1, started_event) else None
    next_gw = gw + 1 if latest_gw is not None and gw + 1 <= latest_gw else None
    return prev_gw, next_gw


def _dot_matches(
    pick: TeamPick, match_ids: tuple[int, ...], fixture_ids: dict[int, int]
) -> list[PickMatch]:
    """The pick's matches behind one dot: those of `match_ids` (a linked
    double-gameweek dot), or all of them when empty or not linked to FPL."""
    fixtures = {fixture_ids[m] for m in match_ids if m in fixture_ids}
    own = [m for m in pick.matches if m.fixture_id in fixtures]
    return own or pick.matches


def build_plot(team: TeamGameweek, session: Session, latest_gw: int | None) -> Plot:
    state = team_state(team, load_positions_synced(session, team.gameweek))
    sofascore_ids = load_sofascore_ids(session, [p.player.id for p in team.picks])
    rows = load_match_positions(session, sofascore_ids.values())
    picks = {p.player.id: p for p in team.picks}
    players = {fpl_id: p.player for fpl_id, p in picks.items()}
    pool = load_depth_pool(session, POOL_MIN_MINUTES)
    multiplier = captain_multiplier(team)

    built = build_dots(team, state, sofascore_ids, rows)
    fixture_ids = load_fixture_ids(session, {m for d in built if d.link_group for m in d.match_ids})

    dots = []
    for dot in built:
        player = players[dot.fpl_id]
        pick = picks[dot.fpl_id]
        y = _round(dot.y)
        dot_multiplier = multiplier if dot.is_captain else 1
        dots.append(
            PlotDot(
                fpl_id=dot.fpl_id,
                name=f"{player.first_name} {player.second_name}",
                web_name=player.web_name,
                role=dot.role,
                club=player.club.short_name,
                slot=dot.slot,
                x=_round(dot.x),
                y=y,
                is_captain=dot.is_captain,
                is_ghost=dot.is_ghost,
                ghost_reason=dot.ghost_reason,
                from_gw=dot.from_gw,
                link_group=dot.link_group,
                replaces=dot.replaces,
                depth_pct=rank_depth(pool, dot.role, y),
                points=pick.points * dot_multiplier,
                multiplier=dot_multiplier,
                from_bench=dot.slot > 11,
                matches=_dot_matches(pick, dot.match_ids if dot.link_group else (), fixture_ids),
            )
        )
    bench = [
        BenchPlayer(
            fpl_id=p.player.id,
            name=f"{p.player.first_name} {p.player.second_name}",
            web_name=p.player.web_name,
            role=p.role,
            club=p.player.club.short_name,
            points=p.points,
            subbed_off=state is GameweekState.LOCKED and p.auto_sub == "out",
            matches=p.matches,
        )
        for p in bench_picks(team, state)
    ]

    prev_gw, next_gw = neighbour_gameweeks(team.gameweek, team.started_event, latest_gw)
    return Plot(
        team_id=team.team_id,
        team_name=team.team_name,
        manager_name=team.manager_name,
        gw=team.gameweek,
        state=state,
        status=team.status,
        chip=team.chip,
        points=team.points,
        transfers_cost=team.transfers_cost,
        prev_gw=prev_gw,
        next_gw=next_gw,
        data_as_of=load_data_as_of(session),
        dots=dots,
        bench=bench,
    )
