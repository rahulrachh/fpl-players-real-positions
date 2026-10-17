"""Offline sync: the only code that writes match and position data. Runs on
the owner's machine (`python -m app.sync run|backfill`); the website never
calls the positions source. Steps, in order:

1. Refresh FPL reference data (clubs, players, gameweeks) and the club
   mapping (`app/mapping/clubs.py`).
2. Re-read FPL's fixtures and move stored matches whose fixture changed
   gameweek (a rescheduled match lands in the gameweek it is played in).
3. List each club's finished league matches from the source (last 3 for
   `run`, the whole season for `backfill`) and store new ones. The gameweek
   always comes from the FPL fixture with the same (home, away) clubs, never
   from the source's round.
4. Fetch positions for every stored match without them, one commit per match.
5. Mark gameweeks whose matches all have positions as `positions_synced`.
6. Refresh squad lists (players who have not played yet).
7. Rebuild the player ID mapping (`app/mapping/players.py`), also after a
   block, since it only reads the local database.
8. Close the `sync_runs` row.

Idempotent: a re-run fetches nothing already stored. A 403 stops the run;
other source failures are recorded and the match is retried next run.
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    FplClub,
    Gameweek,
    Match,
    PlayerIdMap,
    PlayerMatchPosition,
    SofascorePlayer,
    SyncRun,
)
from app.fpl.client import FplClient
from app.fpl.reference import refresh_fpl_reference_data
from app.fpl.schemas import Fixture
from app.mapping.clubs import apply_club_mapping
from app.mapping.players import MappingResult, run_player_mapping
from app.positions.base import (
    PositionsSource,
    PositionsSourceError,
    SourceBlockedError,
    SourceMatch,
    SourcePlayer,
)

log = logging.getLogger(__name__)

# Finished matches per club listed by a regular `run`.
RUN_LAST_N = 3


@dataclass
class SyncSummary:
    trigger: str
    run_id: int | None = None
    # New matches stored, per FPL gameweek.
    matches_added_by_gw: Counter = field(default_factory=Counter)
    # Matches whose positions were downloaded this run.
    matches_fetched: int = 0
    positions_stored: int = 0
    squad_players: int = 0
    # Player ID mapping rebuilt at the end of the run (task 08).
    mapping: MappingResult | None = None
    # Sofascore players with positions but no FPL mapping.
    unmapped_players: int = 0
    synced_gameweeks: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    blocked: bool = False
    duration_seconds: float = 0.0

    def warn(self, message: str) -> None:
        # Both clubs of an unlinked match report it; keep one copy.
        if message in self.warnings:
            return
        log.warning(message)
        self.warnings.append(message)

    def error(self, message: str) -> None:
        log.error(message)
        self.errors.append(message)


def run_sync(
    trigger: str,
    session: Session,
    fpl: FplClient,
    source: PositionsSource,
    clock=time.monotonic,
) -> SyncSummary:
    """Run one sync on a read-write session. Commits as it goes."""
    if trigger not in ("run", "backfill"):
        raise ValueError(f"unknown trigger {trigger!r}")
    started = clock()
    summary = SyncSummary(trigger)
    sync_run = SyncRun(started_at=_utcnow(), trigger=trigger, matches_fetched=0, errors=[])
    session.add(sync_run)
    session.commit()
    summary.run_id = sync_run.id

    try:
        try:
            _sync_source_data(session, fpl, source, trigger, summary)
        except SourceBlockedError as exc:
            session.rollback()
            summary.blocked = True
            summary.error(f"blocked by the positions source, run stopped: {exc}")
        # Local only, so it also runs after a block (matches stored so far).
        _map_players(session, summary)
    except Exception as exc:
        session.rollback()
        summary.error(f"sync failed: {exc!r}")
        _close_run(session, sync_run, summary, started, clock)
        raise
    _close_run(session, sync_run, summary, started, clock)
    return summary


def _sync_source_data(
    session: Session,
    fpl: FplClient,
    source: PositionsSource,
    trigger: str,
    summary: SyncSummary,
) -> None:
    refresh_fpl_reference_data(session, fpl)
    for short_name in apply_club_mapping(session):
        summary.warn(f"club {short_name} has no Sofascore team ID: matches skipped")
    session.commit()

    fixtures = fpl.fixtures()
    _move_rescheduled(session, fixtures, summary)
    session.commit()

    _store_new_matches(session, source, fixtures, trigger, summary)
    _fetch_positions(session, source, summary)
    _mark_synced_gameweeks(session, fixtures, summary)
    session.commit()

    if not summary.blocked:
        _refresh_squads(session, source, summary)


# --- steps -----------------------------------------------------------------


def _move_rescheduled(session: Session, fixtures: list[Fixture], summary: SyncSummary) -> None:
    """Stored matches follow their FPL fixture into its current gameweek."""
    by_id = {f.id: f for f in fixtures}
    for match in session.scalars(select(Match).where(Match.fpl_fixture_id.is_not(None))):
        fixture = by_id.get(match.fpl_fixture_id)
        if fixture is None or fixture.event is None or fixture.event == match.gw:
            continue
        summary.warn(
            f"match {match.id}: FPL fixture {fixture.id} moved from GW{match.gw} "
            f"to GW{fixture.event}"
        )
        match.gw = fixture.event
        session.execute(
            update(PlayerMatchPosition)
            .where(PlayerMatchPosition.match_id == match.id)
            .values(gw=fixture.event)
        )


def _store_new_matches(
    session: Session,
    source: PositionsSource,
    fixtures: list[Fixture],
    trigger: str,
    summary: SyncSummary,
) -> None:
    clubs = session.scalars(
        select(FplClub).where(FplClub.sofascore_team_id.is_not(None)).order_by(FplClub.id)
    ).all()
    club_by_source_id = {c.sofascore_team_id: c for c in clubs}
    # One home fixture per (home, away) pair per season.
    fixture_by_pair = {(f.team_h, f.team_a): f for f in fixtures}
    stored = set(session.scalars(select(Match.id)))
    last_n = RUN_LAST_N if trigger == "run" else None

    for club in clubs:
        for source_match in source.list_team_matches(club.sofascore_team_id, last_n=last_n):
            # One match covers both clubs: the second club sees it stored.
            if source_match.id in stored or not source_match.finished:
                continue
            match = _link_match(source_match, club_by_source_id, fixture_by_pair, summary)
            if match is None:
                continue
            session.add(match)
            session.commit()
            stored.add(match.id)
            summary.matches_added_by_gw[match.gw] += 1


def _link_match(
    source_match: SourceMatch,
    club_by_source_id: dict[int, FplClub],
    fixture_by_pair: dict[tuple[int, int], Fixture],
    summary: SyncSummary,
) -> Match | None:
    """A new `matches` row with its FPL fixture and gameweek, or None (with
    a warning) when it cannot be linked yet."""
    label = (
        f"match {source_match.id} ({source_match.home_team_name} v "
        f"{source_match.away_team_name}, {source_match.kickoff:%Y-%m-%d})"
    )
    home = club_by_source_id.get(source_match.home_team_id)
    away = club_by_source_id.get(source_match.away_team_id)
    if home is None or away is None:
        summary.warn(f"{label}: a Sofascore team is not mapped to an FPL club, skipped")
        return None
    fixture = fixture_by_pair.get((home.id, away.id))
    if fixture is None:
        summary.warn(f"{label}: no FPL fixture {home.short_name} v {away.short_name}, skipped")
        return None
    if fixture.event is None:
        summary.warn(f"{label}: FPL fixture {fixture.id} has no gameweek yet, skipped")
        return None
    if source_match.round != fixture.event:
        summary.warn(
            f"{label}: Sofascore round {source_match.round} != FPL GW{fixture.event} "
            f"(fixture {fixture.id}), using GW{fixture.event}"
        )
    return Match(
        id=source_match.id,
        fpl_fixture_id=fixture.id,
        gw=fixture.event,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff=source_match.kickoff,
        finished=True,
    )


def _fetch_positions(session: Session, source: PositionsSource, summary: SyncSummary) -> None:
    pending = session.scalars(
        select(Match)
        .where(Match.finished.is_(True), Match.positions_fetched_at.is_(None))
        .order_by(Match.kickoff, Match.id)
    ).all()
    for match in pending:
        source_team = {
            True: session.get(FplClub, match.home_club_id).sofascore_team_id,
            False: session.get(FplClub, match.away_club_id).sofascore_team_id,
        }
        try:
            positions = source.match_positions(match.id)
        except SourceBlockedError:
            raise
        except PositionsSourceError as exc:
            summary.error(f"match {match.id} (GW{match.gw}): positions not stored: {exc}")
            continue
        if not positions:
            summary.warn(f"match {match.id} (GW{match.gw}): no positions yet, retried next run")
            continue

        # Replace, so a partially stored match can never keep stale rows.
        session.query(PlayerMatchPosition).filter_by(match_id=match.id).delete()
        for pos in positions:
            _upsert_player(session, pos.player, source_team[pos.is_home])
            session.add(
                PlayerMatchPosition(
                    match_id=match.id,
                    sofascore_player_id=pos.player.id,
                    avg_x=pos.x,
                    avg_y=pos.y,
                    points_count=pos.points_count,
                    sub_on_minute=pos.sub_on_minute,
                    sub_off_minute=pos.sub_off_minute,
                    kickoff=match.kickoff,
                    gw=match.gw,
                )
            )
        match.positions_fetched_at = _utcnow()
        session.commit()
        summary.matches_fetched += 1
        summary.positions_stored += len(positions)


def _mark_synced_gameweeks(
    session: Session, fixtures: list[Fixture], summary: SyncSummary
) -> None:
    """A gameweek is synced when each of its FPL fixtures is finished and its
    match has positions. Recomputed every run: a fixture moved in later
    unsets it again."""
    fetched = set(
        session.scalars(
            select(Match.fpl_fixture_id).where(Match.positions_fetched_at.is_not(None))
        )
    )
    by_gw: dict[int, list[Fixture]] = {}
    for fixture in fixtures:
        if fixture.event is not None:
            by_gw.setdefault(fixture.event, []).append(fixture)
    for gameweek in session.scalars(select(Gameweek)):
        gw_fixtures = by_gw.get(gameweek.id, [])
        gameweek.positions_synced = bool(gw_fixtures) and all(
            f.finished and f.id in fetched for f in gw_fixtures
        )
        if gameweek.positions_synced:
            summary.synced_gameweeks.append(gameweek.id)
    summary.synced_gameweeks.sort()


def _refresh_squads(session: Session, source: PositionsSource, summary: SyncSummary) -> None:
    team_ids = session.scalars(
        select(FplClub.sofascore_team_id)
        .where(FplClub.sofascore_team_id.is_not(None))
        .order_by(FplClub.id)
    ).all()
    for team_id in team_ids:
        try:
            players = source.list_team_players(team_id)
        except SourceBlockedError:
            raise
        except PositionsSourceError as exc:
            summary.error(f"squad of Sofascore team {team_id} not refreshed: {exc}")
            continue
        for player in players:
            _upsert_player(session, player, player.team_id or team_id)
        session.commit()
        summary.squad_players += len(players)


def _upsert_player(session: Session, player: SourcePlayer, team_id: int | None) -> None:
    row = session.get(SofascorePlayer, player.id) or SofascorePlayer(id=player.id)
    row.name = player.name
    row.short_name = player.short_name
    row.slug = player.slug
    if team_id is not None:
        row.sofascore_team_id = team_id
    session.add(row)
    session.flush()


def _map_players(session: Session, summary: SyncSummary) -> None:
    summary.mapping = run_player_mapping(session)
    session.commit()
    for sofa_id, fpl_ids in summary.mapping.clashes:
        summary.warn(
            f"player mapping clash: Sofascore {sofa_id} claimed by FPL "
            f"{', '.join(map(str, fpl_ids))}, none mapped"
        )
    summary.unmapped_players = _count_unmapped(session)


def _count_unmapped(session: Session) -> int:
    return session.scalar(
        select(func.count(func.distinct(PlayerMatchPosition.sofascore_player_id))).where(
            PlayerMatchPosition.sofascore_player_id.not_in(select(PlayerIdMap.sofascore_id))
        )
    )


def _close_run(session, sync_run: SyncRun, summary: SyncSummary, started, clock) -> None:
    summary.duration_seconds = clock() - started
    sync_run = session.merge(sync_run)
    sync_run.finished_at = _utcnow()
    sync_run.matches_fetched = summary.matches_fetched
    sync_run.errors = list(summary.errors)
    session.commit()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
