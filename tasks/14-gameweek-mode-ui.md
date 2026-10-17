# 14 — Gameweek mode UI + navigation

**Status:** done (2026-10-17)
**Depends on:** 13 approved.

## Goal
The full Gameweek mode flow, minus image export (task 15).

## Scope
- Team ID input (remember last ID in localStorage), then show the most recent GW graphic.
- Prev / Next buttons step one GW at a time; disabled at edges; GW number and state badge (Preview / Locked) shown, plus a "positions data as of" date (from `sync_runs`).
- Loading and error states (bad team ID, GW not synced yet).
- No Planner UI and no roast (both v1).

## Done when
- [x] Entering the owner's team ID shows the latest GW.
- [x] The owner's team can be stepped back through at least 5 gameweeks without errors (verified in the running app; noted).
- [x] Preview GW shows "from GWx" labels where applicable; locked GW shows auto-subbed players. (Preview: tests + sample; live check pending GW7, see Notes.)

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- 2026-10-17: prev / next navigation already built during task 13 (owner request): round arrows either side of "GW6", centred in the card header between the team name and the points, plus the left / right arrow keys, disabled at the edges, URL `?team=&gw=`, card dimmed while loading; checked GW6 → GW1 → GW2 for team 2020649. Still to do here: remember the last team ID (localStorage), "positions data as of" placement, loading / error states review, preview-GW checks.
- **Built (2026-10-17):**
  - **Remembered team:** the last team that loaded is kept in this browser (`localStorage` key `realshape.team`, every access in try/catch so a private window still works) and the page opens on it when the URL has no `?team=`. An unknown team ID shows its error but does not replace the remembered team; a remembered team that no longer exists is forgotten. "Show shape" for the same team reloads its latest gameweek.
  - **Empty state:** with no team, a short prompt explains where to find the team ID (the number in the Points page address).
  - **Loading:** a pitch-shaped placeholder on first load; later loads keep the current card on screen, dimmed.
  - **Errors** say what happened and offer the next step: unknown team ("No FPL team has the ID ..."); gameweek before the team joined / not started / not in the season, each with "Show the latest gameweek"; FPL down or server unreachable, with "Try again".
  - **GW not synced yet:** the plot API now sends `status` (in_progress / finished). A finished gameweek still in preview says so on the card ("GW7 has finished, but its positions aren't in yet, so each player ... is shown from his most recent match"); an in-progress one says points are live.
  - "Positions as of" date stays in the card's footnote; GW number and Full time / Preview badge in the card header (task 13).
- **Verified in headless Chrome, one profile** (`docs/screenshots/gameweek-mode/`): empty page; load 2020649 (remembered); reopen `/` opens 2020649 GW6; `?team=999999999` error, remembered team kept; `?team=2020649&gw=39` error then "Show the latest gameweek" -> GW6; all API requests failed -> "Couldn't reach the Real Shape server" then "Try again" -> GW4 loads; stepping GW6 -> GW1 by the arrows (task 13 walk, 11 dots each).
- **Auto-subs:** the owner's team had none in GW1-6 (also noted in task 05). Checked on team 7241584 GW5: Ajayi shown with "auto-sub" in the starter's place, João Pedro on the bench as "did not play"; its circles add up to its 40 points.
- **Preview "from GWx":** no live preview gameweek exists yet (latest is GW6, finished and synced; GW7 deadline 2026-10-17 10:00 UTC). Covered by the backend tests (`test_preview_when_not_synced`, task 11 logic tests) and the `?fixture=edges` sample ("from GW2", "from GW4"). **To re-check live once GW7 opens.**
- 224 backend tests pass; frontend type-check and lint clean.

