# FPL API

**Task:** 04 · Client: `backend/app/fpl/client.py` · Response schemas: `backend/app/fpl/schemas.py` · Reference refresh: `backend/app/fpl/reference.py`

The official Fantasy Premier League API at `https://fantasy.premierleague.com/api` (`FPL_API_BASE_URL`). It is **unofficial and undocumented**: field names and behavior can change without notice. Everything below was verified by experiment on **2026-10-17 ~03:20 UTC**, when GW6 was finished (`data_checked`) and the GW7 deadline (2026-10-17 10:00 UTC) had **not** passed yet.

## Access
- No login, no API key, no cookies. A plain `httpx` GET with a simple `User-Agent` works; no anti-bot measures (unlike Sofascore, no `curl_cffi` needed).
- Trailing slashes matter: always request `.../path/`.
- The app never handles FPL credentials. Endpoints that need a login (`my-team/{id}/`, `me/`) answer **403** `"Authentication credentials were not provided."` and are not used.

## Endpoints used

| Client method | Endpoint | Used for | Fields used |
|---|---|---|---|
| `bootstrap_static()` | `bootstrap-static/` (~1.8 MB) | Players, clubs, roles, prices, availability, gameweeks | `events[]`: `id`, `deadline_time`, `finished`, `data_checked`, `is_previous`/`is_current`/`is_next` · `teams[]`: `id`, `name`, `short_name` · `element_types[]`: `id`, `singular_name_short` · `elements[]`: `id`, `first_name`, `second_name`, `web_name`, `team`, `element_type`, `now_cost`, `status`, `news`, `minutes` |
| `fixtures(event=None)` | `fixtures/` or `fixtures/?event={gw}` | Linking Sofascore matches to FPL fixtures and gameweeks (task 07) | `id`, `event`, `team_h`, `team_a`, `kickoff_time`, `started`, `finished`, `finished_provisional` |
| `entry(id)` | `entry/{id}/` | Validate a team ID; which gameweeks have picks | `id`, `name`, `player_first_name`, `player_last_name`, `started_event`, `current_event`, `entered_events`, `last_deadline_bank`, `last_deadline_value` |
| `entry_history(id)` | `entry/{id}/history/` | Bank and value per gameweek, chips | `current[]`: `event`, `points`, `total_points`, `bank`, `value`, `event_transfers`, `event_transfers_cost`, `points_on_bench` · `chips[]`: `name`, `event` |
| `entry_picks(id, gw)` | `entry/{id}/event/{gw}/picks/` | Starting XI, bench, captain, auto-subs | `active_chip` · `automatic_subs[]`: `element_in`, `element_out`, `event` · `entry_history` (same as a history row) · `picks[]`: `element`, `position`, `multiplier`, `is_captain`, `is_vice_captain`, `element_type` |
| `event_live(gw)` | `event/{gw}/live/` | Minutes per player in a gameweek, if needed | `elements[]`: `id`, `stats.minutes` |
| `event_status()` | `event-status/` | Whether the current gameweek's points/bonus are processed | `status[]`: `event`, `date`, `bonus_added`, `points` (`r` ready, `p` provisional) · `leagues` |

Responses are parsed into frozen pydantic models that keep only these fields (extra fields ignored), so an unused field changing does not break us, and a used one changing fails loudly.

