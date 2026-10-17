"""Position logic I (`app/logic/positions.py`): frame, most recent match
played, ghosts; plus the repository that feeds it."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import Base
from app.db.engine import make_read_write_engine
from app.db.models import (
    FplClub,
    FplPlayer,
    Gameweek,
    Match,
    PlayerIdMap,
    PlayerMatchPosition,
    SofascorePlayer,
)
from app.logic.positions import (
    CENTER_X,
    FrameError,
    GhostReason,
    MatchPosition,
    place_player,
    place_players,
    validate_point,
)
from app.logic.repository import load_match_positions, load_sofascore_ids

FPL_ID, SOFA_ID = 7, 700
GW1 = datetime(2026, 8, 15, 14)


def kickoff(gw: int, extra_days: int = 0) -> datetime:
    return GW1 + timedelta(days=7 * (gw - 1) + extra_days)


def row(gw, x=20.0, y=40.0, *, player=SOFA_ID, match=None, points=30, minutes=90, days=0):
    return MatchPosition(
        sofascore_player_id=player,
        match_id=match if match is not None else (gw or 0) * 100 + days,
        gw=gw,
        kickoff=kickoff(gw or 1, days),
        x=x,
        y=y,
        points_count=points,
        minutes=minutes,
    )


# --- Frame -------------------------------------------------------------------


def test_frame_bounds():
    assert CENTER_X == 50
    validate_point(0, 0)
    validate_point(100, 100)
    for x, y in [(-0.1, 50), (50, 100.1), (101, 0)]:
        with pytest.raises(FrameError):
            validate_point(x, y)


def test_match_position_outside_frame_rejected():
    with pytest.raises(FrameError):
        row(1, x=120)


# --- Most recent match played -------------------------------------------------


def test_played_in_target_gameweek():
    rows = [row(3, x=15, y=30), row(4, x=80, y=60), row(5, x=90, y=90)]
    p = place_player(FPL_ID, SOFA_ID, rows, 4)
    assert not p.is_ghost
    assert p.source_gw == 4
    assert p.from_gw is None
    assert [(m.x, m.y) for m in p.matches] == [(80, 60)]


def test_target_gameweek_keeps_every_match_of_a_double_gameweek():
    rows = [row(6, x=20, days=4), row(6, x=80, days=0), row(5)]
    p = place_player(FPL_ID, SOFA_ID, rows, 6)
    assert p.source_gw == 6
    assert [m.x for m in p.matches] == [80, 20]  # kickoff order


def test_falls_back_to_most_recent_earlier_match_with_label():
    rows = [row(2, x=10), row(4, x=40), row(3, x=30)]
    p = place_player(FPL_ID, SOFA_ID, rows, 6)
    assert not p.is_ghost
    assert p.source_gw == 4
    assert p.from_gw == 4
    assert [m.x for m in p.matches] == [40]


def test_fallback_picks_latest_kickoff_not_highest_gameweek():
    # A GW3 match rescheduled after the GW4 one: the later kickoff wins.
    rows = [row(4, x=40, days=0), row(3, x=30, days=10)]
    p = place_player(FPL_ID, SOFA_ID, rows, 6)
    assert p.from_gw == 3
    assert p.matches[0].x == 30


def test_later_and_unlinked_matches_are_ignored():
    rows = [row(2, x=20), row(5, x=50), row(None, x=99)]
    p = place_player(FPL_ID, SOFA_ID, rows, 3)
    assert p.from_gw == 2
    assert p.matches[0].x == 20


def test_unusable_match_falls_back(monkeypatch):
    rows = [row(4, x=40, points=2), row(3, x=30, points=20)]
    p = place_player(FPL_ID, SOFA_ID, rows, 4, min_points_count=3)
    assert p.from_gw == 3
    # Threshold comes from settings when not passed.
    monkeypatch.setenv("POSITION_MIN_POINTS_COUNT", "3")
    get_settings.cache_clear()
    try:
        assert place_player(FPL_ID, SOFA_ID, rows, 4).from_gw == 3
        monkeypatch.delenv("POSITION_MIN_POINTS_COUNT")
        get_settings.cache_clear()
        assert place_player(FPL_ID, SOFA_ID, rows, 4).from_gw is None  # default 1
    finally:
        get_settings.cache_clear()


def test_rows_of_other_players_ignored():
    p = place_player(FPL_ID, SOFA_ID, [row(4, player=999)], 4)
    assert p.ghost_reason is GhostReason.NO_MATCH


# --- Ghosts ------------------------------------------------------------------


def test_never_played_is_a_ghost():
    p = place_player(FPL_ID, SOFA_ID, [], 4)
    assert p.is_ghost
    assert p.ghost_reason is GhostReason.NO_MATCH
    assert p.source_gw is None and p.from_gw is None and p.matches == ()


def test_only_later_matches_is_a_ghost():
    p = place_player(FPL_ID, SOFA_ID, [row(5)], 4)
    assert p.ghost_reason is GhostReason.NO_MATCH


def test_missing_mapping_is_a_ghost():
    p = place_player(FPL_ID, None, [row(4)], 4)
    assert p.is_ghost
    assert p.ghost_reason is GhostReason.NO_MAPPING
    assert p.matches == ()


def test_place_players_mixes_cases():
    placements = place_players(
        [1, 2, 3, 4],
        {1: 100, 2: 200, 3: 300},
        {100: [row(4, player=100)], 200: [row(2, player=200)], 300: []},
        4,
    )
    assert placements[1].source_gw == 4 and placements[1].from_gw is None
    assert placements[2].from_gw == 2
    assert placements[3].ghost_reason is GhostReason.NO_MATCH
    assert placements[4].ghost_reason is GhostReason.NO_MAPPING


# --- Repository --------------------------------------------------------------


@pytest.fixture
def session(tmp_path):
    engine = make_read_write_engine(tmp_path / "fpl.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(FplClub(id=1, name="Arsenal", short_name="ARS"))
        s.add(FplClub(id=2, name="Spurs", short_name="TOT"))
        for fpl_id in (FPL_ID, 8):
            s.add(
                FplPlayer(
                    id=fpl_id, first_name="A", second_name=f"P{fpl_id}", web_name=f"P{fpl_id}",
                    club_id=1, role="DEF", price=50, status="a",
                )
            )
        s.add_all([SofascorePlayer(id=SOFA_ID, name="A P7"), SofascorePlayer(id=800, name="A P8")])
        s.add(
            PlayerIdMap(
                fpl_id=FPL_ID, sofascore_id=SOFA_ID, match_method="exact",
                match_confidence=1.0, matched_at=GW1,
            )
        )
        for gw in (1, 2, 3):
            s.add(Gameweek(id=gw, deadline=kickoff(gw) - timedelta(days=1)))
            s.add(Match(id=gw, gw=gw, home_club_id=1, away_club_id=2, kickoff=kickoff(gw), finished=True))
            s.add(
                PlayerMatchPosition(
                    match_id=gw, sofascore_player_id=SOFA_ID, avg_x=10.0 * gw, avg_y=40.0,
                    points_count=25, sub_on_minute=None, sub_off_minute=70 if gw == 2 else None,
                    kickoff=kickoff(gw), gw=gw,
                )
            )
        s.commit()
        yield s
    engine.dispose()


def test_load_sofascore_ids(session):
    assert load_sofascore_ids(session, [FPL_ID, 8, 999]) == {FPL_ID: SOFA_ID}


def test_load_match_positions_latest_first(session):
    rows = load_match_positions(session, [SOFA_ID, 800])
    assert rows[800] == []
    assert [r.gw for r in rows[SOFA_ID]] == [3, 2, 1]
    second = rows[SOFA_ID][1]
    assert (second.x, second.y, second.minutes, second.points_count) == (20.0, 40.0, 70, 25)
    assert load_match_positions(session, []) == {}


def test_load_match_positions_uses_player_kickoff_index(session):
    plans = []

    @event.listens_for(session.get_bind(), "before_cursor_execute")
    def explain(conn, cursor, statement, parameters, context, executemany):
        if "player_match_positions" in statement:
            plans.extend(cursor.connection.execute("EXPLAIN QUERY PLAN " + statement, parameters).fetchall())

    load_match_positions(session, [SOFA_ID])
    event.remove(session.get_bind(), "before_cursor_execute", explain)
    assert any("ix_player_match_positions_player_kickoff" in str(p) for p in plans)


def test_repository_to_logic_end_to_end(session):
    ids = load_sofascore_ids(session, [FPL_ID, 8])
    rows = load_match_positions(session, ids.values())
    placements = place_players([FPL_ID, 8], ids, rows, 5)
    assert placements[FPL_ID].from_gw == 3
    assert placements[FPL_ID].matches[0].x == 30.0
    assert placements[8].ghost_reason is GhostReason.NO_MAPPING
