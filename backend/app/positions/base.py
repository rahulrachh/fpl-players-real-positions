"""Source-agnostic interface for the average-positions source.

Everything outside `app/positions/` uses only the types and errors defined
here, plus `get_positions_source()` from the package. A source adapter
(today `sofascore.py`) fetches and normalizes; it never writes to the
database (the offline sync script does that).

Coordinate frame (every adapter must return positions in it)
------------------------------------------------------------
Pitch seen from behind the player's own goal, his team attacking upward:

- **x**: 0 = left touchline, 100 = right touchline (his left and right).
- **y**: 0 = his own goal line, 100 = the opponent's goal line.

Both are floats in 0-100. Every team, home or away, is in this same frame, so
a left-back always has a low x and a striker a high y. A renderer can use
(x, y) as screen coordinates directly, with y pointing up.

IDs (`SourceMatch.id`, `SourcePlayer.id`, team IDs) are the source's own.
Datetimes are naive UTC, matching the database convention.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class PositionsSourceError(Exception):
    """Base class for positions source failures."""


class SourceBlockedError(PositionsSourceError):
    """The source refused us (403, or still rate limited after every retry).
    Stop the run and slow down rather than retrying straight away."""


class SourceUnavailableError(PositionsSourceError):
    """The source could not be reached or kept failing (network, 5xx)."""


class SourceNotFoundError(PositionsSourceError):
    """404: unknown ID, or no data for it yet (e.g. a match with no average
    positions)."""


class SourceSchemaError(PositionsSourceError):
    """The response no longer has the shape we expect (the API changed)."""


@dataclass(frozen=True)
class SourceMatch:
    id: int
    season_id: int
    # The source's round number. Close to the FPL gameweek but not the same
    # (rescheduled matches): assign gameweeks from FPL's fixtures instead.
    round: int | None
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    kickoff: datetime
    # Source status, e.g. "finished", "notstarted", "postponed", "canceled".
    status: str
    home_score: int | None
    away_score: int | None

    @property
    def finished(self) -> bool:
        return self.status == "finished"


@dataclass(frozen=True)
class SourcePlayer:
    id: int
    name: str
    short_name: str | None
    slug: str | None
    # Source position letter: G / D / M / F (None if unknown).
    position: str | None
    # Club the player is listed for; None where the source does not say
    # (match positions: use `SourcePlayerPosition.is_home` and the match).
    team_id: int | None = None


@dataclass(frozen=True)
class SourcePlayerPosition:
    player: SourcePlayer
    is_home: bool
    # Average position in the frame above.
    x: float
    y: float
    # How many data points the average is built from (Sofascore: on-ball
    # actions). Low = unreliable dot.
    points_count: int
    # Set = came on as a sub at this minute.
    sub_on_minute: int | None
    # Set = taken off at this minute.
    sub_off_minute: int | None

    @property
    def is_sub(self) -> bool:
        return self.sub_on_minute is not None

    @property
    def minutes(self) -> int:
        """Approximate minutes: stoppage time and red cards are ignored."""
        return max(0, (self.sub_off_minute or 90) - (self.sub_on_minute or 0))


class PositionsSource(ABC):
    """A source of per-match average positions for Premier League players."""

    @abstractmethod
    def list_round_matches(self, round: int) -> list[SourceMatch]:
        """Every match of a round of the current season, kickoff order."""

    @abstractmethod
    def list_team_matches(
        self, source_team_id: int, last_n: int | None = None
    ) -> list[SourceMatch]:
        """The club's current-season league matches that have kicked off (any
        status), oldest first. `last_n` keeps only the most recent N
        *finished* ones; None returns the whole season so far."""

    @abstractmethod
    def match_positions(self, match_id: int) -> list[SourcePlayerPosition]:
        """Average position of every player who played in the match, both
        teams, starters and subs. Unused subs are not included."""

    @abstractmethod
    def list_team_players(self, source_team_id: int) -> list[SourcePlayer]:
        """The club's current squad, including players who have not played
        (for ID mapping)."""
