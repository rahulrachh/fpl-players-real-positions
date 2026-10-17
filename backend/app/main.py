"""FastAPI app. Opens the database read-only; it never writes."""

import logging

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_ro_session

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(title="FPL Real Shape Visualizer")


@app.get("/api/health")
def health(session: Session = Depends(get_ro_session)) -> dict:
    db: dict = {"file": settings.database_file.name}
    try:
        db["query_only"] = bool(session.execute(text("PRAGMA query_only")).scalar())
        db["read_only"] = db["query_only"] and _connection_is_read_only(session)
        db["ok"] = True
    except SQLAlchemyError as exc:
        logger.warning("health: database check failed: %s", exc)
        db.update(ok=False, error=type(exc).__name__)
    return {"status": "ok" if db["ok"] else "degraded", "database": db}


def _connection_is_read_only(session: Session) -> bool:
    # sqlite3 exposes no direct "opened read-only" flag; the URI mode is the
    # source of truth, so confirm the engine was built with `mode=ro`.
    return "mode=ro" in str(session.get_bind().url)
