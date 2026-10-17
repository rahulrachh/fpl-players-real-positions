"""Swappable average-positions source adapter (task 06).

Callers use only `get_positions_source()` and the types and errors in
`app.positions.base`; nothing outside this package imports a specific
source. Swapping sources means changing `get_positions_source()`.
"""

from app.positions.base import PositionsSource


def get_positions_source() -> PositionsSource:
    """The configured positions source (Sofascore)."""
    from app.positions.sofascore import get_sofascore_source

    return get_sofascore_source()
