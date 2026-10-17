# 15 — Image export

**Status:** todo
**Depends on:** 14.

## Goal
Each gameweek graphic can be downloaded as a shareable image.

## Scope
- "Export as image" button producing a PNG of the pitch card (pitch + team name + GW + legend).
- Client-side export (e.g. `html-to-image` or SVG to canvas). Fonts and colors must match the screen.
- Filename like `realshape-{team}-gw{n}.png`.

## Done when
- [ ] Exported PNGs for 3 different gameweeks match the on-screen graphic (saved to `docs/screenshots/exports/`).
- [ ] Works in Chrome and one other browser (or noted if not tested).

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
