# API

**Task:** 12 · **Code:** `backend/app/main.py` (routes), `backend/app/logic/plot.py` (plot response) · **Tests:** `backend/tests/test_plot.py`, `backend/tests/test_fpl_team.py`

The web app reads the bundled read-only `fpl.db` and live FPL data. It never calls Sofascore. `app.main` does not even import the positions adapter, the sync code or `curl_cffi`, and a test checks this. The server log for plot requests shows only `fantasy.premierleague.com` calls.

## Endpoints
| Method + path | Returns |
|---|---|
| `GET /api/health` | Database status (read-only check). |
| `GET /api/gameweeks/latest` | `{latest, last_finished}`: newest gameweek with a passed deadline, newest with every fixture finished. |
| `GET /api/team/{team_id}/gameweek/{gw}` | The team's 15 picks (task 05, `TeamGameweek`). |
| `GET /api/team/{team_id}/plot/{gw}` | **The gameweek graphic** (below). |
| `GET /api/team/{team_id}/plot/latest` | Same, for the newest gameweek whose deadline has passed. Right after a deadline, until FPL serves that gameweek's picks, it falls back to the gameweek before. |

## Plot response
| Field | Meaning |
|---|---|
| `team_id`, `team_name`, `manager_name` | From FPL. |
| `gw` | The gameweek shown (for `latest`, the one it resolved to). |
| `state` | `locked`: finished in FPL and its positions are synced. Shows the XI after auto-subs, from that gameweek's matches. `preview`: anything else. Shows the XI as picked, each from his most recent match. See `docs/position-logic.md`. |
| `points` / `transfers_cost` | The team's gameweek score before transfer hits (FPL `entry_history.points`, live while the gameweek is in progress) and the hit taken. |
| `prev_gw` / `next_gw` | The neighbouring gameweek to step to, or `null` at an edge. `prev_gw` stops at the team's first gameweek (and GW1). `next_gw` stops at the newest gameweek whose deadline has passed (so also at GW38). |
| `data_as_of` | End of the latest finished offline sync (`sync_runs.finished_at`, UTC, no offset), or `null` if never synced. |
| `dots` | One per XI player in slot order. A double-gameweek player on opposite flanks has two. |

Each dot:

| Field | Meaning |
|---|---|
| `fpl_id` | FPL player ID. |
| `name` / `web_name` | Full name / FPL short name. |
| `role` | `GK` / `DEF` / `MID` / `FWD`, as FPL listed the player in this pick. |
| `club` | Club short name (current club, as FPL shows it). |
| `slot` | XI slot 1-11 in FPL's formation order. A locked auto-sub has the starter's slot. |
| `x`, `y` | 0-100, 2 decimals, attacking upward: x 0 = left touchline, y 0 = own goal line (`docs/data-model.md`). `null` for a ghost. |
| `is_captain` | Armband: the picked captain (preview) or the player FPL multiplied (locked). |
| `is_ghost`, `ghost_reason` | No position to draw: `no_match` (no usable match) or `no_mapping` (no Sofascore link). Drawn on the sideline. |
| `from_gw` | "from GWx" label when the position comes from an older gameweek (preview only), otherwise `null`. |
| `link_group` | Same value (the FPL ID) on the two linked dots of a double gameweek, otherwise `null`. |
| `replaces` | Locked only: FPL ID of the picked starter this auto-sub replaced. |

## Errors
Same codes as the team endpoint, as `{code, detail}`:

| Status | `code` | When |
|---|---|---|
| 404 | `team_not_found` | No FPL team with this ID. |
| 404 | `gameweek_out_of_range` | Not a gameweek of the season. |
| 404 | `gameweek_before_team_started` | The team joined later. |
| 404 | `gameweek_not_started` | Deadline not passed, or picks not served yet. For `latest`: before the GW1 deadline. |
| 422 | (FastAPI) | Team ID or gameweek is not a positive integer. |
| 503 | `fpl_unavailable` | FPL is down or changed its format. |

