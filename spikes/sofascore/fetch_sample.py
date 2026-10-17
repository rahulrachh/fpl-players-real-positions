"""Spike: fetch a club's recent events and one match's average positions from Sofascore.

Usage:
    python spikes/sofascore/fetch_sample.py [team_id] [event_id]

Defaults: team 17 (Manchester City), event 16363878 (Man City vs Liverpool).
Raw responses are saved to spikes/sofascore/samples/.
"""

import json
import sys
import time
from pathlib import Path

# Plain `requests` gets a 403 from Sofascore (TLS fingerprinting); curl_cffi
# impersonates Chrome's TLS handshake and headers.
from curl_cffi import requests

BASE = "https://www.sofascore.com/api/v1"
SAMPLES = Path(__file__).parent / "samples"
DELAY_S = 1.5

session = requests.Session(impersonate="chrome")
session.headers.update({"Referer": "https://www.sofascore.com/"})


def get(path: str) -> dict:
    url = f"{BASE}{path}"
    resp = session.get(url, timeout=20)
    print(f"GET {url} -> {resp.status_code}")
    resp.raise_for_status()
    time.sleep(DELAY_S)
    return resp.json()


def save(name: str, data: dict) -> Path:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    path = SAMPLES / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  saved {path}")
    return path


def main() -> None:
    team_id = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    event_id = int(sys.argv[2]) if len(sys.argv) > 2 else 16363878

    events = get(f"/team/{team_id}/events/last/0")
    save(f"team_{team_id}_events_last_0.json", events)

    print("\nRecent events:")
    for ev in events.get("events", []):
        tourn = ev.get("tournament", {}).get("uniqueTournament", {})
        print(
            f"  {ev['id']:>9}  round {ev.get('roundInfo', {}).get('round', '-'):>3}  "
            f"{tourn.get('name', '?'):<22} {ev['homeTeam']['name']} "
            f"{ev.get('homeScore', {}).get('current', '-')}-"
            f"{ev.get('awayScore', {}).get('current', '-')} "
            f"{ev['awayTeam']['name']}  [{ev.get('status', {}).get('type')}]"
        )

    positions = get(f"/event/{event_id}/average-positions")
    save(f"event_{event_id}_average_positions.json", positions)

    print(f"\nAverage positions for event {event_id}:")
    for side in ("home", "away"):
        players = positions.get(side, [])
        print(f"  {side}: {len(players)} players")
        for p in players:
            pl = p.get("player", {})
            print(
                f"    {pl.get('name', '?'):<28} pos={pl.get('position', '-'):<2} "
                f"x={p.get('averageX')!s:<6} y={p.get('averageY')!s:<6} "
                f"points={p.get('pointsCount')}"
            )
    extra = [k for k in positions if k not in ("home", "away")]
    if extra:
        print(f"  other top-level keys: {extra}")


if __name__ == "__main__":
    main()
