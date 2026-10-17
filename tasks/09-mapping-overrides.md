# 09 — Manual override file + coverage target

**Status:** todo
**Depends on:** 08.

## Goal
Close the gap left by auto-matching with a human-editable override file, reaching a high share of active players.

## Scope
- `backend/data/player_overrides.csv` (committed): `fpl_id, sofascore_id (or empty = force no match), comment`. Applied on every mapping run as rows in `player_id_map` with `match_method = override`, `is_override = true`; "force no match" deletes that player's row. Overrides always win.
- Populate overrides for unmatched / wrong low-confidence players from task 08's report.
- Regenerate the coverage report with an "overrides applied" count; explain the file format at the top of `docs/mapping-coverage.md`.

## Done when
- [ ] Override file exists, is documented, and is applied by the mapping command.
- [ ] **At least 97% of active players** (minutes this season) are mapped; the rest are listed with a reason.
- [ ] Re-running mapping is idempotent and keeps overrides.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
