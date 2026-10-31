# API

**Task:** 12 · **Code:** `backend/app/main.py` (routes), `backend/app/logic/plot.py` (plot response) · **Tests:** `backend/tests/test_plot.py`, `backend/tests/test_fpl_team.py`, `backend/tests/test_fpl_fixtures.py` (fixtures endpoint, task 18)

The web app reads the bundled read-only `fpl.db` and live FPL data. It never calls Sofascore. `app.main` does not even import the positions adapter, the sync code or `curl_cffi`, and a test checks this. The server log for plot requests shows only `fantasy.premierleague.com` calls.

## Endpoints
| Method + path | Returns |
|---|---|
| `GET /api/health` | Database status (read-only check). |
| `GET /api/gameweeks/latest` | `{latest, last_finished}`: newest gameweek with a passed deadline, newest with every fixture finished. |
| `GET /api/team/{team_id}/gameweek/{gw}` | The team's 15 picks (task 05, `TeamGameweek`). |
| `GET /api/team/{team_id}/plot/{gw}` | **The gameweek graphic** (below). |
| `GET /api/team/{team_id}/plot/latest` | Same, for the newest gameweek whose deadline has passed. Right after a deadline, until FPL serves that gameweek's picks, it falls back to the gameweek before. |
| `GET /api/gameweek/{gw}/fixtures` | The gameweek's matches with scores and each match's top 3 players (task 18, [below](#fixtures-response)). |

## Plot response
| Field | Meaning |
|---|---|
| `team_id`, `team_name`, `manager_name` | From FPL. |
| `gw` | The gameweek shown (for `latest`, the one it resolved to). |
| `status` | FPL's gameweek status: `in_progress` or `finished`. A `finished` gameweek in the `preview` state is waiting for its positions (next sync + deploy). |
| `chip` | Chip played this gameweek: `bboost` / `3xc` / `freehit` / `wildcard` / `manager`, or `null`. |
| `state` | `locked`: finished in FPL and its positions are synced. Shows the XI after auto-subs, from that gameweek's matches. `preview`: anything else. Shows the XI as picked, each from his most recent match. See `docs/position-logic.md`. |
| `points` / `transfers_cost` | The team's gameweek score before transfer hits (FPL `entry_history.points`, live while the gameweek is in progress) and the hit taken. |
| `prev_gw` / `next_gw` | The neighbouring gameweek to step to, or `null` at an edge. `prev_gw` stops at the team's first gameweek (and GW1). `next_gw` stops at the newest gameweek whose deadline has passed (so also at GW38). |
| `data_as_of` | End of the latest finished offline sync (`sync_runs.finished_at`, UTC, no offset), or `null` if never synced. |
| `dots` | One per XI player in slot order (slots 12-15 for the bench under Bench Boost). A double-gameweek player on opposite flanks has two. |
| `bench` | The 4 bench players in bench order: `fpl_id`, `name`, `web_name`, `role`, `club`, `points` (their own), `subbed_off` (locked only: a picked starter FPL auto-subbed off), `matches` (as on a dot, below). After auto-subs when locked, as picked in preview. Empty under Bench Boost (they are dots). |
| `summary` | The panel beside the pitch (task 18, `backend/app/logic/summary.py`): `average_score` / `highest_score` of all FPL teams (`null` until FPL has them), `gw_rank`, `overall_rank` and `previous_overall_rank` (`null` while unranked / in the team's first gameweek), `gw_rank_pct` / `overall_rank_pct` (rank as a percent of all FPL teams, from `total_players`), `most_captained` `{id, web_name}` and `top_player` `{id, web_name, points}` of all FPL teams this gameweek (`null` until FPL has them), `total_points`, `transfers`, `transfers_cost`, `bank`, `squad_value` (tenths of £m, value includes the bank), `points_on_bench`, and `season`: `[{gw, played, points, chip}]` for every gameweek of the season (unplayed ones `played: false`, 0 points). From FPL's `entry/{id}/history/` (fetched fresh, 60 s cache, so the season includes gameweeks played after a cached team gameweek) and the gameweek in `bootstrap-static/`. `null` if the history can't be loaded; the rest of the plot is still returned. |

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
| `points` | The points the player scored for the team (`event/{gw}/live`, live while in progress): his own, doubled for the captain, tripled with Triple Captain. The dots add up to the gameweek score before hits. |
| `multiplier` | 2 for the captain (3 with Triple Captain), else 1: `points` = his own points × `multiplier`. |
| `from_bench` | A bench player drawn because of Bench Boost. |
| `matches` | His matches of the gameweek for the match details box, in kick-off order (two in a double gameweek, none in a blank one, or if FPL has no live data for him). A **linked double-gameweek dot** (`link_group` set) has only the match its position came from (`matches.fpl_fixture_id` of its stored match); every other dot, including one averaged dot, has all of them. Live from FPL like `points`. See below. |
| `depth_pct` | How far forward the dot is: percentile (0-100, 1 decimal, ties count half) of `y` among every outfield player-match in the database (defenders, midfielders and forwards together; a player-match counts at 60+ minutes). `null` for a goalkeeper or a ghost. The pitch draws it as the dot's height (`app/logic/depth.py`). |

Each match (`event/{gw}/live/` `explain` joined with `fixtures/`, see `docs/fpl-api.md`):

| Field | Meaning |
|---|---|
| `fixture_id` | FPL fixture ID. |
| `home_club` / `away_club` | Club short names. |
| `is_home` / `opponent` | From the player's side. `null` when his current club played in neither side (he has moved since); show `home_club` v `away_club` then. |
| `kickoff` | UTC, or `null` if not scheduled. |
| `state` | `not_started` / `live` / `finished` (`finished_provisional` counts as finished). |
| `home_score` / `away_score` | `null` before kick-off, live while played. |
| `minutes` | Minutes he played; 0 = did not play. |
| `stats` | One row per stat that scored or cost points, in FPL's order: `identifier`, `label` (as on the FPL site, except "Minutes" and "Def. Con."), `value`, `points`. Empty when he did not play. |
| `points` | Sum of `stats`: his points from this match. Over all of a player's matches this equals his own points; times `multiplier` it is the dot's `points`. |

Sample (GW8, the owner's captain, recorded 2026-10-30):
```json
{
  "fpl_id": 411, "web_name": "Haaland", "is_captain": true, "points": 16, "multiplier": 2,
  "matches": [
    {
      "fixture_id": 72, "home_club": "AVL", "away_club": "MCI", "is_home": false, "opponent": "AVL",
      "kickoff": "2026-10-24T11:30:00Z", "state": "finished", "home_score": 2, "away_score": 1,
      "minutes": 90,
      "stats": [
        {"identifier": "minutes", "label": "Minutes", "value": 90, "points": 2},
        {"identifier": "goals_scored", "label": "Goals scored", "value": 1, "points": 4},
        {"identifier": "bonus", "label": "Bonus", "value": 2, "points": 2}
      ],
      "points": 8
    }
  ]
}
```
A bench player who did not play (same gameweek): `{"fpl_id": 165, "web_name": "João Pedro", "points": 0, "subbed_off": true, "matches": [{"fixture_id": 73, "home_club": "CHE", "away_club": "TOT", "is_home": true, "opponent": "TOT", "kickoff": "2026-10-24T16:30:00Z", "state": "finished", "home_score": 0, "away_score": 2, "minutes": 0, "stats": [], "points": 0}]}`.

## Fixtures response
`GET /api/gameweek/{gw}/fixtures` (`backend/app/fpl/fixtures.py`). The same for every team, so the website highlights the team's starters itself from the plot response. Built live from FPL's `fixtures/?event=`, `event/{gw}/live/` and `bootstrap-static/` (no database). Cached per gameweek: 24 h once FPL has checked it (`data_checked`), otherwise 60 s.

| Field | Meaning |
|---|---|
| `gw`, `data_checked` | The gameweek, and whether FPL has checked its points (final). |
| `fixtures[]` | One per match, in kick-off order (ties by fixture ID). |
| `.id`, `.kickoff` | FPL fixture ID; kick-off (UTC, `null` if not scheduled). |
| `.state` | `not_started` / `live` / `finished` (FPL's `finished` or `finished_provisional`). |
| `.home_club`, `.away_club` | `{id, name, short_name}`. |
| `.home_score`, `.away_score` | `null` until kick-off; live during the match. |
| `.top_players[]` | Top 3 by FPL points **in this match** (both sides), highest first, everyone tied with 3rd included. Points are the sum of the player's `explain` stats for this fixture, so a double-gameweek player has separate points in each of his matches. Only players who played (minutes > 0). Empty until kick-off. Each: `{id, web_name, club, role, points}` (`club` = current club short name, `points` before any captain multiplier). |

Errors: `404 gameweek_out_of_range`, `422` for a non-positive gameweek, `503 fpl_unavailable`.

Sample row (GW8, a tie for 3rd):
```json
{"id": 73, "kickoff": "2026-10-24T16:30:00Z", "state": "finished", "home_club": {"id": 6, "name": "Chelsea", "short_name": "CHE"}, "away_club": {"id": 19, "name": "Spurs", "short_name": "TOT"}, "home_score": 0, "away_score": 2, "top_players": [{"id": 514, "web_name": "Tel", "club": "TOT", "role": "MID", "points": 11}, {"id": 496, "web_name": "Kinsky", "club": "TOT", "role": "GK", "points": 9}, {"id": 112, "web_name": "Van Hecke", "club": "TOT", "role": "DEF", "points": 7}, {"id": 525, "web_name": "Fernandes", "club": "TOT", "role": "MID", "points": 7}]}
```
An unstarted match has `"state": "not_started"`, `null` scores and `"top_players": []`.

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
