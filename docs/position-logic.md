# Position logic

**Tasks:** 10 (frame, most recent match played, ghosts) · 11 (gameweek states, auto-subs, double gameweek, todo)
**Code:** `backend/app/logic/positions.py` (pure), `backend/app/logic/repository.py` (queries) · **Tests:** `backend/tests/test_logic_positions.py`

## Split
- `positions.py` holds pure functions on plain dataclasses (`MatchPosition`, `Placement`). It never sees a DB session or HTTP.
- `repository.py` holds the thin queries that build those dataclasses: `load_sofascore_ids(session, fpl_ids)` and `load_match_positions(session, sofascore_ids)`. The second filters on the player only, so SQLite uses the `(sofascore_player_id, kickoff)` index (a test checks the query plan). Gameweek filtering happens in the logic.

## Frame
`positions.py` is the one place the frame is defined in code: `X_MIN/X_MAX/Y_MIN/Y_MAX` = 0-100, `CENTER_X` = 50, and `validate_point()` (raises `FrameError`). Team attacking upward, x 0 = left touchline, y 0 = own goal line (same as `docs/data-model.md`). Every `MatchPosition` is validated on creation.

## Placing a player for a target gameweek
`place_player(fpl_id, sofascore_id, rows, target_gw)` / `place_players(...)` return a `Placement`:

| Case | `source_gw` | `matches` | `from_gw` | `ghost_reason` |
|---|---|---|---|---|
| Played in the target GW | target | every usable match of the GW, kickoff order (2 in a double GW, combined by task 11) | None | None |
| Didn't, but played earlier | GW of the most recent usable match (by **kickoff**, so a rescheduled match counts when it was played) | that one match | = `source_gw` ("from GW4") | None |
| No usable match up to the target GW | None | () | None | `no_match` |
| No Sofascore mapping | None | () | None | `no_mapping` |

- Matches in later gameweeks, and matches not linked to a gameweek (`gw` null), are never used.
- **Usable** = `points_count >= POSITION_MIN_POINTS_COUNT` (default 1, so every stored row). Raise it to send noisy dots (e.g. a 90th-minute sub with one touch) back to an earlier match.
- A ghost has no x / y; the renderer draws it greyed on the sideline.

On the committed DB (data GW1-6), all 436 active players get a placement for GW6 and GW7. None is a ghost.

## Settings
| Variable | Default | Meaning |
|---|---|---|
| `POSITION_MIN_POINTS_COUNT` | 1 | Minimum on-ball actions behind an average for the match to be usable |
