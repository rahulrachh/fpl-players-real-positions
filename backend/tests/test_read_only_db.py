"""The web app's connection must refuse every write."""

import sqlite3

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.engine import make_read_only_engine, make_read_write_engine


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "sub dir" / "test.db"  # space: checks URI quoting
    with make_read_write_engine(path).begin() as conn:
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
        conn.execute(text("INSERT INTO t VALUES (1)"))
    return path


@pytest.mark.parametrize("immutable", [False, True])
def test_read_only_engine_reads(db_file, immutable):
    with make_read_only_engine(db_file, immutable).connect() as conn:
        assert conn.execute(text("SELECT x FROM t")).scalar() == 1


@pytest.mark.parametrize(
    "stmt",
    ["INSERT INTO t VALUES (2)", "UPDATE t SET x = 3", "CREATE TABLE u (y INTEGER)"],
)
def test_read_only_engine_rejects_writes(db_file, stmt):
    with make_read_only_engine(db_file).connect() as conn:
        with pytest.raises(OperationalError, match="readonly|read-only|query_only"):
            conn.execute(text(stmt))
            conn.commit()


def test_mode_ro_alone_rejects_writes(db_file):
    # Even with query_only switched off, the file itself is opened read-only.
    with make_read_only_engine(db_file).connect() as conn:
        conn.execute(text("PRAGMA query_only = OFF"))
        with pytest.raises(OperationalError, match="readonly"):
            conn.execute(text("INSERT INTO t VALUES (2)"))
            conn.commit()


def test_read_only_engine_does_not_create_missing_file(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(OperationalError):
        make_read_only_engine(missing).connect()
    assert not missing.exists()


def test_data_unchanged_after_rejected_write(db_file):
    with make_read_only_engine(db_file).connect() as conn:
        with pytest.raises(OperationalError):
            conn.execute(text("DELETE FROM t"))
    assert sqlite3.connect(db_file).execute("SELECT COUNT(*) FROM t").fetchone() == (1,)
