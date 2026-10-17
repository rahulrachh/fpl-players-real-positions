# 11 — Position logic II: gameweek states, auto-subs, double gameweek (+ unit tests)

**Status:** todo
**Depends on:** 05, 10.

## Goal
Turn a team's gameweek into the final list of dots, following the spec's Preview / Locked rules. Unit tests required.

## Scope
- **State detection:** `locked` = GW finished in FPL **and** `gameweeks.positions_synced` (the offline sync has stored all its matches and that DB was deployed). Otherwise `preview`.
- **Preview:** starting XI as picked, each dot from the player's most recent match played **that is in the database** (task 10), with "from GWx" label when not the previous GW. No auto-subs.
- **Locked:** actual positions from that GW with FPL's auto-subs applied (sub-in takes the starter's slot). Starter with no match and no auto-sub replacement becomes a ghost.
- **Double gameweek:** use **all** of the player's rows with that `gw`, including a rescheduled match that FPL moved into the DGW (task 07 assigns `gw` from FPL fixtures). One dot (average) if roughly the same position; **two linked dots** if on opposite flanks: different sides of the center line, each beyond `DGW_FLANK_MARGIN` (env-configurable) from center.
- Captain flag carried through for the armband. Bench not plotted.

## Done when
- [ ] Unit tests cover: preview vs locked detection (including finished-but-not-yet-synced = preview); preview fallback label; locked with auto-sub; locked ghost with no replacement; DGW same side gives 1 averaged dot; DGW opposite flanks gives 2 linked dots; DGW within margin gives 1 dot; captain flag preserved.
- [ ] `pytest` passes (including task 10 tests).

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
