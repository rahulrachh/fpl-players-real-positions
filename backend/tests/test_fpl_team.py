"""Team loading service and `GET /api/team/{id}/gameweek/{gw}` against the
recorded FPL responses (`tests/fixtures/fpl/`: GW6 finished, GW7 deadline
2026-10-17 10:00 UTC not passed). No network."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.engine import make_read_write_engine
from app.db.models import FplPlayer
from app.db.session import get_ro_session
from app.fpl.client import FplClient, FplSchemaError, FplUnavailable
from app.fpl.reference import apply_bootstrap
from app.fpl.schemas import BootstrapStatic
from app.fpl.team import (
    GameweekBeforeTeamStarted,
    GameweekNotStarted,
    GameweekOutOfRange,
    GameweekStatus,
    TeamNotFound,
    TeamService,
    get_team_service,
)
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "fpl"
BASE_URL = "https://fpl.test/api"
# Between the GW6 and GW7 deadlines, as when the fixtures were recorded.
NOW = datetime(2026, 10, 17, 3, 0, tzinfo=UTC)


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeFpl:
    """httpx transport: path → JSON body (or an httpx.Response); counts requests."""

    def __init__(self):
        self.routes = {
            "/api/bootstrap-static/": load("bootstrap-static.json"),
            "/api/entry/1234/": load("entry.json"),
            "/api/entry/1234/event/6/picks/": load("picks-gw6.json"),
            "/api/entry/5678/": load("entry-not-started.json"),
        }
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        body = self.routes.get(request.url.path)
        if body is None:
            return httpx.Response(404, json={"detail": "Not found."})
        if isinstance(body, httpx.Response):
            return body
        return httpx.Response(200, json=body)


@pytest.fixture
def fake():
    return FakeFpl()


@pytest.fixture
def session(tmp_path):
    """Reference data from the recorded bootstrap, plus placeholder rows for
    the picked players it does not include. Player 1 (Raya) is left out so
    the service has to fall back to the live bootstrap for him."""
    engine = make_read_write_engine(tmp_path / "fpl.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        apply_bootstrap(s, BootstrapStatic.model_validate(load("bootstrap-static.json")))
        for pick in load("picks-gw6.json")["picks"]:
            if s.get(FplPlayer, pick["element"]) is None:
                s.add(
                    FplPlayer(
                        id=pick["element"],
                        first_name="First",
                        second_name=f"Player{pick['element']}",
                        web_name=f"P{pick['element']}",
                        club_id=2,
                        role="MID",
                        price=50,
                        status="a",
                    )
                )
        s.execute(delete(FplPlayer).where(FplPlayer.id == 1))
        s.commit()
        yield s
    engine.dispose()


def make_service(fake, short_ttl=60.0, finished_ttl=86400.0, now=NOW) -> TeamService:
    client = FplClient(BASE_URL, short_ttl, transport=httpx.MockTransport(fake))
    return TeamService(client, finished_ttl, short_ttl, now=lambda: now)


@pytest.fixture
def service(fake):
    return make_service(fake)


def test_loads_team_gameweek(service, session):
    team = service.load_team_gameweek(1234, 6, session)

    assert (team.team_id, team.team_name, team.manager_name) == (1234, "Test FC", "Test Manager")
    assert (team.gameweek, team.status, team.data_checked) == (6, GameweekStatus.FINISHED, True)
    assert team.deadline == datetime(2026, 10, 10, 10, tzinfo=UTC)
    assert team.chip is None
    assert (team.bank, team.squad_value) == (1, 1017)
    assert (team.points, team.transfers_cost) == (77, 0)

    assert [p.position for p in team.picks] == list(range(1, 16))
    assert [p.starter for p in team.picks] == [True] * 11 + [False] * 4
    assert [p.role for p in team.picks[:5]] == ["GK", "DEF", "DEF", "DEF", "DEF"]
    captain = next(p for p in team.picks if p.is_captain)
    assert team.captain_id == captain.player.id == team.effective_captain_id
    assert captain.multiplier == 2
    assert next(p for p in team.picks if p.is_vice_captain).player.id == team.vice_captain_id


def test_joins_player_and_club_details(service, session):
    picks = {p.player.id: p.player for p in service.load_team_gameweek(1234, 6, session).picks}
    # From the database.
    assert picks[4].web_name == "Gabriel" and picks[4].club.short_name == "ARS"
    assert picks[115].web_name == "P115" and picks[115].club.short_name == "AVL"
    # Not in the database: from the live bootstrap.
    assert (picks[1].web_name, picks[1].second_name, picks[1].club.name) == (
        "Raya",
        "Raya Martín",
        "Arsenal",
    )


def test_player_missing_everywhere_is_schema_error(fake, service, session):
    session.execute(delete(FplPlayer).where(FplPlayer.id == 115))
    with pytest.raises(FplSchemaError):
        service.load_team_gameweek(1234, 6, session)


def test_auto_subs(service, session):
    # Recorded GW6: 304 came off the bench for 368. FPL already shows the
    # post-sub lineup: 304 in the XI, 368 on the bench.
    team = service.load_team_gameweek(1234, 6, session)
    by_id = {p.player.id: p for p in team.picks}
    assert [(s.player_in, s.player_out) for s in team.automatic_subs] == [(304, 368)]

    sub_in, sub_out = by_id[304], by_id[368]
    assert (sub_in.auto_sub, sub_in.starter, sub_in.picked_starter) == ("in", True, False)
    assert (sub_out.auto_sub, sub_out.starter, sub_out.picked_starter) == ("out", False, True)
    assert sum(p.starter for p in team.picks) == sum(p.picked_starter for p in team.picks) == 11
    assert all(p.auto_sub is None for p in team.picks if p.player.id not in (304, 368))


def test_captain_who_did_not_play(fake, service, session):
    # As FPL shows it (seen on real teams): the captain is subbed to the bench
    # with multiplier 0 and keeps is_captain; the vice gets multiplier 2.
    picks = load("picks-gw6.json")
    by_pos = {p["position"]: p for p in picks["picks"]}
    captain = next(p for p in picks["picks"] if p["is_captain"])
    vice = next(p for p in picks["picks"] if p["is_vice_captain"])
    bench = by_pos[14]
    captain["position"], bench["position"] = bench["position"], captain["position"]
    captain["multiplier"], bench["multiplier"], vice["multiplier"] = 0, 1, 2
    picks["automatic_subs"].append(
        {
            "entry": 1234,
            "element_in": bench["element"],
            "element_out": captain["element"],
            "event": 6,
        }
    )
    fake.routes["/api/entry/1234/event/6/picks/"] = picks

    team = service.load_team_gameweek(1234, 6, session)
    assert team.captain_id == captain["element"]
    assert team.effective_captain_id == vice["element"]
    cap = next(p for p in team.picks if p.is_captain)
    assert (cap.starter, cap.picked_starter, cap.auto_sub) == (False, True, "out")
    assert cap.multiplier == 0


def test_chip_and_bench_boost_multipliers(fake, service, session):
    picks = load("picks-gw6.json")
    picks["active_chip"] = "bboost"
    for p in picks["picks"]:
        p["multiplier"] = max(p["multiplier"], 1)
    fake.routes["/api/entry/1234/event/6/picks/"] = picks
    team = service.load_team_gameweek(1234, 6, session)
    assert team.chip == "bboost"
    assert all(p.multiplier == 1 for p in team.picks if not p.starter)


def test_repeat_request_makes_no_fpl_call(fake, service, session):
    first = service.load_team_gameweek(1234, 6, session)
    calls = len(fake.requests)
    assert calls == 3  # bootstrap, entry, picks
    assert service.load_team_gameweek(1234, 6, session) is first
    assert len(fake.requests) == calls


def test_finished_gameweek_outlives_short_ttl(fake, session):
    # Short TTL 0: nothing in the FPL client cache survives, but a gameweek
    # whose points FPL has checked is cached for the long TTL.
    service = make_service(fake, short_ttl=0)
    service.load_team_gameweek(1234, 6, session)
    calls = len(fake.requests)
    service.load_team_gameweek(1234, 6, session)
    assert len(fake.requests) == calls


def test_current_gameweek_uses_short_ttl(fake, session):
    def in_progress(events):
        gw6 = next(e for e in events if e["id"] == 6)
        gw6["finished"] = gw6["data_checked"] = False

    in_progress(fake.routes["/api/bootstrap-static/"]["events"])
    service = make_service(fake, short_ttl=0)
    team = service.load_team_gameweek(1234, 6, session)
    assert (team.status, team.data_checked) == (GameweekStatus.IN_PROGRESS, False)
    calls = len(fake.requests)
    service.load_team_gameweek(1234, 6, session)
    assert len(fake.requests) == 2 * calls


def test_upcoming_gameweek_is_not_started(fake, service, session):
    with pytest.raises(GameweekNotStarted):
        service.load_team_gameweek(1234, 7, session)
    # Decided from the deadline alone: no team call.
    assert fake.requests == ["/api/bootstrap-static/"]


def test_deadline_passed_but_no_picks_yet(fake, session):
    # Just after the GW7 deadline, before FPL serves the picks.
    service = make_service(fake, now=datetime(2026, 10, 17, 10, 1, tzinfo=UTC))
    with pytest.raises(GameweekNotStarted):
        service.load_team_gameweek(1234, 7, session)


def test_unknown_team(fake, service, session):
    with pytest.raises(TeamNotFound):
        service.load_team_gameweek(999999999, 6, session)
    with pytest.raises(TeamNotFound):
        service.load_team_gameweek(0, 6, session)


def test_gameweek_before_team_started(fake, service, session):
    # Team 5678 starts in GW7.
    with pytest.raises(GameweekBeforeTeamStarted):
        service.load_team_gameweek(5678, 6, session)


@pytest.mark.parametrize("gw", [0, 9, 39])
def test_gameweek_out_of_range(service, session, gw):
    # The recorded bootstrap has 8 gameweeks.
    with pytest.raises(GameweekOutOfRange):
        service.load_team_gameweek(1234, gw, session)


def test_fpl_unavailable(fake, service, session):
    fake.routes["/api/bootstrap-static/"] = httpx.Response(503, text="The game is being updated.")
    with pytest.raises(FplUnavailable):
        service.load_team_gameweek(1234, 6, session)


def test_errors_are_not_cached(fake, service, session):
    fake.routes["/api/entry/1234/event/6/picks/"] = httpx.Response(503, text="updating")
    with pytest.raises(FplUnavailable):
        service.load_team_gameweek(1234, 6, session)
    fake.routes["/api/entry/1234/event/6/picks/"] = load("picks-gw6.json")
    assert service.load_team_gameweek(1234, 6, session).team_id == 1234


def test_latest_and_last_finished_gameweek(fake):
    assert make_service(fake).latest_gameweek() == 6
    assert make_service(fake).last_finished_gameweek() == 6
    after_deadline = make_service(fake, now=datetime(2026, 10, 17, 10, tzinfo=UTC))
    assert after_deadline.latest_gameweek() == 7
    assert after_deadline.last_finished_gameweek() == 6
    before_season = make_service(fake, now=datetime(2026, 8, 1, tzinfo=UTC))
    assert before_season.latest_gameweek() is None


# --- endpoint ------------------------------------------------------------------


@pytest.fixture
def api(service, session):
    app.dependency_overrides[get_team_service] = lambda: service
    app.dependency_overrides[get_ro_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoint_returns_team(api):
    response = api.get("/api/team/1234/gameweek/6")
    assert response.status_code == 200
    body = response.json()
    assert (body["team_name"], body["gameweek"], body["status"]) == ("Test FC", 6, "finished")
    assert len(body["picks"]) == 15
    assert body["picks"][0]["player"]["club"]["short_name"] == "ARS"
    assert body["automatic_subs"] == [{"player_in": 304, "player_out": 368}]


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/api/team/999999999/gameweek/6", "team_not_found"),
        ("/api/team/5678/gameweek/6", "gameweek_before_team_started"),
        ("/api/team/1234/gameweek/7", "gameweek_not_started"),
        ("/api/team/1234/gameweek/39", "gameweek_out_of_range"),
    ],
)
def test_endpoint_errors(api, path, code):
    response = api.get(path)
    assert response.status_code == 404
    assert response.json()["code"] == code


def test_endpoint_fpl_unavailable(api, fake):
    fake.routes["/api/bootstrap-static/"] = httpx.Response(503, text="The game is being updated.")
    response = api.get("/api/team/1234/gameweek/6")
    assert response.status_code == 503
    assert response.json()["code"] == "fpl_unavailable"


@pytest.mark.parametrize(
    "path", ["/api/team/abc/gameweek/6", "/api/team/0/gameweek/6", "/api/team/1/gameweek/0"]
)
def test_endpoint_rejects_bad_ids_without_calling_fpl(api, fake, path):
    assert api.get(path).status_code == 422
    assert fake.requests == []


def test_endpoint_latest_gameweeks(api):
    assert api.get("/api/gameweeks/latest").json() == {"latest": 6, "last_finished": 6}
