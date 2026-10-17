"""Sofascore adapter: the only code that talks to Sofascore.

Endpoints, fields and access notes are in `docs/spikes/positions-source.md`
and `docs/positions-source.md`. Unofficial API, so fetch politely: at least
`SOFASCORE_REQUEST_DELAY_SECONDS` between requests, retries with exponential
backoff for 429 / 5xx / network errors, and a `SourceBlockedError` on 403
(no retry: hammering a block makes it worse).

Plain `requests` / `httpx` get 403 (TLS fingerprinting), so the default
session is `curl_cffi` impersonating Chrome. `curl_cffi` is in the `sync`
dependency group and imported only when a default session is built, so the
web app never needs it.

Orientation: Sofascore already normalizes both teams to attack the same way,
as `averageX` 0 = own goal → 100 = opponent goal and `averageY` high = the
team's left. `_to_frame()` converts that to the frame in `base.py` (x = 100 -
averageY, y = averageX). As a guard, a side whose starting goalkeeper sits in
the opponent's half is mirrored and logged.
"""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.positions.base import (
    PositionsSource,
    SourceBlockedError,
    SourceMatch,
    SourceNotFoundError,
    SourcePlayer,
    SourcePlayerPosition,
    SourceSchemaError,
    SourceUnavailableError,
)

log = logging.getLogger(__name__)

PREMIER_LEAGUE_ID = 17
REFERER = "https://www.sofascore.com/"
# events/last/{page} returns 30 events per page, newest page first. A full
# season in all competitions fits in 3 pages; this only stops a runaway loop.
MAX_EVENT_PAGES = 6


def _default_session():
    from curl_cffi import requests

    session = requests.Session(impersonate="chrome")
    session.headers.update({"Referer": REFERER})
    return session


class SofascoreSource(PositionsSource):
    def __init__(
        self,
        base_url: str,
        request_delay_seconds: float,
        max_retries: int = 3,
        backoff_seconds: float = 5.0,
        timeout_seconds: float = 20.0,
        session: Any = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """`session` is anything with `get(url, timeout=...)` returning a
        response with `status_code`, `headers` and `json()` (curl_cffi /
        requests style); built lazily when None."""
        self.base_url = base_url.rstrip("/")
        self.request_delay_seconds = request_delay_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.timeout_seconds = timeout_seconds
        self._session = session
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self._season_id: int | None = None
        self._season_start: datetime | None = None
        self.request_count = 0

    # --- PositionsSource ---------------------------------------------------

    def list_round_matches(self, round: int) -> list[SourceMatch]:
        season_id = self.current_season_id()
        data = self._get(
            f"/unique-tournament/{PREMIER_LEAGUE_ID}/season/{season_id}/events/round/{round}"
        )
        matches = [_match(ev) for ev in _list(data, "events")]
        return sorted(matches, key=lambda m: (m.kickoff, m.id))

    def list_team_matches(
        self, source_team_id: int, last_n: int | None = None
    ) -> list[SourceMatch]:
        season_id = self.current_season_id()
        # Recent matches are on page 0; walk back only for a whole season.
        season_start = self._current_season_start() if last_n is None else None
        by_id: dict[int, SourceMatch] = {}
        for page in range(MAX_EVENT_PAGES):
            data = self._get(f"/team/{source_team_id}/events/last/{page}")
            events = _list(data, "events")
            for ev in events:
                if _is_league_event(ev, season_id):
                    match = _match(ev)
                    by_id[match.id] = match
            if not data.get("hasNextPage") or not events:
                break
            if last_n is not None:
                if sum(m.finished for m in by_id.values()) >= last_n:
                    break
            elif min(_kickoff(ev) for ev in events) < season_start:
                break
        else:
            log.warning("team %s: stopped after %s event pages", source_team_id, MAX_EVENT_PAGES)

        matches = sorted(by_id.values(), key=lambda m: (m.kickoff, m.id))
        if last_n is not None:
            matches = [m for m in matches if m.finished][-last_n:] if last_n > 0 else []
        return matches

    def match_positions(self, match_id: int) -> list[SourcePlayerPosition]:
        data = self._get(f"/event/{match_id}/average-positions")
        sub_on: dict[int, int] = {}
        sub_off: dict[int, int] = {}
        for sub in _list(data, "substitutions"):
            minute = sub.get("time")
            if not isinstance(minute, int):
                continue
            if player_in := sub.get("playerIn"):
                sub_on[player_in["id"]] = minute
            if player_out := sub.get("playerOut"):
                sub_off[player_out["id"]] = minute

        positions: list[SourcePlayerPosition] = []
        for side in ("home", "away"):
            rows = _list(data, side)
            mirror = _side_is_reversed(rows, sub_on)
            if mirror:
                log.warning("match %s: %s side attacks the wrong way, mirroring", match_id, side)
            for row in rows:
                try:
                    player = _player(row["player"])
                    raw_x, raw_y = float(row["averageX"]), float(row["averageY"])
                    points = int(row.get("pointsCount") or 0)
                except (KeyError, TypeError, ValueError) as exc:
                    raise SourceSchemaError(f"match {match_id} {side}: {exc!r}") from exc
                if mirror:
                    raw_x, raw_y = 100 - raw_x, 100 - raw_y
                x, y = _to_frame(raw_x, raw_y)
                positions.append(
                    SourcePlayerPosition(
                        player=player,
                        is_home=side == "home",
                        x=x,
                        y=y,
                        points_count=max(0, points),
                        sub_on_minute=sub_on.get(player.id),
                        sub_off_minute=sub_off.get(player.id),
                    )
                )
        return positions

    def list_team_players(self, source_team_id: int) -> list[SourcePlayer]:
        data = self._get(f"/team/{source_team_id}/players")
        players = []
        for row in _list(data, "players"):
            try:
                raw = row["player"]
            except (KeyError, TypeError) as exc:
                raise SourceSchemaError(f"team {source_team_id} players: {exc!r}") from exc
            team_id = (raw.get("team") or {}).get("id", source_team_id)
            players.append(_player(raw, team_id=team_id))
        return players

    # --- season ------------------------------------------------------------

    def current_season_id(self) -> int:
        """Sofascore's ID for the current Premier League season (the newest
        one listed)."""
        if self._season_id is None:
            seasons = _list(self._get(f"/unique-tournament/{PREMIER_LEAGUE_ID}/seasons"), "seasons")
            if not seasons or "id" not in seasons[0]:
                raise SourceSchemaError("no Premier League seasons listed")
            self._season_id = int(seasons[0]["id"])
        return self._season_id

    def _current_season_start(self) -> datetime:
        """Kickoff of the season's first round: older team events are not in
        this season."""
        if self._season_start is None:
            round_1 = self.list_round_matches(1)
            if not round_1:
                raise SourceSchemaError("current season has no round 1 matches")
            self._season_start = round_1[0].kickoff
        return self._season_start

    # --- HTTP --------------------------------------------------------------

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        if self._session is None:
            self._session = _default_session()

        attempt = 0
        while True:
            self._wait_for_slot()
            try:
                response = self._session.get(url, timeout=self.timeout_seconds)
            except Exception as exc:  # network errors (curl_cffi has its own types)
                failure: str = repr(exc)
                retry_after = None
            else:
                status = response.status_code
                if status == 200:
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise SourceSchemaError(f"GET {path}: response is not JSON") from exc
                    if not isinstance(data, dict):
                        raise SourceSchemaError(f"GET {path}: expected a JSON object")
                    return data
                if status == 404:
                    raise SourceNotFoundError(f"GET {path}: 404")
                if status == 403:
                    raise SourceBlockedError(f"GET {path}: 403 Forbidden (blocked)")
                if status != 429 and status < 500:
                    raise SourceUnavailableError(f"GET {path}: HTTP {status}")
                failure = f"HTTP {status}"
                retry_after = _retry_after(response)

            if attempt >= self.max_retries:
                error = SourceBlockedError if failure == "HTTP 429" else SourceUnavailableError
                raise error(f"GET {path}: {failure} after {attempt + 1} attempts")
            delay = max(self.backoff_seconds * 2**attempt, retry_after or 0)
            log.warning("GET %s: %s, retrying in %.0f s", path, failure, delay)
            self._sleep(delay)
            attempt += 1

    def _wait_for_slot(self) -> None:
        """Keep at least `request_delay_seconds` between request starts."""
        if self._last_request_at is not None:
            wait = self._last_request_at + self.request_delay_seconds - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._clock()
        self.request_count += 1


def get_sofascore_source() -> SofascoreSource:
    settings = get_settings()
    return SofascoreSource(
        settings.sofascore_api_base_url,
        settings.sofascore_request_delay_seconds,
        max_retries=settings.sofascore_max_retries,
        backoff_seconds=settings.sofascore_backoff_seconds,
    )


# --- parsing ---------------------------------------------------------------


def _to_frame(average_x: float, average_y: float) -> tuple[float, float]:
    """Sofascore (averageX depth, averageY high = left) → base frame (x left
    → right, y own goal → opponent goal), clamped to 0-100."""
    return _clamp(100 - average_y), _clamp(average_x)


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))


