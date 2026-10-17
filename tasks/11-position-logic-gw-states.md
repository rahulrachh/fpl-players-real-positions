# 11 — Position logic II: gameweek states, auto-subs, double gameweek (+ unit tests)

**Status:** done (2026-10-17)
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
- [x] Unit tests cover: preview vs locked detection (including finished-but-not-yet-synced = preview); preview fallback label; locked with auto-sub; locked ghost with no replacement; DGW same side gives 1 averaged dot; DGW opposite flanks gives 2 linked dots; DGW within margin gives 1 dot; captain flag preserved.
- [x] `pytest` passes (including task 10 tests).

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- `app/logic/gameweek.py` (pure): `gameweek_state` / `team_state`, `plotted_picks`, `combine_matches`, `build_dots` → `Dot`s. `load_positions_synced` added to `app/logic/repository.py`. Described in `docs/position-logic.md`.
- Preview rebuilds the picked XI from `automatic_subs` (FPL's picks are after auto-subs, task 05) and uses only the single most recent match, so a DGW is combined only when locked.
- "From GWx" is hidden when the match is from the previous GW **or** the target GW itself (already played in an in-progress GW).
- Armband: picked captain in preview; `effective_captain_id` in locked (a captain who did not play is benched, not drawn). Both linked DGW dots carry it.
- Opposite flanks: two dots, each the average of the matches on its side of center (generalizes to more than two matches). New setting `DGW_FLANK_MARGIN` (default 10, 0-50), not yet tuned: no DGW in GW1-6.
- Real data: owner's team GW1-6 all locked with 11 dots and no ghosts; auto-subs checked on teams 7241584 and 4155286 (GW5). 195 tests pass (26 new).
