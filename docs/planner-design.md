# Planner mode: design

Agreed with the owner on 2026-10-31. Spec: "Planner mode" section of `../Project-Description.md`; where they differ, this file wins. Tasks: 19-22 in `../tasks/README.md`.

## Where Planner lives

A **Planner tab in the page header**, next to Gameweek mode, so switching between "how did my team look" and "how will it look" is one tap. Share links open Planner directly at `/p/<code>`. The team ID entered in either mode is shared (one remembered team).

## Squad storage and sharing: no database

Planner adds **no tables** and the web app stays read-only. The squad being edited lives in the browser:

- **In memory** while editing.
- **`localStorage`** keeps the last draft, so it is still there after a reload (same browser only). Every read and write is wrapped in try/catch; the page must work without it.
- **Share link**: the squad is packed into a short code in the URL, e.g. `/p/Eaw3F9xQ2mZp7AbR4tW8nLc0Yv`. The address bar updates as the squad changes, so the current URL is always shareable. Opening a link loads that squad as a new draft; the friend's edits change their own link, never the original.

A database-backed short link (12-char code → stored squad) was considered and **rejected for v1**: it would need the project's first hosted store, a public write endpoint with abuse protection, and a retention policy. Revisit only if we want editable shared plans, saved plans per user, or shorter links.

## Share code format (version 1)

1. **Slot order carries the roles:** slots 1-11 are the starting XI, slots 12-15 the bench. No extra bits mark starters.
2. **Header:** 4-bit format version (`0001` for v1).
3. **Players:** 15 × 10-bit unsigned FPL player IDs (max 1023; current IDs are below 700). **ID `0` = empty slot**, so partial squads (empty-squad start, mid-edit) can be shared. FPL IDs start at 1.
4. **Total** 4 + 150 = 154 bits, padded with zero bits to a multiple of 6 (156), written as base64url (`A-Z a-z 0-9 - _`, no `=` padding) → **26 characters**.

Decoding reverses it: characters → 6-bit groups → one bit string → skip the 4-bit version → 10-bit chunks → IDs. Encoder and decoder live in the frontend, with round-trip tests (full squad, partial squad, all empty, ID 1023).

**Versioning.** FPL reuses player IDs each season, so an old link would show the wrong players. The version is bumped every season (and whenever the format changes, e.g. 11 bits per ID if FPL ever passes 1023 players). The app maps each version to its season; a link with a version from another season shows "This plan is from 20XX/YY and can't be opened" rather than wrong players. An unknown version, wrong length or bad character shows "This link is broken".

**Not secret.** The code only looks opaque; anyone can decode it. Fine, because it holds only public FPL player IDs.

**What a link shows.** The players, not a snapshot: positions and prices are whatever data is live when the link is opened. An ID not in the current player list (left the league) shows as an empty slot with a note.

## Budget: real selling prices (option B)

The budget uses each player's **estimated selling price**, not bank + squad value (which counts current prices and is optimistic when players have risen). Chosen over a plain "≈" budget because the budget is the one Planner number that directly drives a decision.

**FPL selling rule.** Price rose since purchase: selling price = purchase + floor((current − purchase) / 2), in £0.1m units (bought £7.0m, now £7.5m → sells for £7.2m). Price fell or unchanged: selling price = current price.

**Purchase prices**, all from public endpoints:
- Transferred-in players: `element_in_cost` from `entry/{id}/transfers/` (only transfers whose deadline has passed; pending ones are private).
- Players held since the team's first squad: their price in the team's `started_event`, from the per-player price history (`element-summary/{id}/` `history[].value`).
- A player sold and bought back: the latest buy-in price counts.

**Budget** = bank at the last deadline + sum of selling prices of the squad. Removing a squad player adds his selling price; adding a player costs his **current** price. Players added in the planner and then removed again refund their current price (no rise to halve). Re-adding an original squad player you removed counts as undoing the sale: he comes back at his selling price, not the current price.

**Current prices are fetched live** from FPL `bootstrap-static` (the client's 60 s cache), not from `fpl.db`, which is only as fresh as the last deployed sync. Same for availability / injury news in search results.

**To verify in a spike before building** (record in `docs/fpl-api.md`):
- Computed squad selling value matches what the FPL site shows on the owner's transfers page.
- **Free Hit:** do its transfers appear in `transfers/`, and do pre-Free-Hit purchase prices apply again afterwards? **Wildcard:** listed normally?
- Cost: `element-summary` is one call per player; check whether 15 calls per team load is acceptable (cached) or whether a cheaper source for the start-GW price exists.

If Free Hit turns out not to be computable reliably, fall back to "≈" (bank + current prices, with a note) **only** for teams that have played a Free Hit.

**Not in the share link.** A shared squad has no owner team, so it shows only the total current price of the 15 (no bank, no selling prices).

## Which gameweek the positions come from

Planner's base gameweek is **the latest gameweek with synced positions** (`positions_synced`), not FPL's last finished gameweek. Positions only reach the site on sync + deploy, so between FPL finishing GWn and the next deploy, the base stays GWn−1. Following FPL strictly was rejected: every dot would read "from GWn−1" every week until deploy.

- Played in the base gameweek → plain dot, no label.
- Didn't → most recent earlier match, labelled "from GWx".
- No usable match at all → ghost on the sideline.
- Base gameweek was a double gameweek → same rule as Gameweek mode (two linked dots or one averaged dot).
- A banner on the pitch states the base, e.g. "Positions up to GW7", alongside the existing "Positions as of" date.

This is the preview rule from task 11 (`app/logic/gameweek.py`, `place_players()` in `app/logic/positions.py`) with the target set to the base gameweek; reuse it rather than writing a new one. The same base is used for the "no minutes since GWx" status in search results.

The **squad loaded from a team ID** is unaffected: it is still the picks of FPL's latest passed deadline.

## Dots on the Planner pitch

- **All dots are the same size.** Planner answers "does this team lean forward or back?", so only position carries meaning. Size was not tied to price (draws the eye away from the shape), base-GW points (noisy, and looks like Gameweek mode) or form/expected points (no data source chosen).
- Reuse the `Pitch` component from task 13, with points sizing and the points number inside the circle turned off. Role colors, role letter, short-name labels, collision handling, "from GWx" second line, double gameweek links and sideline ghosts stay as in Gameweek mode. No captain badge (captaincy isn't part of Planner).
- Price and availability go in the hover/tap box (task 17's box), not on the dot: current price, selling price (team-loaded squads only), availability flag + news, and which match the position comes from.

## UX reference

[LiveFPL planner](https://www.livefpl.net/planner): look at it when implementing (search panel, squad editing, budget display) for ideas. Take ideas only, not its design or wording.
