# Setup

## What it is
FPL Real Shape Visualizer: enter an FPL team ID and see where the team's players actually played in a gameweek, from Sofascore's per-match average positions, with the graphic exportable as an image.

- **Web app** (what is deployed): a React page (`frontend/`) and a FastAPI API (`backend/app/`) that reads the bundled SQLite database `backend/data/fpl.db` **read-only** and calls the public FPL API live for team picks.
- **Offline scripts** (owner's machine only): sync from FPL + Sofascore, player mapping and Alembic migrations. They are the only code that writes `fpl.db`. The database file is committed and shipped with each deployment; there is no hosted database and no cron.

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (it installs the pinned Python 3.12 from `.python-version` if missing)
- Node.js 20+ and npm
- git
- For deploying only: a Vercel account and the Vercel CLI (`npm i -g vercel`)

## Layout
- `backend/`: FastAPI app (`app/`), Alembic migrations (`alembic/`), tests (`tests/`), database `data/fpl.db` (committed) and `data/player_overrides.csv`.
- `frontend/`: Vite + React + TypeScript.
- `api/index.py`, `vercel.json`, `requirements.txt`, `.python-version`, `.vercelignore`: Vercel deployment (see [Deploying](#deploying)).
- `.env.example`: every environment variable, with defaults.
- `docs/`: API, data model, position logic, sources, release routine, mapping coverage.

## Local setup
```sh
git clone <repo URL> fpl-real-shape
cd fpl-real-shape

cd backend
uv sync                                  # Python 3.12 + all dependencies into backend/.venv
uv run pytest                            # tests (no network)
uv run uvicorn app.main:app --reload     # API on http://127.0.0.1:8000 (check /api/health)
```
In a second terminal:
```sh
cd frontend
npm ci
npm run dev                              # http://localhost:5173, proxies /api to the backend
```
Open `http://localhost:5173/?team=<FPL team ID>` (optionally `&gw=<n>`), or open the page and type the ID. Your team ID is the number in the address of your team's Points page on the FPL site (`.../entry/<ID>/event/<n>`).

The committed database is ready to use: no migration or sync is needed to run the site.

Other commands:
```sh
# backend/
uv run alembic upgrade head              # apply migrations to data/fpl.db (read-write)
uv run alembic revision --autogenerate -m "<message>"   # new migration
# frontend/
npm run build                            # type-check + production build into frontend/dist
npm run lint
```
Dev only: `?fixture=edges` shows a sample graphic with the edge cases (ghosts, double gameweek, "from GW", auto-sub, Triple Captain, negative and double-digit scores, a starter who did not play) and `?fixture=bboost` a Bench Boost week (15 dots). Production builds ignore them.

## Environment variables
All are optional; the defaults work locally and on Vercel. Every variable is listed and explained in `.env.example`.

- The backend reads the **process environment only**. To use a file: `cp .env.example .env`, edit, then `uv run --env-file ../.env uvicorn app.main:app --reload` from `backend/`.
- The Vite dev server reads `API_PROXY_TARGET` from the root `.env` itself.
- `DATABASE_PATH` is relative to `backend/`. Never put an absolute machine path in it, or anything secret in the repo: `.env` is git-ignored.
- On Vercel no variables need setting: `api/index.py` turns on `DATABASE_IMMUTABLE` (the bundled file is never written there).

## Data refresh and release
The site is only as fresh as the last deploy. The full routine is in [`docs/release.md`](release.md); in short, from `backend/`:

1. `uv run python -m app.sync run`: refresh FPL data, download new positions from Sofascore, rebuild the player mapping (live requests, 2-3 minutes; `backfill` instead of `run` once per season).
2. Check the summary (what each warning means is in `release.md`).
3. Run the site locally and load a team for the new gameweek.
4. Commit `backend/data/fpl.db` (plus `player_overrides.csv` and `docs/mapping-coverage.md` if changed).
5. Deploy (below). The card's "Positions as of" date shows the new sync time.

Positions source check only: `uv run python -m app.positions round 6` (see `docs/positions-source.md`).

## Player mapping and overrides
FPL players are linked to Sofascore players automatically by name within the same club, on every sync. To re-run the mapping alone (offline, no network): `uv run python -m app.mapping run`. It rewrites `docs/mapping-coverage.md`, which lists unmatched active players, clashes and low-confidence matches.

To fix a player, add a row to `backend/data/player_overrides.csv` (`fpl_id,sofascore_id,comment`; an empty `sofascore_id` forces "no match"), then re-run the mapping. Overrides always win; deleting a row restores auto-matching. The format and the current overrides are at the top of `docs/mapping-coverage.md`.

## Deploying
Vercel (Hobby plan) serves `frontend/dist` as static files and the FastAPI app as a single Python function:

- `vercel.json` builds the frontend (`npm ci` + `npm run build` in `frontend/`), rewrites `/api/*` to `api/index.py` and bundles `backend/app` and `backend/data/fpl.db` into the function (offline-only modules and tests are excluded).
- `api/index.py` puts `backend/` on the import path, sets `DATABASE_IMMUTABLE=true` and exposes the app.
- `requirements.txt` holds the function's pinned packages (runtime only: no `curl_cffi`, `rapidfuzz` or pytest). After changing backend dependencies, regenerate it from `backend/`:
  ```sh
  uv export --no-default-groups --no-hashes --no-emit-project -o ../requirements.txt
  ```
  A test fails if it drifts from `uv.lock`.

First time, from the repo root:
```sh
vercel login
vercel link              # create or pick the project; accept the settings from vercel.json
vercel deploy            # preview URL
vercel deploy --prod     # production
```
After that, `vercel deploy --prod` after each release commit (or `git push` if the project is connected to the git repository).

Check a deployment: `<url>/api/health` should say `"status": "ok"` with `"read_only": true`, and `<url>/?team=<ID>` should draw the team.

## Known limitations
- **Unofficial sources.** Positions come from Sofascore's undocumented website API, and team data from FPL's public but undocumented API. Either can change shape, rate-limit or block without notice; a Sofascore block (403) stops a sync until it is lifted.
- **Data only as fresh as the last deploy.** Positions are synced by hand on the owner's machine. Team picks and points are live from FPL, but a gameweek is drawn from that week's own matches ("Full time") only after its positions are synced and deployed; until then it is a preview from earlier matches.
- **Average positions, not formations.** A dot is the player's mean on-ball position for the match, so it says nothing about how the shape changed during it. Depth is shown as a league-wide rank, not raw distance.
- **Free hosting.** Vercel Hobby: functions start cold after idle time, and FPL calls are cached in memory per function instance only.
- **Image export** tested in Chrome, Edge and Firefox (desktop and emulated phone), not Safari.
