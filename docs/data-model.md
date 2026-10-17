# Data model

**Task:** 03 · Models: `backend/app/db/models.py` · Migration: `backend/alembic/versions/5cba41167c0a_mvp_tables.py`

## How the database is used
- One SQLite file, `backend/data/fpl.db`, **committed to git and shipped with each deployment**.
- **Only offline scripts write it** (Alembic, the sync script, ID mapping), through the read-write engine. The owner runs them locally, then commits the file; new data goes live on deploy.
- **The website opens it read-only**: SQLite URI `mode=ro` (plus `immutable=1` when `DATABASE_IMMUTABLE=true`, as on Vercel) and `PRAGMA query_only = ON`. Any write raises. See `backend/app/db/engine.py`.
- Both engines turn on `PRAGMA foreign_keys` (SQLite leaves it off by default). Alembic turns it off while migrating, because batch mode rebuilds tables.
- **Not stored:** team picks (fetched live from FPL, task 05). Planner and roast tables are v1 (`tasks/v1-backlog/`).

## Conventions
- Primary keys are the source's own IDs (FPL or Sofascore), so a re-sync updates rows in place. Only `sync_runs` has its own auto-increment ID.
- Datetimes are **naive UTC**.
- Enum-like columns are strings with a `CHECK` constraint.
- Constraints and indexes are named (`pk_`, `fk_`, `uq_`, `ck_`, `ix_` naming convention in `app/db/base.py`) so later SQLite batch migrations can find them.

## Coordinate convention
`player_match_positions.avg_x` / `avg_y` are stored exactly as the positions adapter returns them (`backend/app/positions/base.py`, task 06). The adapter normalizes every source into one frame, so nothing downstream knows about the source's axes or home/away.

Pitch seen from behind the player's own goal, his team **attacking upward**:
- **x**: 0 = left touchline, 100 = right touchline (his left / right). A left-back sits at x ≈ 17.
- **y**: 0 = own goal line, 100 = opponent's goal line. A goalkeeper sits at y ≈ 10, a striker at y ≈ 55-70.
- Both are in 0-100 (`CHECK` enforced).
- To draw a pitch attacking upward: screen x = `x`, screen y = `y` measured from the bottom.

Sofascore's own axes are different (its `averageX` is depth, `averageY` high = left); the adapter converts with x = 100 - `averageY`, y = `averageX`. See `docs/positions-source.md`.

## Tables

### `fpl_clubs`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | FPL club (team) ID |
| `name`, `short_name` | str | e.g. "Man City", "MCI" |
| `sofascore_team_id` | int, unique, nullable | Sofascore team ID, used to fetch the club's matches. Set on every sync from the static table in `app/mapping/clubs.py` |

### `fpl_players`
Refreshed from FPL on every sync. Holds **no mapping data**, so a refresh never touches the mapping.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | FPL element ID |
| `first_name`, `second_name`, `web_name` | str | |
| `club_id` | FK `fpl_clubs`, indexed | |
| `role` | str | `GK` / `DEF` / `MID` / `FWD` (`CHECK`) |
| `price` | int | FPL `now_cost`, tenths of £m (55 = £5.5m) |
| `status` | str(1) | FPL availability code (`a`, `d`, `i`, `s`, `u`, `n`) |
| `news` | text | FPL news, empty string if none |

### `sofascore_players`
Source side of the ID mapping.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | Sofascore player ID |
| `name` | str | |
| `short_name`, `slug` | str, nullable | |
| `sofascore_team_id` | int, nullable, indexed | Club last seen for. Not an FK (the Sofascore team ID lives on `fpl_clubs`) |

### `player_id_map`
FPL player ↔ Sofascore player. One row per **matched** FPL player; unmatched players have no row.

| Column | Type | Notes |
|---|---|---|
| `fpl_id` | int **PK**, FK `fpl_players` | |
| `sofascore_id` | int **NOT NULL UNIQUE**, FK `sofascore_players` | UNIQUE stops two FPL players mapping to one Sofascore player |
| `match_method` | str | `exact` / `short_name` / `surname_initial` / `fuzzy` / `override` (`CHECK`) |
| `match_confidence` | float | 0-1 (`CHECK`) |
| `is_override` | bool | Row comes from the manual override file (task 09) |
| `matched_at` | datetime | |

Both keys are indexed through their PK / UNIQUE constraints.

### `gameweeks`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | FPL gameweek number (1-38) |
| `deadline` | datetime | |
| `finished` | bool | FPL `finished` |
| `data_checked` | bool | FPL `data_checked` (points final) |
| `positions_synced` | bool | Every match of the gameweek has its positions stored |

### `matches`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | Sofascore event ID. A postponed match comes back with a **new** event ID |
| `fpl_fixture_id` | int, unique, nullable | |
| `gw` | FK `gameweeks`, nullable, indexed | Taken from **FPL's fixture list**, not Sofascore's round. Null until linked |
| `home_club_id`, `away_club_id` | FK `fpl_clubs` | |
| `kickoff` | datetime | Sofascore `startTimestamp` |
| `finished` | bool | |
| `positions_fetched_at` | datetime, nullable | Null = average positions not downloaded yet |

### `player_match_positions`
One player's average position in one match. Only players who played are stored (Sofascore omits unused subs). `kickoff` and `gw` are **copied from `matches`** so the website reads only this table.

| Column | Type | Notes |
|---|---|---|
| `match_id` | FK `matches`, PK part | |
| `sofascore_player_id` | FK `sofascore_players`, PK part | The composite PK is the unique (match, player) constraint |
| `avg_x`, `avg_y` | float | See Coordinate convention |
| `points_count` | int ≥ 0 | Sofascore `pointsCount`: on-ball actions the average is built from. Low = unreliable dot (hide or fade) |
| `sub_on_minute` | int, nullable | Set = came on as a sub. A sub is `sub_on_minute IS NOT NULL` (no `is_sub` column) |
| `sub_off_minute` | int, nullable | Set = taken off |
| `minutes` | int ≥ 0 | **Derived on write** (ORM `before_insert` / `before_update`): `(sub_off_minute or 90) - (sub_on_minute or 0)`, floored at 0. Stoppage time and red cards ignored |
| `kickoff` | datetime | Copy of `matches.kickoff` |
| `gw` | int, nullable | Copy of `matches.gw` |

Indexes: `(sofascore_player_id, kickoff)` for "most recent match played", `(sofascore_player_id, gw)` for the gameweek view.

### `sync_runs`
One offline sync. The latest row with `finished_at` set gives the site its "data as of" timestamp.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK, auto-increment | |
| `started_at` | datetime | |
| `finished_at` | datetime, nullable, indexed | Null = still running or crashed |
| `trigger` | str | `run` / `backfill` (`CHECK`) |
| `matches_fetched` | int | Default 0 |
| `errors` | JSON list of strings | One message per failure; empty list = clean run |

## Relationships
```
fpl_clubs 1─* fpl_players 1─0..1 player_id_map 0..1─1 sofascore_players
fpl_clubs 1─* matches (home, away)      gameweeks 1─* matches
matches 1─* player_match_positions *─1 sofascore_players
```
Website lookup for an FPL player: `player_id_map.fpl_id` → `sofascore_id` → `player_match_positions` by `(sofascore_player_id, gw)` or latest `kickoff`.

## Changing the schema
Edit `app/db/models.py`, then from `backend/`:
```sh
uv run alembic revision --autogenerate -m "<message>"   # review the file it writes
uv run alembic upgrade head                             # migrates data/fpl.db; commit it
```
`tests/test_models.py` fails if the models and the migrations drift apart.
