# 03 — Database schema + migrations

**Status:** todo
**Depends on:** 02.

## Goal
All MVP tables defined as SQLAlchemy models with an Alembic migration, in the SQLite file that ships with each deployment.

## Tables (MVP)
Written only by offline scripts; read-only on the website.

| Table | Purpose / key columns |
|---|---|
| `fpl_clubs` | FPL club ID, name, short name, `sofascore_team_id` |
| `fpl_players` | FPL player ID, first/second/web name, club, FPL role (GK/DEF/MID/FWD), price, status/news. No mapping columns: refreshed from FPL on every sync without touching the mapping |
| `player_id_map` | FPL player ID ↔ Sofascore player ID. `fpl_id` **PRIMARY KEY** (FK `fpl_players`), `sofascore_id` **NOT NULL UNIQUE** (FK `sofascore_players`), `match_method` (exact / short_name / surname_initial / fuzzy / override), `match_confidence` (0-1), `is_override`, `matched_at`. Both keys are indexed via their constraints; UNIQUE stops two FPL players mapping to one Sofascore player. Unmatched FPL players have no row |
| `gameweeks` | GW number, deadline, finished, data_checked, `positions_synced` |
| `sofascore_players` | Sofascore player ID, name, short name, slug, Sofascore team ID (source side of the ID mapping) |
| `matches` | Sofascore match ID, FPL fixture ID (nullable), GW, home/away club, kickoff, finished, `positions_fetched_at` |
| `player_match_positions` | match ID, Sofascore player ID, avg x, avg y (**normalized: own goal to opponent goal**; y high = left side, see `docs/spikes/positions-source.md`), `points_count` (Sofascore `pointsCount`: on-ball actions the average is built from; low = unreliable dot, used to hide/fade), `sub_on_minute` (nullable; set = came on as a sub), `sub_off_minute` (nullable; set = taken off), `minutes` (derived on write: `(sub_off_minute or 90) - (sub_on_minute or 0)`, stoppage time ignored). No separate `is_sub` column: a sub is `sub_on_minute IS NOT NULL`. **Copied from `matches` so the website reads only this table:** `kickoff` (match start, from Sofascore `startTimestamp`) and `gw` (FPL gameweek). Unique (match, player). Indexes: (player, kickoff) for "most recent match played", (player, gw) for the gameweek view |
| `sync_runs` | started/finished, trigger (run/backfill), matches fetched, errors. Also gives the site a "data as of" timestamp |

**Not stored:** team picks (fetched live from FPL, task 05). **Not included:** Planner and roast tables (v1, see `tasks/v1-backlog/`).

## Done when
- [ ] Models + Alembic migration exist; `alembic upgrade head` works.
- [ ] `docs/data-model.md` describes each table, the coordinate convention, and that the website opens the file read-only.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
