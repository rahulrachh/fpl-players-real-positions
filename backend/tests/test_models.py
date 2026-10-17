"""Schema: the Alembic migration matches the models, constraints hold, and
the web app's read-only connection can read the tables."""

from datetime import datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db.base import Base
from app.db.engine import (
    get_read_only_engine,
    get_read_write_engine,
    make_read_only_engine,
    make_read_write_engine,
)
from app.db.models import (
    FplClub,
    FplPlayer,
    Gameweek,
    Match,
    PlayerIdMap,
    PlayerMatchPosition,
    SofascorePlayer,
    SyncRun,
    minutes_played,
)

KICKOFF = datetime(2026, 8, 15, 14, 0)
TABLES = {
    "fpl_clubs",
    "fpl_players",
    "player_id_map",
    "gameweeks",
    "sofascore_players",
    "matches",
    "player_match_positions",
    "sync_runs",
}


def _clear_engine_caches():
    get_settings.cache_clear()
    get_read_write_engine.cache_clear()
    get_read_only_engine.cache_clear()


@pytest.fixture
def migrated_db(tmp_path, monkeypatch):
    """A fresh database built by `alembic upgrade head`."""
    path = tmp_path / "fpl.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    _clear_engine_caches()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield path, cfg
    _clear_engine_caches()


@pytest.fixture
def session(migrated_db):
    path, _ = migrated_db
    engine = make_read_write_engine(path)
    with Session(engine) as s:
        s.add_all(
            [
                FplClub(id=13, name="Man City", short_name="MCI", sofascore_team_id=17),
                FplClub(id=12, name="Liverpool", short_name="LIV", sofascore_team_id=44),
                Gameweek(id=6, deadline=KICKOFF),
                SofascorePlayer(id=1, name="Jérémy Doku", short_name="J. Doku"),
                SofascorePlayer(id=2, name="Rio Ngumoha"),
                Match(id=16363878, gw=6, home_club_id=12, away_club_id=13, kickoff=KICKOFF),
            ]
        )
        s.flush()
        s.add(FplPlayer(id=100, first_name="Jérémy", second_name="Doku",
                        web_name="Doku", club_id=13, role="MID", price=65, status="a"))
        s.commit()
        yield s
    engine.dispose()


def _position(**kw) -> PlayerMatchPosition:
    values = dict(match_id=16363878, sofascore_player_id=1, avg_x=60.0, avg_y=82.7,
                  points_count=50, kickoff=KICKOFF, gw=6)
    return PlayerMatchPosition(**(values | kw))


def test_upgrade_creates_all_tables(migrated_db):
    path, _ = migrated_db
    names = set(inspect(make_read_write_engine(path)).get_table_names())
    assert TABLES <= names


def test_migration_matches_models(migrated_db):
    path, _ = migrated_db
    with make_read_write_engine(path).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_then_upgrade(migrated_db):
    path, cfg = migrated_db
    command.downgrade(cfg, "base")
    assert set(inspect(make_read_write_engine(path)).get_table_names()) == {"alembic_version"}
    command.upgrade(cfg, "head")


@pytest.mark.parametrize(
    ("on", "off", "expected"),
    [(None, None, 90), (75, None, 15), (None, 63, 63), (46, 80, 34), (89, 85, 0)],
)
def test_minutes_played(on, off, expected):
    assert minutes_played(on, off) == expected


def test_minutes_derived_on_write(session):
    row = _position(sub_on_minute=75)
    session.add(row)
    session.commit()
    assert row.minutes == 15
    row.sub_off_minute = 85
    session.commit()
    assert session.scalar(select(PlayerMatchPosition.minutes)) == 10


def test_position_unique_per_match_and_player(session):
    session.add(_position())
    session.commit()
    session.add(_position(avg_x=10.0))
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("field", ["avg_x", "avg_y"])
def test_position_out_of_frame_rejected(session, field):
    session.add(_position(**{field: 100.5}))
    with pytest.raises(IntegrityError, match="CHECK"):
        session.commit()


def test_foreign_keys_enforced(session):
    session.add(_position(sofascore_player_id=999))
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


def test_two_fpl_players_cannot_share_a_sofascore_player(session):
    session.add(FplPlayer(id=101, first_name="Rio", second_name="Ngumoha",
                          web_name="Ngumoha", club_id=12, role="MID", price=45, status="a"))
    session.add(PlayerIdMap(fpl_id=100, sofascore_id=1, match_method="exact",
                            match_confidence=1.0, matched_at=KICKOFF))
    session.commit()
    session.add(PlayerIdMap(fpl_id=101, sofascore_id=1, match_method="fuzzy",
                            match_confidence=0.7, matched_at=KICKOFF))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.commit()


@pytest.mark.parametrize(
    ("model", "kw"),
    [
        (FplPlayer, dict(id=102, first_name="A", second_name="B", web_name="B",
                         club_id=13, role="WB", price=50, status="a")),
        (PlayerIdMap, dict(fpl_id=100, sofascore_id=1, match_method="guess",
                           match_confidence=0.5, matched_at=KICKOFF)),
        (PlayerIdMap, dict(fpl_id=100, sofascore_id=1, match_method="exact",
                           match_confidence=1.5, matched_at=KICKOFF)),
        (SyncRun, dict(started_at=KICKOFF, trigger="cron")),
    ],
)
def test_check_constraints(session, model, kw):
    session.add(model(**kw))
    with pytest.raises(IntegrityError, match="CHECK"):
        session.commit()


def test_sync_run_defaults(session):
    run = SyncRun(started_at=KICKOFF, trigger="backfill", errors=["event 1: 403"])
    session.add(run)
    session.commit()
    assert run.matches_fetched == 0
    assert session.get(SyncRun, run.id).errors == ["event 1: 403"]


def test_read_only_engine_reads_models(session, migrated_db):
    path, _ = migrated_db
    session.add(_position())
    session.commit()
    with Session(make_read_only_engine(path, immutable=True)) as ro:
        row = ro.scalars(select(PlayerMatchPosition)).one()
        assert (row.avg_y, row.minutes, row.match.home_club_id) == (82.7, 90, 12)
        ro.add(SyncRun(started_at=KICKOFF, trigger="run"))
        with pytest.raises(Exception, match="readonly|read-only"):
            ro.commit()
