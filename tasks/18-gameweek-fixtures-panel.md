# 18 — Gameweek fixtures panel with top 3 players

**Status:** todo
**Depends on:** 16. Shares the FPL `explain` parsing with task 17 (whichever is built first adds it).

## Goal
While looking at a team's points, see every match of that gameweek and its score, and open a match to see its top 3 players, with the team's own starters highlighted.

## Scope
- **Data (backend):** new `GET /api/gameweek/{gw}/fixtures`. Same for every team, so it is cached on its own (24 h for checked gameweeks, 60 s otherwise) and doesn't touch the plot endpoint.
  - Fixtures from FPL `fixtures/?event={gw}`: home / away club, score, kickoff, state (not started / live / finished).
  - Per fixture, the top 3 players by FPL points **in that fixture** (both teams), from `event/{gw}/live/` `explain` (sum of the stat points for that fixture). Ties at 3rd place: include everyone tied. Each player: FPL ID, web name, club, role, points.
  - Double gameweek: a player's points are split per fixture, so he can appear in two matches.
  - No database change expected.
- **Panel (frontend):**
  - **Desktop / tablet:** a column to the right of the pitch card. **Phone:** stacked below the card (after the bench).
  - Follows the gameweek shown on the card (changes with the < > arrows and arrow keys).
  - One row per match, ordered by kickoff: "ARS 2 – 1 CHE" with club short names; unstarted matches show the kickoff time, live ones a "Live" tag.
  - Each row is a dropdown: click / tap to expand and show the top 3 (name, club, points); click again to collapse. Several can be open at once.
  - Unstarted match: expanding says "Not played yet".
  - **Highlight the team's starters** (XI after auto-subs in a locked gameweek, the XI as picked in preview; bench players are not highlighted): their rows in the top 3 are marked (e.g. role-colour accent and a "Your team" tag), and a collapsed match row shows a small badge when one of them is in its top 3. Highlighting is done in the browser from the plot response, so the endpoint stays team-free.
  - Light / dark theme, keyboard accessible (rows are buttons with `aria-expanded`), fits 360 px.
  - **Not** part of the exported image: the export stays the pitch card.
- **Docs:** endpoint in `docs/api.md` with a sample.

## Done when
- [ ] Endpoint tests cover a finished match, an unstarted match, a tie for 3rd, and a double-gameweek player in two fixtures.
- [ ] GW8 checked against the FPL site: all 10 scores and the top 3 of 3 matches match (recorded in Notes).
- [ ] On the owner's team (2020649), a match with one of his starters in the top 3 shows the header badge and the highlighted row; a bench player in a top 3 is not highlighted.
- [ ] Panel sits right of the card on desktop and below it on an emulated phone; it follows the gameweek arrows (screenshots in `docs/screenshots/fixtures-panel/`).
- [ ] Exported image unchanged (no panel).

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- Owner decisions (2026-10-30): right of the card on desktop, below it on phones; top 3 by FPL points in that match, ties included; highlight the team's starters only, both in the expanded list and as a badge on the collapsed row; not in the exported image.
- Defaults chosen without asking (change if wanted): ordered by kickoff, several dropdowns can be open at once, all collapsed on load.
