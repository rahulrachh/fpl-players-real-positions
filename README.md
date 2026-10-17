# FPL Real Shape Visualizer

## Summary
FPL shows a team as a tidy formation, but managers pick attacking "defenders" and "midfielders". This app plots where a team's players actually played, using real per-match average positions from Sofascore. Enter an FPL team ID, see the team's real shape for the latest gameweek, step back through earlier gameweeks, and export the graphic as an image. Data is refreshed by an offline script and shipped with each deployment. Planner mode and the Claude roast are planned for v1.

## Tech stack
- Python 3.11+
- FastAPI
- SQLAlchemy + Alembic
- SQLite
- React
- Vite
- TypeScript
- Vercel

## Tasks completed
- **Task 01 — Sofascore positions spike** (done, approved 2026-10-16): confirmed Sofascore returns per-match average positions for every EPL player who played, already normalized for both teams. Per-team fetch approach, `curl_cffi` needed to avoid 403s. Findings in `docs/spikes/positions-source.md`, scripts and samples in `spikes/sofascore/`.
- **Task 02 — Project scaffold** (done 2026-10-16): git repo; `backend/` (uv, FastAPI with `GET /api/health`, env-only pydantic-settings config, SQLAlchemy with a read-write engine for offline scripts and a read-only engine for the web app (`mode=ro` + `query_only`, writes verified to fail), Alembic baseline creating the committed `backend/data/fpl.db`, in-memory TTL cache, 13 tests); `frontend/` (Vite + React + TS page showing the health response through the dev proxy); `.env.example`; `docs/setup.md`; `tasks/README.md` status table.
- **Task 03 — Database schema + migrations** (done 2026-10-16): SQLAlchemy models for all 8 MVP tables (`fpl_clubs`, `fpl_players`, `sofascore_players`, `player_id_map`, `gameweeks`, `matches`, `player_match_positions`, `sync_runs`) with named PK/FK/UNIQUE/CHECK constraints and the two lookup indexes; `minutes` derived on write; foreign keys enforced on both engines. Alembic migration `5cba41167c0a` applied to the committed `backend/data/fpl.db`. `docs/data-model.md` covers tables, the coordinate convention and read-only access. 33 tests pass.

## Next task
**Task 04 — FPL API client + public/private boundaries** → `tasks/04-fpl-api-client.md`
