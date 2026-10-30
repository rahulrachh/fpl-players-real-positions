"""`GET /api/team/{id}/plot/{gw}` and `/plot/latest` (`app/logic/plot.py`)
against the recorded FPL responses (see `test_fpl_team.py`) and a small
positions database. No network."""

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.models import (
    Gameweek,
    Match,
    PlayerIdMap,
    PlayerMatchPosition,
    SofascorePlayer,
    SyncRun,
)
from app.db.session import get_ro_session
from app.fpl.team import get_team_service
from app.logic.plot import neighbour_gameweeks
from app.main import app
from tests.test_fpl_team import FakeFpl, load, make_service, session  # noqa: F401

# Recorded GW6: 304 came off the bench for 368; player 1 is not in the
# database, so he has no mapping.
PICKS = [p["element"] for p in load("picks-gw6.json")["picks"]]
XI = PICKS[:11]
SYNCED_AT = datetime(2026, 10, 12, 8, 0)


def sofa(fpl_id: int) -> int:
    return 10_000 + fpl_id


@pytest.fixture
def db(session):  # noqa: F811
    """GW5 and GW6 matches; everyone mapped (except 1) played both, except
    368 who missed GW6."""
    for gw, match_id in ((5, 5000), (6, 6000)):
        session.add(
            Match(
                id=match_id,
                gw=gw,
                home_club_id=1,
                away_club_id=2,
                kickoff=datetime(2026, 8, 15, 14) + timedelta(weeks=gw),
                finished=True,
            )
        )
    for i, fpl_id in enumerate(PICKS):
        if fpl_id == 1:
            continue
        session.add(SofascorePlayer(id=sofa(fpl_id), name=f"S{fpl_id}"))
        session.add(
            PlayerIdMap(
                fpl_id=fpl_id,
                sofascore_id=sofa(fpl_id),
                match_method="exact",
                match_confidence=1.0,
                matched_at=SYNCED_AT,
            )
        )
        for gw, match_id in ((5, 5000), (6, 6000)):
            if fpl_id == 368 and gw == 6:
                continue
            session.add(
                PlayerMatchPosition(
                    match_id=match_id,
                    sofascore_player_id=sofa(fpl_id),
                    avg_x=5.0 + 6 * i,
                    avg_y=10.0 + gw,
                    points_count=30,
                    kickoff=datetime(2026, 8, 15, 14) + timedelta(weeks=gw),
                    gw=gw,
                )
            )
    session.add(SyncRun(started_at=SYNCED_AT, finished_at=SYNCED_AT, trigger="run"))
    session.get(Gameweek, 5).positions_synced = True
    session.get(Gameweek, 6).positions_synced = True
    session.commit()
    return session


@pytest.fixture
def fake():
    fake = FakeFpl()
    # The recorded bootstrap has only clubs 1-3: the recorded GW6 fixtures
    # (ARS v 13, AVL v 4) are played against BOU instead.
    for fixture in fake.routes["/api/fixtures/"][:2]:
        fixture["team_a"] = 3
    return fake


def client_for(service, db):
    app.dependency_overrides[get_team_service] = lambda: service
    app.dependency_overrides[get_ro_session] = lambda: db
    return TestClient(app)


@pytest.fixture
def api(fake, db):
    yield client_for(make_service(fake), db)
    app.dependency_overrides.clear()


