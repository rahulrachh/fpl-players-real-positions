# 07 — Offline sync script + season backfill

**Status:** todo
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
- [ ] `backfill` populates all finished GWs of the current season (row counts per GW in Notes).
- [ ] Running `run` immediately again fetches 0 matches.
- [ ] Every stored match has a `gw` taken from its FPL fixture; any Sofascore round ≠ FPL GW cases are listed in Notes.
- [ ] Test with a rescheduled match in a double gameweek: both of the club's matches carry the DGW's `gw`, so a (player, gw) lookup returns 2 rows.
- [ ] Database file size after backfill recorded in Notes (expected: a few MB).
- [ ] `docs/release.md` exists.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
