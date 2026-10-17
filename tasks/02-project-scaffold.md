# 02 — Project scaffold

**Status:** done (2026-10-16)
**Depends on:** 01 approved.

## Goal
A runnable empty skeleton with a clean backend/frontend split, ready for Vercel deployment later.

## Scope
- `git init` with a `.gitignore` (Python, Node, `.env*`, cache dirs). **Do not ignore** `backend/data/fpl.db`: the database file is committed and shipped with each deployment.
- **Backend** `backend/`: Python 3.11+, FastAPI, `uv` (or `pip`; Vercel needs a `requirements.txt` or `pyproject.toml` it can read). Layout:
  - `app/main.py` (FastAPI, `GET /api/health`), `app/config.py` (pydantic-settings, env only), `app/db/`, `app/fpl/`, `app/positions/`, `app/sync/`, `app/mapping/`, `app/logic/`.
  - SQLAlchemy 2.x with SQLite at a path from `DATABASE_PATH` (default `backend/data/fpl.db`, resolved relative to the backend package, never an absolute machine path).
  - Two connection modes: **read-write** for offline scripts (sync, mapping) and **read-only** for the web app (`mode=ro` / immutable URI). The web app must never write to the database.
  - Alembic set up for migrations.
  - Small in-memory short-TTL cache helper for live FPL calls.
- **Frontend** `frontend/`: Vite + React + TypeScript. One page that calls `/api/health` via the dev proxy.
- `.env.example` listing every env var (`DATABASE_PATH`, request delay, ...). No machine-specific paths.
- `docs/setup.md` stub with run commands (the root `README.md` is the project status file; keep setup docs out of it).

## Done when
- [x] Backend starts; `GET /api/health` returns OK and reports the DB opened read-only.
- [x] Frontend dev server shows the health response through the proxy.
- [x] `alembic upgrade head` creates `backend/data/fpl.db` (empty migration is fine).
- [x] A write attempt through the web app's read-only connection fails (quick check recorded in Notes).
- [x] `.env.example` complete; config read from env only.
- [x] Initial git commit made.

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes

**Done 2026-10-16.**

- **Backend** (`backend/`, uv, `pyproject.toml` + `uv.lock`, Python >=3.11; tested on 3.12): FastAPI, SQLAlchemy 2.x, Alembic, pydantic-settings. `app/config.py` reads env vars only (no `.env` auto-load; use `uv run --env-file ../.env`). `DATABASE_PATH` defaults to `data/fpl.db`, relative paths resolve against `backend/`.
- **Two engines** (`app/db/engine.py`): read-write for offline scripts/Alembic (creates the dir); read-only for the web app = SQLite URI `mode=ro` (+ `immutable=1` when `DATABASE_IMMUTABLE=true`, meant for Vercel) **and** `PRAGMA query_only = ON` on every connection. The read-only engine also refuses to create a missing file.
- **Alembic**: `alembic/env.py` uses the read-write engine and `Base.metadata` (`app/db/base.py`), `render_as_batch=True` for SQLite. Baseline (empty) revision `fb1fcb25607c`. `alembic upgrade head` created `backend/data/fpl.db` (12 KB, only `alembic_version`). The file is committed.
- **Cache**: `app/cache.py` `TTLCache` (thread-safe, `get` / `set` / `get_or_set`, max-entries eviction, injectable clock for tests). Default TTL from `FPL_CACHE_TTL_SECONDS`.
- **Frontend** (`frontend/`): `create-vite` react-ts template (React 19, Vite 8, TS 6, oxlint), demo assets removed. One page fetching `/api/health`; dev proxy `/api` → `API_PROXY_TARGET` (default `http://127.0.0.1:8000`). `npm run build` and `npm run lint` clean.
- **Tests**: `uv run pytest` → 13 passed (read-only engine: reads OK, INSERT/UPDATE/CREATE rejected, rejected even with `query_only` turned off, missing file not created, data unchanged; health endpoint; TTL cache).

**Checks recorded:**
- `GET http://127.0.0.1:8000/api/health` → `{"status":"ok","database":{"file":"fpl.db","query_only":true,"read_only":true,"ok":true}}`. Same body through the Vite proxy at `http://localhost:5173/api/health`.
- Write through the web app's own engine (`get_read_only_engine()`) on the real `fpl.db`: `CREATE TABLE probe ...` → `OperationalError: attempt to write a readonly database`. After `PRAGMA query_only = OFF` on that connection, it still fails with the same error (the `mode=ro` file handle is the hard guarantee; `query_only` is the second layer).
- Env-only config: `DATABASE_PATH=elsewhere/x.db FPL_CACHE_TTL_SECONDS=5` is picked up; `uv run --env-file ../.env` works.

**For later tasks:**
- `tasks/README.md` did not exist; created in this task with the status table.
- Vercel (task 16): set `DATABASE_IMMUTABLE=true`; Vercel can read `backend/pyproject.toml`. If it needs `requirements.txt`, run `uv export --no-dev --no-hashes > requirements.txt`.
- Dev-only warning: Starlette deprecates `httpx` in `TestClient` in favour of `httpx2`. Harmless for now.

