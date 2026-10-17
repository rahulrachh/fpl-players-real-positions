"""`run_sync()` against a fake FPL client and a fake positions source.

Three clubs from the recorded bootstrap (ARS 1, AVL 2, BOU 3; Sofascore 42,
40, 60). BOU v ARS was Sofascore round 3 but rescheduled by FPL into GW5,
next to ARS v BOU, so GW5 is a double gameweek for both clubs.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.engine import make_read_write_engine
from app.db.models import (
    FplClub,
    Gameweek,
    Match,
    PlayerIdMap,
    PlayerMatchPosition,
    SofascorePlayer,
    SyncRun,
)
from app.fpl.schemas import BootstrapStatic, Fixture
from app.mapping.clubs import apply_club_mapping
from app.positions.base import (
    PositionsSource,
    SourceBlockedError,
    SourceMatch,
    SourceNotFoundError,
    SourcePlayer,
    SourcePlayerPosition,
)
from app.sync.service import run_sync

BOOTSTRAP = BootstrapStatic.model_validate(
    json.loads(
        (Path(__file__).parent / "fixtures" / "fpl" / "bootstrap-static.json").read_text(
            encoding="utf-8"
        )
    )
)
ARS, AVL, BOU = 42, 40, 60
NAMES = {ARS: "Arsenal", AVL: "Aston Villa", BOU: "Bournemouth"}
SAKA = SourcePlayer(934235, "Bukayo Saka", "B. Saka", "bukayo-saka", "F")
WATKINS = SourcePlayer(827606, "Ollie Watkins", "O. Watkins", "ollie-watkins", "F")
SEMENYO = SourcePlayer(1002223, "Antoine Semenyo", "A. Semenyo", "antoine-semenyo", "F")
PLAYER = {ARS: SAKA, AVL: WATKINS, BOU: SEMENYO}


def fixture(id, event, team_h, team_a, finished=True) -> Fixture:
    return Fixture(
        id=id,
        event=event,
        team_h=team_h,
        team_a=team_a,
        kickoff_time=None,
        started=finished,
        finished=finished,
        finished_provisional=finished,
    )


def source_match(id, round, home, away, day, status="finished") -> SourceMatch:
    return SourceMatch(
        id=id,
        season_id=96668,
        round=round,
        home_team_id=home,
        home_team_name=NAMES[home],
        away_team_id=away,
        away_team_name=NAMES[away],
        kickoff=datetime(2026, 8, day, 14),
        status=status,
        home_score=1,
        away_score=0,
    )


class FakeFpl:
    def __init__(self, fixtures):
        self.fixtures_list = fixtures

    def bootstrap_static(self):
        return BOOTSTRAP

    def fixtures(self, event=None):
        return self.fixtures_list


class FakeSource(PositionsSource):
    def __init__(self, matches, fail=None):
        self.matches = matches
        self.fail = fail or {}  # match ID -> exception
        self.position_calls: list[int] = []

    def list_round_matches(self, round):
        return [m for m in self.matches if m.round == round]

    def list_team_matches(self, source_team_id, last_n=None):
        matches = [
            m for m in self.matches if source_team_id in (m.home_team_id, m.away_team_id)
        ]
        if last_n is not None:
            matches = [m for m in matches if m.finished][-last_n:]
        return sorted(matches, key=lambda m: m.kickoff)

    def match_positions(self, match_id):
        self.position_calls.append(match_id)
        if match_id in self.fail:
            raise self.fail[match_id]
        match = next(m for m in self.matches if m.id == match_id)
        return [
            SourcePlayerPosition(PLAYER[match.home_team_id], True, 70, 80, 40, None, 75),
            SourcePlayerPosition(PLAYER[match.away_team_id], False, 30, 85, 25, 60, None),
        ]

    def list_team_players(self, source_team_id):
        return [
            PLAYER[source_team_id],
            SourcePlayer(source_team_id * 1000, "Unused Youngster", None, None, "M", source_team_id),
        ]


FIXTURES = [
    fixture(1, 1, 1, 2),  # ARS v AVL
    fixture(2, 2, 2, 3),  # AVL v BOU
    fixture(3, 5, 3, 1),  # BOU v ARS: postponed from GW3, played in GW5
    fixture(4, 5, 1, 3),  # ARS v BOU
    fixture(5, 7, 2, 1, finished=False),  # AVL v ARS: not played yet
]
MATCHES = [
    source_match(101, 1, ARS, AVL, 16),
    source_match(102, 2, AVL, BOU, 23),
    source_match(103, 3, BOU, ARS, 30),
    source_match(104, 5, ARS, BOU, 31),
]


@pytest.fixture
def session(tmp_path):
    engine = make_read_write_engine(tmp_path / "fpl.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def count(session, model, *where):
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_backfill_stores_season_with_fpl_gameweeks(session):
    source = FakeSource(MATCHES)
    summary = run_sync("backfill", session, FakeFpl(FIXTURES), source)

    assert dict(summary.matches_added_by_gw) == {1: 1, 2: 1, 5: 2}
    assert summary.matches_fetched == 4 and summary.positions_stored == 8
    gws = dict(session.execute(select(Match.id, Match.gw)).all())
    assert gws == {101: 1, 102: 2, 103: 5, 104: 5}
    fixtures = dict(session.execute(select(Match.id, Match.fpl_fixture_id)).all())
    assert fixtures == {101: 1, 102: 2, 103: 3, 104: 4}
    # Round 3 match is in FPL GW5: reported, not used.
    assert any("round 3 != FPL GW5" in w for w in summary.warnings)
    assert summary.errors == [] and not summary.blocked

    # Positions carry the match's gw and kickoff, minutes derived.
    row = session.get(PlayerMatchPosition, (103, SEMENYO.id))
    assert (row.gw, row.kickoff, row.minutes) == (5, datetime(2026, 8, 30, 14), 75)
    assert session.get(SofascorePlayer, SAKA.id).sofascore_team_id == ARS

    # GW7 has an unplayed fixture; GW3 / GW4 / GW6 have none.
    assert summary.synced_gameweeks == [1, 2, 5]
    assert session.get(Gameweek, 5).positions_synced
    assert not session.get(Gameweek, 7).positions_synced

    # Squads add players who have not played yet.
    assert session.get(SofascorePlayer, ARS * 1000).sofascore_team_id == ARS
    assert summary.squad_players == 6

    # The mapping ran: Watkins is in the recorded bootstrap, Saka and
    # Semenyo are not (it predates their FPL entries).
    assert summary.mapping.by_method == {"exact": 1}
    assert session.get(PlayerIdMap, 55).sofascore_id == WATKINS.id
    assert summary.unmapped_players == 2

    sync_run = session.scalars(select(SyncRun)).one()
    assert sync_run.trigger == "backfill" and sync_run.finished_at is not None
    assert (sync_run.matches_fetched, sync_run.errors) == (4, [])


def test_double_gameweek_player_has_two_rows(session):
    run_sync("backfill", session, FakeFpl(FIXTURES), FakeSource(MATCHES))
    rows = session.scalars(
        select(PlayerMatchPosition).where(
            PlayerMatchPosition.sofascore_player_id == SAKA.id, PlayerMatchPosition.gw == 5
        )
    ).all()
    assert sorted(r.match_id for r in rows) == [103, 104]


def test_rerun_fetches_nothing(session):
    run_sync("backfill", session, FakeFpl(FIXTURES), FakeSource(MATCHES))
    source = FakeSource(MATCHES)
    summary = run_sync("run", session, FakeFpl(FIXTURES), source)

    assert source.position_calls == []
    assert summary.matches_fetched == 0 and not summary.matches_added_by_gw
    assert count(session, Match) == 4 and count(session, PlayerMatchPosition) == 8
    assert count(session, SyncRun) == 2


def test_run_picks_up_newly_finished_match(session):
    run_sync("backfill", session, FakeFpl(FIXTURES), FakeSource(MATCHES))
    played = [*FIXTURES[:4], fixture(5, 7, 2, 1)]
    source = FakeSource([*MATCHES, source_match(105, 7, AVL, ARS, 31)])
    summary = run_sync("run", session, FakeFpl(played), source)

    assert source.position_calls == [105]
    assert dict(summary.matches_added_by_gw) == {7: 1}
    assert 7 in summary.synced_gameweeks


def test_moved_fixture_updates_both_tables(session):
    # First stored while FPL still had the fixture in GW3.
    before = [*FIXTURES[:2], fixture(3, 3, 3, 1), *FIXTURES[3:]]
    run_sync("backfill", session, FakeFpl(before), FakeSource(MATCHES))
    assert session.get(Match, 103).gw == 3

    summary = run_sync("run", session, FakeFpl(FIXTURES), FakeSource(MATCHES))
    session.expire_all()
    assert session.get(Match, 103).gw == 5
    assert {r.gw for r in session.scalars(select(PlayerMatchPosition).filter_by(match_id=103))} == {5}
    assert any("moved from GW3 to GW5" in w for w in summary.warnings)
    assert summary.matches_fetched == 0


def test_postponed_fixture_without_gameweek_is_skipped(session):
    unscheduled = [*FIXTURES[:2], fixture(3, None, 3, 1, finished=False), *FIXTURES[3:]]
    summary = run_sync("backfill", session, FakeFpl(unscheduled), FakeSource(MATCHES))

    assert session.get(Match, 103) is None
    assert sum("has no gameweek yet" in w for w in summary.warnings) == 1


def test_missing_positions_retried_next_run(session):
    source = FakeSource(MATCHES, fail={102: SourceNotFoundError("GET /event/102: 404")})
    summary = run_sync("backfill", session, FakeFpl(FIXTURES), source)

    assert summary.matches_fetched == 3 and len(summary.errors) == 1
    assert session.get(Match, 102).positions_fetched_at is None
    assert 2 not in summary.synced_gameweeks
    assert session.scalars(select(SyncRun)).one().errors == summary.errors

    source = FakeSource(MATCHES)
    summary = run_sync("run", session, FakeFpl(FIXTURES), source)
    assert source.position_calls == [102]
    assert 2 in summary.synced_gameweeks


def test_blocked_stops_run_and_keeps_earlier_matches(session):
    source = FakeSource(MATCHES, fail={103: SourceBlockedError("403")})
    summary = run_sync("backfill", session, FakeFpl(FIXTURES), source)

    assert summary.blocked and summary.squad_players == 0
    # 101 and 102 were committed before the block; 104 was never tried.
    assert source.position_calls == [101, 102, 103]
    assert count(session, Match, Match.positions_fetched_at.is_not(None)) == 2
    sync_run = session.scalars(select(SyncRun)).one()
    assert sync_run.finished_at is not None and "blocked" in sync_run.errors[0]
    # Mapping is local, so it still ran on what was stored.
    assert summary.mapping is not None


def test_unknown_trigger(session):
    with pytest.raises(ValueError):
        run_sync("nightly", session, FakeFpl(FIXTURES), FakeSource(MATCHES))


def test_club_mapping_reports_unknown_clubs(session):
    session.add_all(
        [FplClub(id=1, name="Arsenal", short_name="ARS"), FplClub(id=2, name="X", short_name="XXX")]
    )
    session.flush()
    assert apply_club_mapping(session) == ["XXX"]
    assert session.get(FplClub, 1).sofascore_team_id == 42
    assert session.get(FplClub, 2).sofascore_team_id is None
