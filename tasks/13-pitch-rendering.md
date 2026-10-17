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
- **Iteration 2 (owner feedback, 2026-10-17):** (1) the gameweek score is shown in the header ("66 pts", plus "−4 transfer hit" when there is one). `points` / `transfers_cost` were added to the team service and the plot API (from FPL picks `entry_history`; tests updated, 215 pass). (2) Names next to close dots were ambiguous, so every dot with another dot within ~11 m now gets a callout: the label moves out of the cluster and a thin leader line joins it to its own dot. Placement tries 16 directions at 3 distances and avoids labels over dots, lines through dots and crossing lines. Lone dots keep the plain label next to them. Checked on GW1-6 (GW2's Haaland / João Pedro overlap is now clear).
- **Iteration 3 (owner feedback, 2026-10-17): "everyone is in midfield".** Not a bug: average positions compress toward the middle. Over all 1,144 outfield player-matches of 60+ min (GW1-6), depth runs 23-80 with DEF median 41, MID 55, FWD 62; keepers 9-14 every match, so the frame is right. Haaland's GW6 (53.6) is his deepest of the season. Three depth views are on the page as buttons above the card (also `?depth=true|stretch|league`), **default True scale**: (A) true scale with dashed "typical DEF / MID / FWD" lines at the league medians; (B) one fixed piecewise stretch, keeper zone unchanged, 30-75 spread over 24-90; (C) outfield depth as a league percentile, drawn over 20-90. Side-by-side comparisons: `docs/screenshots/depth-options/gw6-compare.png`, `gw2-compare.png`. The league medians and percentiles are hard-coded in `pitchLayout.ts` from the GW1-6 data; if a view other than true scale is kept, they should come from the API and refresh with each sync. Owner to decide which views to keep.
- **Iteration 4 (owner decision, 2026-10-17):** true scale and stretched dropped (accurate but not visually good). Two views stay, as buttons above the card (`?depth=role` for the second): **All outfield players** (default): height = percentile of the dot's depth among every outfield player-match; **Same position**: percentile among player-matches of the same FPL role only (Haaland against forwards). Percentiles 0-100 are drawn at 20-90% of the pitch length; keepers keep their real spot; left-right is always real. The ranking is now computed in the backend from the database (`app/logic/depth.py`, pool = player-matches of 60+ min, refreshed with every sync) and sent as `depth_pct_all` / `depth_pct_role` on each dot; hard-coded quantiles removed from the frontend. GW6 check: Calafiori 97.6% of defenders, Haaland 9.5% of forwards (his deepest game). 219 backend tests pass. Screenshots: `pitch-v1.png` (all outfield players), `pitch-v1-same-position.png`.
- **Overlapping players:** dots closer than 1.7 dot radii are pushed apart, at most 0.9 radius (about 2.3 m, under 2.5% of the pitch), so two players in the same spot both show (GW6: Hall and De Cuyper are 1.4 units apart). Labels try 8 spots around each dot and take the first with no collision, else the least overlap.
- **Screenshots:** `docs/screenshots/pitch-v1.png` (owner's team 2020649, GW6 locked, 600 px wide), `pitch-v1-phone.png` (same at 360 px), `pitch-v1-edge-cases.png`. The owner's team has no ghost, double gameweek or "from GW" label yet, so the edge-case shot uses a dev-only sample: `http://localhost:5173/?fixture=edges` (`src/fixtures/edgeCases.ts`, not in the production build).
- Checked: `npm run build` and `npm run lint` clean; GW1-6 render; headless Chrome screenshots at 600 px and 360 px.
