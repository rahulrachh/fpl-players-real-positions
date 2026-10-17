# 04 — FPL API client + public/private boundaries

**Status:** done (2026-10-17)
**Depends on:** 03.

## Goal
Fetch all public FPL data the app needs, persist the stable parts, and document what is public vs. private.

## Scope
- `backend/app/fpl/client.py` wrapping public endpoints:
  - `bootstrap-static/` (players, clubs, roles, prices, availability, gameweeks/deadlines/status)
  - `fixtures/`
  - `entry/{id}/`, `entry/{id}/history/` (bank, value per GW)
  - `entry/{id}/event/{gw}/picks/` (picks, captain, `automatic_subs`, `entry_history`)
  - `event/{gw}/live/` (minutes, if needed)
- `refresh_fpl_reference_data()` upserts `fpl_clubs`, `fpl_players`, `gameweeks` (called by the offline sync script in task 07).
- Short-TTL cache for volatile calls (current GW status, live data).
- **Verify by experiment** and document: are upcoming-GW picks visible before the deadline? Which money fields are public? What happens with an invalid team ID?

## Done when
- [x] Client functions exist for every endpoint above.
- [x] `refresh_fpl_reference_data()` populates the three tables (row counts in Notes).
- [x] `docs/fpl-api.md` documents endpoints, fields used, and the verified public/private boundary.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes

**Done 2026-10-17.**

- **Client** `backend/app/fpl/client.py`: `FplClient` (httpx, 20 s timeout) with `bootstrap_static()`, `fixtures(event=None)`, `entry(id)`, `entry_history(id)`, `entry_picks(id, gw)`, `event_live(gw)`, `event_status()`. Process-wide `get_fpl_client()`. Errors: `FplNotFound` (404), `FplUnavailable` (network / timeout / other HTTP errors), `FplSchemaError` (not JSON / changed shape), all `FplError`.
- **Schemas** `backend/app/fpl/schemas.py`: frozen pydantic models keeping only the fields we use. `BootstrapStatic.current_event` / `next_event` helpers.
- **Cache**: every call goes through the existing `TTLCache` for `FPL_CACHE_TTL_SECONDS` (60 s); errors are not cached.
- **Reference refresh** `backend/app/fpl/reference.py`: `refresh_fpl_reference_data(session, client)` upserts `fpl_clubs`, `fpl_players`, `gameweeks` by FPL ID, keeps `sofascore_team_id` and `positions_synced`, keeps players that disappear, fails loudly on an unknown `element_type`. Flushes, caller commits.
- **Row counts** after running it on the committed `backend/data/fpl.db` (2026-10-17): **20 clubs, 667 players (73 GK / 217 DEF / 298 MID / 79 FWD), 38 gameweeks**. Second run identical; `integrity_check` ok, no FK violations.
- **Verified boundaries** (GW7 deadline not yet passed): upcoming picks → 404; pending transfers not listed; `bank`/`value` public per passed deadline; `value` = market-price squad + bank (not selling value); unknown team → 404 JSON, non-numeric ID → 404 HTML (validate input first); `current_event` is the game's GW, so use `entered_events` for which GWs have picks. Purchase prices are public via `entry/{id}/transfers/` (useful for v1 Planner budget).
- **Dependencies**: `httpx` moved from dev to runtime.
- **Tests**: `tests/test_fpl_client.py`, `tests/test_fpl_reference.py` against trimmed real responses in `tests/fixtures/fpl/` (manager names replaced). 55 tests pass.
- **Docs**: `docs/fpl-api.md`.

