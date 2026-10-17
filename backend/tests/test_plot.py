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
    return FakeFpl()


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

    # Depth rank: outfield dots only. Every stored match is at y 15 (GW5) or
    # 16 (GW6), so a GW6 dot at 16 is above half the pool (ties count half).
    assert dots[1]["depth_pct"] is None
    assert 0 < gabriel["depth_pct"] < 100
    keeper = next(d for d in body["dots"] if d["role"] == "GK")
    assert keeper["depth_pct"] is None


def test_preview_when_not_synced(api, db):
    db.get(Gameweek, 6).positions_synced = False
    db.commit()
    body = api.get("/api/team/1234/plot/6").json()
    assert body["state"] == "preview"
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
