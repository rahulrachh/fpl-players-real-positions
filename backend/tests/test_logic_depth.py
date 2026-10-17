import pytest

from app.logic.depth import DepthPools, percentile, rank_depth


def test_percentile():
    pool = [10.0, 20.0, 30.0, 40.0]
    assert percentile(pool, 5.0) == 0.0
    assert percentile(pool, 25.0) == 50.0
    assert percentile(pool, 50.0) == 100.0
    # A tie counts half.
    assert percentile(pool, 20.0) == 37.5
    assert percentile([], 20.0) is None


def test_pools_leave_out_goalkeepers():
    pools = DepthPools.from_rows(
        [("GK", 11.0), ("DEF", 40.0), ("FWD", 62.0), ("MID", 55.0), ("DEF", 35.0)]
    )
    assert pools.outfield == [35.0, 40.0, 55.0, 62.0]
    assert pools.by_role == {"DEF": [35.0, 40.0], "MID": [55.0], "FWD": [62.0]}


@pytest.fixture
def pools():
    # Defenders deep, forwards high: a "deep" forward is still above most players.
    return DepthPools.from_rows(
        [("DEF", y) for y in (35.0, 40.0, 45.0)]
        + [("MID", y) for y in (50.0, 55.0, 60.0)]
        + [("FWD", y) for y in (55.0, 62.0, 70.0)]
    )


def test_rank_against_everyone_and_own_role(pools):
    # A forward at 56: above 6 of 9 players, but only 1 of 3 forwards.
    all_pct, role_pct = rank_depth(pools, "FWD", 56.0)
    assert all_pct == pytest.approx(100 * 6 / 9, abs=0.1)
    assert role_pct == pytest.approx(100 / 3, abs=0.1)
    # An attacking defender at 50 tops the defenders but is mid-table overall.
    all_pct, role_pct = rank_depth(pools, "DEF", 50.0)
    assert role_pct == 100.0
    assert all_pct == pytest.approx(100 * 3.5 / 9, abs=0.1)


def test_goalkeepers_and_ghosts_are_not_ranked(pools):
    assert rank_depth(pools, "GK", 11.0) == (None, None)
    assert rank_depth(pools, "MID", None) == (None, None)
