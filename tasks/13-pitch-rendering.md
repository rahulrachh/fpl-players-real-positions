# 13 — Pitch rendering (static, one locked GW) 🛑

**Status:** todo
**Gate:** 🛑 Owner approves the look. When finished, set status `awaiting-approval` and STOP.
**Depends on:** 12.

## Goal
A good-looking pitch graphic for one locked gameweek, drawn from the plot API.

## Scope
- React `Pitch` component rendering SVG: pitch markings, team attacking upward.
- Dots colored by FPL role (GK / DEF / MID / FWD) with a legend; short name label; captain armband marker; small "from GWx" label; double-GW linked dots joined by a line; ghosts greyed on the sideline.
- Real positions only, no formation view.
- Responsive (fits phone width) and readable when exported later.
- Use the `frontend-design` skill for visual direction.

## Done when
- [ ] The frontend shows the owner's team for one locked GW.
- [ ] Screenshot saved to `docs/screenshots/pitch-v1.png`.
- [ ] Status `awaiting-approval`, stopped; **owner approves the look** and flips to `done` (or leaves feedback in Notes for another iteration).

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
