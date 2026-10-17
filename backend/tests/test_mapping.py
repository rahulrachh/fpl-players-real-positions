"""Player ID auto-matching (`app/mapping/`) on small hand-built clubs.

Names are real cases from the 2026/27 data: FPL's long legal names
("Gabriel dos Santos Magalhães"), one-name players ("Sávio"), reversed
web names ("B.Fernandes", "Tóth.A") and letters NFKD does not strip (Ø, ß, ı).
"""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.engine import make_read_write_engine
from app.db.models import FplClub, FplPlayer, PlayerIdMap, SofascorePlayer
from app.mapping.names import initial_and_surname, normalize, order_free
from app.mapping.players import LOW_CONFIDENCE, run_player_mapping
from app.mapping.report import coverage, render_report

ARS, TOT, NOCLUB = 1, 2, 3
SOFA_TEAM = {ARS: 42, TOT: 33}
T0 = datetime(2026, 10, 1)


@pytest.fixture
def session(tmp_path):
    engine = make_read_write_engine(tmp_path / "fpl.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(
            [
                FplClub(id=ARS, name="Arsenal", short_name="ARS", sofascore_team_id=42),
                FplClub(id=TOT, name="Spurs", short_name="TOT", sofascore_team_id=33),
                FplClub(id=NOCLUB, name="Promoted", short_name="PRO"),
            ]
        )
        s.flush()
        yield s
    engine.dispose()


def fpl(s, id, first, second, web, club=ARS, minutes=90):
    s.add(
        FplPlayer(
            id=id,
            first_name=first,
            second_name=second,
            web_name=web,
            club_id=club,
            role="MID",
            price=50,
            status="a",
            minutes=minutes,
        )
    )


def sofa(s, id, name, short_name=None, club=ARS):
    s.add(SofascorePlayer(id=id, name=name, short_name=short_name, sofascore_team_id=SOFA_TEAM.get(club)))


def mapped(s) -> dict[int, tuple[int, str]]:
    return {r.fpl_id: (r.sofascore_id, r.match_method) for r in s.scalars(select(PlayerIdMap))}


# --- names -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Martin Ødegaard", "martin odegaard"),
        ("Pascal Groß", "pascal gross"),
        ("Altay Bayındır", "altay bayindir"),
        ("Benjamin Šeško", "benjamin sesko"),
        ("Myles Lewis-Skelly", "myles lewis skelly"),
        ("Jun'ai Byfield", "junai byfield"),
        ("B.Fernandes", "b fernandes"),
        ("  Jan Paul   van Hecke ", "jan paul van hecke"),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_name_order_does_not_matter():
    assert order_free("Son Heung-min") == order_free("Heung-Min Son")
    assert order_free("Tóth.A") == order_free("A. Tóth")


def test_initial_and_surname():
    assert initial_and_surname("G. Magalhães") == ("g", ["magalhaes"])
    assert initial_and_surname("J. P. van Hecke") == ("j", ["van", "hecke"])
    assert initial_and_surname("Richarlison") is None


# --- strategies ------------------------------------------------------------


def test_each_strategy(session):
    fpl(session, 1, "Martin", "Ødegaard", "Ødegaard")
    sofa(session, 101, "Martin Ødegaard", "M. Ødegaard")
    fpl(session, 2, "Sávio", "Moreira de Oliveira", "Sávio", club=TOT)
    sofa(session, 102, "Sávio", "Sávio", club=TOT)
    fpl(session, 3, "Bruno", "Borges Fernandes", "B.Fernandes")
    sofa(session, 103, "Bruno Fernandes", "B. Fernandes")
    fpl(session, 4, "Gabriel", "dos Santos Magalhães", "Gabriel")
    sofa(session, 104, "Gabriel Magalhães", "G. Magalhães")
    fpl(session, 5, "Jaden", "Philogene", "Philogene")
    sofa(session, 105, "Jaden Philogene-Bidace", "J. Philogene-Bidace")
    fpl(session, 6, "Heung-Min", "Son", "Son", club=TOT)
    sofa(session, 106, "Son Heung-min", "H. Son", club=TOT)
    session.flush()

    result = run_player_mapping(session, now=T0)

    assert mapped(session) == {
        1: (101, "exact"),
        2: (102, "short_name"),
        3: (103, "short_name"),
        4: (104, "surname_initial"),
        5: (105, "fuzzy"),
        6: (106, "exact"),
    }
    assert result.unmatched == {} and result.clashes == []
    fuzzy = session.get(PlayerIdMap, 5)
    assert 0 < fuzzy.match_confidence < LOW_CONFIDENCE
    assert session.get(PlayerIdMap, 1).match_confidence == 1.0


