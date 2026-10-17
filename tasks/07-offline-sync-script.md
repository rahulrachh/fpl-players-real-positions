# 07 — Offline sync script + season backfill

**Status:** done (2026-10-17)
**Depends on:** 04, 06.

## Goal
The owner refreshes data by running a script **on their own machine**. It updates the local SQLite file; committing and deploying that file is what puts new data online. There is no online worker or cron, and the website never calls Sofascore.

## Scope
- `backend/app/sync/service.py` with `run_sync(trigger)` (read-write DB connection):
  1. `refresh_fpl_reference_data()` (task 04).
  2. For each of the 20 clubs, list its last N finished Premier League matches via the adapter (`/team/{id}/events/last/0`; N = 3 for `run`, whole season for `backfill`); upsert `matches`, skipping event IDs already stored (one match covers both clubs). See `docs/spikes/positions-source.md`.
  2b. **Assign the gameweek from FPL, never from Sofascore's round number.** Map the Sofascore home/away team IDs to FPL clubs (`fpl_clubs.sofascore_team_id`), then find the FPL fixture with the same (home club, away club): each pair has exactly one home fixture per season. Store its fixture ID and `event` as the match's `gw` in `matches` and `player_match_positions`. If Sofascore's round differs from FPL's gameweek (usually a rescheduled match), log a warning in the run summary.
  2c. **Rescheduled matches:** FPL moves a rescheduled fixture to the gameweek it is actually played in, so a rescheduled match played in a double gameweek gets that DGW's `gw`, next to the club's regular match. Every run re-reads FPL `fixtures/` and updates `gw` in both tables for stored matches whose fixture moved. Fixtures with `event = null` (postponed, no new date) are skipped until they are finished.
  3. For every **finished** match with `positions_fetched_at IS NULL`: fetch positions, upsert `player_match_positions` and `sofascore_players`, set `positions_fetched_at`. Each match is committed on its own, so a failure midway loses nothing.
  4. Mark `gameweeks.positions_synced = true` when all of a GW's matches are fetched.
  5. Refresh `sofascore_players` squad lists (players who have not played yet) and re-run the ID mapping (task 08, once it exists).
  6. Write a `sync_runs` row (counts, errors, duration).
  - **Idempotent:** re-running fetches nothing already stored; midweek GWs and postponed matches are picked up by a later run.
- **CLI:** `python -m app.sync backfill` (whole season so far, run once) and `python -m app.sync run` (regular refresh). Both print a short summary: matches added per GW, unmapped players, warnings.
- `docs/release.md`: the owner's release routine: run sync, check the site locally, commit `backend/data/fpl.db`, push / `vercel deploy --prod`.

## Done when
- [x] `backfill` populates all finished GWs of the current season (row counts per GW in Notes).
- [x] Running `run` immediately again fetches 0 matches.
- [x] Every stored match has a `gw` taken from its FPL fixture; any Sofascore round ≠ FPL GW cases are listed in Notes.
- [x] Test with a rescheduled match in a double gameweek: both of the club's matches carry the DGW's `gw`, so a (player, gw) lookup returns 2 rows.
- [x] Database file size after backfill recorded in Notes (expected: a few MB).
- [x] `docs/release.md` exists.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- **Club mapping pulled forward from task 08.** `fpl_clubs.sofascore_team_id` was empty, and the sync cannot list a club's matches without it. `backend/app/mapping/clubs.py` holds a static table of the 20 clubs keyed by FPL short name (IDs read from Sofascore's 2026/27 round 6); `apply_club_mapping()` runs on every sync and reports clubs missing from the table. Task 08 still owns the player mapping.
- **Backfill (2026-10-17, run 1):** 254 s, 60 matches (10 each in GW1-6), 1849 position rows, 555 squad players, GW1-6 `positions_synced`, 0 errors, 0 warnings. Position rows per GW: GW1 307, GW2 312, GW3 306, GW4 307, GW5 302, GW6 315. 562 `sofascore_players` rows. GW7 had not started.
- **Re-run:** `run` straight after (run 2, 101 s, mostly the squad refresh) added 0 matches and fetched 0 positions.
- **Gameweeks:** all 60 stored matches have an FPL fixture ID and `gw`; `player_match_positions.gw` matches `matches.gw` for every row. No Sofascore round ≠ FPL GW cases yet (no rescheduled matches so far this season).
- **Double gameweek / rescheduled match:** covered by `tests/test_sync.py` with a fake FPL client and source: BOU v ARS (Sofascore round 3) moved by FPL into GW5 next to ARS v BOU, so a (player, GW5) lookup returns 2 rows; also a fixture moving GW3 → GW5 after it was stored updates both tables, and a fixture with `event = null` is skipped. 10 new tests, 117 pass.
- **Database size:** `backend/data/fpl.db` 143 KB → 463 KB after the backfill.
- **Failure handling:** a 404 on positions is recorded in `sync_runs.errors` and retried next run; a 403 stops the run with everything fetched so far kept (one commit per match); the `sync_runs` row is always closed. The CLI exits 1 on any error.
- **Not done here:** re-running the player ID mapping at the end of the sync is a `TODO(task 08)` in `service.py`. The summary's "unmapped players" (436) counts Sofascore players with positions and no `player_id_map` row, so it is everyone until task 08.