def test_locked_gameweek(api):
    response = api.get("/api/team/1234/plot/6")
    assert response.status_code == 200
    body = response.json()
    assert (body["team_id"], body["team_name"], body["gw"]) == (1234, "Test FC", 6)
    assert body["state"] == "locked"
    assert body["status"] == "finished"
    assert (body["points"], body["transfers_cost"]) == (77, 0)
    assert (body["prev_gw"], body["next_gw"]) == (5, None)
    assert body["data_as_of"] == "2026-10-12T08:00:00"

    dots = {d["fpl_id"]: d for d in body["dots"]}
    assert len(body["dots"]) == 11
    # XI after auto-subs: 304 in, 368 out.
    assert 368 not in dots and dots[304]["replaces"] == 368
    assert [d["slot"] for d in body["dots"]] == list(range(1, 12))
    # Unmapped player: ghost on the sideline.
    assert dots[1]["is_ghost"] and dots[1]["ghost_reason"] == "no_mapping"
    assert dots[1]["x"] is dots[1]["y"] is None
    assert dots[1]["web_name"] == "Raya" and dots[1]["club"] == "ARS"
    # Everyone else from GW6.
    gabriel = dots[4]
    assert (gabriel["web_name"], gabriel["role"], gabriel["club"]) == ("Gabriel", "DEF", "ARS")
    assert gabriel["name"].endswith("Magalhães")
    assert (gabriel["y"], gabriel["from_gw"], gabriel["link_group"]) == (16.0, None, None)
    assert not gabriel["is_ghost"]
    captain = [d for d in body["dots"] if d["is_captain"]]
    assert len(captain) == 1
    assert body["chip"] is None

    # Each player's own points from event/6/live (fixture: player 1 scored 3,
    # players missing from it 0); no Bench Boost, so no bench dots.
    assert dots[1]["points"] == 3
    assert dots[4]["points"] == 0
    assert not any(d["from_bench"] for d in body["dots"])
    # Bench after auto-subs: 368 (subbed off) sits where 304 was.
    bench = body["bench"]
    assert [b["fpl_id"] for b in bench] == [58, 368, 290, 31]
    assert [b["subbed_off"] for b in bench] == [False, True, False, False]

    # Depth rank: outfield dots only. Every stored match is at y 15 (GW5) or
    # 16 (GW6), so a GW6 dot at 16 is above half the pool (ties count half).
    assert dots[1]["depth_pct"] is None
    assert 0 < gabriel["depth_pct"] < 100
    keeper = next(d for d in body["dots"] if d["role"] == "GK")
    assert keeper["depth_pct"] is None


@pytest.mark.parametrize(("chip", "multiplier"), [(None, 2), ("3xc", 3)])
def test_captain_dot_carries_multiplied_points(fake, db, chip, multiplier):
    picks = load("picks-gw6.json")
    picks["active_chip"] = chip
    fake.routes["/api/entry/1234/event/6/picks/"] = picks
    captain_id = next(p["element"] for p in picks["picks"] if p["is_captain"])
    live = load("live-gw6.json")
    live["elements"].append({"id": captain_id, "stats": {**live["elements"][0]["stats"], "total_points": 5}})
    fake.routes["/api/event/6/live/"] = live

    body = client_for(make_service(fake), db).get("/api/team/1234/plot/6").json()
    captain = next(d for d in body["dots"] if d["is_captain"])
    assert captain["points"] == 5 * multiplier
    assert captain["multiplier"] == multiplier
    assert all(d["multiplier"] == 1 for d in body["dots"] if not d["is_captain"])
    assert body["chip"] == chip


def test_preview_when_not_synced(api, db):
    db.get(Gameweek, 6).positions_synced = False
    db.commit()
    body = api.get("/api/team/1234/plot/6").json()
    # Finished in FPL but not synced: preview, and the status says why.
    assert (body["state"], body["status"]) == ("preview", "finished")
    ids = [d["fpl_id"] for d in body["dots"]]
    # XI as picked: 368 back in, 304 on the bench.
    assert 368 in ids and 304 not in ids
    dots = {d["fpl_id"]: d for d in body["dots"]}
    # 368's latest match is GW5, the previous gameweek: no label.
    assert dots[368]["from_gw"] is None and dots[368]["y"] == 15.0
    assert all(d["replaces"] is None for d in body["dots"])


def test_latest(api):
    body = api.get("/api/team/1234/plot/latest").json()
    assert (body["gw"], body["state"], body["next_gw"]) == (6, "locked", None)


def test_latest_falls_back_while_picks_not_served(fake, db):
    # Just after the GW7 deadline: FPL does not serve the GW7 picks yet.
    service = make_service(fake, now=datetime(2026, 10, 17, 10, 1, tzinfo=UTC))
    body = client_for(service, db).get("/api/team/1234/plot/latest").json()
    app.dependency_overrides.clear()
    assert (body["gw"], body["prev_gw"], body["next_gw"]) == (6, 5, None)


