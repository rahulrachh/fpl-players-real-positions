"""FPL player ↔ Sofascore player auto-matching. FPL and Sofascore share no
player ID, so the link is built from names, only ever between players of
the same club (`fpl_clubs.sofascore_team_id` = `sofascore_players.sofascore_team_id`).

Strategies, tried in order; each pass only sees Sofascore players no earlier
pass claimed:

1. `exact`: full names equal after normalization, in any word order.
2. `short_name`: FPL `web_name` (alone or after the first name) equals the
   Sofascore name or short name ("Sávio", "B.Fernandes" = "B. Fernandes").
3. `surname_initial`: Sofascore short name "G. Magalhães" = FPL first name
   starting with G and "magalhaes" among the FPL surname words. Covers the
   long FPL names ("Gabriel dos Santos Magalhães").
4. `fuzzy`: best rapidfuzz `token_set_ratio` at or above `FUZZY_THRESHOLD`,
   clearly ahead of the runner-up. Always below `LOW_CONFIDENCE`, so every
   fuzzy match is listed for review.

A pass only accepts a player with exactly one candidate. Two FPL players
claiming one Sofascore player in the same pass is a clash: neither gets a
row, both are reported for a manual fix (task 09 overrides).

Overrides (`overrides.py`, `backend/data/player_overrides.csv`) are applied
first and always win: their FPL players and Sofascore IDs are left out of
matching, and a "force no match" override leaves the player without a row.

`player_id_map` is rebuilt on every run, override rows included (the file is
their only source). Rows that come out the same keep their `matched_at`.
"""

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FplClub, FplPlayer, PlayerIdMap, SofascorePlayer
from app.mapping.names import contains_run, initial_and_surname, normalize, order_free, tokens
from app.mapping.overrides import Override, load_overrides

CONFIDENCE = {"override": 1.0, "exact": 1.0, "short_name": 0.95, "surname_initial": 0.9}
# Fuzzy: token_set_ratio (0-100) must reach the threshold and beat the
# second-best candidate by the margin. Confidence = ratio / 100 * scale.
FUZZY_THRESHOLD = 85
FUZZY_MARGIN = 5
FUZZY_CONFIDENCE_SCALE = 0.85
# Matches below this are listed in the coverage report.
LOW_CONFIDENCE = 0.9


@dataclass(frozen=True)
class _Fpl:
    id: int
    full: str  # "first second", normalized
    first: list[str]
    second: list[str]
    web: str
    team_id: int | None

    @classmethod
    def of(cls, p: FplPlayer, team_id: int | None) -> "_Fpl":
        return cls(
            id=p.id,
            full=normalize(f"{p.first_name} {p.second_name}"),
            first=tokens(p.first_name),
            second=tokens(p.second_name),
            web=normalize(p.web_name),
            team_id=team_id,
        )


@dataclass(frozen=True)
class _Sofa:
    id: int
    name: str  # normalized
    short_name: str  # normalized, "" if none
    initial_surname: tuple[str, list[str]] | None

    @classmethod
    def of(cls, p: SofascorePlayer) -> "_Sofa":
        return cls(
            id=p.id,
            name=normalize(p.name),
            short_name=normalize(p.short_name),
            initial_surname=initial_and_surname(p.short_name),
        )


@dataclass(frozen=True)
class Match:
    fpl_id: int
    sofascore_id: int
    method: str
    confidence: float


@dataclass
class MappingResult:
    matches: list[Match] = field(default_factory=list)  # auto-matches only
    # FPL ID -> why it has no row (only players the run tried to match).
    unmatched: dict[int, str] = field(default_factory=dict)
    # (Sofascore ID, FPL IDs claiming it), for a manual fix.
    clashes: list[tuple[int, list[int]]] = field(default_factory=list)
    # Overrides written as rows / forcing no row / not applicable (with why).
    overrides_applied: list[Override] = field(default_factory=list)
    forced_no_match: list[Override] = field(default_factory=list)
    overrides_skipped: list[tuple[Override, str]] = field(default_factory=list)
    added: int = 0
    changed: int = 0
    removed: int = 0

    @property
    def by_method(self) -> Counter:
        return Counter(m.method for m in self.matches)


