# Positions source adapter

**Task:** 06 · Code: `backend/app/positions/` · Source research: `docs/spikes/positions-source.md`

## Boundary
- `app/positions/` is the **only** code that talks to the positions source (today Sofascore). It fetches and normalizes; it never writes the database. The offline sync (task 07) does that.
- Callers use `get_positions_source()` and the types and errors in `app/positions/base.py`. Nothing outside the package imports `sofascore.py` or `curl_cffi`. Swapping sources means a new adapter plus a change to `get_positions_source()`.
- The website never calls the source. `curl_cffi` lives in the backend's `sync` dependency group, which is installed by default locally (`uv sync`).

## Interface (`PositionsSource`)
| Method | Returns |
|---|---|
| `list_round_matches(round)` | `SourceMatch` for every match of a round of the current season, kickoff order |
| `list_team_matches(team_id, last_n=None)` | The club's current-season league matches, oldest first. `last_n` keeps the last N **finished** ones; `None` = whole season (pages back as needed) |
| `match_positions(match_id)` | `SourcePlayerPosition` for every player who played: player, `is_home`, `x`/`y`, `points_count`, `sub_on_minute`, `sub_off_minute`, plus `is_sub` and approximate `minutes` |
| `list_team_players(team_id)` | `SourcePlayer` for the club's current squad, including players who have not played (for ID mapping) |

`SourceMatch`: source match ID, season ID, source round, home/away team IDs and names, kickoff (naive UTC), status (`finished`, `notstarted`, `postponed`, ...), score. Assign FPL gameweeks from FPL's fixtures, never from `round`.

## Frame
The team attacks **upward**, seen from behind its own goal:
- **x**: 0 = left touchline → 100 = right touchline (the player's left / right).
- **y**: 0 = own goal line → 100 = opponent's goal line.

Every team, home or away, is in this frame. Sofascore's `averageX` (depth) / `averageY` (high = left) become x = 100 - `averageY`, y = `averageX`. Sofascore already normalizes both teams; as a guard, a side whose starting goalkeeper averages in the opponent's half is mirrored and a warning is logged (never seen so far).

## Errors
All derive from `PositionsSourceError`:
- `SourceBlockedError`: a 403 (never retried), or still 429 after every retry. Stop the run and wait.
- `SourceUnavailableError`: network errors or 5xx after every retry, or another unexpected status.
- `SourceNotFoundError`: 404, e.g. a match without average positions.
- `SourceSchemaError`: the response no longer has the expected shape.

## Polite fetching
Settings (`.env.example`):
- `SOFASCORE_REQUEST_DELAY_SECONDS` (default 2.5): minimum gap between request starts.
- `SOFASCORE_MAX_RETRIES` (3) and `SOFASCORE_BACKOFF_SECONDS` (5): 429 / 5xx / network errors wait 5, 10, 20 s (or `Retry-After` if longer).
- `SOFASCORE_API_BASE_URL` (default `https://www.sofascore.com/api/v1`). `api.sofascore.com` answers 403 even through `curl_cffi`.

## Endpoints used
Base `https://www.sofascore.com/api/v1`, Premier League `uniqueTournament` 17.

| Endpoint | Used by |
|---|---|
| `/unique-tournament/17/seasons` | Current season ID (newest listed; 2026/27 = `96668`). Fetched once per adapter |
| `/unique-tournament/17/season/{season}/events/round/{round}` | `list_round_matches`. Round 1 also gives the season start for whole-season paging |
| `/team/{id}/events/last/{page}` | `list_team_matches`. 30 events per page, all competitions, page 0 newest, `hasNextPage`. Paging stops at the first page that reaches before the season start |
| `/event/{id}/average-positions` | `match_positions`. 404 `{"error": {"code": 404, "message": "Not Found"}}` when there is no data |
| `/team/{id}/players` | `list_team_players` (`players` list; each player has `team.id`). Answers the spike's open question on squad lists |

## Command-line check
From `backend/` (live requests, spaced as above):
```sh
uv run python -m app.positions round 6               # a round's matches and every player's position
uv run python -m app.positions round 6 --match 16363878
uv run python -m app.positions team 17 --last 3      # a club's league matches
uv run python -m app.positions squad 17              # a club's squad
```

## Known limits
- Minutes are approximate: stoppage time and red cards are ignored (red cards would need `/event/{id}/incidents`, not fetched).
- Low `points_count` means a noisy average (late subs). Filtering or fading is left to the position logic (task 10).
