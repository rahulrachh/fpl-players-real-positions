// Dev-only samples (?fixture=edges, ?fixture=bboost) with the cases the owner's
// real team does not have yet: a ghost for each reason, a double-gameweek pair,
// "from GWx", an auto-sub, Triple Captain, negative and double-digit scores, a
// bench with a starter who did not play, a live and an unstarted match, and
// Bench Boost (15 dots).

import type { BenchPlayer, PickMatch, Plot, PlotDot, StatPoints } from '../api'

const stat = (identifier: string, label: string, value: number, points: number): StatPoints => ({
  identifier,
  label,
  value,
  points,
})

// A finished home match whose breakdown adds up to `points` (0 minutes when
// `played` is false).
const match = (points: number, fixture_id = 1, played = true): PickMatch => {
  const stats: StatPoints[] = []
  if (played) {
    stats.push(stat('minutes', 'Minutes', 90, 2))
    const rest = points - 2
    if (rest > 0) {
      if (rest >= 4) stats.push(stat('goals_scored', 'Goals scored', 1, rest - Math.min(3, rest - 4)))
      if (rest !== 4) stats.push(stat('bonus', 'Bonus', Math.min(3, rest % 4 || 3), Math.min(3, rest % 4 || 3)))
    }
    if (rest === -1) stats.push(stat('yellow_cards', 'Yellow cards', 1, -1))
    if (rest < -1) stats.push(stat('red_cards', 'Red cards', 1, rest))
  }
  const total = stats.reduce((sum, s) => sum + s.points, 0)
  return {
    fixture_id,
    home_club: 'ARS',
    away_club: fixture_id === 1 ? 'CHE' : 'LIV',
    is_home: true,
    opponent: fixture_id === 1 ? 'CHE' : 'LIV',
    kickoff: '2026-10-11T14:00:00Z',
    state: 'finished',
    home_score: 2,
    away_score: 1,
    minutes: played ? 90 : 0,
    stats,
    points: total,
  }
}

const dot = (d: Partial<PlotDot> & Pick<PlotDot, 'fpl_id' | 'web_name' | 'role' | 'slot'>): PlotDot => ({
  multiplier: 1,
  matches: [match((d.points ?? 0) / (d.multiplier ?? 1))],
  name: d.web_name,
  club: 'ARS',
  x: null,
  y: null,
  is_captain: false,
  is_ghost: false,
  ghost_reason: null,
  from_gw: null,
  link_group: null,
  replaces: null,
  depth_pct: null,
  points: 0,
  from_bench: false,
  ...d,
})

const bench = (b: Partial<BenchPlayer> & Pick<BenchPlayer, 'fpl_id' | 'web_name' | 'role' | 'points'>): BenchPlayer => ({
  matches: [match(b.points, 1, !b.subbed_off)],
  name: b.web_name,
  club: 'ARS',
  subbed_off: false,
  ...b,
})

export const edgeCases: Plot = {
  team_id: 1,
  team_name: 'Edge Case FC',
  manager_name: 'Sample data',
  gw: 7,
  state: 'preview',
  status: 'in_progress',
  chip: '3xc',
  points: 58,
  transfers_cost: 4,
  prev_gw: 6,
  next_gw: null,
  data_as_of: '2026-10-17T05:21:57.469430',
  dots: [
    dot({ fpl_id: 1, web_name: 'Raya', role: 'GK', slot: 1, x: 50.5, y: 9.5, points: 6 }),
    dot({ fpl_id: 2, web_name: 'Alexander-Arnold', role: 'DEF', slot: 2, x: 84, y: 58, from_gw: 4, depth_pct: 70, points: 2 }),
    dot({ fpl_id: 3, web_name: 'Gabriel', role: 'DEF', slot: 3, x: 38, y: 30, depth_pct: 12, points: -1 }),
    dot({ fpl_id: 4, web_name: 'Gvardiol', role: 'DEF', slot: 4, x: 15, y: 47, link_group: 4, depth_pct: 42, points: 9, matches: [match(5)] }),
    dot({ fpl_id: 4, web_name: 'Gvardiol', role: 'DEF', slot: 4, x: 79, y: 44, link_group: 4, depth_pct: 35, points: 9, matches: [match(4, 2)] }),
    dot({ fpl_id: 5, web_name: 'Saliba', role: 'DEF', slot: 5, is_ghost: true, ghost_reason: 'no_match' }),
    dot({ fpl_id: 6, web_name: 'Saka', role: 'MID', slot: 6, x: 86, y: 74, is_captain: true, depth_pct: 93, points: 15, multiplier: 3 }),
    dot({ fpl_id: 7, web_name: 'Rice', role: 'MID', slot: 7, x: 50, y: 50, replaces: 99, depth_pct: 50, points: 3 }),
    dot({ fpl_id: 8, web_name: 'Ødegaard', role: 'MID', slot: 8, x: 51, y: 51, depth_pct: 54, points: 0 }),
    dot({ fpl_id: 9, web_name: 'Mbeumo', role: 'MID', slot: 9, is_ghost: true, ghost_reason: 'no_mapping' }),
    dot({ fpl_id: 10, web_name: 'Haaland', role: 'FWD', slot: 10, x: 50, y: 88, depth_pct: 97, points: 13,
      // One dot for both matches, the second still on.
      matches: [match(9), { ...match(4, 2), state: 'live', home_score: 1, away_score: 0 }] }),
    dot({ fpl_id: 11, web_name: 'Wissa', role: 'FWD', slot: 11, x: 12, y: 80, from_gw: 2, depth_pct: 88, points: 1 }),
  ],
  bench: [
    bench({
      fpl_id: 12, web_name: 'Kelleher', role: 'GK', points: 0,
      matches: [{ ...match(0, 1, false), state: 'not_started', home_score: null, away_score: null }],
    }),
    bench({ fpl_id: 99, web_name: 'Merino', role: 'MID', points: 0, subbed_off: true }),
    bench({ fpl_id: 14, web_name: 'Burn', role: 'DEF', points: 2 }),
    bench({ fpl_id: 15, web_name: 'Archer', role: 'FWD', points: 5 }),
  ],
}

export const benchBoost: Plot = {
  ...edgeCases,
  team_name: 'Bench Boost FC',
  state: 'locked',
  status: 'finished',
  chip: 'bboost',
  points: 71,
  transfers_cost: 0,
  dots: [
    // Locked: no "from GWx"; no auto-subs under Bench Boost.
    ...edgeCases.dots.map((d) => ({ ...d, from_gw: null, replaces: null })),
    dot({ fpl_id: 12, web_name: 'Kelleher', role: 'GK', slot: 12, x: 46, y: 12, points: 2, from_bench: true }),
    dot({ fpl_id: 13, web_name: 'Merino', role: 'MID', slot: 13, x: 62, y: 60, depth_pct: 62, points: 7, from_bench: true }),
    dot({ fpl_id: 14, web_name: 'Burn', role: 'DEF', slot: 14, x: 22, y: 35, depth_pct: 20, points: 2, from_bench: true }),
    dot({ fpl_id: 15, web_name: 'Archer', role: 'FWD', slot: 15, x: 60, y: 82, depth_pct: 90, points: 5, from_bench: true }),
  ],
  // Everyone is on the pitch under Bench Boost.
  bench: [],
}
