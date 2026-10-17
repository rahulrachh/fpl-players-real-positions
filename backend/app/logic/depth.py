"""League-relative depth: how far forward a player's dot is compared with the
rest of the league. Pure functions on plain data: the pool comes from
`app/logic/repository.py`.

Average positions bunch up in midfield (outfield depth runs ~25-80 on the
0-100 frame), so the pitch draws depth as a rank instead: the percentile of
the dot's depth (y) among every outfield player-match in the database,
defenders, midfielders and forwards together.

A player-match counts when the player played at least `POOL_MIN_MINUTES`
(short sub appearances have noisy averages). Goalkeepers are not ranked:
the pitch keeps their real position.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Sequence

POOL_MIN_MINUTES = 60
OUTFIELD_ROLES = ("DEF", "MID", "FWD")
PERCENTILE_DECIMALS = 1


def outfield_pool(rows: Iterable[tuple[str, float]]) -> list[float]:
    """Sorted depths from (FPL role, depth) pairs; goalkeepers are left out."""
    return sorted(y for role, y in rows if role in OUTFIELD_ROLES)


def percentile(pool: Sequence[float], value: float) -> float | None:
    """Share of `pool` (sorted) below `value`, ties counted half, 0-100.
    None for an empty pool."""
    if not pool:
        return None
    below = bisect_left(pool, value)
    ties = bisect_right(pool, value) - below
    return round(100 * (below + ties / 2) / len(pool), PERCENTILE_DECIMALS)


def rank_depth(pool: Sequence[float], role: str, y: float | None) -> float | None:
    """Percentile of an outfield dot's depth; None for a goalkeeper or a ghost."""
    if y is None or role not in OUTFIELD_ROLES:
        return None
    return percentile(pool, y)
