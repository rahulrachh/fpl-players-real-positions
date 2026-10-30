# 17 — Player match details box (hover / tap)

**Status:** done (2026-10-30)
**Depends on:** 16.

## Goal
The circles are sized by points, but nothing says where the points came from. Hovering a player (tapping on a phone) opens a small box showing who he played, how many minutes, and how his FPL points add up.

## Scope
- **Data (backend):** add per-player match details to the plot API (`GET /api/team/{id}/plot/{gw}`), so the frontend needs no extra request.
  - Source: FPL `event/{gw}/live/`, which the app already calls for points. Its `explain` field lists, per fixture, each stat with its `value` and `points` (e.g. `minutes` 22 → 1). Extend `LiveElement` in `app/fpl/schemas.py` with `explain`; check the stat identifiers against a real response (minutes, goals_scored, assists, clean_sheets, goals_conceded, own_goals, penalties_saved, penalties_missed, yellow_cards, red_cards, saves, bonus, defensive contribution, ...) and record them in `docs/fpl-api.md`.
  - Opponent, home / away, score and kickoff from FPL `fixtures/` (already wrapped by the client).
  - On each dot and bench player: a list of matches, each with fixture ID, opponent club, home/away, score (or "not started" / live), minutes, the breakdown rows (stat label, value, points) and the match total; plus the captain multiplier so the box can show "× 2 = 16".
  - **Double gameweek split into two dots** (`link_group` set): each dot carries only the match its position came from (use `matches.fpl_fixture_id` for the position match). **One averaged dot**: carries both matches.
  - No database change expected: live data, cached as today (24 h for checked gameweeks, 60 s otherwise).
- **Box (frontend):**
  - Header: player name, club, role. Then per match: opponent, H/A, score, minutes played.
  - Full FPL-style breakdown: one row per stat that scored or cost points ("Minutes 90 → 2", "Goals 1 → 5", "Bonus 2 → 2", "Yellow card → −1"), then the total; captain / triple captain shown as a multiplier line, and the final number equals the circle's points.
  - A player who didn't play: "Did not play" with 0 points.
  - **Desktop:** opens on hover, closes when the pointer leaves.
  - **Touch:** tap a dot to open its box; tap the same dot, the box itself, or anywhere else to close; tapping another dot switches to that one.
  - Box stays inside the card (flips side / above-below near edges), works at 360 px wide, follows the light / dark theme, keyboard focus opens it too.
  - Applies to **pitch dots and bench cards**.
  - **Not** shown for ghosts or "from GWx" dots (owner, 2026-10-30).
  - Never appears in the exported image (the export draws from an off-screen copy; confirm the box isn't copied).
- **Docs:** new fields in `docs/api.md` with a sample.

## Done when
- [x] Plot API returns the match details; tests cover a normal match, a non-player, a captain, a double gameweek with two dots (one match each) and with one averaged dot (both matches).
- [x] On the owner's team (2020649), for 3 players in GW8, the box's breakdown and total match the FPL site (recorded in Notes).
- [x] Hover works in a desktop browser; tap open / switch / close works on an emulated phone (screenshots in `docs/screenshots/match-details/`).
- [x] Bench cards open the box; ghosts and "from GWx" dots don't.
- [x] Exported image has no box in it.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- Owner decisions (2026-10-30): tap to open on touch (tap same dot / box / elsewhere to close, another dot to switch); full FPL-style breakdown; bench cards included, ghosts and "from GWx" dots excluded; split double-gameweek dots show only their own match.
- **Backend:** `LiveElement.explain` and fixture scores added to `app/fpl/schemas.py`. `TeamService` builds each pick's `matches` (opponent, H/A, score, state, minutes, non-zero stat rows with FPL-site labels, match total) from `event/{gw}/live/` + `fixtures/?event={gw}` (one extra FPL call per team load, in the same cache). Dots carry `multiplier` and `matches`; a linked double-gameweek dot keeps only the match its position came from (the stored match's `fpl_fixture_id`), an averaged dot keeps both. Bench players carry `matches` too. No database change. 8 new tests (normal match, did not play, bench, captain multiplier, DGW two dots, DGW one dot, match states); 234 backend tests pass.
- **Real data check (GW8, 669 players):** every player's `explain` points add up to `total_points`. Owner's team GW8: all 15 breakdowns add up to the circle / bench points, the dots to 48.
- **FPL site comparison (owner's team 2020649, GW8, 2026-10-30):** opened the FPL points page in Chrome and each player's breakdown. Haaland: Minutes played 90 → 2, Goals scored 1 → 4, Bonus 2 → 2 = 8, box shows `8 × 2` = 16 (captain). Konsa: 90 → 2, goal 1 → 6, clean sheet 1 → 4, bonus 2 → 2 = 14. Palmer: 79 → 2, red card 1 → −3 = −1. All three identical to the box (`docs/screenshots/match-details/fpl-site-*.png`).
- **Frontend:** `MatchDetails.tsx` (the box) and `useMatchDetails.ts` (open / close). The box is rendered in a frame around the card, outside the `<article>` the export copies, so it can't appear in the image. Placed below the dot, flipped above near the bottom, kept inside the card's sides. Split DGW dot: its own match, then an "Other match, vs X" line, so the total equals the circle. Hover outline only on devices that hover (a tap left `:hover` stuck on phones); the phone tap highlight is turned off.
- **Browser checks (Playwright, Chrome, 27 / 27 pass):** desktop hover opens / leaving closes, bench card, keyboard focus + Escape; edge-case sample: "from GWx" dot and ghosts not interactive, split DGW, Triple Captain `5 × 3`, "Did not play"; emulated phone at 412 px light and 360 px dark: tap open, box inside card, tap same dot closes, another dot switches, tap box closes, tap elsewhere closes, bench card opens. An export drawn while a box was open has no box (`export-with-box-open.png`). Screenshots in `docs/screenshots/match-details/`.
- On a phone the open box covers part of the pitch; a dot under it is reached by tapping the box (closes it) first, as the spec says.
- **Owner changes (2026-10-30, after first review):** box made smaller (13rem wide, smaller text and spacing); the opponent / home-away / score line removed; the "90 min" line under it removed, since minutes are already the first breakdown row. The box now shows only "Did not play" (0 minutes) or "Not played yet" (match not started) above the breakdown, and "Match 1" / "Match 2" labels in a double gameweek with one averaged dot. The split double-gameweek line reads "Other match". The API still returns opponent, home / away, score and kick-off (unused by the box for now). Browser checks re-run: 27 / 27 pass; screenshots replaced.
- **Owner changes, round 2 (2026-10-30):** labels shortened to "Minutes" and "Def. Con." (in `STAT_LABELS`, so the API sends them too); the bench box no longer says the points didn't count. The box header shows a short name: the first word of the first name + FPL's short name, or the short name alone when it already holds the first name; initials FPL adds to short names are dropped ("Maxim De Cuyper", "Ezri Konsa", "João Pedro", "Gabriel", "Jurriën Timber" from "J.Timber", "Pape Sarr" from "P.M.Sarr"). Checked over all 667 FPL players. Browser checks: 27 / 27 pass; screenshots replaced.