def run_player_mapping(
    session: Session, now: datetime | None = None, overrides: list[Override] | None = None
) -> MappingResult:
    """Apply the overrides (default: the override file), match every other
    FPL player and rebuild `player_id_map`. Flushes, caller commits."""
    result = MappingResult()
    if overrides is None:
        overrides = load_overrides()
    overridden_fpl, taken_sofa = _apply_overrides(session, overrides, result)

    team_by_club = dict(session.execute(select(FplClub.id, FplClub.sofascore_team_id)).all())
    fpl_players = [
        _Fpl.of(p, team_by_club.get(p.club_id))
        for p in session.scalars(select(FplPlayer).order_by(FplPlayer.id))
        if p.id not in overridden_fpl
    ]
    pool: dict[int, list[_Sofa]] = defaultdict(list)
    for s in session.scalars(select(SofascorePlayer).order_by(SofascorePlayer.id)):
        if s.id not in taken_sofa and s.sofascore_team_id is not None:
            pool[s.sofascore_team_id].append(_Sofa.of(s))

    todo: list[_Fpl] = []
    for player in fpl_players:
        if player.team_id is None:
            result.unmatched[player.id] = "club has no Sofascore team ID"
        else:
            todo.append(player)

    ambiguous: dict[int, list[int]] = {}
    for method, find in _STRATEGIES:
        proposals: dict[int, list[tuple[int, float]]] = defaultdict(list)  # Sofascore ID -> claims
        for player in todo:
            candidates = find(player, pool[player.team_id])
            if len(candidates) == 1:
                sofa, confidence = candidates[0]
                proposals[sofa.id].append((player.id, confidence))
            elif len(candidates) > 1:
                ambiguous.setdefault(player.id, [c.id for c, _ in candidates])

        done: set[int] = set()
        for sofa_id, claims in proposals.items():
            fpl_ids = [fpl_id for fpl_id, _ in claims]
            if len(claims) == 1:
                fpl_id, confidence = claims[0]
                result.matches.append(Match(fpl_id, sofa_id, method, confidence))
            else:
                result.clashes.append((sofa_id, fpl_ids))
                for fpl_id in fpl_ids:
                    result.unmatched[fpl_id] = f"clash: Sofascore {sofa_id} also claimed by " + (
                        ", ".join(f"FPL {o}" for o in fpl_ids if o != fpl_id)
                    )
            done.update(fpl_ids)
            # A contested Sofascore player is out of later passes too.
            for players in pool.values():
                players[:] = [s for s in players if s.id != sofa_id]
        todo = [p for p in todo if p.id not in done]

    for player in todo:
        if player.id in ambiguous:
            ids = ", ".join(map(str, ambiguous[player.id]))
            result.unmatched[player.id] = f"ambiguous: Sofascore {ids}"
        else:
            result.unmatched[player.id] = "no candidate at the club"

    _write(session, result, now or _utcnow())
    return result


def _apply_overrides(
    session: Session, overrides: list[Override], result: MappingResult
) -> tuple[set[int], set[int]]:
    """Sort the overrides into applied / forced no match / skipped. Returns the
    FPL IDs kept out of auto-matching and the Sofascore IDs taken."""
    fpl_ids = set(session.scalars(select(FplPlayer.id)))
    sofa_ids = set(session.scalars(select(SofascorePlayer.id)))
    overridden_fpl: set[int] = set()
    taken_sofa: set[int] = set()
    for o in overrides:
        if o.fpl_id not in fpl_ids:
            result.overrides_skipped.append((o, "FPL player not in the database"))
            continue
        overridden_fpl.add(o.fpl_id)
        if o.sofascore_id is None:
            result.forced_no_match.append(o)
            result.unmatched[o.fpl_id] = "override: forced no match"
        elif o.sofascore_id not in sofa_ids:
            # Not auto-matched either: the file says who he is.
            why = f"Sofascore {o.sofascore_id} not in the database yet"
            result.overrides_skipped.append((o, why))
            result.unmatched[o.fpl_id] = f"override: {why}"
        else:
            result.overrides_applied.append(o)
            taken_sofa.add(o.sofascore_id)
    return overridden_fpl, taken_sofa


