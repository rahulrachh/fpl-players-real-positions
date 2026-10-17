"""League-relative depth: how far forward a player's dot is compared with the
rest of the league. Pure functions on plain data: the pools come from
`app/logic/repository.py`.

Average positions bunch up in midfield (outfield depth runs ~25-80 on the
0-100 frame), so the pitch can draw depth as a rank instead:

- **all**: percentile of the dot's depth (y) among every outfield
  player-match in the database.
- **role**: the same, among player-matches of the player's own FPL role
  only (a forward against forwards).

A player-match counts when the player played at least `POOL_MIN_MINUTES`
(short sub appearances have noisy averages). Goalkeepers are not ranked:
the pitch keeps their real position.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

POOL_MIN_MINUTES = 60
OUTFIELD_ROLES = ("DEF", "MID", "FWD")
PERCENTILE_DECIMALS = 1


@dataclass(frozen=True)
class DepthPools:
    # Sorted depths of every counted outfield player-match, and per role.
    outfield: list[float]
    by_role: dict[str, list[float]]

    @classmethod
    def from_rows(cls, rows: Iterable[tuple[str, float]]) -> "DepthPools":
        """From (FPL role, depth) pairs; goalkeepers are left out."""
        by_role: dict[str, list[float]] = {role: [] for role in OUTFIELD_ROLES}
        for role, y in rows:
            if role in by_role:
                by_role[role].append(y)
        for pool in by_role.values():
            pool.sort()
        return cls(outfield=sorted(y for pool in by_role.values() for y in pool), by_role=by_role)


def percentile(pool: Sequence[float], value: float) -> float | None:
    """Share of `pool` (sorted) below `value`, ties counted half, 0-100.
    None for an empty pool."""
    if not pool:
        return None
    below = bisect_left(pool, value)
    ties = bisect_right(pool, value) - below
    return round(100 * (below + ties / 2) / len(pool), PERCENTILE_DECIMALS)


def rank_depth(pools: DepthPools, role: str, y: float | None) -> tuple[float | None, float | None]:
    """(all, role) percentiles of an outfield dot's depth; (None, None) for a
    goalkeeper or a ghost."""
    if y is None or role not in OUTFIELD_ROLES:
        return None, None
    return percentile(pools.outfield, y), percentile(pools.by_role[role], y)
