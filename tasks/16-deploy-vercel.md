# 16 — Deploy-readiness + Vercel deployment 🛑 👤

**Status:** todo
**Gate:** 👤 Needs the owner's Vercel account linked (`vercel login` / `vercel link`). 🛑 Deploying is outward-facing: prepare everything, then set `awaiting-approval` and STOP **before the production deploy**. Deploy only after the owner approves.
**Depends on:** all previous tasks.

## Goal
A fresh clone runs locally from `docs/setup.md` alone, and the MVP is live on Vercel's free (Hobby) plan, serving the bundled read-only database.

## Scope
- Configuration cleanup: all settings in env, `.env.example` complete and commented, no machine-specific paths, no secrets in the repo.
- Vercel setup: React static build + FastAPI as Python functions under `/api`. Make sure `backend/data/fpl.db` is included in the function bundle (check Vercel's file-inclusion settings) and opened read-only. No hosted database, no cron.
- `docs/setup.md`: what it is, prerequisites, local setup, env vars, run commands, the release routine (`docs/release.md`: sync, check, commit DB, deploy), regenerating mapping + editing overrides, known limitations (unofficial sources; data only as fresh as the last deploy).

## Done when
- [ ] Fresh clone in a temp directory runs locally following only `docs/setup.md`; gaps fixed (noted).
- [ ] No secrets or absolute local paths in the repo (grep check in Notes).
- [ ] Preview deployment works end to end (owner's team renders); then `awaiting-approval`, stopped.
- [ ] After owner approval: production deployed and the owner's team renders on the live URL.
- [ ] One full release cycle tested: run sync locally, commit, redeploy, live site shows the new "data as of" time.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
