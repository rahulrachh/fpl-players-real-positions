"""Sofascore adapter against recorded responses (`tests/fixtures/sofascore/`,
trimmed real data from 2026-10-16: 2026/27 rounds 1-6 played). No network."""

import json
import logging
from datetime import datetime
from pathlib import Path

import pytest

from app.positions import get_positions_source
from app.positions.base import (
    PositionsSource,
    SourceBlockedError,
    SourceNotFoundError,
    SourceSchemaError,
    SourceUnavailableError,
)
from app.positions.sofascore import SofascoreSource

FIXTURES = Path(__file__).parent / "fixtures" / "sofascore"
BASE_URL = "https://sofa.test/api/v1"
SEASON = 96668  # Premier League 2026/27
MCI = 17

# Liverpool 0-3 Man City (Man City away) and Man City 2-1 Bournemouth (home).
LIV_MCI = 16363878
MCI_BOU = 16363243

ROUTES = {
    "/unique-tournament/17/seasons": "seasons.json",
    f"/unique-tournament/17/season/{SEASON}/events/round/6": "round-6.json",
    "/team/17/events/last/0": "team-17-events-last-0.json",
    "/team/17/players": "team-17-players.json",
    f"/event/{LIV_MCI}/average-positions": f"event-{LIV_MCI}-average-positions.json",
    f"/event/{MCI_BOU}/average-positions": f"event-{MCI_BOU}-average-positions.json",
}


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code: int, data=None, headers=None):
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}

    def json(self):
        if self._data is None:
            raise ValueError("not JSON")
        return self._data


class FakeSession:
    """curl_cffi-style session serving the recorded responses.

    `responses` maps a path to a list of responses/exceptions served in turn
    (the last one repeats); other paths come from ROUTES, else 404."""

    def __init__(self):
        self.paths: list[str] = []
        self.responses: dict[str, list] = {}
        self.data: dict[str, object] = {}

    def get(self, url: str, timeout: float):
        path = url.removeprefix(BASE_URL)
        self.paths.append(path)
        if path in self.responses:
            queue = self.responses[path]
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(item, Exception):
                raise item
            return item
        if path in self.data:
            return FakeResponse(200, self.data[path])
        if path in ROUTES:
            return FakeResponse(200, load(ROUTES[path]))
        return FakeResponse(404, {"error": {"code": 404, "message": "Not Found"}})


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def fake_time():
    return FakeTime()


@pytest.fixture
def source(session, fake_time):
    return SofascoreSource(
        BASE_URL,
        request_delay_seconds=2.5,
        max_retries=3,
        backoff_seconds=5.0,
        session=session,
        sleep=fake_time.sleep,
        clock=fake_time.clock,
    )


def by_name(positions):
    return {p.player.name: p for p in positions}


# --- interface ---------------------------------------------------------------


def test_factory_returns_a_positions_source():
    assert isinstance(get_positions_source(), PositionsSource)


def test_current_season_is_the_newest_listed(source, session):
    assert source.current_season_id() == SEASON
    assert source.current_season_id() == SEASON
    assert session.paths.count("/unique-tournament/17/seasons") == 1


# --- matches -----------------------------------------------------------------


def test_list_round_matches(source):
    matches = source.list_round_matches(6)
    assert len(matches) == 10
    assert [m.kickoff for m in matches] == sorted(m.kickoff for m in matches)
    liv_mci = next(m for m in matches if m.id == LIV_MCI)
    assert (liv_mci.home_team_id, liv_mci.away_team_id) == (44, MCI)
    assert (liv_mci.home_team_name, liv_mci.away_team_name) == ("Liverpool FC", "Manchester City")
    assert (liv_mci.home_score, liv_mci.away_score) == (0, 3)
    assert liv_mci.round == 6 and liv_mci.season_id == SEASON
    assert liv_mci.finished
    # Naive UTC.
    assert liv_mci.kickoff.tzinfo is None
    assert liv_mci.kickoff == datetime(2026, 10, 11, 15, 30)


def test_list_team_matches_last_n_keeps_recent_finished_league_matches(source, session):
    matches = source.list_team_matches(MCI, last_n=3)
    # Last season's league matches, cups and Champions League are dropped.
    assert [m.id for m in matches] == [16363645, 16363867, LIV_MCI]
    assert all(m.season_id == SEASON and m.finished for m in matches)
    # Page 0 has enough: no further pages, no season-start lookup.
    assert session.paths == ["/unique-tournament/17/seasons", "/team/17/events/last/0"]


