"""Position logic II (`app/logic/gameweek.py`): gameweek states, auto-subs,
double gameweek, captain; plus `load_positions_synced`."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.engine import make_read_write_engine
from app.db.models import Gameweek
from app.fpl.team import AutoSub, Club, GameweekStatus, Player, TeamGameweek, TeamPick
from app.logic.gameweek import (
    GameweekState,
    build_dots,
    combine_matches,
    gameweek_state,
    plotted_picks,
    team_state,
)
from app.logic.positions import GhostReason, MatchPosition
from app.logic.repository import load_positions_synced

GW = 6
GW1 = datetime(2026, 8, 15, 14)
MARGIN = 10.0
ROLES = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD"]
ROLES += ["GK", "DEF", "MID", "FWD"]  # bench 12-15


def kickoff(gw: int, extra_days: int = 0) -> datetime:
    return GW1 + timedelta(days=7 * (gw - 1) + extra_days)


def sofa(fpl_id: int) -> int:
    return fpl_id * 100


def row(fpl_id, gw, x=30.0, y=40.0, *, days=0, points=30):
    return MatchPosition(
        sofascore_player_id=sofa(fpl_id),
        match_id=gw * 1000 + fpl_id * 10 + days,
        gw=gw,
        kickoff=kickoff(gw, days),
        x=x,
        y=y,
        points_count=points,
        minutes=90,
    )


def make_team(
    *,
    status=GameweekStatus.FINISHED,
    subs: list[tuple[int, int]] = (),
    captain=1,
    vice=2,
    effective_captain=None,
) -> TeamGameweek:
    """FPL IDs 1-15 picked in positions 1-15; `subs` = (out, in) auto-subs,
    applied the way FPL shows them (positions swapped)."""
    position = {i: i for i in range(1, 16)}
    for out, in_ in subs:
        position[out], position[in_] = position[in_], position[out]
    outs = {o for o, _ in subs}
    ins = {i for _, i in subs}
    picks = [
        TeamPick(
            position=position[i],
            starter=position[i] <= 11,
            picked_starter=i <= 11,
            role=ROLES[i - 1],
            multiplier=0 if position[i] > 11 else 2 if i == (effective_captain or captain) else 1,
            is_captain=i == captain,
            is_vice_captain=i == vice,
            auto_sub="out" if i in outs else "in" if i in ins else None,
            player=Player(
                id=i,
                web_name=f"P{i}",
                first_name="",
                second_name=f"P{i}",
                club=Club(id=1, name="Club", short_name="CLB"),
            ),
        )
        for i in range(1, 16)
    ]
    return TeamGameweek(
        team_id=1,
        team_name="Team",
        manager_name="Manager",
        gameweek=GW,
        status=status,
        data_checked=status is GameweekStatus.FINISHED,
        deadline=datetime(2026, 9, 26, 10, 0, tzinfo=UTC),
        chip=None,
        bank=0,
        squad_value=1000,
        captain_id=captain,
        vice_captain_id=vice,
        effective_captain_id=effective_captain or captain,
        automatic_subs=[AutoSub(player_in=i, player_out=o) for o, i in subs],
        picks=sorted(picks, key=lambda p: p.position),
    )


def everyone_played(gw=GW, *, skip=()):
    """One match in `gw` for each of the 15, except `skip`."""
    return {sofa(i): [row(i, gw, x=4.0 * i, y=5.0 * i)] for i in range(1, 16) if i not in skip}


def all_mapped():
    return {i: sofa(i) for i in range(1, 16)}


def dots_by_id(dots):
    by_id: dict[int, list] = {}
    for d in dots:
        by_id.setdefault(d.fpl_id, []).append(d)
    return by_id


def build(team, state, rows, sofascore_ids=None):
    return build_dots(
        team,
        state,
        all_mapped() if sofascore_ids is None else sofascore_ids,
        rows,
        min_points_count=1,
        flank_margin=MARGIN,
    )


# --- State detection -----------------------------------------------------------


@pytest.mark.parametrize(
    ("finished", "synced", "state"),
    [
        (True, True, GameweekState.LOCKED),
        (True, False, GameweekState.PREVIEW),  # finished but not yet synced
        (False, False, GameweekState.PREVIEW),
        (False, True, GameweekState.PREVIEW),
    ],
)
def test_gameweek_state(finished, synced, state):
    assert gameweek_state(finished, synced) is state


def test_team_state_uses_fpl_status():
    assert team_state(make_team(), True) is GameweekState.LOCKED
    assert team_state(make_team(), False) is GameweekState.PREVIEW
    in_progress = make_team(status=GameweekStatus.IN_PROGRESS)
    assert team_state(in_progress, True) is GameweekState.PREVIEW


def test_load_positions_synced(tmp_path):
    engine = make_read_write_engine(tmp_path / "t.db")
    Base.metadata.create_all(engine)
    deadline = datetime(2026, 9, 1)
    with Session(engine) as session:
        session.add_all(
            [
                Gameweek(id=5, deadline=deadline, finished=True, positions_synced=True),
                Gameweek(id=6, deadline=deadline, finished=True, positions_synced=False),
            ]
        )
        session.commit()
        assert load_positions_synced(session, 5) is True
        assert load_positions_synced(session, 6) is False
        assert load_positions_synced(session, 7) is False  # unknown gameweek


# --- Preview -------------------------------------------------------------------


def test_preview_plots_picked_xi_without_auto_subs():
    team = make_team(status=GameweekStatus.IN_PROGRESS, subs=[(4, 13)])
    dots = build(team, GameweekState.PREVIEW, everyone_played(GW - 1))
    assert [d.fpl_id for d in dots] == list(range(1, 12))
    assert [d.slot for d in dots] == list(range(1, 12))  # 4 back in his own slot
    assert all(d.replaces is None for d in dots)


def test_preview_previous_gameweek_has_no_label():
    team = make_team(status=GameweekStatus.IN_PROGRESS)
    dots = build(team, GameweekState.PREVIEW, everyone_played(GW - 1))
    assert all(d.from_gw is None and not d.is_ghost for d in dots)


def test_preview_fallback_label():
    team = make_team(status=GameweekStatus.IN_PROGRESS)
    rows = everyone_played(GW - 1, skip={7})
    rows[sofa(7)] = [row(7, 2, x=10, y=20), row(7, 4, x=70, y=60)]
    dots = dots_by_id(build(team, GameweekState.PREVIEW, rows))
    (dot,) = dots[7]
    assert dot.from_gw == 4
    assert (dot.x, dot.y) == (70, 60)


def test_preview_uses_most_recent_match_including_target_gameweek():
    team = make_team(status=GameweekStatus.IN_PROGRESS)
    rows = everyone_played(GW - 1)
    rows[sofa(3)].append(row(3, GW, x=88, y=77))  # already played this gameweek
    (dot,) = dots_by_id(build(team, GameweekState.PREVIEW, rows))[3]
    assert (dot.x, dot.y, dot.from_gw) == (88, 77, None)


def test_preview_finished_but_not_synced_still_uses_fallback():
    # Finished in FPL but positions not synced: preview, so no ghost for a
    # player whose only stored match is from an earlier gameweek.
    team = make_team()
    state = team_state(team, positions_synced=False)
    rows = everyone_played(GW - 1, skip={9})
    rows[sofa(9)] = [row(9, 3)]
    (dot,) = dots_by_id(build(team, state, rows))[9]
    assert not dot.is_ghost
    assert dot.from_gw == 3


def test_preview_ghosts():
    team = make_team(status=GameweekStatus.IN_PROGRESS)
    rows = everyone_played(GW - 1, skip={5})
    ids = all_mapped()
    del ids[8]
    dots = dots_by_id(build(team, GameweekState.PREVIEW, rows, ids))
    assert dots[5][0].ghost_reason is GhostReason.NO_MATCH
    assert dots[8][0].ghost_reason is GhostReason.NO_MAPPING
    assert dots[5][0].x is None and dots[5][0].y is None


# --- Locked --------------------------------------------------------------------


def test_locked_with_auto_sub():
    team = make_team(subs=[(4, 13)])
    rows = everyone_played(skip={4})
    dots = build(team, GameweekState.LOCKED, rows)
    assert [d.slot for d in dots] == list(range(1, 12))
    assert 4 not in {d.fpl_id for d in dots}
    sub = next(d for d in dots if d.fpl_id == 13)
    assert sub.slot == 4  # takes the starter's slot
    assert sub.replaces == 4
    assert (sub.x, sub.y) == (52, 65)
    assert not any(d.is_ghost for d in dots)


def test_locked_ghost_with_no_replacement():
    # 6 did not play and no bench player could come on.
    team = make_team()
    rows = everyone_played(skip={6})
    rows[sofa(6)] = [row(6, GW - 1)]  # an earlier match does not count when locked
    (dot,) = dots_by_id(build(team, GameweekState.LOCKED, rows))[6]
    assert dot.is_ghost
    assert dot.ghost_reason is GhostReason.NO_MATCH
    assert dot.from_gw is None
    assert dot.match_ids == ()


def test_locked_unmapped_starter_is_ghost():
    ids = all_mapped()
    del ids[10]
    (dot,) = dots_by_id(build(make_team(), GameweekState.LOCKED, everyone_played(), ids))[10]
    assert dot.ghost_reason is GhostReason.NO_MAPPING


def test_bench_not_plotted():
    for state in GameweekState:
        dots = build(make_team(), state, everyone_played())
        assert {d.fpl_id for d in dots} == set(range(1, 12))


# --- Double gameweek -----------------------------------------------------------


def dgw(x1, y1, x2, y2):
    team = make_team()
    rows = everyone_played(skip={7})
    rows[sofa(7)] = [row(7, GW, x1, y1), row(7, GW, x2, y2, days=3)]
    return dots_by_id(build(team, GameweekState.LOCKED, rows))[7]


def test_dgw_same_side_one_averaged_dot():
    (dot,) = dgw(20, 40, 30, 60)
    assert (dot.x, dot.y) == (25, 50)
    assert dot.link_group is None
    assert len(dot.match_ids) == 2


def test_dgw_opposite_flanks_two_linked_dots():
    dots = dgw(80, 70, 15, 50)
    assert len(dots) == 2
    assert [(d.x, d.y) for d in dots] == [(15, 50), (80, 70)]  # left flank first
    assert dots[0].link_group == dots[1].link_group == 7
    assert all(d.slot == dots[0].slot for d in dots)


def test_dgw_within_margin_one_dot():
    # Different sides of the center line, but one is within the margin.
    (dot,) = dgw(45, 40, 75, 60)
    assert (dot.x, dot.y) == (60, 50)
    assert dot.link_group is None


def test_dgw_rescheduled_match_counts():
    # A match FPL moved into this gameweek is stored with gw=GW even though it
    # was played weeks later; both rows of the gameweek are combined.
    team = make_team()
    rows = everyone_played(skip={7})
    rows[sofa(7)] = [row(7, GW, 20, 40), row(7, GW, 30, 60, days=21)]
    (dot,) = dots_by_id(build(team, GameweekState.LOCKED, rows))[7]
    assert len(dot.match_ids) == 2


def test_combine_matches_margin_boundary():
    on_margin = [row(1, GW, 40, 50), row(1, GW, 60, 50, days=1)]
    assert len(combine_matches(on_margin, MARGIN)) == 1  # must be *beyond* the margin
    assert len(combine_matches(on_margin, MARGIN - 0.1)) == 2
    assert combine_matches([], MARGIN) == []


def test_flank_margin_from_settings(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DGW_FLANK_MARGIN", "40")
    get_settings.cache_clear()
    try:
        team = make_team()
        rows = everyone_played(skip={7})
        rows[sofa(7)] = [row(7, GW, 15, 50), row(7, GW, 80, 70, days=3)]
        dots = build_dots(team, GameweekState.LOCKED, all_mapped(), rows, min_points_count=1)
        assert len(dots_by_id(dots)[7]) == 1  # 15 / 80 are not beyond 40 from center
    finally:
        get_settings.cache_clear()


# --- Captain -------------------------------------------------------------------


def test_captain_flag_preserved():
    for state in GameweekState:
        dots = build(make_team(captain=9, vice=2), state, everyone_played())
        assert [d.fpl_id for d in dots if d.is_captain] == [9]


def test_captain_flag_on_both_linked_dots():
    team = make_team(captain=7)
    rows = everyone_played(skip={7})
    rows[sofa(7)] = [row(7, GW, 15, 50), row(7, GW, 80, 70, days=3)]
    dots = dots_by_id(build(team, GameweekState.LOCKED, rows))[7]
    assert len(dots) == 2 and all(d.is_captain for d in dots)


def test_captain_who_did_not_play():
    # FPL subs the captain off (12 comes on) and multiplies the vice.
    team = make_team(captain=9, vice=2, effective_captain=2, subs=[(9, 12)])
    rows = everyone_played(skip={9})
    locked = build(team, GameweekState.LOCKED, rows)
    assert [d.fpl_id for d in locked if d.is_captain] == [2]
    preview = build(team, GameweekState.PREVIEW, everyone_played(GW - 1))
    assert [d.fpl_id for d in preview if d.is_captain] == [9]


def test_plotted_picks_slots_preview_vs_locked():
    team = make_team(subs=[(4, 13), (10, 14)])
    locked = [(slot, p.player.id) for slot, p in plotted_picks(team, GameweekState.LOCKED)]
    preview = [(slot, p.player.id) for slot, p in plotted_picks(team, GameweekState.PREVIEW)]
    assert dict(locked)[4] == 13 and dict(locked)[10] == 14
    assert preview == [(i, i) for i in range(1, 12)]
