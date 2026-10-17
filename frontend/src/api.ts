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
}

export type Plot = {
  team_id: number
  team_name: string
  manager_name: string
  gw: number
  state: 'preview' | 'locked'
  // Gameweek score before transfer hits (live while in progress), and the hit.
  points: number
  transfers_cost: number
  prev_gw: number | null
  next_gw: number | null
  data_as_of: string | null
  dots: PlotDot[]
}

export const fetchPlot = (teamId: number, gw: number | 'latest') =>
  getJson<Plot>(`/api/team/${teamId}/plot/${gw}`)
