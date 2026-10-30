"""Team loading service: team ID + gameweek → the team's picks for that
gameweek. Described in `docs/fpl-api.md` ("Team loading").

Team data is fetched live from FPL (the database is read-only and holds no
team data). Player and club details are joined from the bundled database,
falling back to the live `bootstrap-static/` for players added since the
last sync.

Results are cached per (team, gameweek): for a long TTL once FPL has checked
the gameweek's points (nothing changes after that), otherwise for the short
FPL TTL. A cache hit makes no FPL call at all.
"""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.cache import TTLCache
from app.config import get_settings
from app.db.models import FplPlayer
from app.fpl.client import FplClient, FplNotFound, FplSchemaError, get_fpl_client
from app.fpl.reference import ROLE_BY_ELEMENT_TYPE
from app.fpl.schemas import BootstrapStatic, Event, Fixture, LiveElement


class TeamError(Exception):
    """A request the service cannot answer for this team and gameweek."""


class TeamNotFound(TeamError):
    """No FPL team has this ID."""


class GameweekOutOfRange(TeamError):
    """The gameweek number is not in the season (1-38)."""


class GameweekBeforeTeamStarted(TeamError):
    """The team joined after this gameweek, so it has no picks for it."""


class GameweekNotStarted(TeamError):
    """The gameweek's deadline has not passed: its picks are still private."""


class GameweekStatus(StrEnum):
    # Deadline not passed.
    UPCOMING = "upcoming"
    # Deadline passed, not every fixture finished.
    IN_PROGRESS = "in_progress"
    # Every fixture finished (points may still be provisional: `data_checked`).
    FINISHED = "finished"


def gameweek_status(event: Event, now: datetime) -> GameweekStatus:
    if event.finished:
        return GameweekStatus.FINISHED
    if now < event.deadline_time:
        return GameweekStatus.UPCOMING
    return GameweekStatus.IN_PROGRESS


# --- response ----------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class Club(_Model):
    id: int
    name: str
    short_name: str


class Player(_Model):
    id: int
    web_name: str
    first_name: str
    second_name: str
    # Current club, also for past gameweeks (as on the FPL website).
    club: Club


class StatPoints(_Model):
    """One line of FPL's points breakdown ("Goals scored 1 → 6")."""

    # FPL's stat identifier (`docs/fpl-api.md`) and its label on the FPL site.
    identifier: str
    label: str
    value: int
    points: int


class PickMatch(_Model):
    """One of the player's matches in the gameweek, with how his points add up."""

    fixture_id: int
    # Club short names. `is_home` / `opponent` are None when the player's
    # current club played in neither side (he has moved since).
    home_club: str
    away_club: str
    is_home: bool | None
    opponent: str | None
    kickoff: datetime | None
    state: Literal["not_started", "live", "finished"]
    # None until kick-off; live while the match is played.
    home_score: int | None
    away_score: int | None
    minutes: int
    # Only the stats that scored or cost points, in FPL's order.
    stats: list[StatPoints]
    # Sum of `stats`: his points from this match.
    points: int


class TeamPick(_Model):
    """One of the 15 picks, as FPL shows them after its automatic subs: an
    auto-subbed starter is on the bench and the bench player who replaced
    them is in the XI (verified, see `docs/fpl-api.md`)."""

    # 1-11 XI in FPL's formation order, 12-15 bench in sub order.
    position: int
    # In the XI after auto-subs (position 1-11).
    starter: bool
    # In the XI the manager picked, before auto-subs.
    picked_starter: bool
    # GK / DEF / MID / FWD, as FPL listed the player in this pick.
    role: str
    # FPL's, after auto-subs: 0 bench, 1 starter (or bench under Bench
    # Boost), 2 captain, 3 triple captain. A captain who did not play gets 0
    # and the vice captain gets the captain's multiplier.
    multiplier: int
    is_captain: bool
    is_vice_captain: bool
    # FPL's automatic substitution: "out" = picked starter who did not play,
    # "in" = bench player who replaced them. None until FPL applies auto-subs.
    auto_sub: Literal["in", "out"] | None
    # The player's own FPL points for the gameweek (live while it is in
    # progress), before the captain multiplier.
    points: int
    # His matches of the gameweek in kick-off order (two in a double
    # gameweek, none in a blank one).
    matches: list[PickMatch]
    player: Player


class AutoSub(_Model):
    player_in: int
    player_out: int


class TeamGameweek(_Model):
    team_id: int
    team_name: str
    manager_name: str
    gameweek: int
    # The team's first gameweek (no picks before it).
    started_event: int
    status: GameweekStatus
    # FPL has checked the points: the gameweek's data is final.
    data_checked: bool
    deadline: datetime
    # bboost / 3xc / freehit / wildcard / manager; None = no chip.
    chip: str | None
    # Tenths of £m, as of the end of the gameweek. `squad_value` includes the
    # bank and uses market prices (see `docs/fpl-api.md`).
    bank: int
    squad_value: int
    # Gameweek points before transfer hits (live while the gameweek is in
    # progress) and the hit taken, as FPL reports them.
    points: int
    transfers_cost: int
    # As picked by the manager.
    captain_id: int
    vice_captain_id: int
    # Whose points are multiplied (FPL multiplier >= 2): the vice when the
    # captain did not play, None if neither did. Until FPL applies
    # auto-subs, the captain.
    effective_captain_id: int | None
    automatic_subs: list[AutoSub]
    picks: list[TeamPick]


