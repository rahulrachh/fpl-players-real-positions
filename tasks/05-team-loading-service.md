# 05 — Team loading service 🛑 👤

**Status:** todo
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
- [ ] Correct data for the owner's team for at least 2 past GWs (compared against the FPL website; recorded in Notes).
- [ ] Auto-subs and captain match FPL.
- [ ] A repeat request within the cache window makes no FPL call.
- [ ] Status `awaiting-approval`, stopped; **owner confirms** and flips to `done`.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
