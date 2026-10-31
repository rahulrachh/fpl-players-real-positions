# 20 — Planner backend: squad, player search, positions

**Status:** todo
**Depends on:** 12, 19. Design: `docs/planner-design.md`.

## Goal
Everything the Planner UI needs from the server, with no new tables and no writes (the web app stays read-only).

## Scope
- **`GET /api/planner/squad/{team_id}`** → the 15 picks of FPL's **latest passed deadline**, in slot order (1-11 starters, 12-15 bench), with bank, and per player: current price, purchase price and selling price (rules and fallback from task 19). Includes a flag when the budget is approximate (Free Hit fallback, if task 19 needs it). Same coded 404 / 503 errors as the plot endpoint.
- **`GET /api/players/search?q=&position=&club=`** → accent-tolerant, partial and short-name search over all FPL players ("odegaard" finds Ødegaard). Each result: FPL ID, name, web name, club, position, **live** current price, availability flag + news, and position-data status relative to the base gameweek ("no minutes since GW3", "no data").
- **`POST /api/planner/positions`** with up to 15 FPL IDs → a dot per player from the **base gameweek** (latest `positions_synced`): plain dot if he played in it, else most recent earlier match with `from_gw`, else ghost. DGW rule as in Gameweek mode. Reuse task 11's preview logic and `depth_pct`; no new placement code. Response includes `base_gw` and `data_as_of` for the banner. Unknown IDs are returned as `unknown` (not an error), so old share links can show an empty slot.
- **Live FPL data:** prices, availability and news come from `bootstrap-static` via the client's 60 s cache, not from `fpl.db`. Selling-price inputs (`transfers/`, `element-summary/`) cached as task 19 recommends.
- Docs: endpoints with samples in `docs/api.md`.

## Done when
- [ ] Owner's team (2020649) loads: 15 players in slot order, bank, selling prices equal to task 19's verified numbers.
- [ ] Search examples work and are recorded in Notes: "odegaard", "salah", a partial name, a position filter, a club filter.
- [ ] Positions endpoint tested on a mixed list: played in the base GW, "from GWx", ghost, double gameweek, unknown ID.
- [ ] A test checks the base gameweek is the latest `positions_synced` one even when FPL has finished a later gameweek.
- [ ] No database writes and no Sofascore import in the web app (existing tests still pass).

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update `tasks/PROGRESS.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path.

## Notes