### Field notes
- **Roles:** `element_type` 1-4 = GKP / DEF / MID / FWD. Stored as `GK` / `DEF` / `MID` / `FWD`. Any other `element_type` makes the refresh fail loudly rather than guess.
- **Money** (`now_cost`, `bank`, `value`, `last_deadline_*`): integers in tenths of £m (`1017` = £101.7m).
- **`value` = squad at market prices (`now_cost`) + bank**, not selling value. Checked on six top teams: `value - bank` equals the sum of the 15 picks' `now_cost` before the latest price changes (e.g. 995 + 22 = 1017).
- **Picks:** `position` 1-11 is the starting XI, 12-15 the bench in sub order. `multiplier` 0 = bench, 1 = starter, 2 = captain; bench multipliers are 1 under Bench Boost (seen on the owner's GW1, task 05); 3 = triple captain is known FPL behavior, not checked.
- **Picks are shown after FPL's automatic subs** (verified in task 05, 2026-10-17): the auto-subbed starter is moved to the bench and the bench player who replaced them into the XI, with their positions and multipliers swapped. E.g. the owner's GW5: João Pedro (picked to start) is at position 13 with multiplier 0, Ajayi (picked on the bench) at position 5 with multiplier 1. The picked XI can only be rebuilt from `automatic_subs`.
- **Captain who did not play:** FPL subs them to the bench with multiplier 0 and keeps `is_captain`; the vice captain gets multiplier 2. Seen on 4 of 4 such cases among 100 teams checked (e.g. team 4155286 GW5: captain 165 at position 13, multiplier 0; vice 411 multiplier 2).
- **`automatic_subs`** is final once the gameweek is processed: `element_out` (picked starter who did not play) replaced by `element_in`.
- **`entered_events`** is the reliable list of gameweeks with public picks. **`current_event` is not**: it is the game's current gameweek, so a team created for GW7 still reports `current_event: 6` while GW6 picks are 404.
- **Statuses:** `a` available, `d` doubtful, `i` injured, `s` suspended, `u` unavailable (e.g. left the league), `n` not in squad. On 2026-10-17: 468 a, 105 u, 63 i, 28 d, 3 s.
- **Datetimes** are UTC with `Z`; the database stores naive UTC.
- **`event/{gw}/live/`** for an unstarted gameweek returns `200` with `{"elements": []}`, not an error.
- **`fixtures/`** returns all 380 fixtures. A postponed fixture not yet rescheduled has `event: null` (none on 2026-10-17).

## Public / private boundary (verified)

| Question | Answer |
|---|---|
| Are **upcoming-gameweek picks** visible before the deadline? | **No.** `entry/{id}/event/7/picks/` → **404** `{"detail":"Not found."}` before the GW7 deadline, for an established team and for a team created for GW7. Picks become public once the deadline passes. |
| Are **pending transfers** visible? | **No.** `entry/{id}/transfers/` lists only transfers for gameweeks whose deadline has passed (the top team's list held GW3-5 only; a team created for GW7 returned `[]`). |
| Which **money fields** are public? | `bank` and `value` per gameweek (`history.current[]` and picks `entry_history`), and `last_deadline_bank` / `last_deadline_value` on the entry. All as of a passed deadline. **Selling prices are not published**, but `entry/{id}/transfers/` (public, not used in MVP) includes `element_in_cost` / `element_out_cost`, i.e. purchase prices, from which v1 Planner could estimate selling prices. |
| What else is private? | The live "my team" view (`my-team/{id}/`, 403), unsaved changes, and anything else needing a login. |
| **Invalid team ID** (well-formed, does not exist, incl. `0`) | `entry/{id}/` → **404** `{"detail":"No Entry matches the given query."}` |
| **Non-numeric team ID** (`entry/abc/`) | **404 with an HTML page**, not JSON. The app must validate that the ID is a positive integer before calling FPL. |
| Picks for a gameweek the team did not play / out of range (`0`, `99`) | **404** `{"detail":"Not found."}` |
| Team joined late (`started_event` > 1) | Picks for earlier gameweeks → 404; `entered_events` omits them. `last_deadline_bank` / `last_deadline_value` are `null` until its first deadline passes. |

Not observed yet: FPL's **503 "The game is being updated."** during gameweek processing (widely reported; the client treats any 5xx as `FplUnavailable`).

## Errors
All failures raise a subclass of `FplError`:

| Exception | When | Website should show |
|---|---|---|
| `FplNotFound` | HTTP 404: unknown team, or no picks for that gameweek | "Team not found" / "No picks for GW N" |
| `FplUnavailable` | Network error, timeout (20 s), or any other HTTP ≥ 400 (5xx, 403, 429) | "FPL is unavailable, try again shortly" |
| `FplSchemaError` | Body is not JSON, or a used field is missing or has the wrong type | Same as unavailable; log it, the API changed |

## Caching
- One process-wide client (`get_fpl_client()`) holds an in-memory `TTLCache` (`app/cache.py`). **Every** call is cached for `FPL_CACHE_TTL_SECONDS` (default 60 s), keyed by path (plus `event` for fixtures). This covers the volatile calls (gameweek status in `bootstrap-static/`, `event-status/`, `event/{gw}/live/`) and saves repeat hits when a user steps back and forth through gameweeks.
- Errors are not cached.
- Per process only: each Vercel function instance has its own cache. The team loading service caches its finished results longer (see below).

## Team loading
**Task:** 05 · Service: `backend/app/fpl/team.py` · Endpoint: `GET /api/team/{team_id}/gameweek/{gw}`

`TeamService.load_team_gameweek(team_id, gw, session)` returns a `TeamGameweek`: team and manager name, gameweek status, `data_checked`, deadline, chip, bank, squad value, captain / vice captain / effective captain, FPL's automatic subs and the 15 picks. Each pick has its position, `starter` (in the XI after auto-subs), `picked_starter` (in the XI the manager picked), role, multiplier, captain flags, `auto_sub` (`in` / `out` / null) and the player with their club.

- **Team data is live from FPL**: `bootstrap-static/` (gameweek status), `entry/{id}/` (team, start gameweek), `entry/{id}/event/{gw}/picks/`. Nothing about teams is stored.
- **Player and club details come from the bundled database**, falling back to the live bootstrap for players added since the last sync. The club is the player's current club, also for past gameweeks (as on the FPL website). The role is FPL's `element_type` on the pick.
- **Gameweek status** from the live bootstrap: `upcoming` (deadline not passed), `in_progress` (deadline passed, not every fixture finished), `finished` (every fixture finished). `data_checked` says whether the points are final.
- **Helpers:** `latest_gameweek()` = newest gameweek whose deadline has passed (the newest with public picks; None before GW1). `last_finished_gameweek()` = newest gameweek with every fixture finished. Both served by `GET /api/gameweeks/latest` → `{"latest": 6, "last_finished": 6}`.

### Caching
Results are cached per (team, gameweek) in the service's own `TTLCache`, checked before any FPL call, so a repeat request within the window makes **no FPL call**:
- `data_checked` gameweeks: `FPL_FINISHED_CACHE_TTL_SECONDS` (default 24 h). Their data never changes.
- Anything else (in progress, finished but not checked): `FPL_CACHE_TTL_SECONDS` (60 s).
Errors are not cached.

### Errors
| Case | Exception | HTTP | `code` |
|---|---|---|---|
| Non-numeric or < 1 team ID / gameweek | (FastAPI validation, no FPL call) | 422 | |
| Unknown team | `TeamNotFound` | 404 | `team_not_found` |
| Gameweek not in the season | `GameweekOutOfRange` | 404 | `gameweek_out_of_range` |
| Gameweek before the team's `started_event` | `GameweekBeforeTeamStarted` | 404 | `gameweek_before_team_started` |
| Deadline not passed, or passed but FPL not serving picks yet | `GameweekNotStarted` | 404 | `gameweek_not_started` |
| FPL unreachable, 5xx, or response shape changed | `FplUnavailable` / `FplSchemaError` | 503 | `fpl_unavailable` |

Error bodies are `{"code": ..., "detail": ...}`.

## Reference data in the database
`refresh_fpl_reference_data(session, client)` fetches `bootstrap-static/` and upserts, by FPL ID:

| Table | From | Columns written | Left alone |
|---|---|---|---|
| `fpl_clubs` | `teams[]` | `name`, `short_name` | `sofascore_team_id` |
| `fpl_players` | `elements[]` | names, `club_id`, `role`, `price` (`now_cost`), `status`, `news`, `minutes` | (no mapping data lives here) |
| `gameweeks` | `events[]` | `deadline` (naive UTC), `finished`, `data_checked` | `positions_synced` |

It flushes but does not commit (the caller owns the transaction). Players that disappear from FPL are kept, since the mapping and position history may refer to them. Run by the offline sync script (task 07); the web app never writes.

Row counts after the first run (2026-10-17): **20 clubs, 667 players (73 GK, 217 DEF, 298 MID, 79 FWD), 38 gameweeks**. A second run changes nothing.
