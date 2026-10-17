# 05 — Team loading service 🛑 👤

**Status:** done (approved 2026-10-17)
**Gate:** 🛑 Owner confirms their real team loads correctly. 👤 Needs the owner's FPL team ID: ask the owner at the start of the task, and record it in this task's Notes.
**Depends on:** 04.

## Goal
Team ID + gameweek gives everything the app needs about that team for that GW. Team data is **fetched live from FPL** (the website's database is read-only), with a short in-memory cache.

## Scope
- `backend/app/fpl/team.py`: `load_team_gameweek(team_id, gw)` returns 15 picks (player, role, club, starter/bench, multiplier), captain/vice, FPL's auto-subs, chip, bank, squad value, GW status (upcoming / in progress / finished). Player/club details are joined from the bundled database.
- In-memory cache: finished GWs with a long TTL (their data never changes), current GW with a short TTL.
- `latest_gameweek()` and `last_finished_gameweek()` helpers.
- `GET /api/team/{team_id}/gameweek/{gw}`.
- Clear errors: unknown team, GW before the team existed, GW not started, FPL unavailable.

## Done when
- [x] Correct data for the owner's team for at least 2 past GWs (compared against the FPL website; recorded in Notes). *Owner checked via the interim list view and approved.*
- [x] Auto-subs and captain match FPL.
- [x] A repeat request within the cache window makes no FPL call.
- [x] Status `awaiting-approval`, stopped; **owner confirms** and flips to `done`.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- **Owner's FPL team ID: 2020649** ("navratri OG"). Started GW1. Chips: Triple Captain GW3, Wildcard GW4. (7241584, the ID first given for this task, was also loaded and matched FPL's raw responses.)
- **Live check, 2026-10-17 ~04:35 UTC** (GW6 finished and checked, GW7 deadline 10:00 UTC not passed), via `GET /api/team/2020649/gameweek/{gw}` on the committed `fpl.db`:

  | GW | Chip | Bank | Value | XI | Captain | Vice | Auto-subs |
  |---|---|---|---|---|---|---|---|
  | 1 | | £0.0m | £100.0m | 3-5-2 | B.Fernandes | Raya | none |
  | 2 | | £0.0m | £100.2m | 3-5-2 | B.Fernandes | Haaland | none |
  | 3 | 3xc | £0.3m | £100.5m | 3-5-2 | Haaland (multiplier 3) | B.Fernandes | none |
  | 4 | wildcard | £1.9m | £101.2m | 3-4-3 | Palmer | João Pedro | none |
  | 5 | | £0.1m | £101.7m | 3-5-2 | Haaland | Gibbs-White | none |
  | 6 | | £0.9m | £102.3m | 4-4-2 | Gibbs-White | Haaland | none |

  **Owner compared against the FPL website and approved on 2026-10-17.** This team had no auto-subs; auto-subs were checked on 7241584 (GW5: Ajayi in for João Pedro) and on the recorded fixture.
- **Finding:** FPL's `picks/` are the lineup *after* automatic subs (GW5: João Pedro, picked to start, is at position 13; Ajayi at 5). A captain who did not play is benched with multiplier 0 and the vice gets 2 (4 of 4 cases in 100 other teams). Task 04's note in `docs/fpl-api.md` said otherwise and is corrected. The service exposes both `starter` (after subs) and `picked_starter`, plus `effective_captain_id`. Relevant to task 11.
- Errors checked live: GW7 → `gameweek_not_started`, GW39 → `gameweek_out_of_range`, team 999999999 → `team_not_found`, `abc` / `0` → 422. Repeat request for GW5 made 0 FPL calls.
- Cache: `data_checked` gameweeks 24 h (`FPL_FINISHED_CACHE_TTL_SECONDS`, new), others 60 s. `TTLCache.set()` gained an optional per-entry TTL.
- **Interim list view** (owner request): the frontend page now takes a team ID and lists the XI by role and the bench, with captain / vice / triple-captain badges, auto-sub badges, chip, bank, value and formation, and previous / next gameweek buttons (`frontend/src/TeamList.tsx`, `?team=&gw=` in the URL). It opens on `GET /api/gameweeks/latest`. To be replaced by the pitch view in tasks 13-14.
- 85 tests pass (29 new in `tests/test_fpl_team.py`, 1 in `test_cache.py`).
