# 13 — Pitch rendering (static, one locked GW) 🛑

**Status:** awaiting-approval
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
- [x] The frontend shows the owner's team for one locked GW.
- [x] Screenshot saved to `docs/screenshots/pitch-v1.png`.
- [ ] Status `awaiting-approval`, stopped; **owner approves the look** and flips to `done` (or leaves feedback in Notes for another iteration).

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- **Built (2026-10-17):** `frontend/src/Pitch.tsx` (SVG pitch, to scale in metres: 68 x 105 with boxes, arcs, spots, goals, mown stripes), `frontend/src/pitchLayout.ts` (0-100 frame → SVG, label placement, nudging), `frontend/src/PitchCard.tsx` (team name, GW number, state badge, legend, note), `fetchPlot()` in `frontend/src/api.ts`. `App.tsx` now loads `GET /api/team/{id}/plot/{gw|latest}` from `?team=&gw=`. The interim list view (`TeamList.tsx`) is removed; prev / next navigation comes in task 14.
- **Look:** Archivo variable font (self-hosted via `@fontsource-variable/archivo`, so the export in task 15 gets the same font), wide heavy team name, condensed `GW6` numeral. Role colors chosen to stay apart on grass: GK yellow, DEF sky blue, MID pink, FWD orange-red, each dot also carries its role letter (G / D / M / F) so it reads without color. Captain: black "C" badge on the dot. "from GWx" / "auto-sub" as a small second label line. Double gameweek: dashed line between the two dots. Ghosts: dashed grey circles in the right margin (the sideline). The pitch keeps the same colors in dark mode so exports match.
- **State badge wording:** locked shows "Full time", preview shows "Preview". Say if you prefer "Locked".
- **Overlapping players:** dots closer than 1.7 dot radii are pushed apart, at most 0.9 radius (about 2.3 m, under 2.5% of the pitch), so two players in the same spot both show (GW6: Hall and De Cuyper are 1.4 units apart). Labels try 8 spots around each dot and take the first with no collision, else the least overlap.
- **Screenshots:** `docs/screenshots/pitch-v1.png` (owner's team 2020649, GW6 locked, 600 px wide), `pitch-v1-phone.png` (same at 360 px), `pitch-v1-edge-cases.png`. The owner's team has no ghost, double gameweek or "from GW" label yet, so the edge-case shot uses a dev-only sample: `http://localhost:5173/?fixture=edges` (`src/fixtures/edgeCases.ts`, not in the production build).
- Checked: `npm run build` and `npm run lint` clean; GW1-6 render; headless Chrome screenshots at 600 px and 360 px.