def test_list_team_matches_whole_season_stops_at_the_season_start(source, session):
    page_0 = load("team-17-events-last-0.json")
    round_1 = next(ev for ev in page_0["events"] if ev["id"] == MCI_BOU)
    session.data[f"/unique-tournament/17/season/{SEASON}/events/round/1"] = {
        "events": [round_1],
        "hasNextPage": False,
    }
    matches = source.list_team_matches(MCI)
    assert [m.id for m in matches] == [
        MCI_BOU, 16363252, 16363263, 16363645, 16363867, LIV_MCI
    ]
    # Page 0 already reaches last season, so page 1 is not fetched.
    assert "/team/17/events/last/1" not in session.paths


def test_list_team_matches_walks_back_through_pages(source, session):
    events = load("team-17-events-last-0.json")["events"]
    round_1 = next(ev for ev in events if ev["id"] == MCI_BOU)
    start = events.index(round_1)
    session.data[f"/unique-tournament/17/season/{SEASON}/events/round/1"] = {
        "events": [round_1]
    }
    # Newest page first; page 0 starts after round 1.
    session.data["/team/17/events/last/0"] = {"events": events[start + 1 :], "hasNextPage": True}
    session.data["/team/17/events/last/1"] = {"events": events[: start + 1], "hasNextPage": True}
    matches = source.list_team_matches(MCI)
    assert len(matches) == 6 and matches[0].id == MCI_BOU
    assert "/team/17/events/last/1" in session.paths
    assert "/team/17/events/last/2" not in session.paths


# --- positions: frame and sanity checks --------------------------------------


@pytest.mark.parametrize("match_id", [LIV_MCI, MCI_BOU])
def test_every_position_is_in_the_frame(source, match_id):
    positions = source.match_positions(match_id)
    assert positions
    for p in positions:
        assert 0 <= p.x <= 100 and 0 <= p.y <= 100


def test_away_match_left_back_left_striker_top(source):
    """Man City away at Liverpool."""
    positions = by_name(source.match_positions(LIV_MCI))
    oreilly = positions["Nico O'Reilly"]  # MCI left-back, away side
    kerkez = positions["Miloš Kerkez"]  # LIV left-back, home side
    nunes = positions["Matheus Nunes"]  # MCI right-back
    haaland = positions["Erling Haaland"]  # MCI striker
    keeper = positions["Gianluigi Donnarumma"]
    assert not oreilly.is_home and kerkez.is_home
    assert oreilly.x < 25 and kerkez.x < 25
    assert nunes.x > 75
    # Haaland drops deep away from home (y 53.6), but is still ahead of every
    # starting defender; Gvardiol (on at 66') pushed up to 54.6 chasing the game.
    assert haaland.y > 50 and haaland.y > max(
        p.y for p in positions.values()
        if not p.is_home and not p.is_sub and p.player.position == "D"
    )
    assert keeper.y < 15
    # Sofascore averageX 40.33 / averageY 83.35 → x 16.65, y 40.33.
    assert oreilly.x == pytest.approx(100 - 83.348076923077)
    assert oreilly.y == pytest.approx(40.328846153846)


def test_home_match_left_back_left_striker_top(source):
    """Man City at home to Bournemouth."""
    positions = by_name(source.match_positions(MCI_BOU))
    haaland = positions["Erling Haaland"]  # MCI striker, home side
    truffert = positions["Adrien Truffert"]  # BOU left-back, away side
    gvardiol = positions["Joško Gvardiol"]  # MCI left-sided defender
    assert haaland.is_home and not truffert.is_home
    assert haaland.y > 65
    # Level with Semenyo (70.7) at the top, well ahead of every defender.
    assert haaland.y >= max(p.y for p in positions.values() if p.is_home) - 1
    assert haaland.y > max(
        p.y for p in positions.values() if p.is_home and p.player.position == "D"
    ) + 5
    assert truffert.x < 25 and gvardiol.x < 25
    assert positions["Đorđe Petrović"].y < 15


# --- positions: subs and minutes ---------------------------------------------


