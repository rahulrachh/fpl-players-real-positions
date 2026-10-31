# 21 — Planner UI: squad on the pitch, search, substitutions, share link

**Status:** todo
**Depends on:** 20. Design: `docs/planner-design.md`. UX ideas: [LiveFPL planner](https://www.livefpl.net/planner) (ideas only, not its design or wording).

## Goal
The first usable Planner: build or edit a squad, see its real shape, and send it to a friend.

## Scope
- **Navigation:** a Planner tab in the page header next to Gameweek mode. Share links open at `/p/<code>` (Vercel rewrite to the app if needed).
- **Starting a squad:** from the remembered / entered team ID, from a share link, or empty.
- **Pitch:** reuse `Pitch` with all dots the same size, no points number, no captain badge; role colours, labels, "from GWx", DGW links and sideline ghosts as in Gameweek mode. 4 bench players in a row below. Banner "Positions up to GWn" plus the "Positions as of" date.
- **Hover / tap box** (task 17's box): current price, selling price (team-loaded squads only), availability + news, which match the position comes from.
- **Search panel:** name search, position and club filters, result rows with all task 20 fields. Add → starter if the XI has room, else bench; dot appears immediately. Remove from pitch or bench.
- **Substitutions:** select a starter then a bench player (or the reverse) to swap; GK only with GK. Instant, client-side (positions already loaded).
- **Draft in the browser:** squad kept in `localStorage` (wrapped in try/catch; page works without it).
- **Share code:** encoder / decoder per "Share code format (version 1)", with round-trip tests (full, partial, all empty, ID 1023). The address bar follows the squad, a "Copy link" button copies it. Broken link → "This link is broken"; other season → "This plan is from 20XX/YY…"; unknown player → empty slot with a note.
- Light / dark theme, keyboard accessible, fits 360 px. No image export in this task.

## Done when
- [ ] 🛑 Owner approves the look (desktop + phone screenshots in `docs/screenshots/planner/`).
- [ ] Owner's squad loads with 11 on the pitch and 4 on the bench.
- [ ] Empty start works; adding players one by one updates the pitch immediately; removing works for starters and bench.
- [ ] Valid swaps update the pitch instantly; GK ↔ outfield swap is refused.
- [ ] A copied link opened in a fresh browser profile shows the same squad; a broken and an other-season code show their messages.
- [ ] Reload keeps the draft.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md` (stop at `awaiting-approval` for the 🛑 gate).
- [ ] Update `tasks/PROGRESS.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to "waiting for owner approval on task 21".

## Notes