def test_latest_before_season(fake, db):
    service = make_service(fake, now=datetime(2026, 8, 1, tzinfo=UTC))
    response = client_for(service, db).get("/api/team/1234/plot/latest")
    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json()["code"] == "gameweek_not_started"


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/api/team/1234/plot/7", 404, "gameweek_not_started"),
        ("/api/team/1234/plot/39", 404, "gameweek_out_of_range"),
        ("/api/team/999999999/plot/6", 404, "team_not_found"),
        ("/api/team/999999999/plot/latest", 404, "team_not_found"),
        ("/api/team/5678/plot/6", 404, "gameweek_before_team_started"),
    ],
)
def test_errors(api, path, status, code):
    response = api.get(path)
    assert response.status_code == status
    assert response.json()["code"] == code


@pytest.mark.parametrize("path", ["/api/team/1234/plot/0", "/api/team/1234/plot/abc"])
def test_bad_gameweek(api, fake, path):
    assert api.get(path).status_code == 422
    assert fake.requests == []


@pytest.mark.parametrize(
    ("gw", "started", "latest", "expected"),
    [
        (1, 1, 6, (None, 2)),  # season start
        (6, 1, 6, (5, None)),  # newest gameweek
        (38, 1, 38, (37, None)),  # season end
        (4, 4, 6, (None, 5)),  # team's first gameweek
        (5, 4, 6, (4, 6)),
        (3, 1, None, (2, None)),
    ],
)
def test_neighbour_gameweeks(gw, started, latest, expected):
    assert neighbour_gameweeks(gw, started, latest) == expected


def test_web_app_never_loads_the_sofascore_adapter():
    # The adapter (and curl_cffi) is not even importable from the web app.
    code = (
        "import sys, app.main; "
        "bad = [m for m in sys.modules if m.startswith(('app.positions', 'app.sync', 'curl_cffi'))]; "
        "sys.exit(1 if bad else 0)"
    )
    backend = Path(__file__).resolve().parents[1]
    assert subprocess.run([sys.executable, "-c", code], cwd=backend).returncode == 0


def test_only_fpl_requests(api, fake):
    api.get("/api/team/1234/plot/6")
    api.get("/api/team/1234/plot/latest")
    assert fake.requests and all(path.startswith("/api/") for path in fake.requests)


# --- Match details (the hover box) ---------------------------------------------


def explain(fixture: int, minutes: int, *extra: tuple[str, int, int]) -> dict:
    stats = [("minutes", minutes, 2 if minutes >= 60 else 1 if minutes else 0), *extra]
    return {
        "fixture": fixture,
        "stats": [
            {"identifier": i, "value": v, "points": p, "points_modification": 0}
            for i, v, p in stats
        ],
    }


def live_with(fake, fpl_id: int, *explains: dict) -> None:
    live = load("live-gw6.json")
    total = sum(s["points"] for e in explains for s in e["stats"])
    stats = {**live["elements"][0]["stats"], "total_points": total}
    live["elements"].append({"id": fpl_id, "stats": stats, "explain": list(explains)})
    fake.routes["/api/event/6/live/"] = live


def test_match_details_normal_match(api):
    body = api.get("/api/team/1234/plot/6").json()
    raya = next(d for d in body["dots"] if d["fpl_id"] == 1)
    # Recorded: Raya (ARS) kept goal for 90 minutes in ARS 2-1, 4 saves.
    (match,) = raya["matches"]
    assert match == {
        "fixture_id": 51,
        "home_club": "ARS",
        "away_club": "BOU",
        "is_home": True,
        "opponent": "BOU",
        "kickoff": "2026-10-10T11:30:00Z",
        "state": "finished",
        "home_score": 2,
        "away_score": 1,
        "minutes": 90,
        "stats": [
            {"identifier": "minutes", "label": "Minutes", "value": 90, "points": 2},
            {"identifier": "saves", "label": "Saves", "value": 4, "points": 1},
        ],
        "points": 3,
    }
    assert raya["points"] == 3 and raya["multiplier"] == 1


