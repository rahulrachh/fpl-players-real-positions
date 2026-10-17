# Position logic

**Tasks:** 10 (frame, most recent match played, ghosts) · 11 (gameweek states, auto-subs, double gameweek)
**Code:** `backend/app/logic/positions.py` and `backend/app/logic/gameweek.py` (pure), `backend/app/logic/repository.py` (queries) · **Tests:** `backend/tests/test_logic_positions.py`, `backend/tests/test_logic_gameweek.py`

## Split
- `positions.py` holds pure functions on plain dataclasses (`MatchPosition`, `Placement`). It never sees a DB session or HTTP.
- `repository.py` holds the thin queries that build those dataclasses: `load_sofascore_ids(session, fpl_ids)`, `load_match_positions(session, sofascore_ids)` and `load_positions_synced(session, gw)`. The second filters on the player only, so SQLite uses the `(sofascore_player_id, kickoff)` index (a test checks the query plan). Gameweek filtering happens in the logic.

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

## A team's gameweek → dots
`gameweek.py`: `build_dots(team, state, sofascore_ids, rows_by_sofascore_id)` turns a `TeamGameweek` (task 05) into a list of `Dot`s in slot order. Each dot has `fpl_id`, `slot` (1-11), `role`, `is_captain`, `x` / `y` (None for a ghost), `ghost_reason`, `from_gw`, `link_group`, `replaces` and `match_ids`.

### State
`gameweek_state(finished, positions_synced)` / `team_state(team, positions_synced)`: **locked** = finished in FPL **and** `gameweeks.positions_synced`; anything else (upcoming, in progress, finished but not yet synced or deployed) is **preview**.

| | Preview | Locked |
|---|---|---|
| Who is drawn | XI as picked: FPL's auto-subs undone, a subbed-out starter back in the slot of the bench player who replaced them | XI after FPL's auto-subs; a sub-in takes the starter's slot and `replaces` names the starter |
| Matches used | The single most recent usable match in the DB (task 10 fallback; a match already played in the target GW counts) | Every usable match of the target GW only |
| `from_gw` label | Source GW, unless it is the target GW or the one before | Never |
| No match | Ghost (`no_match` / `no_mapping`) | Ghost, even if he played earlier: a starter with no match and no auto-sub replacement |
| Armband | Picked captain | The player FPL multiplied (`effective_captain_id`): the vice when the captain did not play, since that captain is benched |

Bench players are not drawn, except under Bench Boost: all 15 score, so the four bench players are drawn too (slots 12-15). The plot lists the bench separately either way (`bench_picks`).

### Double gameweek
All usable rows with the target `gw` count, including a rescheduled match FPL moved into the gameweek (task 07 takes `gw` from FPL fixtures). `combine_matches(matches, margin)`:
- **Opposite flanks** (at least one match with `x < 50 - margin` and one with `x > 50 + margin`): two dots, left flank first, each the average of the matches on its side of the center line. Both carry the player's FPL ID as `link_group` (and the captain flag, if any).
- **Otherwise** (same side, or one within the margin): one dot, the plain average.

Only locked gameweeks combine; preview uses the most recent match. No double gameweek in data GW1-6 yet, so `DGW_FLANK_MARGIN` is untuned.

### Real data check (task 11)
Owner's team 2020649 GW1-6: all locked, 11 dots each, no ghosts, captain marked. Team 7241584 GW5: Ajayi drawn in João Pedro's slot. Team 4155286 GW5: captain did not play, armband on the vice.

## Settings
| Variable | Default | Meaning |
|---|---|---|
| `POSITION_MIN_POINTS_COUNT` | 1 | Minimum on-ball actions behind an average for the match to be usable |
| `DGW_FLANK_MARGIN` | 10 | Double gameweek: distance from the center line (0-100 width) each match must exceed for two linked dots |