# --- strategies ------------------------------------------------------------
# Each returns the candidates (with confidence) for one FPL player among the
# unclaimed Sofascore players of his club.

_Candidates = list[tuple[_Sofa, float]]


def _exact(p: _Fpl, pool: list[_Sofa]) -> _Candidates:
    key = order_free(p.full)
    return [(s, CONFIDENCE["exact"]) for s in pool if order_free(s.name) == key]


def _short_name(p: _Fpl, pool: list[_Sofa]) -> _Candidates:
    keys = {order_free(p.web), order_free(f"{' '.join(p.first)} {p.web}")}
    return [
        (s, CONFIDENCE["short_name"])
        for s in pool
        if order_free(s.name) in keys or (s.short_name and order_free(s.short_name) in keys)
    ]


def _surname_initial(p: _Fpl, pool: list[_Sofa]) -> _Candidates:
    if not p.first:
        return []
    found = []
    for s in pool:
        if s.initial_surname is None:
            continue
        initial, surname = s.initial_surname
        if p.first[0][0] == initial and contains_run(p.second, surname):
            found.append((s, CONFIDENCE["surname_initial"]))
    return found


def _fuzzy(p: _Fpl, pool: list[_Sofa]) -> _Candidates:
    fpl_names = {p.full, f"{' '.join(p.first)} {p.web}"}
    scored = sorted(
        ((max(fuzz.token_set_ratio(n, s.name) for n in fpl_names), s) for s in pool),
        key=lambda pair: -pair[0],
    )
    if not scored or scored[0][0] < FUZZY_THRESHOLD:
        return []
    best_score, best = scored[0]
    runners_up = [s for score, s in scored[1:] if score > best_score - FUZZY_MARGIN]
    if runners_up:
        # Too close to call: report all of them.
        return [(s, 0.0) for s in (best, *runners_up)]
    return [(best, round(best_score / 100 * FUZZY_CONFIDENCE_SCALE, 3))]


_STRATEGIES: list[tuple[str, Callable[[_Fpl, list[_Sofa]], _Candidates]]] = [
    ("exact", _exact),
    ("short_name", _short_name),
    ("surname_initial", _surname_initial),
    ("fuzzy", _fuzzy),
]


# --- write -----------------------------------------------------------------


def _write(session: Session, result: MappingResult, now: datetime) -> None:
    existing = {row.fpl_id: row for row in session.scalars(select(PlayerIdMap))}
    wanted = {m.fpl_id: m for m in result.matches}
    for o in result.overrides_applied:
        wanted[o.fpl_id] = Match(o.fpl_id, o.sofascore_id, "override", CONFIDENCE["override"])
    # Delete first, so a Sofascore ID moving between players never trips the
    # UNIQUE mid-flush.
    for fpl_id, row in existing.items():
        match = wanted.get(fpl_id)
        if match is None or (row.sofascore_id, row.match_method) != (
            match.sofascore_id,
            match.method,
        ):
            session.delete(row)
            if match is None:
                result.removed += 1
            else:
                result.changed += 1
    session.flush()
    for fpl_id, match in wanted.items():
        row = existing.get(fpl_id)
        if row is not None and (row.sofascore_id, row.match_method) == (
            match.sofascore_id,
            match.method,
        ):
            row.match_confidence = match.confidence
            continue
        if row is None:
            result.added += 1
        session.add(
            PlayerIdMap(
                fpl_id=fpl_id,
                sofascore_id=match.sofascore_id,
                match_method=match.method,
                match_confidence=match.confidence,
                is_override=match.method == "override",
                matched_at=now,
            )
        )
    session.flush()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