# --- service -----------------------------------------------------------------


class TeamService:
    def __init__(
        self,
        client: FplClient,
        finished_ttl_seconds: float,
        short_ttl_seconds: float,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.client = client
        self.short_ttl_seconds = short_ttl_seconds
        self.finished_ttl_seconds = finished_ttl_seconds
        self.cache: TTLCache[TeamGameweek] = TTLCache(short_ttl_seconds)
        self._now = now

    def latest_gameweek(self) -> int | None:
        """The gameweek whose deadline passed most recently: the newest one
        with public picks. None before the GW1 deadline."""
        now = self._now()
        passed = [e.id for e in self.client.bootstrap_static().events if e.deadline_time <= now]
        return max(passed, default=None)

    def last_finished_gameweek(self) -> int | None:
        """The newest gameweek whose fixtures have all finished."""
        finished = [e.id for e in self.client.bootstrap_static().events if e.finished]
        return max(finished, default=None)

    def load_team_gameweek(self, team_id: int, gw: int, session: Session) -> TeamGameweek:
        """Raises a `TeamError` for a request FPL cannot answer, or an
        `FplError` (unavailable / schema changed) if FPL fails."""
        if team_id < 1:
            raise TeamNotFound(f"team {team_id} does not exist")
        key = (team_id, gw)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        result = self._load(team_id, gw, session)
        ttl = self.finished_ttl_seconds if result.data_checked else self.short_ttl_seconds
        self.cache.set(key, result, ttl)
        return result

    def _load(self, team_id: int, gw: int, session: Session) -> TeamGameweek:
        bootstrap = self.client.bootstrap_static()
        event = next((e for e in bootstrap.events if e.id == gw), None)
        if event is None:
            raise GameweekOutOfRange(f"gameweek {gw} is not in the season")
        status = gameweek_status(event, self._now())
        if status is GameweekStatus.UPCOMING:
            raise GameweekNotStarted(f"gameweek {gw} deadline has not passed")

        try:
            entry = self.client.entry(team_id)
        except FplNotFound:
            raise TeamNotFound(f"team {team_id} does not exist") from None
        if gw < entry.started_event:
            raise GameweekBeforeTeamStarted(
                f"team {team_id} started in gameweek {entry.started_event}"
            )
        try:
            picks = self.client.entry_picks(team_id, gw)
        except FplNotFound:
            # Deadline just passed and FPL is not serving the picks yet.
            raise GameweekNotStarted(f"no picks for team {team_id} in gameweek {gw} yet") from None

        players = _players(session, bootstrap, [p.element for p in picks.picks])
        live = {e.id: e for e in self.client.event_live(gw).elements}
        matches = _pick_matches(
            [live[p.element] for p in picks.picks if p.element in live],
            players,
            self._fixtures(gw, live.values()),
            {t.id: t.short_name for t in bootstrap.teams},
        )
        subs_in = {s.element_in for s in picks.automatic_subs}
        subs_out = {s.element_out for s in picks.automatic_subs}
        team_picks = []
        for pick in sorted(picks.picks, key=lambda p: p.position):
            role = ROLE_BY_ELEMENT_TYPE.get(pick.element_type)
            if role is None:
                raise FplSchemaError(f"pick {pick.element} has unknown element_type")
            starter = pick.position <= 11
            team_picks.append(
                TeamPick(
                    position=pick.position,
                    starter=starter,
                    picked_starter=(starter and pick.element not in subs_in)
                    or pick.element in subs_out,
                    role=role,
                    multiplier=pick.multiplier,
                    is_captain=pick.is_captain,
                    is_vice_captain=pick.is_vice_captain,
                    auto_sub="in"
                    if pick.element in subs_in
                    else "out"
                    if pick.element in subs_out
                    else None,
                    points=live[pick.element].stats.total_points if pick.element in live else 0,
                    matches=matches.get(pick.element, []),
                    player=players[pick.element],
                )
            )

        return TeamGameweek(
            team_id=entry.id,
            team_name=entry.name,
            manager_name=f"{entry.player_first_name} {entry.player_last_name}",
            gameweek=gw,
            started_event=entry.started_event,
            status=status,
            data_checked=event.data_checked,
            deadline=event.deadline_time,
            chip=picks.active_chip,
            bank=picks.entry_history.bank,
            squad_value=picks.entry_history.value,
            points=picks.entry_history.points,
            transfers_cost=picks.entry_history.event_transfers_cost,
            captain_id=_one(picks.picks, "is_captain"),
            vice_captain_id=_one(picks.picks, "is_vice_captain"),
            effective_captain_id=next(
                (p.element for p in picks.picks if p.position <= 11 and p.multiplier >= 2),
                None,
            ),
            automatic_subs=[
                AutoSub(player_in=s.element_in, player_out=s.element_out)
                for s in picks.automatic_subs
            ],
            picks=team_picks,
        )


    def _fixtures(self, gw: int, live: Iterable[LiveElement]) -> dict[int, Fixture]:
        """The gameweek's fixtures by ID; the whole season's if a player's
        breakdown names a fixture not listed under this gameweek."""
        fixtures = {f.id: f for f in self.client.fixtures(gw)}
        named = {x.fixture for e in live for x in e.explain}
        if not named <= fixtures.keys():
            fixtures = {f.id: f for f in self.client.fixtures()}
        return fixtures


# Labels as on the FPL site's points breakdown, two shortened for the small
# box (owner); an unknown stat shows its identifier.
STAT_LABELS = {
    "minutes": "Minutes",
    "goals_scored": "Goals scored",
    "assists": "Assists",
    "clean_sheets": "Clean sheets",
    "goals_conceded": "Goals conceded",
    "own_goals": "Own goals",
    "penalties_saved": "Penalties saved",
    "penalties_missed": "Penalties missed",
    "yellow_cards": "Yellow cards",
    "red_cards": "Red cards",
    "saves": "Saves",
    "bonus": "Bonus",
    "defensive_contribution": "Def. Con.",
}


def _match_state(fixture: Fixture) -> Literal["not_started", "live", "finished"]:
    if not fixture.started:
        return "not_started"
    if fixture.finished or fixture.finished_provisional:
        return "finished"
    return "live"


def _pick_matches(
    live: list[LiveElement],
    players: dict[int, Player],
    fixtures: dict[int, Fixture],
    club_names: dict[int, str],
) -> dict[int, list[PickMatch]]:
    """FPL ID → the player's matches, from the `explain` of `event/{gw}/live/`
    joined with the fixture list. A fixture FPL does not list is skipped."""
    result: dict[int, list[PickMatch]] = {}
    for element in live:
        club_id = players[element.id].club.id
        matches = []
        for explain in element.explain:
            fixture = fixtures.get(explain.fixture)
            if fixture is None:
                continue
            is_home = (
                True if fixture.team_h == club_id else False if fixture.team_a == club_id else None
            )
            stats = [
                StatPoints(
                    identifier=s.identifier,
                    label=STAT_LABELS.get(s.identifier, s.identifier),
                    value=s.value,
                    points=s.points,
                )
                for s in explain.stats
                if s.points != 0
            ]
            matches.append(
                PickMatch(
                    fixture_id=fixture.id,
                    home_club=club_names.get(fixture.team_h, "?"),
                    away_club=club_names.get(fixture.team_a, "?"),
                    is_home=is_home,
                    opponent=None
                    if is_home is None
                    else club_names.get(fixture.team_a if is_home else fixture.team_h, "?"),
                    kickoff=fixture.kickoff_time,
                    state=_match_state(fixture),
                    home_score=fixture.team_h_score,
                    away_score=fixture.team_a_score,
                    minutes=next((s.value for s in explain.stats if s.identifier == "minutes"), 0),
                    stats=stats,
                    points=sum(s.points for s in stats),
                )
            )
        far_future = datetime.max.replace(tzinfo=UTC)
        result[element.id] = sorted(matches, key=lambda m: m.kickoff or far_future)
    return result


def _players(session: Session, bootstrap: BootstrapStatic, ids: list[int]) -> dict[int, Player]:
    """Player details from the database; players it does not have yet (signed
    since the last sync) come from the live bootstrap."""
    rows = session.scalars(
        select(FplPlayer).options(joinedload(FplPlayer.club)).where(FplPlayer.id.in_(ids))
    )
    players = {
        p.id: Player(
            id=p.id,
            web_name=p.web_name,
            first_name=p.first_name,
            second_name=p.second_name,
            club=Club(id=p.club.id, name=p.club.name, short_name=p.club.short_name),
        )
        for p in rows
    }
    missing = set(ids) - players.keys()
    if missing:
        clubs = {t.id: t for t in bootstrap.teams}
        for element in bootstrap.elements:
            if element.id in missing and element.team in clubs:
                team = clubs[element.team]
                players[element.id] = Player(
                    id=element.id,
                    web_name=element.web_name,
                    first_name=element.first_name,
                    second_name=element.second_name,
                    club=Club(id=team.id, name=team.name, short_name=team.short_name),
                )
        if not_found := missing - players.keys():
            raise FplSchemaError(f"picked players not in bootstrap-static: {sorted(not_found)}")
    return players


def _one(picks, flag: str) -> int:
    ids = [p.element for p in picks if getattr(p, flag)]
    if len(ids) != 1:
        raise FplSchemaError(f"expected one {flag} pick, got {len(ids)}")
    return ids[0]


@lru_cache
def get_team_service() -> TeamService:
    """Process-wide service (one result cache), on the process-wide client."""
    settings = get_settings()
    return TeamService(
        get_fpl_client(),
        finished_ttl_seconds=settings.fpl_finished_cache_ttl_seconds,
        short_ttl_seconds=settings.fpl_cache_ttl_seconds,
    )
