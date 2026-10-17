"""Offline sync of FPL reference data and match positions into the local
SQLite file. Run on the owner's machine, then commit `backend/data/fpl.db`
(see `docs/release.md`).

From backend/:
    uv run python -m app.sync backfill   # whole season so far (run once)
    uv run python -m app.sync run        # regular refresh: each club's last 3 matches
"""

import argparse
import logging
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.engine import get_read_write_engine
from app.fpl.client import get_fpl_client
from app.positions import get_positions_source
from app.sync.service import SyncSummary, run_sync


def print_summary(summary: SyncSummary) -> None:
    print(f"\nSync {summary.trigger} (run {summary.run_id}): {summary.duration_seconds:.0f} s")
    if summary.matches_added_by_gw:
        added = ", ".join(
            f"GW{gw}: {n}" for gw, n in sorted(summary.matches_added_by_gw.items())
        )
        print(f"  Matches added: {added}")
    else:
        print("  Matches added: none")
    print(
        f"  Positions fetched: {summary.matches_fetched} matches, "
        f"{summary.positions_stored} player rows"
    )
    print(f"  Squad players refreshed: {summary.squad_players}")
    synced = ", ".join(map(str, summary.synced_gameweeks)) or "none"
    print(f"  Gameweeks fully synced: {synced}")
    print(f"  Unmapped players (with positions, no FPL mapping): {summary.unmapped_players}")
    for title, lines in (("Warnings", summary.warnings), ("Errors", summary.errors)):
        if lines:
            print(f"  {title} ({len(lines)}):")
            for line in lines:
                print(f"    - {line}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # team and player names have accents
    parser = argparse.ArgumentParser(prog="python -m app.sync", description=__doc__.split("\n")[0])
    parser.add_argument("trigger", choices=["run", "backfill"])
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=get_settings().log_level.upper(), format="%(levelname)s %(name)s: %(message)s"
    )

    with Session(get_read_write_engine()) as session:
        summary = run_sync(args.trigger, session, get_fpl_client(), get_positions_source())
    print_summary(summary)
    return 1 if summary.blocked or summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())
