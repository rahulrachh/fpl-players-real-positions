// Dev-only sample (?fixture=edges) with the cases the owner's real team does not
// have yet: a ghost from each reason, a double-gameweek pair, "from GWx" and an auto-sub.

import type { Plot, PlotDot } from '../api'

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
  ...d,
})

export const edgeCases: Plot = {
  team_id: 1,
  team_name: 'Edge Case FC',
  manager_name: 'Sample data',
  gw: 7,
  state: 'preview',
  points: 58,
  transfers_cost: 4,
  prev_gw: 6,
  next_gw: null,
  data_as_of: '2026-10-17T05:21:57.469430',
  dots: [
    dot({ fpl_id: 1, web_name: 'Raya', role: 'GK', slot: 1, x: 50.5, y: 9.5 }),
    dot({ fpl_id: 2, web_name: 'Alexander-Arnold', role: 'DEF', slot: 2, x: 84, y: 58, from_gw: 4, depth_pct: 70 }),
    dot({ fpl_id: 3, web_name: 'Gabriel', role: 'DEF', slot: 3, x: 38, y: 30, depth_pct: 12 }),
    dot({ fpl_id: 4, web_name: 'Gvardiol', role: 'DEF', slot: 4, x: 15, y: 47, link_group: 4, depth_pct: 42 }),
    dot({ fpl_id: 4, web_name: 'Gvardiol', role: 'DEF', slot: 4, x: 79, y: 44, link_group: 4, depth_pct: 35 }),
    dot({ fpl_id: 5, web_name: 'Saliba', role: 'DEF', slot: 5, is_ghost: true, ghost_reason: 'no_match' }),
    dot({ fpl_id: 6, web_name: 'Saka', role: 'MID', slot: 6, x: 86, y: 74, is_captain: true, depth_pct: 93 }),
    dot({ fpl_id: 7, web_name: 'Rice', role: 'MID', slot: 7, x: 50, y: 50, replaces: 99, depth_pct: 50 }),
    dot({ fpl_id: 8, web_name: 'Ødegaard', role: 'MID', slot: 8, x: 51, y: 51, depth_pct: 54 }),
    dot({ fpl_id: 9, web_name: 'Mbeumo', role: 'MID', slot: 9, is_ghost: true, ghost_reason: 'no_mapping' }),
    dot({ fpl_id: 10, web_name: 'Haaland', role: 'FWD', slot: 10, x: 50, y: 88, depth_pct: 97 }),
    dot({ fpl_id: 11, web_name: 'Wissa', role: 'FWD', slot: 11, x: 12, y: 80, from_gw: 2, depth_pct: 88 }),
  ],
}
