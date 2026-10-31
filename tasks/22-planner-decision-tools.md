# 22 — Planner decision tools: warnings, budget, balance

**Status:** todo
**Depends on:** 21 approved. Design: `docs/planner-design.md`.

## Goal
Turn the Planner into a decision tool: rule warnings, money left and shape balance, all updating instantly as the squad changes.

## Scope
- **Warnings** (shown, never blocking):
  - Squad isn't exactly 15 with 2 GK / 5 DEF / 5 MID / 3 FWD.
  - More than 3 players from one club.
  - Starting XI isn't a valid formation (1 GK, ≥3 DEF, ≥2 MID, ≥1 FWD).
  - Budget exceeded.
- **Budget** per "Budget: real selling prices": bank + selling prices; removing a squad player adds his selling price, adding a player costs his current price, undoing a sale restores the selling price. "≈" with a note only for the Free Hit fallback (if task 19 needed it). A share-link squad without a team shows only the total current price.
- **Balance readout:** count of starters in the defensive / middle / attacking thirds (by the dot's plotted depth); ghosts counted separately.
- No bench order, no auto-sub simulation.

## Done when
- [ ] Each of the 4 warnings is triggered and cleared in the running app (steps recorded in Notes).
- [ ] Budget for the owner's team matches the FPL site's transfers page, and changes correctly when selling, buying and undoing a sale.
- [ ] Balance readout updates instantly on add, remove and swap; ghosts shown separately.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update `tasks/PROGRESS.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path.

## Notes
