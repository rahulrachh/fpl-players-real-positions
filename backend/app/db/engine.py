"""SQLAlchemy engines for the two connection modes.

- **read-write**: offline scripts only (sync, mapping, Alembic). Creates the
  file and its directory if missing.
- **read-only**: the web app. Opens the file with SQLite's `mode=ro` URI (plus
  `immutable=1` when `DATABASE_IMMUTABLE` is set) and turns on
  `PRAGMA query_only`, so any write raises. The web app never writes.

Both turn on `PRAGMA foreign_keys` (SQLite leaves it off by default).
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import Engine, create_engine, event

from app.config import get_settings


def _ro_url(path: Path, immutable: bool) -> str:
    # SQLite URI form: file:/abs/path or file:/C:/abs/path on Windows.
    posix = path.as_posix()
    if not posix.startswith("/"):
        posix = "/" + posix
    uri = f"file:{quote(posix, safe='/:')}?mode=ro"
    if immutable:
        uri += "&immutable=1"
    return f"sqlite:///{uri}&uri=true"


def make_read_only_engine(path: Path, immutable: bool = False) -> Engine:
    engine = create_engine(_ro_url(path, immutable))

    @event.listens_for(engine, "connect")
    def _query_only(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA query_only = ON")
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    return engine


def make_read_write_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path.as_posix()}")

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    return engine


@lru_cache
def get_read_only_engine() -> Engine:
    settings = get_settings()
    return make_read_only_engine(settings.database_file, settings.database_immutable)


@lru_cache
def get_read_write_engine() -> Engine:
    return make_read_write_engine(get_settings().database_file)
