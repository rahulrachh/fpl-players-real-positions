// Dev-only samples (?fixture=edges, ?fixture=bboost) with the cases the owner's
// real team does not have yet: a ghost for each reason, a double-gameweek pair,
// "from GWx", an auto-sub, Triple Captain, negative and double-digit scores, a
// bench with a starter who did not play, and Bench Boost (15 dots).

import type { BenchPlayer, Plot, PlotDot } from '../api'

const dot = (d: Partial<PlotDot> & Pick<PlotDot, 'fpl_id' | 'web_name' | 'role' | 'slot'>): PlotDot => ({
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
    dot({ fpl_id: 4, web_name: 'Gvardiol', role: 'DEF', slot: 4, x: 15, y: 47, link_group: 4, depth_pct: 42, points: 9 }),
    dot({ fpl_id: 4, web_name: 'Gvardiol', role: 'DEF', slot: 4, x: 79, y: 44, link_group: 4, depth_pct: 35, points: 9 }),
    dot({ fpl_id: 5, web_name: 'Saliba', role: 'DEF', slot: 5, is_ghost: true, ghost_reason: 'no_match' }),
    dot({ fpl_id: 6, web_name: 'Saka', role: 'MID', slot: 6, x: 86, y: 74, is_captain: true, depth_pct: 93, points: 15 }),
    dot({ fpl_id: 7, web_name: 'Rice', role: 'MID', slot: 7, x: 50, y: 50, replaces: 99, depth_pct: 50, points: 3 }),
    dot({ fpl_id: 8, web_name: 'Ødegaard', role: 'MID', slot: 8, x: 51, y: 51, depth_pct: 54, points: 0 }),
    dot({ fpl_id: 9, web_name: 'Mbeumo', role: 'MID', slot: 9, is_ghost: true, ghost_reason: 'no_mapping' }),
    dot({ fpl_id: 10, web_name: 'Haaland', role: 'FWD', slot: 10, x: 50, y: 88, depth_pct: 97, points: 13 }),
    dot({ fpl_id: 11, web_name: 'Wissa', role: 'FWD', slot: 11, x: 12, y: 80, from_gw: 2, depth_pct: 88, points: 1 }),
  ],
  bench: [
    bench({ fpl_id: 12, web_name: 'Kelleher', role: 'GK', points: 0 }),
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
