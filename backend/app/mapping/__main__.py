"""Rebuild the FPL ↔ Sofascore player ID mapping from what is already in
the local database (no network calls) and rewrite the coverage report.
Also runs at the end of every sync.

From backend/:
    uv run python -m app.mapping run
"""

import argparse
import logging
import sys
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.engine import get_read_write_engine
from app.mapping.players import run_player_mapping
from app.mapping.report import render_report, summary_lines, write_report


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m app.mapping", description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["run"])
    parser.parse_args(argv)
    logging.basicConfig(
        level=get_settings().log_level.upper(), format="%(levelname)s %(name)s: %(message)s"
    )

    with Session(get_read_write_engine()) as session:
        result = run_player_mapping(session)
        session.commit()
        path = write_report(render_report(session, result, datetime.now(UTC)))
        print("\n".join(summary_lines(session, result)))
    print(f"  Report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
