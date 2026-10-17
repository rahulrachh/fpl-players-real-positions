# FPL Real Shape Visualizer: Spec (v0)

> **Scope changes (2026-10-16), these override the text below:**
> - **Planner mode is moved to v1.** The MVP is Gameweek mode only. Planner sections and milestone 7 are kept for reference; do not build them. See `tasks/v1-backlog/planner.md`.
> - **Claude roast is moved to v1.** No live Claude API calls from the site; the plan is pre-generated roasts per shape bucket, shipped with each deployment. See `tasks/v1-backlog/roast.md`.
> - **Data is refreshed offline.** The owner runs a sync script locally that updates a SQLite file; the file is committed and shipped with each deployment, and the site opens it read-only. New data goes live only on deploy. No online worker, no hosted database.
> - **The MVP is deployed to Vercel** (free Hobby plan). Task breakdown: `tasks/README.md`.

## What it is

FPL shows your team as a tidy formation. In reality, FPL managers pick attacking players: wing-backs as "defenders" and forwards as "midfielders". This tool plots where a team's players **actually** played on the pitch, using real per-match average positions.

It has two modes:

- **Gameweek mode** shows the joke you share. You see a team's real shape for any gameweek, with a Claude-written roast and an image export.
- **Planner mode** is the decision tool. Before the deadline, you build or edit your team and see whether it leans too far forward or back, based on where each player played most recently.

Defaults chosen during scoping are marked **(default)**. The owner can override them.

---

## Gameweek mode

### User flow
1. The user enters an FPL team ID.
2. The app shows the graphic for the **most recent gameweek**.
3. **Prev / Next** buttons step through earlier gameweeks, one graphic per gameweek.
4. Each graphic has a Claude roast caption and an **export as image** button.

### Gameweek states
- **Preview** (the gameweek is upcoming or in progress): plot the starting XI picked for that gameweek. Each dot uses that player's **most recent match he actually played**. If that match wasn't in the previous gameweek, show a small label such as "from GW4". No auto-subs are applied.
- **Locked** (all fixtures are finished and position data is available): plot actual positions from that gameweek with **FPL auto-subs applied**. Locked gameweeks never change and are cached permanently.

### Plotting rules
- Show **real positions only**, with no formation view. Dots are colored by FPL role (GK / DEF / MID / FWD), so the mismatch speaks for itself.
- **Orientation:** normalize every position so all teams attack in the same direction, for example upward. Positions from different clubs and home/away matches must not be mirrored.
- **Double gameweek:** show one dot (the average of both matches) if he played roughly the same position both times, or **two linked dots** if he played on opposite flanks.
  - **(default)** "Opposite flanks" means the two positions are on different sides of the pitch's center line, each beyond a configurable margin from center. Everything else counts as "roughly similar." Tune the margin after seeing real data.
- **(default)** The captain gets an armband marker.
- **(default)** Bench players are not plotted.
- **(default)** A starter with no match and no auto-sub replacement appears as a greyed-out ghost on the sideline.

---

## Planner mode

### Purpose
Before a deadline, for example while picking a GW7 team, you see where your players line up on the pitch based on **the last completed gameweek** (GW6). This answers whether enough of the team plays forward or back.

### Loading a team
- **No FPL login.** You enter a team ID, and the app loads that team's squad from the **last completed gameweek** (public data).
- Pending transfers for the upcoming gameweek are private and **not** loaded. You make those swaps in the planner instead.
- You can also **start from an empty squad**.

### Player search (FPL-style)
- Searches all players from FPL's public player list.
- Name search tolerates accents and partial or short names (for example, "odegaard" finds Ødegaard).
- Filters by position and club.
- Each result shows name, club, position, price, an injury/availability flag, and whether the player has usable recent position data (for example, "no minutes since GW3").
- Adding a player places him in the squad. If he's in the starting XI, his dot appears on the pitch immediately.
- Removing a player is supported.

### Dot position in Planner mode
- Uses the player's average position from **the last completed gameweek**.
- If he didn't play that gameweek, it uses his **most recent match played** and shows a label such as "from GW4".
- If he has no position data at all, he shows as a ghost on the sideline. **(default)**
- Double gameweek rule: the same as in Gameweek mode.

