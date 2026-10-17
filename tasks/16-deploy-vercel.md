# 16 — Deploy-readiness + Vercel deployment 🛑 👤

**Status:** awaiting-approval
**Gate:** 👤 Needs the owner's Vercel account linked (`vercel login` / `vercel link`). 🛑 Deploying is outward-facing: prepare everything, then set `awaiting-approval` and STOP **before the production deploy**. Deploy only after the owner approves.
**Depends on:** all previous tasks.

## Goal
A fresh clone runs locally from `docs/setup.md` alone, and the MVP is live on Vercel's free (Hobby) plan, serving the bundled read-only database.

## Scope
- Configuration cleanup: all settings in env, `.env.example` complete and commented, no machine-specific paths, no secrets in the repo.
- Vercel setup: React static build + FastAPI as Python functions under `/api`. Make sure `backend/data/fpl.db` is included in the function bundle (check Vercel's file-inclusion settings) and opened read-only. No hosted database, no cron.
- `docs/setup.md`: what it is, prerequisites, local setup, env vars, run commands, the release routine (`docs/release.md`: sync, check, commit DB, deploy), regenerating mapping + editing overrides, known limitations (unofficial sources; data only as fresh as the last deploy).

## Done when
- [x] Fresh clone in a temp directory runs locally following only `docs/setup.md`; gaps fixed (noted).
- [x] No secrets or absolute local paths in the repo (grep check in Notes).
- [x] Preview deployment works end to end (owner's team renders); then `awaiting-approval`, stopped. (The first deployment landed on production; see Notes.)
- [ ] After owner approval: production deployed and the owner's team renders on the live URL.
- [ ] One full release cycle tested: run sync locally, commit, redeploy, live site shows the new "data as of" time.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- **Vercel layout (2026-10-17):** classic static build + one Python function. `vercel.json`: `framework: null`, install / build in `frontend/`, output `frontend/dist`, rewrite `/api/(.*)` → `/api/index`, and `functions["api/index.py"].includeFiles = backend/{app/**,data/fpl.db}` (excluding `app/positions`, `app/sync`, tests, `.venv`). `api/index.py` adds `backend/` to `sys.path`, defaults `DATABASE_IMMUTABLE=true` (Vercel's filesystem is read-only and nothing writes the file) and imports `app.main:app`. No env vars need setting in the Vercel dashboard. `.vercelignore` keeps `.venv`, `node_modules`, docs, spikes, tasks and tests out of the upload.
- **Python deps:** root `requirements.txt` exported from `uv.lock` with runtime packages only (`uv export --no-default-groups --no-hashes --no-emit-project`). Root `.python-version` = 3.12 (Vercel's Python; also what the local `.venv` already used, uv picks it up from `backend/`).
- **Tests:** `backend/tests/test_deploy.py`: the entrypoint, loaded as Vercel does from the repo root, serves `/api/health` read-only with `immutable=1` and without loading the Sofascore adapter; `requirements.txt` matches `uv.lock`, covers every direct dependency and leaves out `curl-cffi` / `rapidfuzz` / pytest. 226 tests pass.
- **Fresh clone (2026-10-17):** `git clone` into the scratchpad, then only the `docs/setup.md` steps: `uv sync` (226 tests pass), `npm ci`, `npm run build`, `npm run lint` clean; backend + Vite dev server: `/api/health` ok and read-only, owner's team 2020649 `plot/latest` = GW6, locked, 11 dots, positions as of 2026-10-17 05:21 UTC. Gaps fixed in the docs: setup.md was a stub (no release routine, mapping, env, deploy or limitations); Vite listens on `localhost`, not `127.0.0.1` (docs use `localhost`); the card's label is "Positions as of", not "data as of".
- **Grep check (2026-10-17), on tracked files excluding lock files:** `git grep -nIiE "[A-Z]:[\/](Users|Program)|/home/|/Users/|rahulrachh"` → no hits. `git grep -nIiE "(api[_-]?key|secret|token|password|passwd|bearer|sk-[a-z0-9]{10})"` → only `.gitignore`'s "secrets" comment, Alembic's "token" comments, name-matching `tokens()` / `token_set_ratio` and task text. `.env` is git-ignored; nothing in the app needs a secret.
- **Vercel login (2026-10-17):** the owner ran `vercel login` (account `rahulrachh3-2871`). `vercel link --yes --project fpl-real-shape` created the project (`.vercel/` and `.env.local` with a Vercel OIDC token, both git-ignored). The CLI also appended `.vercel` and `.env*` to `.gitignore`; reverted, because `.env*` would match `.env.example` and the existing rules already cover both.
- **First deployment went to production:** `vercel deploy` (no `--prod`) was the project's first deployment, and Vercel assigns a project's first deployment to production, so https://fpl-real-shape.vercel.app went live before the owner's approval. Lesson: on a new project, make the first deployment with production protection or a throwaway project, or ask first. Later `vercel deploy` calls make preview deployments.
- **Live check (2026-10-17, deployment `fpl-real-shape-liu9wi1jz-watching-sunset.vercel.app`):** `/` 200; `/api/health` ok, `query_only` and `read_only` true; `/api/team/2020649/plot/latest` = GW6, locked, 11 dots, `data_as_of` 2026-10-17T05:21:57 (the bundled database). Headless Chrome on `/?team=2020649` draws the full card: `docs/screenshots/deploy-live.png`.
- **Waiting for the owner:** approve production as is (then the release-cycle test), or have it taken down until approval.