def test_match_details_did_not_play(fake, db):
    # 115 (AVL) was in the squad of AVL v BOU but did not play: one minutes row
    # with value 0, no points.
    live_with(fake, 115, explain(52, 0))
    body = client_for(make_service(fake), db).get("/api/team/1234/plot/6").json()
    app.dependency_overrides.clear()
    (match,) = next(d for d in body["dots"] if d["fpl_id"] == 115)["matches"]
    assert (match["opponent"], match["is_home"], match["minutes"]) == ("BOU", True, 0)
    assert (match["stats"], match["points"]) == ([], 0)
    # A player missing from the live data has no matches.
    assert next(d for d in body["dots"] if d["fpl_id"] == 4)["matches"] == []


def test_match_details_on_bench(fake, db):
    live_with(fake, 58, explain(52, 90, ("goals_scored", 1, 5)))
    body = client_for(make_service(fake), db).get("/api/team/1234/plot/6").json()
    app.dependency_overrides.clear()
    bench = next(b for b in body["bench"] if b["fpl_id"] == 58)
    assert [m["points"] for m in bench["matches"]] == [7]
    assert bench["matches"][0]["stats"][1]["label"] == "Goals scored"


def double_gameweek(fake, db, second_x: float) -> list[dict]:
    """115 (AVL, stored at x 17 in match 6000 = fixture 52, at home to BOU)
    plays a second GW6 match away at ARS (fixture 60), stored at `second_x`."""
    db.get(Match, 6000).fpl_fixture_id = 52
    db.add(
        Match(
            id=6001,
            fpl_fixture_id=60,
            gw=6,
            home_club_id=1,
            away_club_id=2,
            kickoff=datetime(2026, 9, 29, 19),
            finished=True,
        )
    )
    db.add(
        PlayerMatchPosition(
            match_id=6001,
            sofascore_player_id=sofa(115),
            avg_x=second_x,
            avg_y=20.0,
            points_count=30,
            kickoff=datetime(2026, 9, 29, 19),
            gw=6,
        )
    )
    db.commit()
    fixtures = fake.routes["/api/fixtures/"]
    fixtures.append(
        {**fixtures[1], "id": 60, "team_h": 1, "team_a": 2, "kickoff_time": "2026-10-13T19:00:00Z"}
    )
    fake.routes["/api/fixtures/"] = fixtures
    live_with(fake, 115, explain(52, 90, ("assists", 1, 3)), explain(60, 30))
    body = client_for(make_service(fake), db).get("/api/team/1234/plot/6").json()
    app.dependency_overrides.clear()
    return [d for d in body["dots"] if d["fpl_id"] == 115]


def test_match_details_double_gameweek_two_dots(fake, db):
    left, right = double_gameweek(fake, db, second_x=80.0)
    assert left["link_group"] == right["link_group"] == 115
    # Each dot carries only the match its position came from; both show the
    # gameweek's points.
    assert [m["fixture_id"] for m in left["matches"]] == [52]
    assert [m["fixture_id"] for m in right["matches"]] == [60]
    assert (left["matches"][0]["points"], right["matches"][0]["points"]) == (5, 1)
    assert (right["matches"][0]["is_home"], right["matches"][0]["opponent"]) == (False, "ARS")
    assert left["points"] == right["points"] == 6


def test_match_details_double_gameweek_one_dot(fake, db):
    (dot,) = double_gameweek(fake, db, second_x=25.0)
    assert dot["link_group"] is None
    # Both matches, in kick-off order.
    assert [m["fixture_id"] for m in dot["matches"]] == [52, 60]
    assert sum(m["points"] for m in dot["matches"]) == dot["points"] == 6


@pytest.mark.parametrize(
    ("started", "finished_provisional", "finished", "state", "score"),
    [
        (False, False, False, "not_started", None),
        (True, False, False, "live", 1),
        (True, True, False, "finished", 1),
    ],
)
def test_match_details_state(fake, db, started, finished_provisional, finished, state, score):
    raya_fixture = fake.routes["/api/fixtures/"][0]
    raya_fixture.update(
        started=started,
        finished_provisional=finished_provisional,
        finished=finished,
        team_h_score=score,
        team_a_score=score,
    )
    body = client_for(make_service(fake), db).get("/api/team/1234/plot/6").json()
    app.dependency_overrides.clear()
    (match,) = next(d for d in body["dots"] if d["fpl_id"] == 1)["matches"]
    assert (match["state"], match["home_score"], match["away_score"]) == (state, score, score)
