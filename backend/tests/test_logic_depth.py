import pytest

from app.logic.depth import outfield_pool, percentile, rank_depth


def test_percentile():
    pool = [10.0, 20.0, 30.0, 40.0]
    assert percentile(pool, 5.0) == 0.0
    assert percentile(pool, 25.0) == 50.0
    assert percentile(pool, 50.0) == 100.0
    # A tie counts half.
    assert percentile(pool, 20.0) == 37.5
    assert percentile([], 20.0) is None


def test_pool_leaves_out_goalkeepers():
    rows = [("GK", 11.0), ("DEF", 40.0), ("FWD", 62.0), ("MID", 55.0), ("DEF", 35.0)]
    assert outfield_pool(rows) == [35.0, 40.0, 55.0, 62.0]


def test_rank_against_every_outfield_player():
    pool = outfield_pool(
        [("DEF", y) for y in (35.0, 40.0, 45.0)]
        + [("MID", y) for y in (50.0, 55.0, 60.0)]
        + [("FWD", y) for y in (55.0, 62.0, 70.0)]
    )
    # A forward at 56 is above 6 of the 9 players, whatever their role.
    assert rank_depth(pool, "FWD", 56.0) == pytest.approx(100 * 6 / 9, abs=0.1)
    # An attacking defender at 50: three below, one tie.
    assert rank_depth(pool, "DEF", 50.0) == pytest.approx(100 * 3.5 / 9, abs=0.1)


def test_goalkeepers_and_ghosts_are_not_ranked():
    pool = [40.0, 50.0]
    assert rank_depth(pool, "GK", 11.0) is None
    assert rank_depth(pool, "MID", None) is None
