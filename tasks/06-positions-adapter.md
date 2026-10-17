# 06 — Positions adapter module

**Status:** done (2026-10-17)
**Depends on:** 01 approved, 03.

## Goal
The **only** module that talks to Sofascore. It fetches and normalizes; it does **not** write to the database (the offline sync script in task 07 does). Swapping sources changes only this module.

## Scope
- `backend/app/positions/base.py` interface:
  - `list_round_matches(round) -> [SourceMatch]` (source match ID, home/away source team IDs, kickoff, finished?)
  - `match_positions(match_id) -> [SourcePlayerPosition]` (source player ID, name, team, minutes, is_sub, avg x/y **normalized to the attacking-upward frame**)
  - `list_team_players(source_team_id) -> [SourcePlayer]` (squad lists for ID mapping)
- `backend/app/positions/sofascore.py` implementing it per `docs/spikes/positions-source.md`.
- Orientation normalization happens **inside the adapter**; the output convention is documented in the module docstring (e.g. x 0-100 left to right, y 0-100 own goal to opponent goal).
- Polite fetching: configurable min delay, retries with backoff, a distinct `SourceBlockedError` when blocked.

## Done when
- [x] A script prints matches + normalized positions for one past round (excerpt in Notes).
- [x] Sanity check: a known left-sided player is on the left and a known striker near the top, for both a home and an away match.
- [x] Nothing outside `app/positions/` imports Sofascore-specific code.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes

### What was built
- `backend/app/positions/base.py`: `PositionsSource` interface, `SourceMatch` / `SourcePlayer` / `SourcePlayerPosition`, errors (`SourceBlockedError`, `SourceUnavailableError`, `SourceNotFoundError`, `SourceSchemaError`), and the frame in the docstring: **x 0 = left touchline → 100 = right, y 0 = own goal → 100 = opponent goal**, team attacking upward.
- `backend/app/positions/sofascore.py`: `SofascoreSource`. Converts Sofascore's axes (x = 100 - averageY, y = averageX). As a guard, mirrors a side whose starting keeper sits in the opponent's half. Derives subs / minutes from `substitutions`. Keeps a minimum gap between requests, retries 429 / 5xx / network errors with exponential backoff (honours `Retry-After`), and raises `SourceBlockedError` on 403 with no retry.
- `get_positions_source()` in `app/positions/__init__.py` is the only entry point. `python -m app.positions round|team|squad` is the check script.
- Docs: `docs/positions-source.md` (new); frame in `docs/data-model.md` and `models.py` updated (no position rows stored yet, so no data migration).

### Decisions and deviations
- **Both listing styles:** `list_round_matches(round)` as specified, plus `list_team_matches(team_id, last_n)` for the per-team approach agreed in the spike and used by task 07. Whole-season listing pages back through `events/last/{page}` until it reaches before round 1's kickoff.
- **`match_positions` returns `is_home`, not a team ID**: the average-positions response has no team IDs, and fetching `/event/{id}` would double the requests. The caller has the `SourceMatch`.
- **Stored frame changed** from Sofascore's raw axes to the adapter frame, so the database and logic are source-agnostic (task 10 builds on it).
- **Config fixes:** `SOFASCORE_API_BASE_URL` default changed to `https://www.sofascore.com/api/v1` (`api.sofascore.com` returns 403 even through `curl_cffi`). The delay default went from 1.5 to 2.5 s, as the spike recommends. New settings: `SOFASCORE_MAX_RETRIES`, `SOFASCORE_BACKOFF_SECONDS`.
- `curl_cffi` is in a new `sync` dependency group (default-installed locally) and imported lazily, so the web app does not need it.
- **Bug fix found on the way:** `alembic/env.py` called `fileConfig()` with its default `disable_existing_loggers=True`, so running migrations in-process (the model tests, later the sync) silenced every `app.*` logger. It now passes `False`.
- Squad endpoint `/team/{id}/players` (open question from the spike) works: 25 players for Man City, each with `team.id`.

### Script excerpt (`uv run python -m app.positions round 6`, live, 2026-10-17)
Round 6: 10 matches, all finished, 315 player positions, all 20 goalkeepers at y ≤ 16.1, no mirror warnings.
```
 16363878  R6  2026-10-11 15:30  Liverpool FC (44) 0-3 Manchester City (17)  [finished]
    Liverpool FC (home), 16 players, top of the pitch first
      M  Florian Wirtz              x= 40.8 y= 63.3  centre  66 min  pts=56   off 66'
      F  Lewis Koumas               x= 55.4 y= 60.1  centre  75 min  pts=27   off 75'
      F  Bradley Barcola            x= 24.7 y= 56.9  left    88 min  pts=53   off 88'
      D  Ronald Araújo              x= 86.7 y= 45.6  right   75 min  pts=48   off 75'
      D  Miloš Kerkez               x= 16.9 y= 37.0  left    90 min  pts=63
      G  Alisson                    x= 48.1 y=  9.4  centre  90 min  pts=37
    Manchester City (away), 15 players, top of the pitch first
      M  Jérémy Doku                x= 17.3 y= 71.0  left    34 min  pts=43  on 56'
      M  Antoine Semenyo            x= 28.7 y= 64.4  left    90 min  pts=50
      F  Erling Haaland             x= 45.7 y= 53.6  centre  80 min  pts=30   off 80'
      D  Matheus Nunes              x= 87.9 y= 46.1  right   90 min  pts=50
      D  Nico O'Reilly              x= 16.7 y= 40.3  left    66 min  pts=52   off 66'
      G  Gianluigi Donnarumma       x= 50.6 y=  9.7  centre  90 min  pts=63
```
(rows trimmed; the script prints every player)

### Sanity check
- **Away match** (Liverpool 0-3 Man City, City away): left-backs O'Reilly (MCI, away) x 16.7 and Kerkez (LIV, home) x 16.9 are on the left; right-back Nunes x 87.9 on the right. Haaland is central at y 53.6: he dropped deep that day, but is still ahead of every City starting defender (best 46.1).
- **Home match** (Man City 5-3 Sunderland, `round 5 --match 16363867`): Gvardiol (left) x 18.7, Nunes (right) x 80.1; Haaland x 52.2 y 64.2 is City's most advanced central starter; Sunderland's striker Brobbey is at y 67.5, top of his side.
- Both checks are also tests (`tests/test_positions_sofascore.py`, recorded fixtures, no network).
- `grep` confirms only `app/positions/` (and its own test) imports `sofascore.py` / `curl_cffi`.

### Tests
22 new tests (frame and sanity checks for home and away, subs and minutes, mirroring guard, squad, round and team listing with paging, request spacing, retry and backoff, 403 / 429 / 5xx / 404 / schema errors). Full suite: 107 passed.
