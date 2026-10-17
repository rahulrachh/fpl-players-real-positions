# 08 — Player ID auto-matching + coverage report

**Status:** todo
**Depends on:** 07 (needs `fpl_players` and `sofascore_players` populated).

## Goal
Automatically link each FPL player to his Sofascore player and measure how well it worked. The two systems share no ID, so the link is built from names + clubs.

## Scope
- `backend/app/mapping/`:
  - Club mapping first: fill `fpl_clubs.sofascore_team_id` (20 clubs; a small static table is fine). **Done in task 07** (`app/mapping/clubs.py`).
  - Name normalization: strip accents (O-slash to o, e-acute to e...), lowercase, remove punctuation, handle hyphens and name order.
  - Candidates restricted to the same club; strategies in order: exact full name, then web/short name, then surname + first initial, then fuzzy score (e.g. `rapidfuzz`) above a threshold.
  - Write results into `player_id_map` (`fpl_id`, `sofascore_id`, `match_method`, `match_confidence`, `matched_at`). A re-run rebuilds non-override rows; never overwrite rows with `is_override = true`. A `UNIQUE(sofascore_id)` clash (two FPL players claiming one Sofascore player) is reported for manual fixing, not silently resolved. Unmatched players get no row.
- Single command: `python -m app.mapping run`. Also run automatically at the end of each offline sync (new signings).
- Coverage report: `docs/mapping-coverage.md` with % matched of all FPL players and of **active** players (minutes this season), plus unmatched and low-confidence lists.

## Done when
- [ ] Mapping runs from one command and from the sync.
- [ ] `docs/mapping-coverage.md` exists with both percentages and the lists.
- [ ] Spot-check of 10 tricky names (accents, nicknames, one-name players such as Odegaard, Son) recorded in Notes.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