def test_candidates_restricted_to_the_club(session):
    fpl(session, 1, "Ben", "Davies", "Davies", club=ARS)
    sofa(session, 101, "Ben Davies", "B. Davies", club=TOT)
    fpl(session, 2, "Tom", "New", "New", club=NOCLUB)
    session.flush()

    result = run_player_mapping(session, now=T0)

    assert mapped(session) == {}
    assert result.unmatched == {
        1: "no candidate at the club",
        2: "club has no Sofascore team ID",
    }


def test_two_players_with_one_surname_are_not_guessed(session):
    # "Fletcher" fits both Sofascore Fletchers at surname level: no match.
    fpl(session, 1, "J", "Fletcher", "Fletcher")
    sofa(session, 101, "Jack Fletcher", "J. Fletcher")
    sofa(session, 102, "Jamie Fletcher", "J. Fletcher")
    session.flush()

    result = run_player_mapping(session, now=T0)

    assert mapped(session) == {}
    assert result.unmatched[1].startswith("ambiguous")


def test_clash_is_reported_not_resolved(session):
    # Two FPL entries for one player (e.g. a duplicate after a transfer).
    fpl(session, 1, "Eberechi", "Eze", "Eze")
    fpl(session, 2, "Eberechi", "Eze", "Eze", minutes=0)
    sofa(session, 101, "Eberechi Eze", "E. Eze")
    session.flush()

    result = run_player_mapping(session, now=T0)

    assert mapped(session) == {}
    assert result.clashes == [(101, [1, 2])]
    assert "clash" in result.unmatched[1] and "FPL 2" in result.unmatched[1]


def test_earlier_strategy_wins_over_later(session):
    # Exact "Ben White" takes the player; the other White does not clash.
    fpl(session, 1, "Ben", "White", "White")
    fpl(session, 2, "Benjamin", "White", "B.White")
    sofa(session, 101, "Ben White", "B. White")
    session.flush()

    result = run_player_mapping(session, now=T0)

    assert mapped(session) == {1: (101, "exact")}
    assert result.clashes == []
    assert 2 in result.unmatched


# --- rebuild ---------------------------------------------------------------


def test_rerun_is_idempotent_and_keeps_matched_at(session):
    fpl(session, 1, "Bukayo", "Saka", "Saka")
    sofa(session, 101, "Bukayo Saka", "B. Saka")
    session.flush()
    run_player_mapping(session, now=T0)

    result = run_player_mapping(session, now=datetime(2026, 10, 8))

    assert (result.added, result.changed, result.removed) == (0, 0, 0)
    assert session.get(PlayerIdMap, 1).matched_at == T0


def test_rerun_rebuilds_changed_rows(session):
    fpl(session, 1, "Bukayo", "Saka", "Saka")
    fpl(session, 2, "Declan", "Rice", "Rice")
    sofa(session, 101, "Bukayo Saka", "B. Saka")
    sofa(session, 102, "Declan Rice", "D. Rice")
    session.flush()
    run_player_mapping(session, now=T0)

    # Rice moves to Spurs on FPL only: his old row goes.
    session.get(FplPlayer, 2).club_id = TOT
    session.flush()
    result = run_player_mapping(session, now=T0)

    assert mapped(session) == {1: (101, "exact")}
    assert result.removed == 1


def test_overrides_are_never_touched(session):
    fpl(session, 1, "Bukayo", "Saka", "Saka")
    fpl(session, 2, "Bukayo", "Saka", "Saka.B")  # would claim 101 too
    sofa(session, 101, "Bukayo Saka", "B. Saka")
    sofa(session, 102, "Someone Else")
    session.flush()
    session.add(
        PlayerIdMap(
            fpl_id=1,
            sofascore_id=102,
            match_method="override",
            match_confidence=1.0,
            is_override=True,
            matched_at=T0,
        )
    )
    session.flush()

    result = run_player_mapping(session, now=datetime(2026, 10, 8))

    # The override stays; FPL 2 is matched alone, no clash with FPL 1.
    assert mapped(session) == {1: (102, "override"), 2: (101, "exact")}
    assert result.overrides_kept == 1 and result.clashes == []
    assert session.get(PlayerIdMap, 1).matched_at == T0


# --- report ----------------------------------------------------------------


def test_coverage_counts_active_players(session):
    fpl(session, 1, "Bukayo", "Saka", "Saka", minutes=540)
    fpl(session, 2, "Max", "Dowman", "Dowman", minutes=0)
    fpl(session, 3, "Ethan", "Nwaneri", "Nwaneri", minutes=12)
    sofa(session, 101, "Bukayo Saka", "B. Saka")
    session.flush()

    result = run_player_mapping(session, now=T0)
    cov = coverage(session)

    assert (cov.players, cov.matched, cov.active, cov.active_matched) == (3, 1, 2, 1)
    assert cov.active_pct == 50.0
    report = render_report(session, result, T0)
    assert "| Active players | 2 | 1 | 50.0% |" in report
    assert "## Unmatched active players (1)" in report and "Nwaneri" in report
    assert "## Unmatched inactive players (1)" in report
