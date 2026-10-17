# 14 — Gameweek mode UI + navigation

**Status:** todo
**Depends on:** 13 approved.

## Goal
The full Gameweek mode flow, minus image export (task 15).

## Scope
- Team ID input (remember last ID in localStorage), then show the most recent GW graphic.
- Prev / Next buttons step one GW at a time; disabled at edges; GW number and state badge (Preview / Locked) shown, plus a "positions data as of" date (from `sync_runs`).
- Loading and error states (bad team ID, GW not synced yet).
- No Planner UI and no roast (both v1).

## Done when
- [ ] Entering the owner's team ID shows the latest GW.
- [ ] The owner's team can be stepped back through at least 5 gameweeks without errors (verified in the running app; noted).
- [ ] Preview GW shows "from GWx" labels where applicable; locked GW shows auto-subbed players.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- 2026-10-17: prev / next navigation already built during task 13 (owner request): round arrows either side of the GW label in the card header plus the left / right arrow keys, disabled at the edges, URL `?team=&gw=`, card dimmed while loading; checked GW6 → GW1 → GW2 for team 2020649. Still to do here: remember the last team ID (localStorage), "positions data as of" placement, loading / error states review, preview-GW checks.
