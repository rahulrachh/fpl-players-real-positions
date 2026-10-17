# 01 — Sofascore positions spike 🛑

**Status:** done
**Gate:** 🛑 Human approval required. When finished, set status `awaiting-approval` and STOP.
**Depends on:** nothing (no app scaffold needed; throwaway scripts live in `spikes/`).

## Goal
Prove that Sofascore (unofficial, free) returns **per-match average positions** for EPL players, and document everything later tasks need.

## Scope
- Throwaway Python scripts in `spikes/sofascore/`. Fetch politely (at least 1-2 s between requests, realistic User-Agent).
- Find and document the endpoints for:
  - EPL tournament/season IDs and the list of rounds (round ~ FPL gameweek; note where they differ, e.g. postponed or rearranged matches).
  - Matches per round (event IDs, home/away team, status, kickoff).
  - Per-match **average positions** per player (are subs included? minutes played?).
  - Player identity fields (Sofascore player ID, name, short name, slug, team) and a way to list **club squads** (needed to match players who have not played yet).
- Document the **coordinate system**: axis ranges, origin, attacking direction, and whether home/away is already normalized. Prove it with one real match (a known left-back appears on the left).
- **Coverage:** for at least 2 recent EPL rounds, % of matches with average-position data and % of players who appeared with a position.
- **Request budget:** how many requests a full gameweek sync takes, and how many a full-season backfill takes.
- Sync runs offline from the owner's machine, so a cloud-IP test is **not required**. Just note any blocking seen from the owner's connection.
- Access constraints: rate limits, headers needed, endpoint stability. One sentence on a fallback source (e.g. FotMob).
- Save 1-2 raw JSON samples in `spikes/sofascore/samples/`.

## Out of scope
App code, adapter module, database, ID matching.

## Done when
- [x] `docs/spikes/positions-source.md` covers: endpoints, fields, coordinate system with proof, coverage, request budget, risks, recommendation.
- [x] Sample JSON saved in `spikes/sofascore/samples/`.
- [x] Status `awaiting-approval`, stopped.
- [x] **Owner approves the source** (owner flips status to `done`).

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`. (Status updated; `tasks/README.md` does not exist yet.)
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes

- **Scope change (owner, 2026-10-16):** no rounds endpoint. Fetch per team via `/team/{id}/events/last/0`, keep the last N finished Premier League matches (spike N = 6, later N = 3), fetch `/event/{id}/average-positions` for any event not yet downloaded. Checked on Man City rounds 1-6 instead of 2 full rounds.
- Plain `requests` gets 403; use `curl_cffi` with `impersonate="chrome"`.
- Squad-list endpoint not tested; left for task 08.
