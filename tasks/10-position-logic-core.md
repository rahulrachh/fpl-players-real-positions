# 10 — Position logic I: frame, "last match played" fallback, ghosts (+ unit tests)

**Status:** done (2026-10-17)
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
- [x] pytest unit tests cover: played in target GW; fell back to an earlier GW with the correct label; never played gives a ghost; mapping missing gives a ghost.
- [x] `pytest` passes.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- `app/logic/positions.py` (pure) + `app/logic/repository.py` (queries); described in `docs/position-logic.md`.
- Target GW keeps **every** usable match of that GW (a DGW gives two; task 11 combines them). The fallback takes the single most recent usable match by **kickoff**, so a rescheduled match counts when it was played.
- Matches in later GWs or with no GW are never used. A ghost carries a reason (`no_mapping` / `no_match`) and no x / y.
- New setting `POSITION_MIN_POINTS_COUNT` (default 1): a match is usable only if its average comes from at least that many on-ball actions.
- The repository filters on player only so SQLite uses the (player, kickoff) index (filtering on `gw` made it pick the (player, gw) index); a test checks the query plan.
- On the committed DB, all 436 active players are placed for GW6 and GW7, 0 ghosts.