## Samples
Owner's team 2020649, recorded 2026-10-17 against live FPL and the committed database (data GW1-6).

### Locked: `GET /api/team/2020649/plot/latest` (resolves to GW6)
```json
{
  "team_id": 2020649,
  "team_name": "navratri OG",
  "manager_name": "RR R",
  "gw": 6,
  "state": "locked",
  "points": 66,
  "transfers_cost": 0,
  "prev_gw": 5,
  "next_gw": null,
  "data_as_of": "2026-10-17T05:21:57.469430",
  "dots": [
    {"fpl_id": 567, "name": "Lukás Hornícek", "web_name": "Horníček", "role": "GK", "club": "NEW", "slot": 1, "x": 48.08, "y": 10.89, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 8, "name": "Riccardo Calafiori", "web_name": "Calafiori", "role": "DEF", "club": "ARS", "slot": 2, "x": 29.31, "y": 57.72, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 449, "name": "Lewis Hall", "web_name": "Hall", "role": "DEF", "club": "NEW", "slot": 3, "x": 18.65, "y": 51.22, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 115, "name": "Maxim De Cuyper", "web_name": "De Cuyper", "role": "DEF", "club": "BHA", "slot": 4, "x": 17.29, "y": 51.14, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 31, "name": "Ezri Konsa Ngoyo", "web_name": "Konsa", "role": "DEF", "club": "ARS", "slot": 5, "x": 64.02, "y": 36.91, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 40, "name": "Morgan Rogers", "web_name": "Rogers", "role": "MID", "club": "CHE", "slot": 6, "x": 30.64, "y": 52.21, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 15, "name": "Martin Ødegaard", "web_name": "Ødegaard", "role": "MID", "club": "ARS", "slot": 7, "x": 52.02, "y": 62.31, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 480, "name": "Morgan Gibbs-White", "web_name": "Gibbs-White", "role": "MID", "club": "NFO", "slot": 8, "x": 73.83, "y": 64.58, "is_captain": true, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 124, "name": "Pascal Groß", "web_name": "Groß", "role": "MID", "club": "BHA", "slot": 9, "x": 57.26, "y": 51.46, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 165, "name": "João Pedro Junqueira de Jesus", "web_name": "João Pedro", "role": "FWD", "club": "CHE", "slot": 10, "x": 38.86, "y": 55.16, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 411, "name": "Erling Haaland", "web_name": "Haaland", "role": "FWD", "club": "MCI", "slot": 11, "x": 45.7, "y": 53.6, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null}
  ]
}
```

At the season edges: GW1 returns `prev_gw: null, next_gw: 2`, GW3 returns `2` / `4`, and GW6 (the newest) returns `next_gw: null`.

### Preview: GW7
FPL keeps GW7 picks private until its deadline (2026-10-17 10:00 UTC). This sample was built in-process from the GW6 squad with the status set to in progress. Each dot is from the player's most recent match. That match is from GW6, the previous gameweek, so no dot has a `from_gw` label.
```json
{
  "team_id": 2020649,
  "team_name": "navratri OG",
  "manager_name": "RR R",
  "gw": 7,
  "state": "preview",
  "prev_gw": 6,
  "next_gw": null,
  "data_as_of": "2026-10-17T05:21:57.469430",
  "dots": [
    {"fpl_id": 567, "name": "Lukás Hornícek", "web_name": "Horníček", "role": "GK", "club": "NEW", "slot": 1, "x": 48.08, "y": 10.89, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 8, "name": "Riccardo Calafiori", "web_name": "Calafiori", "role": "DEF", "club": "ARS", "slot": 2, "x": 29.31, "y": 57.72, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    {"fpl_id": 449, "name": "Lewis Hall", "web_name": "Hall", "role": "DEF", "club": "NEW", "slot": 3, "x": 18.65, "y": 51.22, "is_captain": false, "is_ghost": false, "ghost_reason": null, "from_gw": null, "link_group": null, "replaces": null},
    … 8 more
  ]
}
```
