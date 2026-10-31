"""`GET /api/gameweek/{gw}/fixtures` (`app/fpl/fixtures.py`) against the
recorded bootstrap and a made-up GW6: a finished match, a double-gameweek
Arsenal playing twice with a tie for 3rd in one match, and an unstarted
match. No network."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.fpl.client import FplClient
from app.fpl.fixtures import FixturesService, get_fixtures_service, top_players
from app.fpl.team import GameweekOutOfRange
from app.main import app
from tests.test_fpl_team import BASE_URL, FakeFpl

ARS, AVL, BOU = 1, 2, 3


def fixture(id, home, away, kickoff, state, score=(None, None)):
    started = state != "not_started"
    finished = state == "finished"
    return {
        "id": id,
        "event": 6,
        "team_h": home,
        "team_a": away,
        "kickoff_time": kickoff,
        "started": started,
        "finished": finished,
        "finished_provisional": finished,
        "team_h_score": score[0],
        "team_a_score": score[1],
    }


FIXTURES = [
    fixture(101, ARS, AVL, "2026-10-10T14:00:00Z", "finished", (2, 1)),
    fixture(103, AVL, BOU, "2026-10-11T16:30:00Z", "not_started"),
    fixture(102, BOU, ARS, "2026-10-10T11:30:00Z", "live", (0, 1)),
    # Another gameweek's fixture (the fake ignores ?event=): left out.
    {**fixture(999, ARS, BOU, "2026-10-18T14:00:00Z", "not_started"), "event": 7},
]


def explain(fixture_id, minutes, points):
    """One fixture's breakdown: minutes points plus the rest as goals."""
    minutes_pts = 2 if minutes >= 60 else 1 if minutes > 0 else 0
    stats = [{"identifier": "minutes", "value": minutes, "points": minutes_pts}]
    if points != minutes_pts:
        stats.append({"identifier": "goals_scored", "value": 1, "points": points - minutes_pts})
    return {"fixture": fixture_id, "stats": stats}


# FPL ID → [(fixture, minutes, points)]
PLAYED = {
    1: [(101, 90, 6)],  # Raya
    4: [(101, 90, 8), (102, 90, 7)],  # Gabriel, double gameweek
    7: [(101, 70, 2)],
    25: [(101, 90, 8)],  # Gyökeres
    29: [(101, 90, 3)],
    30: [(101, 90, 3)],
    35: [(101, 0, 0)],  # did not play
    55: [(101, 90, 5)],
    9: [(102, 90, 6)],  # Hincapie, tied 3rd
    6: [(102, 90, 2)],
    57: [(102, 90, 2)],
    60: [(102, 90, 6)],  # Hill, tied 3rd
    67: [(102, 45, 1)],
    79: [(102, 90, 9)],  # Evanilson
}


def live():
    return {
        "elements": [
            {
                "id": pid,
                "stats": {"minutes": sum(m for _, m, _ in rows), "total_points": sum(p for *_, p in rows)},
                "explain": [explain(f, m, p) for f, m, p in rows],
            }
            for pid, rows in PLAYED.items()
        ]
    }


@pytest.fixture
def fake():
    fake = FakeFpl()
    fake.routes["/api/fixtures/"] = FIXTURES
    fake.routes["/api/event/6/live/"] = live()
    return fake


def make_service(fake, short_ttl=60.0) -> FixturesService:
    client = FplClient(BASE_URL, short_ttl, transport=httpx.MockTransport(fake))
    return FixturesService(client, finished_ttl_seconds=86400.0, short_ttl_seconds=short_ttl)


@pytest.fixture
def service(fake):
    return make_service(fake)


def top(summary):
    return [(p.web_name, p.points) for p in summary.top_players]


def test_fixtures_in_kickoff_order_with_scores_and_states(service):
    result = service.gameweek_fixtures(6)

    assert (result.gw, result.data_checked) == (6, True)
    rows = [
        (f.id, f.home_club.short_name, f.away_club.short_name, f.home_score, f.away_score, f.state)
        for f in result.fixtures
    ]
    assert rows == [
        (102, "BOU", "ARS", 0, 1, "live"),
        (101, "ARS", "AVL", 2, 1, "finished"),
        (103, "AVL", "BOU", None, None, "not_started"),
    ]


