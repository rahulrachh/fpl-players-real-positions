# 04 — FPL API client + public/private boundaries

**Status:** todo
**Depends on:** 03.

## Goal
Fetch all public FPL data the app needs, persist the stable parts, and document what is public vs. private.

## Scope
- `backend/app/fpl/client.py` wrapping public endpoints:
  - `bootstrap-static/` (players, clubs, roles, prices, availability, gameweeks/deadlines/status)
  - `fixtures/`
  - `entry/{id}/`, `entry/{id}/history/` (bank, value per GW)
  - `entry/{id}/event/{gw}/picks/` (picks, captain, `automatic_subs`, `entry_history`)
  - `event/{gw}/live/` (minutes, if needed)
- `refresh_fpl_reference_data()` upserts `fpl_clubs`, `fpl_players`, `gameweeks` (called by the offline sync script in task 07).
- Short-TTL cache for volatile calls (current GW status, live data).
- **Verify by experiment** and document: are upcoming-GW picks visible before the deadline? Which money fields are public? What happens with an invalid team ID?

## Done when
- [ ] Client functions exist for every endpoint above.
- [ ] `refresh_fpl_reference_data()` populates the three tables (row counts in Notes).
- [ ] `docs/fpl-api.md` documents endpoints, fields used, and the verified public/private boundary.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
