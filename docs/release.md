# Release routine

**Task:** 07 · Code: `backend/app/sync/`

The website never fetches positions. All match and position data comes from an offline sync the owner runs **on their own machine**, which writes the local `backend/data/fpl.db`. Committing that file and deploying is what puts new data online. There is no online worker or cron, so the site is only as fresh as the last deploy.

## When
After each gameweek's last match (positions usually appear on Sofascore within an hour of full time). Midweek games and rescheduled matches are picked up by the next run, so an extra run after a midweek round is enough.

## Steps
From `backend/`:

1. **Sync**
   ```sh
   uv run python -m app.sync run
   ```
   Refreshes FPL clubs, players and gameweeks, stores each club's last 3 finished league matches, downloads their average positions, refreshes squad lists, rebuilds the FPL ↔ Sofascore player mapping, rewrites `docs/mapping-coverage.md` and writes a `sync_runs` row. Takes 2-3 minutes (requests are spaced 2.5 s apart). The summary lists matches added per gameweek, fully synced gameweeks, unmapped players, mapping coverage, warnings and errors. Exit code 1 means at least one error.
   - Running it again straight away fetches nothing: it is safe to re-run.
   - `backfill` instead of `run` walks the whole season. Needed once per season (or after the database is rebuilt); also works to fill gaps if more than 3 matches per club were missed.
2. **Check the summary**
   - *Errors* like `positions not stored: 404`: Sofascore has no positions yet. Run again later.
   - *Blocked by the positions source*: Sofascore answered 403. Stop, wait a few hours, then re-run. Do not loop it.
   - *Sofascore round N != FPL GW M*: a rescheduled match. Expected; the FPL gameweek is used.
   - *Club XXX has no Sofascore team ID*: a promoted club is missing from `backend/app/mapping/clubs.py`. Add it, then re-run.
   - *Player mapping clash* or a drop in active coverage: open `docs/mapping-coverage.md` and fix the listed players with a row in `backend/data/player_overrides.csv` (format at the top of the report). `uv run python -m app.mapping run` re-runs only the mapping, offline.
   - *Player override skipped*: the override names an FPL player that no longer exists, or a Sofascore player not stored yet. Fix or delete the row.
3. **Check the site locally**: `uv run uvicorn app.main:app --reload` and `npm run dev` in `frontend/`, then load a team for the new gameweek.
4. **Commit the database**
   ```sh
   git add backend/data/fpl.db backend/data/player_overrides.csv docs/mapping-coverage.md
   git commit -m "Data: sync after GW<n>"
   ```
5. **Deploy**: `git push` (if the Vercel project deploys from git) or `vercel deploy --prod`. Set up in task 16.

## What a run does
See the docstring of `backend/app/sync/service.py`. In short:
- Gameweeks always come from FPL's fixture list (`fixtures/`), matched on (home club, away club), never from Sofascore's round number.
- Every run re-reads FPL's fixtures and moves stored matches whose fixture changed gameweek (in `matches` and `player_match_positions`). A rescheduled match played in a double gameweek gets that gameweek, so a player can have two rows for one gameweek.
- Fixtures without a gameweek (postponed, no new date) are skipped until they are played.
- Each match is committed on its own, so a crash or a block loses nothing already fetched.
- A gameweek is `positions_synced` when every FPL fixture in it is finished and has positions.