def test_finished_match_top_three(service):
    match = next(f for f in service.gameweek_fixtures(6).fixtures if f.id == 101)

    assert top(match) == [("Gabriel", 8), ("Gyökeres", 8), ("Raya", 6)]
    gabriel = match.top_players[0]
    assert (gabriel.id, gabriel.club, gabriel.role) == (4, "ARS", "DEF")


def test_tie_for_third_includes_everyone_tied(service):
    match = next(f for f in service.gameweek_fixtures(6).fixtures if f.id == 102)

    assert top(match) == [("Evanilson", 9), ("Gabriel", 7), ("Hincapie", 6), ("Hill", 6)]


def test_double_gameweek_player_has_his_points_per_match(service):
    fixtures = service.gameweek_fixtures(6).fixtures
    gabriel = {
        f.id: p.points for f in fixtures for p in f.top_players if p.id == 4
    }

    assert gabriel == {101: 8, 102: 7}


def test_unstarted_match_has_no_top_players(service):
    match = next(f for f in service.gameweek_fixtures(6).fixtures if f.id == 103)

    assert (match.state, match.top_players, match.kickoff.isoformat()) == (
        "not_started",
        [],
        "2026-10-11T16:30:00+00:00",
    )


def test_top_players_ignores_who_did_not_play_and_keeps_short_lists():
    assert top_players({1: (0, 0), 2: (3, 90)}) == [(2, 3)]
    assert top_players({1: (2, 90), 2: (2, 90), 3: (2, 90), 4: (2, 90)}) == [
        (1, 2),
        (2, 2),
        (3, 2),
        (4, 2),
    ]
    # A tie for 1st beyond 3 places still stops at the 3rd place's points.
    assert top_players({1: (5, 90), 2: (5, 90), 3: (4, 90), 4: (3, 90)}) == [
        (1, 5),
        (2, 5),
        (3, 4),
    ]


def test_unstarted_gameweek_skips_live(fake):
    fake.routes["/api/fixtures/"] = [
        {**f, "started": False, "finished": False, "finished_provisional": False}
        for f in FIXTURES
    ]
    result = make_service(fake).gameweek_fixtures(6)

    assert all(f.top_players == [] for f in result.fixtures)
    assert "/api/event/6/live/" not in fake.requests


def test_cached_per_gameweek(fake, service):
    service.gameweek_fixtures(6)
    calls = len(fake.requests)
    service.gameweek_fixtures(6)

    assert len(fake.requests) == calls


def test_checked_gameweek_cached_long_others_short(fake):
    service = make_service(fake, short_ttl=0.0)
    service.gameweek_fixtures(6)  # data_checked
    calls = len(fake.requests)
    service.gameweek_fixtures(6)
    assert len(fake.requests) == calls

    service.gameweek_fixtures(7)  # not checked: short TTL (0 here)
    calls = len(fake.requests)
    service.gameweek_fixtures(7)
    assert len(fake.requests) > calls


def test_gameweek_out_of_range(service):
    with pytest.raises(GameweekOutOfRange):
        service.gameweek_fixtures(39)


@pytest.fixture
def api(service):
    app.dependency_overrides[get_fixtures_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoint(api):
    response = api.get("/api/gameweek/6/fixtures")

    assert response.status_code == 200
    body = response.json()
    assert [f["id"] for f in body["fixtures"]] == [102, 101, 103]
    first = body["fixtures"][1]
    assert first["home_club"] == {"id": 1, "name": "Arsenal", "short_name": "ARS"}
    assert first["top_players"][0] == {
        "id": 4,
        "web_name": "Gabriel",
        "club": "ARS",
        "role": "DEF",
        "points": 8,
    }


def test_endpoint_errors(api, fake):
    assert api.get("/api/gameweek/39/fixtures").json()["code"] == "gameweek_out_of_range"
    assert api.get("/api/gameweek/0/fixtures").status_code == 422

    fake.routes["/api/fixtures/"] = httpx.Response(503, text="The game is being updated.")
    response = api.get("/api/gameweek/6/fixtures")
    assert (response.status_code, response.json()["code"]) == (503, "fpl_unavailable")
