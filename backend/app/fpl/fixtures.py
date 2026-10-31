"""A gameweek's fixtures with their scores and each match's top 3 players
by FPL points. The same for every team, so it is cached per gameweek on its
own: for a long TTL once FPL has checked the gameweek, otherwise for the
short FPL TTL. Described in `docs/api.md` (`GET /api/gameweek/{gw}/fixtures`).

Everything comes live from FPL (`fixtures/?event=`, `event/{gw}/live/`,
`bootstrap-static/`); the database is not used.
"""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.cache import TTLCache
from app.config import get_settings
from app.fpl.client import FplClient, get_fpl_client
from app.fpl.reference import ROLE_BY_ELEMENT_TYPE
from app.fpl.schemas import Fixture, LiveElement
from app.fpl.team import Club, GameweekOutOfRange, match_state

TOP_N = 3


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class TopPlayer(_Model):
    id: int
    web_name: str
    # Club short name (the player's current club, as on the FPL site).
    club: str
    role: str
    # His FPL points from this match only (before any captain multiplier).
    points: int


class FixtureSummary(_Model):
    id: int
    kickoff: datetime | None
    state: Literal["not_started", "live", "finished"]
    home_club: Club
    away_club: Club
    # None until kick-off; live while the match is played.
    home_score: int | None
    away_score: int | None
    # The top 3 by points in this match, both sides, everyone tied for 3rd
    # included; highest first. Empty until kick-off.
    top_players: list[TopPlayer]


class GameweekFixtures(_Model):
    gw: int
    # FPL has checked the gameweek's points: nothing changes any more.
    data_checked: bool
    # In kick-off order.
    fixtures: list[FixtureSummary]


def fixture_points(live: list[LiveElement]) -> dict[int, dict[int, tuple[int, int]]]:
    """Fixture ID → {FPL ID → (points, minutes)} from each player's `explain`.
    A double-gameweek player has an entry under each of his fixtures."""
    result: dict[int, dict[int, tuple[int, int]]] = {}
    for element in live:
        for explain in element.explain:
            points = sum(s.points for s in explain.stats)
            minutes = next((s.value for s in explain.stats if s.identifier == "minutes"), 0)
            result.setdefault(explain.fixture, {})[element.id] = (points, minutes)
    return result


def top_players(points: dict[int, tuple[int, int]], n: int = TOP_N) -> list[tuple[int, int]]:
    """(FPL ID, points) of the top `n` among players who played, plus everyone
    tied with the `n`th; highest first, ties by ID."""
    played = sorted(
        ((pid, pts) for pid, (pts, minutes) in points.items() if minutes > 0),
        key=lambda p: (-p[1], p[0]),
    )
    if len(played) <= n:
        return played
    cutoff = played[n - 1][1]
    return [p for p in played if p[1] >= cutoff]


class FixturesService:
    def __init__(
        self, client: FplClient, finished_ttl_seconds: float, short_ttl_seconds: float
    ) -> None:
        self.client = client
        self.finished_ttl_seconds = finished_ttl_seconds
        self.short_ttl_seconds = short_ttl_seconds
        self.cache: TTLCache[GameweekFixtures] = TTLCache(short_ttl_seconds)

    def gameweek_fixtures(self, gw: int) -> GameweekFixtures:
        """Raises `GameweekOutOfRange`, or an `FplError` if FPL fails."""
        cached = self.cache.get(gw)
        if cached is not None:
            return cached
        result = self._load(gw)
        ttl = self.finished_ttl_seconds if result.data_checked else self.short_ttl_seconds
        self.cache.set(gw, result, ttl)
        return result

    def _load(self, gw: int) -> GameweekFixtures:
        bootstrap = self.client.bootstrap_static()
        event = next((e for e in bootstrap.events if e.id == gw), None)
        if event is None:
            raise GameweekOutOfRange(f"gameweek {gw} is not in the season")
        clubs = {t.id: Club(id=t.id, name=t.name, short_name=t.short_name) for t in bootstrap.teams}
        elements = {e.id: e for e in bootstrap.elements}
        fixtures = [f for f in self.client.fixtures(gw) if f.event == gw]
        # No live data before the gameweek starts: FPL answers with no elements.
        by_fixture = fixture_points(self.client.event_live(gw).elements) if any(
            f.started for f in fixtures
        ) else {}

        def summary(fixture: Fixture) -> FixtureSummary:
            state = match_state(fixture)
            top = []
            if state != "not_started":
                for pid, pts in top_players(by_fixture.get(fixture.id, {})):
                    element = elements.get(pid)
                    if element is None:
                        continue
                    top.append(
                        TopPlayer(
                            id=pid,
                            web_name=element.web_name,
                            club=clubs[element.team].short_name if element.team in clubs else "?",
                            role=ROLE_BY_ELEMENT_TYPE.get(element.element_type, "?"),
                            points=pts,
                        )
                    )
            return FixtureSummary(
                id=fixture.id,
                kickoff=fixture.kickoff_time,
                state=state,
                home_club=clubs[fixture.team_h],
                away_club=clubs[fixture.team_a],
                home_score=fixture.team_h_score,
                away_score=fixture.team_a_score,
                top_players=top,
            )

        far_future = datetime.max.replace(tzinfo=UTC)
        ordered = sorted(fixtures, key=lambda f: (f.kickoff_time or far_future, f.id))
        return GameweekFixtures(
            gw=gw, data_checked=event.data_checked, fixtures=[summary(f) for f in ordered]
        )


@lru_cache
def get_fixtures_service() -> FixturesService:
    """Process-wide service (one result cache), on the process-wide client."""
    settings = get_settings()
    return FixturesService(
        get_fpl_client(),
        finished_ttl_seconds=settings.fpl_finished_cache_ttl_seconds,
        short_ttl_seconds=settings.fpl_cache_ttl_seconds,
    )
