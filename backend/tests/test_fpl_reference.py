"""`refresh_fpl_reference_data()` upserts clubs, players and gameweeks from
the recorded `bootstrap-static/` response."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.engine import make_read_write_engine
from app.db.models import FplClub, FplPlayer, Gameweek
from app.fpl.client import FplClient
from app.fpl.reference import apply_bootstrap, refresh_fpl_reference_data
from app.fpl.schemas import BootstrapStatic

BOOTSTRAP = json.loads(
    (Path(__file__).parent / "fixtures" / "fpl" / "bootstrap-static.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture
def session(tmp_path):
    engine = make_read_write_engine(tmp_path / "fpl.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def bootstrap(**changes) -> BootstrapStatic:
    data = json.loads(json.dumps(BOOTSTRAP))
    for key, fn in changes.items():
        fn(data[key])
    return BootstrapStatic.model_validate(data)


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_refresh_through_client(session):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=BOOTSTRAP))
    client = FplClient("https://fpl.test/api", 60, transport=transport)
    counts = refresh_fpl_reference_data(session, client)
    session.commit()

    assert (counts.clubs, counts.players, counts.gameweeks) == (3, 14, 8)
    assert (count(session, FplClub), count(session, FplPlayer), count(session, Gameweek)) == (
        3,
        14,
        8,
    )


def test_fields_are_mapped(session):
    apply_bootstrap(session, bootstrap())

    assert session.get(FplClub, 1).short_name == "ARS"
    raya = session.get(FplPlayer, 1)
    assert (raya.second_name, raya.web_name, raya.club_id, raya.role, raya.price) == (
        "Raya Martín",
        "Raya",
        1,
        "GK",
        61,
    )
    roles = {p.id: p.role for p in session.scalars(select(FplPlayer))}
    assert {roles[1], roles[4], roles[7], roles[25]} == {"GK", "DEF", "MID", "FWD"}
    injured = session.get(FplPlayer, 9)
    assert injured.status == "i" and injured.news

    gw7 = session.get(Gameweek, 7)
    # Stored as naive UTC.
    assert gw7.deadline == datetime(2026, 10, 17, 10, 0)
    assert (gw7.finished, gw7.data_checked, gw7.positions_synced) == (False, False, False)
    assert session.get(Gameweek, 6).finished


def test_refresh_updates_in_place_and_keeps_our_columns(session):
    apply_bootstrap(session, bootstrap())
    session.get(FplClub, 1).sofascore_team_id = 42
    session.get(Gameweek, 6).positions_synced = True
    session.commit()

    def change_player(elements):
        elements[0].update(now_cost=65, status="d", news="Knock - 75% chance of playing")

    def finish_gw7(events):
        events[6].update(finished=True, data_checked=True)

    apply_bootstrap(session, bootstrap(elements=change_player, events=finish_gw7))
    session.commit()

    assert count(session, FplPlayer) == 14
    raya = session.get(FplPlayer, 1)
    assert (raya.price, raya.status, raya.news) == (65, "d", "Knock - 75% chance of playing")
    assert session.get(Gameweek, 7).finished
    assert session.get(FplClub, 1).sofascore_team_id == 42
    assert session.get(Gameweek, 6).positions_synced


def test_player_transfer_between_clubs(session):
    apply_bootstrap(session, bootstrap())

    def move(elements):
        elements[0]["team"] = 2

    apply_bootstrap(session, bootstrap(elements=move))
    assert session.get(FplPlayer, 1).club_id == 2


def test_unknown_element_type_fails(session):
    def manager(elements):
        elements[0]["element_type"] = 5

    with pytest.raises(ValueError, match="element_type 5"):
        apply_bootstrap(session, bootstrap(elements=manager))
