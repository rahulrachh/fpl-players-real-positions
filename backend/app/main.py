"""FastAPI app. Opens the database read-only; it never writes."""

import logging

from fastapi import Depends, FastAPI, Path, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_ro_session
from app.fpl.client import FplError
from app.fpl.fixtures import FixturesService, GameweekFixtures, get_fixtures_service
from app.fpl.team import (
    GameweekBeforeTeamStarted,
    GameweekNotStarted,
    GameweekOutOfRange,
    TeamError,
    TeamGameweek,
    TeamNotFound,
    TeamService,
    get_team_service,
)
from app.logic.plot import Plot, build_plot
from app.logic.summary import build_summary

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(title="FPL Real Shape Visualizer")

# Team error → (HTTP status, machine-readable code for the website).
_TEAM_ERRORS: dict[type[TeamError], tuple[int, str]] = {
    TeamNotFound: (404, "team_not_found"),
    GameweekOutOfRange: (404, "gameweek_out_of_range"),
    GameweekBeforeTeamStarted: (404, "gameweek_before_team_started"),
    GameweekNotStarted: (404, "gameweek_not_started"),
}


@app.exception_handler(TeamError)
def _team_error(_request: Request, exc: TeamError) -> JSONResponse:
    status, code = _TEAM_ERRORS.get(type(exc), (404, "not_found"))
    return JSONResponse(status_code=status, content={"code": code, "detail": str(exc)})


@app.exception_handler(FplError)
def _fpl_error(_request: Request, exc: FplError) -> JSONResponse:
    logger.warning("FPL request failed: %s: %s", type(exc).__name__, exc)
    return JSONResponse(
        status_code=503,
        content={"code": "fpl_unavailable", "detail": "FPL is unavailable, try again shortly"},
    )


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


@app.get("/api/team/{team_id}/gameweek/{gw}")
def team_gameweek(
    team_id: int = Path(ge=1),
    gw: int = Path(ge=1),
    session: Session = Depends(get_ro_session),
    service: TeamService = Depends(get_team_service),
) -> TeamGameweek:
    return service.load_team_gameweek(team_id, gw, session)


# Declared before `/plot/{gw}` so "latest" is not parsed as a gameweek.
@app.get("/api/team/{team_id}/plot/latest")
def team_plot_latest(
    team_id: int = Path(ge=1),
    session: Session = Depends(get_ro_session),
    service: TeamService = Depends(get_team_service),
) -> Plot:
    """The newest gameweek whose deadline has passed; the one before it if FPL
    is not serving that gameweek's picks yet (just after the deadline)."""
    latest = service.latest_gameweek()
    if latest is None:
        raise GameweekNotStarted("the season has not started")
    try:
        team = service.load_team_gameweek(team_id, latest, session)
    except GameweekNotStarted:
        if latest == 1:
            raise
        latest -= 1
        team = service.load_team_gameweek(team_id, latest, session)
    return _with_summary(build_plot(team, session, latest), service)


@app.get("/api/team/{team_id}/plot/{gw}")
def team_plot(
    team_id: int = Path(ge=1),
    gw: int = Path(ge=1),
    session: Session = Depends(get_ro_session),
    service: TeamService = Depends(get_team_service),
) -> Plot:
    team = service.load_team_gameweek(team_id, gw, session)
    return _with_summary(build_plot(team, session, service.latest_gameweek()), service)


def _with_summary(plot: Plot, service: TeamService) -> Plot:
    """Adds the summary panel's numbers. The graphic does not need them, so
    if FPL's history fails the plot is still returned, without a summary."""
    try:
        history = service.client.entry_history(plot.team_id)
        bootstrap = service.client.bootstrap_static()
    except FplError as exc:
        logger.warning("summary for team %s GW%s left out: %s", plot.team_id, plot.gw, exc)
        return plot
    return plot.model_copy(update={"summary": build_summary(plot.gw, history, bootstrap)})


@app.get("/api/gameweek/{gw}/fixtures")
def gameweek_fixtures(
    gw: int = Path(ge=1),
    service: FixturesService = Depends(get_fixtures_service),
) -> GameweekFixtures:
    """The gameweek's matches and scores, each with its top 3 players by FPL
    points. The same for every team (the website highlights the team's own)."""
    return service.gameweek_fixtures(gw)


@app.get("/api/gameweeks/latest")
def latest_gameweeks(service: TeamService = Depends(get_team_service)) -> dict:
    """Newest gameweek with public picks, and newest with every fixture finished."""
    return {
        "latest": service.latest_gameweek(),
        "last_finished": service.last_finished_gameweek(),
    }
