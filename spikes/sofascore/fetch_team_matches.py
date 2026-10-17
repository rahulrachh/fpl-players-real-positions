"""Spike: fetch average positions for a club's last N Premier League matches.

Usage:
    python spikes/sofascore/fetch_team_matches.py [team_id] [last_n]

Defaults: team 17 (Manchester City), last 6 matches.
A match file covers both teams, so events already saved (e.g. via the
opponent) are skipped. Saves to spikes/sofascore/samples/.
"""

import sys

import fetch_sample
from fetch_sample import SAMPLES, get, save

fetch_sample.DELAY_S = 2.5


def main() -> None:
    team_id = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    last_n = int(sys.argv[2]) if len(sys.argv) > 2 else 6

    events = get(f"/team/{team_id}/events/last/0")
    save(f"team_{team_id}_events_last_0.json", events)

    league = [
        ev for ev in events.get("events", [])
        if ev.get("tournament", {}).get("uniqueTournament", {}).get("name") == "Premier League"
        and ev.get("status", {}).get("type") == "finished"
    ]
    league = league[-last_n:]  # events are oldest first

    print(f"\nLast {last_n} Premier League matches: {len(league)} found")
    for ev in league:
        name = f"event_{ev['id']}_average_positions.json"
        label = (
            f"R{ev['roundInfo']['round']} {ev['homeTeam']['name']} "
            f"{ev['homeScore'].get('current')}-{ev['awayScore'].get('current')} "
            f"{ev['awayTeam']['name']}"
        )
        if (SAMPLES / name).exists():
            print(f"  {label}: already saved, skipping")
            continue
        print(f"  {label}")
        positions = get(f"/event/{ev['id']}/average-positions")
        save(name, positions)
        print(
            f"    home {len(positions.get('home', []))} players, "
            f"away {len(positions.get('away', []))} players"
        )


if __name__ == "__main__":
    main()
