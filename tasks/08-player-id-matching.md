# 08 — Player ID auto-matching + coverage report

**Status:** done (2026-10-17)
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
- [x] Mapping runs from one command and from the sync.
- [x] `docs/mapping-coverage.md` exists with both percentages and the lists.
- [x] Spot-check of 10 tricky names (accents, nicknames, one-name players such as Odegaard, Son) recorded in Notes.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- **Code:** `backend/app/mapping/names.py` (normalization), `players.py` (`run_player_mapping()`), `report.py` (coverage report), `__main__.py` (`python -m app.mapping run`, offline, no network). The sync calls `run_player_mapping()` as its last step, also after a 403 block since it only reads the local DB; the sync CLI then rewrites the report.
- **Active players need FPL minutes**, which were not stored. Added `fpl_players.minutes` (FPL `elements[].minutes`, refreshed every sync) with migration `259b15793154`.
- **Normalization:** explicit table for letters NFKD keeps (ø, ß → ss, ı, ł, đ, æ, œ), then accents stripped, lowercase, apostrophes dropped (`Jun'ai` → `junai`), every other non-letter (hyphen, dot) splits words. Name order is handled by comparing sorted words.
- **Strategies** as specified, each pass only on Sofascore players no earlier pass took, same club only. Two small additions: `short_name` also tries first name + web name ("Andrey Santos"), and every strategy needs exactly one candidate (two same-club "J. Fletcher" style candidates = no match, reported as ambiguous). Fuzzy is `rapidfuzz.token_set_ratio` ≥ 85 with a 5-point lead over the runner-up; its confidence is scaled to ≤ 0.85 so every fuzzy match lands in the low-confidence list (< 0.9). Confidence: exact 1.0, short_name 0.95, surname_initial 0.9.
- **Rebuild:** non-override rows are recomputed each run; unchanged rows keep `matched_at`, so a re-run reports `added 0, changed 0, removed 0`. Override rows are skipped and their Sofascore IDs are taken out of the pool.
- **First real run (2026-10-17, sync run 3):** 540 of 667 FPL players mapped (81.0%); **435 of 436 active players (99.8%)**. By method: exact 470, short_name 51, surname_initial 11, fuzzy 8. 0 clashes. All 8 fuzzy and 11 surname_initial matches checked by hand: all correct. `python -m app.mapping run` straight after: no changes.
- **Only active miss:** José María Andrés (BHA, FPL 639) is "Chema Andrés" on Sofascore (Sofascore 1464641; a nickname, shares only the surname). Left for the task 09 override file instead of adding a surname-only rule, which would mis-link players absent from Sofascore. The report's "Sofascore players with positions but no FPL player" section lists him, which is where task 09 should look.
- **126 unmatched inactive players** (0 minutes) are mostly not in Sofascore's squad lists at all (e.g. Bayındır, Byfield, Martinelli); they match automatically once they show up.
- **Spot-check (10 tricky names):**

  | FPL (web name) | Sofascore | Method | OK |
  |---|---|---|---|
  | Martin Ødegaard (Ødegaard) | Martin Ødegaard | exact (ø → o) | yes |
  | Pascal Groß (Groß) | Pascal Groß | exact (ß) | yes |
  | Benjamin Sesko (Šeško) | Benjamin Šeško | exact (accents on one side only) | yes |
  | Gabriel dos Santos Magalhães (Gabriel) | Gabriel Magalhães | surname_initial | yes |
  | Rúben dos Santos Gato Alves Dias (Rúben) | Rúben Dias | surname_initial | yes |
  | Sávio Moreira de Oliveira (Sávio) | Sávio | short_name (one-name player) | yes |
  | Richarlison de Andrade (Richarlison) | Richarlison | short_name (one-name player) | yes |
  | Bruno Borges Fernandes (B.Fernandes) | Bruno Fernandes | short_name | yes |
  | Alisson Becker (A.Becker) | Alisson | fuzzy 0.85 (one-name on Sofascore) | yes |
  | Junior Kroupi (Kroupi.Jr) | Eli Junior Kroupi | fuzzy 0.85 | yes |
  | Dango Ouattara (O.Dango), Alex Tóth (Tóth.A) | Dango Ouattara, Alex Tóth | exact (reversed web names) | yes |

  Son Heung-min is no longer in FPL's 2026/27 list; his name-order case ("Son Heung-min" = "Heung-Min Son") is a unit test instead.
- **Tests:** `tests/test_mapping.py` (20: normalization, each strategy, club restriction, ambiguity, clash, earlier strategy wins, idempotent re-run, rebuilt rows, overrides untouched, coverage counts); `test_sync.py` asserts the mapping ran, also after a block. 137 pass.