### Pitch and bench
- Only the **11 starters** are plotted on the pitch.
- The **4 bench players** sit in a row below the pitch.
- **Bench order does not matter in v0.**

### Substitution
- Select a starter, then a bench player (or the reverse), and they swap.
- The pitch graphic and the balance readout **update instantly**.
- **(default)** A goalkeeper can only swap with a goalkeeper, as in FPL.

### Warnings (shown, never blocking)
- The squad isn't exactly 15 players with 2 GK, 5 DEF, 5 MID and 3 FWD.
- There are more than 3 players from one club.
- The starting XI isn't a valid FPL formation: exactly 1 GK, at least 3 DEF, at least 2 MID and at least 1 FWD.
- The **approximate budget** is exceeded (see below).

### Budget (approximate)
- Start from the team's public **bank and squad value** as of the last completed gameweek, then update as players are swapped.
- Real selling prices depend on purchase prices, which are private, so the budget is shown with "≈" and a short note that it may be slightly optimistic.

### Balance readout
- Counts of starters whose position falls in the **defensive, middle and attacking thirds** of the pitch.

### Claude in Planner mode
- **(default)** No roast in Planner mode. Keep it clean while you make real decisions.

---

## Data

### Official FPL API (public, no login)
Provides the player list (names, clubs, positions, prices, availability), fixtures, gameweek status and deadlines, each team's picks for gameweeks whose deadline has passed, captaincy, auto-subs, and bank/squad value per gameweek.

**Verify in the spike:** confirm exactly which data is public and which is private, especially picks before a deadline and the money fields. The API is unofficial and can change.

### Average positions (unofficial free source)
- Accessed **only through one swappable adapter module**. If the source breaks or blocks access, only that module changes.
- Fetch politely with a low request rate.
- Cache locked gameweeks permanently and recent or preview data with a short expiry.

### Player ID mapping
- Link FPL player IDs to the positions source's player IDs.
- This is the **hardest hidden task**: names differ in accents, nicknames and shortened forms.
- It needs an automatic matching step, a **coverage report** (percentage of players matched), and a **manual override file** for the leftovers.

---

## Claude roast (Gameweek mode only)

- One **savage roast** per team per gameweek.
- Claude receives a structured summary of the shape, not raw data. Examples: average defender depth, players far from their FPL role, ghosts, and where the captain played.
- Guardrails: football banter only. It roasts the manager's picks and the shape, never real players' personal lives.
- The caption is cached per team and gameweek. A preview-state caption is replaced once the gameweek locks.

---

## Hosting

- **Local first, deployable later.**
- Keep a clean backend/frontend split, put configuration and API keys in environment settings, and avoid machine-specific paths.
- No FPL credentials are ever handled.

## Out of scope for v0
- FPL login or reading pending transfers.
- Bench order and auto-sub simulation in Planner mode.
- League comparisons, season animations, user accounts.
- Public deployment with rate limiting.

---

## Milestones

Each milestone has a "done" condition. 🛑 marks a **human checkpoint**: the build loop must stop and wait for review.

1. **Positions source spike** 🛑. Confirm the unofficial source returns per-match average positions for EPL players, and document the fields, orientation and coverage. *Done when* a written report exists and the owner approves the source.
2. **FPL data layer.** Team ID → picks, captain, auto-subs, gameweek status, bank and value. Player list loaded. Public/private boundaries documented. *Done when* the owner's real team loads correctly for a past gameweek.
3. **Player ID mapping.** *Done when* the coverage report exists, a high share of active players match, and the override file is in place.
4. **Position logic.** Preview vs. locked states, orientation normalization, the double gameweek rule, the "last match played" fallback and ghosts. *Done when* tests cover each rule.
5. **Pitch rendering** 🛑. A static graphic for one locked gameweek. *Done when* the owner approves the look.
6. **Gameweek mode.** Prev/next navigation and image export. *Done when* the owner can step back through several gameweeks and export each one.
7. **Planner mode.** Load squad from team ID or start empty, search, add/remove, substitution, warnings, approximate budget, balance readout. *Done when* each warning triggers correctly and substitutions update the graphic instantly.
8. **Claude roast.** Caption generation with caching. *Done when* captions appear for locked and preview gameweeks and repeat views don't call the API again.
9. **Deploy-readiness pass.** Configuration cleanup and a README. *Done when* a fresh clone runs locally from the README alone.