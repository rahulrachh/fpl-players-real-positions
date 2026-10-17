"""Client for the public FPL API (no login). Endpoints, fields used and the
public/private boundary are in `docs/fpl-api.md`.

Every call goes through a short-TTL in-memory cache (`FPL_CACHE_TTL_SECONDS`),
so repeated page views within a minute do not hit FPL again. Gameweek status
and live data change often, so nothing here is cached for longer.
"""

from functools import lru_cache
from typing import TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.cache import TTLCache
from app.config import get_settings
from app.fpl.schemas import (
    BootstrapStatic,
    Entry,
    EntryHistory,
    EventLive,
    EventStatus,
    Fixture,
    Picks,
)

M = TypeVar("M", bound=BaseModel)

USER_AGENT = "fpl-real-shape/0.1"
_FIXTURES = TypeAdapter(list[Fixture])


class FplError(Exception):
    """Base class for FPL API failures."""


class FplNotFound(FplError):
    """404: unknown team ID, or no picks for that gameweek (not played yet,
    deadline not passed, or the team joined later)."""


class FplUnavailable(FplError):
    """FPL could not be reached or answered with an error (5xx, including 503
    "The game is being updated." while FPL processes a gameweek)."""


class FplSchemaError(FplError):
    """The response no longer has the shape we expect (the API changed)."""


class FplClient:
    def __init__(
        self,
        base_url: str,
        cache_ttl_seconds: float,
        timeout_seconds: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        self.cache: TTLCache[object] = TTLCache(cache_ttl_seconds)

    def close(self) -> None:
        self._http.close()

    # --- endpoints ---------------------------------------------------------

    def bootstrap_static(self) -> BootstrapStatic:
        """Players, clubs, roles, prices, availability, gameweeks."""
        return self._get_model("/bootstrap-static/", BootstrapStatic)

    def fixtures(self, event: int | None = None) -> list[Fixture]:
        """All 380 fixtures, or one gameweek's."""
        params = {"event": event} if event is not None else None
        return self._cached(
            ("/fixtures/", event),
            lambda: self._parse(_FIXTURES, self._get_json("/fixtures/", params)),
        )

    def entry(self, entry_id: int) -> Entry:
        return self._get_model(f"/entry/{entry_id}/", Entry)

    def entry_history(self, entry_id: int) -> EntryHistory:
        """Bank, value and points per gameweek, plus chips played."""
        return self._get_model(f"/entry/{entry_id}/history/", EntryHistory)

    def entry_picks(self, entry_id: int, event: int) -> Picks:
        """Picks for a gameweek whose deadline has passed. 404 (FplNotFound)
        before the deadline: upcoming picks are private."""
        return self._get_model(f"/entry/{entry_id}/event/{event}/picks/", Picks)

    def event_live(self, event: int) -> EventLive:
        """Per-player stats (minutes) for a gameweek. Empty before it starts."""
        return self._get_model(f"/event/{event}/live/", EventLive)

    def event_status(self) -> EventStatus:
        """Points/bonus processing state of the current gameweek's match days."""
        return self._get_model("/event-status/", EventStatus)

    # --- plumbing ----------------------------------------------------------

    def _get_model(self, path: str, model: type[M]) -> M:
        return self._cached(path, lambda: self._parse(model, self._get_json(path)))

    def _cached(self, key, factory):
        return self.cache.get_or_set(key, factory)

    def _get_json(self, path: str, params: dict | None = None):
        try:
            response = self._http.get(path, params=params)
        except httpx.HTTPError as exc:
            raise FplUnavailable(f"GET {path}: {exc!r}") from exc
        if response.status_code == 404:
            raise FplNotFound(f"GET {path}: 404")
        if response.status_code >= 400:
            raise FplUnavailable(
                f"GET {path}: HTTP {response.status_code} {response.text[:200]!r}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise FplSchemaError(f"GET {path}: response is not JSON") from exc

    @staticmethod
    def _parse(model, data):
        try:
            if isinstance(model, TypeAdapter):
                return model.validate_python(data)
            return model.model_validate(data)
        except ValidationError as exc:
            raise FplSchemaError(str(exc)) from exc


@lru_cache
def get_fpl_client() -> FplClient:
    """Process-wide client (one connection pool, one cache)."""
    settings = get_settings()
    return FplClient(settings.fpl_api_base_url, settings.fpl_cache_ttl_seconds)
