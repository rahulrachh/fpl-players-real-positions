"""Session helpers: a read-only dependency for the web app, a read-write
context manager for offline scripts."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.db.engine import get_read_only_engine, get_read_write_engine


def get_ro_session() -> Iterator[Session]:
    """FastAPI dependency: a session on the read-only engine."""
    with sessionmaker(bind=get_read_only_engine())() as session:
        yield session


@contextmanager
def rw_session() -> Iterator[Session]:
    """Read-write session for offline scripts. Commits on success."""
    with sessionmaker(bind=get_read_write_engine())() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
