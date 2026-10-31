// Response types of the backend team endpoints (backend/app/fpl/team.py).

export type Role = 'GK' | 'DEF' | 'MID' | 'FWD'

export type TeamPick = {
  position: number
  starter: boolean
  picked_starter: boolean
  role: Role
  multiplier: number
  is_captain: boolean
  is_vice_captain: boolean
  auto_sub: 'in' | 'out' | null
  player: {
    id: number
    web_name: string
    first_name: string
    second_name: string
    club: { id: number; name: string; short_name: string }
  }
}

export type TeamGameweek = {
  team_id: number
  team_name: string
  manager_name: string
  gameweek: number
  status: 'upcoming' | 'in_progress' | 'finished'
  data_checked: boolean
  deadline: string
  chip: string | null
  // Tenths of £m.
  bank: number
  squad_value: number
  points: number
  transfers_cost: number
  captain_id: number
  vice_captain_id: number
  effective_captain_id: number | null
  automatic_subs: { player_in: number; player_out: number }[]
  picks: TeamPick[]
}

export type LatestGameweeks = { latest: number | null; last_finished: number | null }

export class ApiError extends Error {
  status: number
  code: string | null

  constructor(status: number, code: string | null, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.code ?? null, body?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const fetchLatestGameweeks = () => getJson<LatestGameweeks>('/api/gameweeks/latest')

export const fetchTeamGameweek = (teamId: number, gw: number) =>
  getJson<TeamGameweek>(`/api/team/${teamId}/gameweek/${gw}`)

// Response of GET /api/team/{id}/plot/{gw} (backend/app/logic/plot.py, docs/api.md).

// One line of FPL's points breakdown ("Goals scored 1 → 6").
export type StatPoints = { identifier: string; label: string; value: number; points: number }

// One of the player's matches in the gameweek, with how his points add up.
export type PickMatch = {
  fixture_id: number
  // Club short names. is_home / opponent are null when the player's current
  // club played in neither side (he has moved since).
  home_club: string
  away_club: string
  is_home: boolean | null
  opponent: string | null
  kickoff: string | null
  state: 'not_started' | 'live' | 'finished'
  home_score: number | null
  away_score: number | null
  minutes: number
  // Only the stats that scored or cost points.
  stats: StatPoints[]
  points: number
}

export type PlotDot = {
  fpl_id: number
  name: string
  web_name: string
  role: Role
  club: string
  slot: number
  // 0-100, attacking upward: x 0 = left touchline, y 0 = own goal line. null for a ghost.
  x: number | null
  y: number | null
  is_captain: boolean
  is_ghost: boolean
  ghost_reason: 'no_match' | 'no_mapping' | null
  from_gw: number | null
  link_group: number | null
  replaces: number | null
  // Percentile (0-100) of y among every outfield player-match, drawn as the
  // dot's height. null for a goalkeeper or ghost.
  depth_pct: number | null
  // The points the player scored for the team (live while in progress): his
  // own, doubled for the captain (tripled with Triple Captain).
  points: number
  // 2 for the captain (3 with Triple Captain), else 1.
  multiplier: number
  // A bench player drawn because of Bench Boost.
  from_bench: boolean
  // His matches of the gameweek (the details box). A linked double-gameweek
  // dot has only the match its position came from.
  matches: PickMatch[]
}

export type BenchPlayer = {
  fpl_id: number
  name: string
  web_name: string
  role: Role
  club: string
  points: number
  // Locked only: a picked starter FPL auto-subbed off (did not play).
  subbed_off: boolean
  matches: PickMatch[]
}

export type Plot = {
  team_id: number
  team_name: string
  manager_name: string
  gw: number
  state: 'preview' | 'locked'
  // FPL's status. A finished gameweek in preview is waiting for its positions.
  status: 'in_progress' | 'finished'
  // bboost / 3xc / freehit / wildcard / manager; null = no chip.
  chip: string | null
  // Gameweek score before transfer hits (live while in progress), and the hit.
  points: number
  transfers_cost: number
  prev_gw: number | null
  next_gw: number | null
  data_as_of: string | null
  dots: PlotDot[]
  bench: BenchPlayer[]
  // The summary beside the pitch; null if FPL's history could not be loaded.
  summary?: GameweekSummary | null
}

// The team's gameweek in numbers and its season so far (backend/app/logic/summary.py).
export type GameweekSummary = {
  // Of all FPL teams; null until FPL has them.
  average_score: number | null
  highest_score: number | null
  gw_rank: number | null
  overall_rank: number | null
  // Rank as a share of all FPL teams, in percent ("top 7%").
  gw_rank_pct: number | null
  overall_rank_pct: number | null
  previous_overall_rank: number | null
  // Of all FPL teams this gameweek; the top player carries his points.
  most_captained: { id: number; web_name: string } | null
  top_player: { id: number; web_name: string; points: number | null } | null
  total_points: number
  transfers: number
  transfers_cost: number
  // Tenths of £m; squad_value includes the bank.
  bank: number
  squad_value: number
  points_on_bench: number
  // Every gameweek of the season; unplayed ones have played false and 0 points.
  season: { gw: number; played: boolean; points: number; chip: string | null }[]
}

export const fetchPlot = (teamId: number, gw: number | 'latest') =>
  getJson<Plot>(`/api/team/${teamId}/plot/${gw}`)

// Response of GET /api/gameweek/{gw}/fixtures (backend/app/fpl/fixtures.py, docs/api.md).

export type TopPlayer = { id: number; web_name: string; club: string; role: Role; points: number }

export type FixtureSummary = {
  id: number
  kickoff: string | null
  state: 'not_started' | 'live' | 'finished'
  home_club: { id: number; name: string; short_name: string }
  away_club: { id: number; name: string; short_name: string }
  home_score: number | null
  away_score: number | null
  // Top 3 by FPL points in this match (ties for 3rd included), highest first.
  // Empty until kick-off.
  top_players: TopPlayer[]
}

export type GameweekFixtures = { gw: number; data_checked: boolean; fixtures: FixtureSummary[] }

export const fetchGameweekFixtures = (gw: number) => getJson<GameweekFixtures>(`/api/gameweek/${gw}/fixtures`)