def test_subs_and_minutes(source):
    positions = by_name(source.match_positions(LIV_MCI))
    assert len(positions) == 31  # 22 starters + 9 subs
    doku = positions["Jérémy Doku"]  # on at 56'
    ndiaye = positions["Iliman Ndiaye"]  # off at 56'
    haaland = positions["Erling Haaland"]  # off at 80'
    anderson = positions["Elliot Anderson"]  # full match
    assert (doku.is_sub, doku.sub_on_minute, doku.sub_off_minute, doku.minutes) == (True, 56, None, 34)
    assert (ndiaye.is_sub, ndiaye.sub_off_minute, ndiaye.minutes) == (False, 56, 56)
    assert (haaland.is_sub, haaland.sub_off_minute, haaland.minutes) == (False, 80, 80)
    assert (anderson.is_sub, anderson.sub_off_minute, anderson.minutes) == (False, None, 90)
    assert sum(p.is_sub for p in positions.values()) == 9
    assert positions["Federico Chiesa"].points_count == 1
    assert haaland.player.id == 839956 and haaland.player.position == "F"


def test_a_side_that_attacks_the_wrong_way_is_mirrored(source, session, caplog):
    data = load(f"event-{LIV_MCI}-average-positions.json")
    for row in data["away"]:
        row["averageX"] = 100 - row["averageX"]
        row["averageY"] = 100 - row["averageY"]
    session.data[f"/event/{LIV_MCI}/average-positions"] = data
    with caplog.at_level(logging.WARNING):
        positions = by_name(source.match_positions(LIV_MCI))
    assert "away side attacks the wrong way" in caplog.text
    assert positions["Nico O'Reilly"].x == pytest.approx(100 - 83.348076923077)
    assert positions["Gianluigi Donnarumma"].y < 15
    # The home side was already right and is untouched.
    assert positions["Miloš Kerkez"].x == pytest.approx(100 - 83.061904761905)


def test_match_without_positions_is_not_found(source):
    with pytest.raises(SourceNotFoundError):
        source.match_positions(1)


def test_schema_change_raises_schema_error(source, session):
    session.data["/event/5/average-positions"] = {"home": [{"player": {"id": 1}}], "away": []}
    with pytest.raises(SourceSchemaError):
        source.match_positions(5)


# --- squads ------------------------------------------------------------------


def test_list_team_players(source):
    players = source.list_team_players(MCI)
    assert len(players) == 25
    haaland = next(p for p in players if p.id == 839956)
    assert (haaland.name, haaland.short_name, haaland.slug, haaland.position, haaland.team_id) == (
        "Erling Haaland",
        "E. Haaland",
        "erling-haaland",
        "F",
        MCI,
    )


# --- polite fetching ---------------------------------------------------------


def test_requests_are_spaced_by_the_min_delay(source, fake_time):
    source.list_round_matches(6)  # seasons + round: 2 requests
    source.match_positions(LIV_MCI)
    assert source.request_count == 3
    assert fake_time.sleeps == [2.5, 2.5]


def test_no_wait_when_enough_time_has_passed(source, fake_time):
    source.current_season_id()
    fake_time.now += 10
    source.match_positions(LIV_MCI)
    assert fake_time.sleeps == []


def test_403_is_blocked_without_retry(source, session):
    session.responses["/team/17/players"] = [FakeResponse(403, {"error": {"code": 403}})]
    with pytest.raises(SourceBlockedError):
        source.list_team_players(MCI)
    assert session.paths.count("/team/17/players") == 1


def test_5xx_and_network_errors_retry_with_backoff(source, session, fake_time):
    session.responses["/team/17/players"] = [
        FakeResponse(503),
        ConnectionError("reset"),
        FakeResponse(200, load("team-17-players.json")),
    ]
    assert len(source.list_team_players(MCI)) == 25
    assert session.paths.count("/team/17/players") == 3
    assert fake_time.sleeps == [5.0, 10.0]


def test_persistent_5xx_is_unavailable(source, session, fake_time):
    session.responses["/team/17/players"] = [FakeResponse(500)]
    with pytest.raises(SourceUnavailableError):
        source.list_team_players(MCI)
    assert session.paths.count("/team/17/players") == 4  # 1 + 3 retries
    assert fake_time.sleeps == [5.0, 10.0, 20.0]


def test_persistent_429_is_blocked_and_honours_retry_after(source, session, fake_time):
    session.responses["/team/17/players"] = [FakeResponse(429, headers={"Retry-After": "30"})]
    with pytest.raises(SourceBlockedError):
        source.list_team_players(MCI)
    assert fake_time.sleeps == [30.0, 30.0, 30.0]


def test_non_json_response_is_schema_error(source, session):
    session.responses["/team/17/players"] = [FakeResponse(200, None)]
    with pytest.raises(SourceSchemaError):
        source.list_team_players(MCI)
