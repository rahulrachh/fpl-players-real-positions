"""A team's gameweek → the JSON the frontend draws (`GET /api/team/{id}/plot/{gw}`,
documented in `docs/api.md`). Joins the dots from `app/logic/gameweek.py`
with the player details and the navigation around the gameweek.

Reads only the bundled database and the already-loaded FPL team; never
Sofascore.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.fpl.team import TeamGameweek
from app.logic.depth import POOL_MIN_MINUTES, rank_depth
from app.logic.gameweek import GameweekState, build_dots, team_state
from app.logic.positions import GhostReason
from app.logic.repository import (
    load_data_as_of,
    load_depth_pools,
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
    # Percentile (0-100) of y among every outfield player-match / those of
    # the same FPL role (`app/logic/depth.py`). None for a goalkeeper or ghost.
    depth_pct_all: float | None
    depth_pct_role: float | None


class Plot(_Model):
    team_id: int
    team_name: str
    manager_name: str
    gw: int
    state: GameweekState
    # The team's gameweek score before hits, and the hit (FPL `entry_history`).
    points: int
    transfers_cost: int
    # Neighbouring gameweeks the team can be shown for; None at an edge.
    prev_gw: int | None
    next_gw: int | None
    # End of the latest finished sync; None if the database was never synced.
    data_as_of: datetime | None
    dots: list[PlotDot]


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


def build_plot(team: TeamGameweek, session: Session, latest_gw: int | None) -> Plot:
    state = team_state(team, load_positions_synced(session, team.gameweek))
    sofascore_ids = load_sofascore_ids(session, [p.player.id for p in team.picks])
    rows = load_match_positions(session, sofascore_ids.values())
    players = {p.player.id: p.player for p in team.picks}
    pools = load_depth_pools(session, POOL_MIN_MINUTES)

    dots = []
    for dot in build_dots(team, state, sofascore_ids, rows):
        player = players[dot.fpl_id]
        y = _round(dot.y)
        pct_all, pct_role = rank_depth(pools, dot.role, y)
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
                depth_pct_all=pct_all,
                depth_pct_role=pct_role,
            )
        )

    prev_gw, next_gw = neighbour_gameweeks(team.gameweek, team.started_event, latest_gw)
    return Plot(
        team_id=team.team_id,
        team_name=team.team_name,
        manager_name=team.manager_name,
        gw=team.gameweek,
        state=state,
        points=team.points,
        transfers_cost=team.transfers_cost,
        prev_gw=prev_gw,
        next_gw=next_gw,
        data_as_of=load_data_as_of(session),
        dots=dots,
    )
