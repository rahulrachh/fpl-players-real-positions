# Setup

> Stub from task 02. Completed in task 16 (release routine, mapping, known limitations).

## Prerequisites
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm

## Layout
- `backend/`: FastAPI app (`app/`), Alembic migrations (`alembic/`), SQLite database `data/fpl.db` (committed, shipped with each deployment).
- `frontend/`: Vite + React + TypeScript.
- `.env.example`: every environment variable, with defaults. All are optional.

## Backend
```sh
cd backend
uv sync                                  # install dependencies into backend/.venv
uv run alembic upgrade head              # create / migrate data/fpl.db (read-write)
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000/api/health
uv run pytest                            # tests
```
To use a local `.env`: `uv run --env-file ../.env uvicorn app.main:app --reload`.

The web app opens the database **read-only** (`mode=ro` plus `PRAGMA query_only`). Only offline scripts (Alembic, sync, mapping) open it read-write.

New migration: `uv run alembic revision --autogenerate -m "<message>"`.

## Frontend
```sh
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to API_PROXY_TARGET (default http://127.0.0.1:8000)
npm run build      # type-check + production build into frontend/dist
npm run lint
```
Start the backend first; the page shows the `/api/health` response.