def _side_is_reversed(rows: list[dict], sub_on: dict[int, int]) -> bool:
    """True if this side's starting goalkeeper averages in the opponent's
    half, i.e. Sofascore did not normalize it."""
    for row in rows:
        player = row.get("player") or {}
        if player.get("position") == "G" and player.get("id") not in sub_on:
            depth = row.get("averageX")
            return isinstance(depth, (int, float)) and depth > 50
    return False


def _list(data: dict, key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise SourceSchemaError(f"'{key}' is not a list")
    return value


def _is_league_event(event: dict, season_id: int) -> bool:
    tournament = (event.get("tournament") or {}).get("uniqueTournament") or {}
    season = event.get("season") or {}
    return tournament.get("id") == PREMIER_LEAGUE_ID and season.get("id") == season_id


def _kickoff(event: dict) -> datetime:
    try:
        timestamp = event["startTimestamp"]
    except KeyError as exc:
        raise SourceSchemaError(f"event {event.get('id')}: no startTimestamp") from exc
    return datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None)


def _match(event: dict) -> SourceMatch:
    try:
        return SourceMatch(
            id=int(event["id"]),
            season_id=int(event["season"]["id"]),
            round=(event.get("roundInfo") or {}).get("round"),
            home_team_id=int(event["homeTeam"]["id"]),
            home_team_name=event["homeTeam"]["name"],
            away_team_id=int(event["awayTeam"]["id"]),
            away_team_name=event["awayTeam"]["name"],
            kickoff=_kickoff(event),
            status=event["status"]["type"],
            home_score=(event.get("homeScore") or {}).get("current"),
            away_score=(event.get("awayScore") or {}).get("current"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceSchemaError(f"event {event.get('id')}: {exc!r}") from exc


def _player(raw: dict, team_id: int | None = None) -> SourcePlayer:
    try:
        return SourcePlayer(
            id=int(raw["id"]),
            name=raw["name"],
            short_name=raw.get("shortName"),
            slug=raw.get("slug"),
            position=raw.get("position") or None,
            team_id=team_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceSchemaError(f"player {raw!r:.80}: {exc!r}") from exc


def _retry_after(response) -> float | None:
    try:
        return float(response.headers.get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None
