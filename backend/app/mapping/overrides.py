"""Manual player ID overrides: `backend/data/player_overrides.csv`.

Columns `fpl_id,sofascore_id,comment`, one row per FPL player:

- `sofascore_id` set: map the FPL player to that Sofascore player
  (`match_method = override`), whatever auto-matching would do.
- `sofascore_id` empty: force no match; the player gets no row.

The file is the only source of override rows: `run_player_mapping()` applies
it on every run, so deleting a line hands the player back to auto-matching.
A malformed file (bad header, non-integer ID, an FPL or Sofascore ID listed
twice) raises `OverrideFileError` before anything is written.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from app.config import BACKEND_DIR

OVERRIDES_PATH = BACKEND_DIR / "data" / "player_overrides.csv"
COLUMNS = ["fpl_id", "sofascore_id", "comment"]


class OverrideFileError(ValueError):
    pass


@dataclass(frozen=True)
class Override:
    fpl_id: int
    sofascore_id: int | None  # None = force no match
    comment: str


def load_overrides(path: Path | None = None) -> list[Override]:
    """Parse the override file (default `OVERRIDES_PATH`). A missing file
    means no overrides."""
    path = path or OVERRIDES_PATH
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = [c.strip() for c in next(reader, [])]
        if header != COLUMNS:
            raise OverrideFileError(f"{path.name}: header must be {','.join(COLUMNS)}, got {header}")
        overrides: list[Override] = []
        seen_fpl: set[int] = set()
        seen_sofa: set[int] = set()
        for line, row in enumerate(reader, start=2):
            if not any(c.strip() for c in row):
                continue
            if len(row) > len(COLUMNS):
                raise OverrideFileError(f"{path.name}:{line}: too many columns (quote commas in comments)")
            fpl_raw, sofa_raw, comment = (row + ["", ""])[:3]
            fpl_id = _int(fpl_raw, path, line, "fpl_id")
            sofa_id = _int(sofa_raw, path, line, "sofascore_id") if sofa_raw.strip() else None
            if fpl_id in seen_fpl:
                raise OverrideFileError(f"{path.name}:{line}: FPL {fpl_id} listed twice")
            if sofa_id is not None and sofa_id in seen_sofa:
                raise OverrideFileError(f"{path.name}:{line}: Sofascore {sofa_id} listed twice")
            seen_fpl.add(fpl_id)
            if sofa_id is not None:
                seen_sofa.add(sofa_id)
            overrides.append(Override(fpl_id, sofa_id, comment.strip()))
    return overrides


def _int(raw: str, path: Path, line: int, column: str) -> int:
    try:
        return int(raw.strip())
    except ValueError:
        raise OverrideFileError(f"{path.name}:{line}: {column} must be an integer, got {raw!r}") from None
