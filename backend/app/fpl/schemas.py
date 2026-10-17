"""Typed views of the public FPL API responses, holding only the fields the
app uses (everything else is ignored). Described in `docs/fpl-api.md`.

Money fields are in tenths of £m (1017 = £101.7m), as FPL sends them.
Datetimes are timezone-aware UTC, as FPL sends them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


# --- bootstrap-static/ -------------------------------------------------------


class Event(_Model):
    """A gameweek."""

    id: int
    deadline_time: datetime
    finished: bool
    data_checked: bool
    is_previous: bool
    is_current: bool
    is_next: bool


class Team(_Model):
    """A club."""

    id: int
    name: str
    short_name: str


class ElementType(_Model):
    """A role. FPL's short names are GKP / DEF / MID / FWD."""

    id: int
    singular_name_short: str


class Element(_Model):
    """A player."""

    id: int
    first_name: str
    second_name: str
    web_name: str
    team: int
    element_type: int
    now_cost: int
    # a (available), d (doubtful), i (injured), s (suspended),
    # u (unavailable, e.g. left the club), n (not in squad)
    status: str
    news: str
    # Minutes played this season (all gameweeks so far).
    minutes: int


class BootstrapStatic(_Model):
    events: list[Event]
    teams: list[Team]
    element_types: list[ElementType]
    elements: list[Element]

    @property
    def current_event(self) -> Event | None:
        """The gameweek whose deadline passed most recently (None before GW1)."""
        return next((e for e in self.events if e.is_current), None)

    @property
    def next_event(self) -> Event | None:
        return next((e for e in self.events if e.is_next), None)


# --- fixtures/ ---------------------------------------------------------------


class Fixture(_Model):
    id: int
    # None = not scheduled into a gameweek yet (postponed).
    event: int | None
    team_h: int
    team_a: int
    kickoff_time: datetime | None
    started: bool | None
    finished: bool
    finished_provisional: bool


# --- entry/{id}/ and entry/{id}/history/ -------------------------------------


class Entry(_Model):
    """A manager's team (an "entry")."""

    id: int
    name: str
    player_first_name: str
    player_last_name: str
    # First gameweek the team plays (its first deadline may not have passed).
    started_event: int
    # The game's current gameweek, NOT the team's latest picks: a team that
    # joined for the next gameweek still reports it. Use `entered_events`.
    current_event: int | None
    # Gameweeks whose picks are public (deadline passed). Empty for a team
    # whose first deadline has not passed yet.
    entered_events: list[int]
    # As of the last deadline that passed; None until the team's first one.
    last_deadline_bank: int | None
    last_deadline_value: int | None


class EntryEventHistory(_Model):
    """One gameweek of a team's history (also `entry_history` in picks)."""

    event: int
    points: int
    total_points: int
    bank: int
    # Squad at market prices (`now_cost`, not selling prices) plus bank,
    # as of the end of the gameweek. Verified in `docs/fpl-api.md`.
    value: int
    event_transfers: int
    event_transfers_cost: int
    points_on_bench: int


class ChipPlay(_Model):
    name: str
    event: int


class EntryHistory(_Model):
    current: list[EntryEventHistory]
    chips: list[ChipPlay]


# --- entry/{id}/event/{gw}/picks/ --------------------------------------------


class Pick(_Model):
    element: int
    # 1-11 starting XI (in formation order), 12-15 bench (in sub order).
    position: int
    # 0 = bench, 1 = starter, 2 = captain, 3 = triple captain.
    multiplier: int
    is_captain: bool
    is_vice_captain: bool
    element_type: int


class AutomaticSub(_Model):
    element_in: int
    element_out: int
    event: int


class Picks(_Model):
    # bboost / 3xc / freehit / wildcard / manager; None = no chip.
    active_chip: str | None
    automatic_subs: list[AutomaticSub]
    entry_history: EntryEventHistory
    picks: list[Pick]


# --- event/{gw}/live/ --------------------------------------------------------


class LiveStats(_Model):
    minutes: int
    # The player's FPL points for the gameweek so far (before any captain
    # multiplier).
    total_points: int


class LiveElement(_Model):
    id: int
    stats: LiveStats


class EventLive(_Model):
    elements: list[LiveElement]


# --- event-status/ -----------------------------------------------------------


class EventStatusDay(_Model):
    event: int
    date: str
    bonus_added: bool
    # "r" = points ready, "p" = provisional, "" = not started.
    points: str


class EventStatus(_Model):
    status: list[EventStatusDay]
    # e.g. "Updated", "Updating", "" (league tables).
    leagues: str
