# 10 — Position logic I: frame, "last match played" fallback, ghosts (+ unit tests)

**Status:** todo
**Depends on:** 09.

## Goal
Pure functions that decide **where each player's dot goes**, independent of HTTP and UI. Unit tests required for this task.

## Scope
- `backend/app/logic/positions.py`: pure and source-agnostic; takes plain data (rows loaded by a thin repository function), not DB sessions.
- Frame: the single place the shared "attacking upward" frame is defined/validated.
- **Most recent match played:** given a player and a target GW, return his position from that GW if he played, otherwise from his most recent earlier match, plus the source GW (for the "from GW4" label). Repository query uses the (player, kickoff) index.
- **Ghost:** no usable match, or no Sofascore mapping, means ghost (sideline, greyed).
- Config values (e.g. margins) from settings, not literals.

## Done when
- [ ] pytest unit tests cover: played in target GW; fell back to an earlier GW with the correct label; never played gives a ghost; mapping missing gives a ghost.
- [ ] `pytest` passes.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
