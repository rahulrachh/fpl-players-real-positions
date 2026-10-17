"""Print what the positions source returns, in the normalized frame.

From backend/:
    uv run python -m app.positions round 6              # round 6: matches + positions
    uv run python -m app.positions round 6 --match 16363878
    uv run python -m app.positions team 17 [--last 3]   # a club's league matches
    uv run python -m app.positions squad 17             # a club's squad

Read-only: talks to the source live (politely spaced), never to the database.
"""

import argparse
import sys

from app.positions import get_positions_source
from app.positions.base import SourceMatch, SourcePlayerPosition


def _side(x: float) -> str:
    return "left" if x < 33.3 else "right" if x > 66.7 else "centre"


def _print_match(match: SourceMatch) -> None:
    score = "" if match.home_score is None else f" {match.home_score}-{match.away_score}"
    print(
        f"{match.id:>9}  R{match.round}  {match.kickoff:%Y-%m-%d %H:%M}  "
        f"{match.home_team_name} ({match.home_team_id}){score} "
        f"{match.away_team_name} ({match.away_team_id})  [{match.status}]"
    )


def _print_positions(match: SourceMatch, positions: list[SourcePlayerPosition]) -> None:
    for is_home, team in ((True, match.home_team_name), (False, match.away_team_name)):
        side = [p for p in positions if p.is_home == is_home]
        print(f"    {team} ({'home' if is_home else 'away'}), {len(side)} players, top of the pitch first")
        for p in sorted(side, key=lambda p: -p.y):
            sub = f"on {p.sub_on_minute}'" if p.is_sub else ""
            off = f"off {p.sub_off_minute}'" if p.sub_off_minute is not None else ""
            print(
                f"      {p.player.position or '-'}  {p.player.name:<26} "
                f"x={p.x:5.1f} y={p.y:5.1f}  {_side(p.x):<6}  "
                f"{p.minutes:>2} min  pts={p.points_count:<3} {sub} {off}".rstrip()
            )


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # player names have accents
    parser = argparse.ArgumentParser(prog="python -m app.positions", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rnd = sub.add_parser("round", help="a round's matches and positions")
    rnd.add_argument("round", type=int)
    rnd.add_argument("--match", type=int, help="only this match ID")
    team = sub.add_parser("team", help="a club's league matches this season")
    team.add_argument("team_id", type=int)
    team.add_argument("--last", type=int, help="only the last N finished")
    squad = sub.add_parser("squad", help="a club's squad")
    squad.add_argument("team_id", type=int)
    args = parser.parse_args(argv)

    source = get_positions_source()
    print("Frame: x 0 = left touchline -> 100 = right; y 0 = own goal -> 100 = opponent goal.\n")

    if args.command == "round":
        matches = source.list_round_matches(args.round)
        print(f"Round {args.round}: {len(matches)} matches")
        for match in matches:
            _print_match(match)
        for match in matches:
            if (args.match and match.id != args.match) or not match.finished:
                continue
            print()
            _print_match(match)
            _print_positions(match, source.match_positions(match.id))
    elif args.command == "team":
        for match in source.list_team_matches(args.team_id, last_n=args.last):
            _print_match(match)
    else:
        for player in source.list_team_players(args.team_id):
            print(f"{player.id:>8}  {player.position or '-'}  {player.name:<28} {player.short_name or ''}")


if __name__ == "__main__":
    main()
