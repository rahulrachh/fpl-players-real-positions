# Positions source spike: Sofascore

**Task:** 01 · **Date:** 2026-10-16 · **Status:** approved by owner (2026-10-16)
**Scripts:** `spikes/sofascore/` · **Samples:** `spikes/sofascore/samples/`

## Recommendation
Use Sofascore. It returns per-match average positions for every EPL player who played (starters and subs), on a coordinate system that is already normalized for both teams. Access needs a Chrome-impersonating HTTP client (`curl_cffi`), not plain `requests`.

## Scope change (agreed with owner)
The original task asked for a rounds-based approach and coverage across 2 full rounds. The owner chose a simpler **per-team** approach instead (below), and the spike was checked on **Manchester City's first 6 EPL matches of 2026/27** (rounds 1-6), which include 12 different clubs. No rounds endpoint is used or documented.

## Endpoints
Base URL: `https://www.sofascore.com/api/v1`

| Endpoint | Returns |
|---|---|
| `/team/{teamId}/events/last/0` | The club's last 30 matches, **all competitions**, oldest first |
| `/event/{eventId}/average-positions` | Average position of every player who played in the match, both teams, plus substitutions |

Example IDs: Manchester City team `17`; Liverpool 0-3 Man City event `16363878`. Premier League is `uniqueTournament.id = 17` (same number as City's team ID by coincidence); season 2026/27 is `season.id = 96668`.

### `/team/{teamId}/events/last/0` fields used
- `id`: event ID
- `tournament.uniqueTournament.name` / `.id`: filter to `"Premier League"` / `17`. The list also has FA Cup, EFL Cup, Champions League, Community Shield and friendlies.
- `season.id`: the list spans two seasons; keep the current one.
- `status.type`: `finished`, `postponed`, ...
- `roundInfo.round`: Sofascore round, close to the FPL gameweek but not identical (see Risks).
- `homeTeam` / `awayTeam` (`id`, `name`), `homeScore.current` / `awayScore.current`.

### `/event/{eventId}/average-positions` shape
```json
{
  "home": [ { "player": {...}, "averageX": 37.03, "averageY": 83.06, "pointsCount": 63 }, ... ],
  "away": [ ... ],
  "substitutions": [
    { "playerIn": {...}, "playerOut": {...}, "time": 56, "isHome": false, "injury": false, ... }
  ]
}
```
- `player`: `id` (Sofascore player ID), `name`, `firstName`, `lastName`, `shortName`, `slug`, `position` (`G`/`D`/`M`/`F`), `jerseyNumber`.
- `averageX`, `averageY`: average position, 0-100 (see Coordinate system).
- `pointsCount`: undocumented; most likely the number of **on-ball actions** (touches, passes, tackles) the average is built from, not time samples. It follows involvement, not minutes: Elliot Anderson (90 min) 120, Alisson (90 min, GK) 37, Rio Ngumoha (on at 75') 1. So the average is where the player was when on the ball, and a low count makes it noise (Federico Chiesa, 1 action, sits by the corner flag at x 5.6, y 4.6).
- `substitutions`: each change with match minute and side. Player IDs match the `home`/`away` lists.

## Who played, subs, minutes
- Only players who played are listed; unused subs are not. In all 6 matches, players listed = 22 + number of substitutions (e.g. 22 + 8 = 30).
- There is **no "started" flag** on a player. Derive it:
  - **Sub:** appears as `playerIn` in `substitutions`.
  - **Starter:** listed but never a `playerIn`.
  - **Minutes (approx.):** a sub plays from `time` to 90; a starter taken off plays 0 to `time`; otherwise 90. Stoppage time is ignored. Red cards are not handled (not seen in samples).

## Coordinate system
- **x: 0 = own goal, 100 = opponent's goal.** Both teams are normalized to attack the same way: in all 6 matches both goalkeepers sit at x ≈ 8-14.
- **y: high = left side, low = right side** (from the attacking team's view). Proof from Liverpool 0-3 Man City (`16363878`):

| Player | Role | averageY |
|---|---|---|
| Miloš Kerkez (LIV) | left-back | 83.1 |
| Nico O'Reilly (MCI) | left-back | 83.3 |
| Jérémy Doku (MCI) | left winger | 82.7 |
| Matheus Nunes (MCI) | right-back | 12.1 |
| Ronald Araújo (LIV) | right side of defence | 13.3 |

So no home/away flipping is needed. To draw a pitch with the left side on the left, plot `y' = 100 - y`.

## Coverage (Man City rounds 1-6)
| Round | Match | Event | Players (home / away) | Subs |
|---|---|---|---|---|
| R1 | Man City 2-1 Bournemouth | 16363243 | 15 / 15 | 8 |
| R2 | Crystal Palace 1-4 Man City | 16363252 | 16 / 16 | 10 |
| R3 | Man City 1-0 Coventry | 16363263 | 14 / 16 | 8 |
| R4 | Man Utd 0-1 Man City | 16363645 | 13 / 13 | 4 |
| R5 | Man City 5-3 Sunderland | 16363867 | 13 / 14 | 5 |
| R6 | Liverpool 0-3 Man City | 16363878 | 16 / 15 | 9 |

- **Matches with average-position data: 6 / 6 (100%).**
- **Players who appeared with a position: 176 / 176 (100%).** All 44 subs who came on are in the position lists.
- **Low-sample players:** 11 of 176 had `pointsCount < 10`, all subs (on between 63' and 89'). Suggest a minimum `pointsCount` before plotting, or showing them faded.

## Fetch approach (agreed)
1. For each of the 20 clubs: `GET /team/{teamId}/events/last/0`, keep finished Premier League matches of the current season, take the last **N** (spike default `N = 6`; regular syncs will use `N = 3`).
2. For each event ID: if it is already downloaded, skip; else `GET /event/{eventId}/average-positions` and mark it downloaded. One file covers **both** clubs, so the opponent's turn skips it.
3. `N = 3` rather than 1 so a sync still catches a match if two gameweeks pass between syncs (midweek rounds, rescheduled matches). Already-downloaded matches cost nothing.

Script: `python spikes/sofascore/fetch_team_matches.py <teamId> [N]`. Sofascore team IDs for all 20 clubs come from the owner and belong in `fpl_clubs.sofascore_team_id`.

## Request budget
- **Gameweek sync:** 20 team lists + ~10 new matches ≈ **30 requests**, ~75 s at 2.5 s apart.
- **Full-season backfill:** 20 team lists + 380 matches ≈ **400 requests**, ~17 min at 2.5 s. `events/last/0` returns only the last 30 matches in all competitions, so late in the season older league matches drop off it; `events/last/1` (the next page) is the likely fix but is **not tested**.

## Access
- Plain Python `requests` with browser headers gets **403** (`{"error": {"code": 403, "reason": "Forbidden"}}`, server `Varnish`), most likely TLS fingerprinting.
- `curl_cffi` with `impersonate="chrome"` works (200) with no extra headers. A `Referer: https://www.sofascore.com/` header is sent anyway.
- About 15 requests made from the owner's connection, 1.5-2.5 s apart: no blocking or rate limiting seen. Limits are unknown; stay at 2+ s between requests.
- Unofficial API: no docs, no guarantees, can change or block without notice.

## Risks
- **Unofficial / blocking:** Sofascore could tighten bot checks. Keep raw JSON so we never need to re-fetch, and keep requests slow.
- **Rounds vs gameweeks:** postponed matches show up twice in the team list (once `postponed`, later `finished` with a **new event ID**, e.g. City vs Crystal Palace in 2025/26 round 31). Filter on `finished`; assign matches to FPL gameweeks from FPL's fixture list, not from Sofascore's round number.
- **Approximate minutes:** stoppage time and red cards are not handled.
- **Player ID mapping:** Sofascore player IDs must be matched to FPL player IDs (tasks 08-09). Not covered here.
- **Fallback source:** FotMob has similar unofficial match data and could be tested if Sofascore blocks us.

## Not covered (open questions for later tasks)
- **Squad lists** (players who have not played yet) for ID matching: no endpoint tested. Needed for task 08.
- Pagination of `events/last/{page}`.
- Red cards and their effect on minutes.
