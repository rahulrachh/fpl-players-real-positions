# 12 — Gameweek plot API endpoint

**Status:** todo
**Depends on:** 11.

## Goal
One endpoint the frontend calls to draw a gameweek graphic. Reads only from the bundled read-only database and live FPL data; never calls Sofascore.

## Scope
- `GET /api/team/{team_id}/plot/{gw}` returns `{ team_name, gw, state: preview|locked, prev_gw, next_gw, data_as_of, dots: [{fpl_id, name, web_name, role, club, x, y, is_captain, is_ghost, from_gw?, link_group?}] }`.
- `GET /api/team/{team_id}/plot/latest` resolves the most recent gameweek.
- Response shape documented in `docs/api.md`.

## Done when
- [ ] Valid plot JSON for the owner's team for a locked GW and for the current/preview GW (samples in `docs/api.md`).
- [ ] No Sofascore requests during these calls (verified in logs).
- [ ] `prev_gw` / `next_gw` correct at the season edges.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
