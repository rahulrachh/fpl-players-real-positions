# v1 Backlog — Planner mode

**Not part of the MVP.** Moved out on 2026-10-16 by the owner's decision.
The owner is still designing Planner's data model (which tables, how squads/edits are stored). **Do not start any of this** until the owner writes the design and moves these into the main task board.

Spec reference: "Planner mode" section of `../../Project-Description.md`.
The drafts below were written before the database design (Postgres, weekly sync) and will need revising.

---

## 14 — Planner backend: squad load, player search, positions

**Status:** todo
**Depends on:** 09.

## Goal
Backend support for Planner mode.

## Scope
- `GET /api/planner/squad/{team_id}` → squad from the **last completed GW** (15 players, starter/bench), bank, squad value.
- `GET /api/players/search?q=&position=&club=` → accent-tolerant, partial/short-name search over all FPL players (e.g. "odegaard" finds Ødegaard). Each result: name, club, position, price, availability/injury flag + news, and position-data status (e.g. "no minutes since GW3", or "no data").
- `POST /api/planner/positions` with a list of FPL IDs → dot for each, using the last completed GW, falling back to most recent match played with "from GWx", ghost if none. DGW rule same as Gameweek mode.
- No roast here.

## Done when
- [ ] Squad loads for the owner's team ID.
- [ ] Search examples work and are recorded in Notes: "odegaard", "salah", a partial name, position filter, club filter.
- [ ] Positions endpoint returns fallback labels and ghosts correctly for a mixed list.


---

## 15 — Planner UI: squad, pitch + bench, add/remove

**Status:** todo
**Depends on:** 11 approved, 14.

## Goal
Build/edit a squad and see it on the pitch.

## Scope
- Planner page: load from team ID **or** start with an empty squad.
- Pitch (reuse `Pitch` component) shows only the 11 starters; 4 bench players in a row below the pitch.
- Player search panel (FPL-style) with name search, position and club filters, result rows showing all fields from task 14.
- Add player → goes to the squad (starter if XI has room, else bench); his dot appears immediately if starter. Remove player supported.

## Done when
- [ ] Owner's squad loads and renders with 11 on pitch + 4 on bench.
- [ ] Empty-squad start works; adding players one by one updates the pitch immediately.
- [ ] Remove works for starters and bench players.


---

## 16 — Planner: substitutions, warnings, approximate budget, balance readout

**Status:** todo
**Depends on:** 15.

## Goal
Make the planner a decision tool: swaps, rule warnings, money, and shape balance — all updating instantly.

## Scope
- **Substitution:** select a starter then a bench player (or reverse) → swap. GK can only swap with GK. Pitch and readouts update instantly (client-side; dot positions already loaded).
- **Warnings** (shown, never blocking):
  - Squad isn't exactly 15 with 2 GK / 5 DEF / 5 MID / 3 FWD.
  - More than 3 players from one club.
  - Starting XI isn't a valid formation (1 GK, ≥3 DEF, ≥2 MID, ≥1 FWD).
  - Approximate budget exceeded.
- **Approximate budget:** start from public bank + squad value (last completed GW); adjust by current prices as players are added/removed; shown with "≈" and a note that it may be slightly optimistic (selling prices are private).
- **Balance readout:** count of starters in defensive / middle / attacking thirds (ghosts counted separately).
- No bench order, no auto-sub simulation.

## Done when
- [ ] Each of the 4 warnings is triggered and cleared manually in the running app (steps recorded in Notes).
- [ ] GK↔outfield swap is refused; valid swaps update pitch + balance instantly.
- [ ] Budget shows "≈" with the note and changes correctly when adding/removing a player.


---

