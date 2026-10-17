# 06 — Positions adapter module

**Status:** todo
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
- [ ] A script prints matches + normalized positions for one past round (excerpt in Notes).
- [ ] Sanity check: a known left-sided player is on the left and a known striker near the top, for both a home and an away match.
- [ ] Nothing outside `app/positions/` imports Sofascore-specific code.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
