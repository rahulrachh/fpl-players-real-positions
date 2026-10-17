// Turns plot dots (0-100 frame, attacking upward) into SVG coordinates in metres,
// keeps stacked dots readable and picks a label spot for each one.

import type { PlotDot, Role } from './api'

export const ROLE_LETTER: Record<Role, string> = { GK: 'G', DEF: 'D', MID: 'M', FWD: 'F' }

export const PITCH_W = 68
export const PITCH_L = 105
// Room around the pitch. Ghosts stand in the right margin (the sideline); the
// left one matches it so the pitch stays centred.
export const MARGIN = { top: 3, bottom: 3, left: 7.5, right: 7.5 }
export const VIEW_W = MARGIN.left + PITCH_W + MARGIN.right
export const VIEW_H = MARGIN.top + PITCH_L + MARGIN.bottom

export const DOT_R = 2.6
export const NAME_SIZE = 2.6
export const SUB_SIZE = 1.9
const GHOST_R = 2.1
const GHOST_GAP = 9

// Two dots closer than this are pushed apart, by at most MAX_NUDGE each, so
// players in the same spot stay visible. Positions move by under 2% of the pitch.
const MIN_GAP = DOT_R * 1.7
const MAX_NUDGE = DOT_R * 0.9

export type Box = { x0: number; y0: number; x1: number; y1: number }

export type LaidDot = {
  dot: PlotDot
  key: string
  cx: number
  cy: number
  r: number
  // Label anchor (text-anchor middle / start / end) and the name's baseline.
  label: { x: number; y: number; anchor: 'middle' | 'start' | 'end' }
  // Second line under the name ("from GW4", "auto-sub"), if any.
  sub: string | null
  // Line from the dot's edge to a label placed away from a crowded dot.
  leader: [number, number, number, number] | null
}

export type Layout = {
  dots: LaidDot[]
  ghosts: LaidDot[]
  // Pairs of laid dots of the same double-gameweek player on opposite flanks.
  links: [LaidDot, LaidDot][]
}

// --- Depth views ------------------------------------------------------------
// Average positions bunch up in midfield, so outfield depth is drawn as a rank
// from the API (backend `app/logic/depth.py`): against every outfield player
// ('all') or only players of the same FPL role ('role'). Keepers keep their real
// depth.
export type DepthMode = 'all' | 'role'

// Ranks 0-100 are drawn between these depths, clear of both penalty boxes.
const RANK_BOTTOM = 20
const RANK_TOP = 90

export function displayDepth(dot: PlotDot, y: number, mode: DepthMode): number {
  const pct = mode === 'all' ? dot.depth_pct_all : dot.depth_pct_role
  return pct === null ? y : RANK_BOTTOM + (pct / 100) * (RANK_TOP - RANK_BOTTOM)
}

export function toSvg(x: number, y: number): [number, number] {
  return [MARGIN.left + (x / 100) * PITCH_W, MARGIN.top + ((100 - y) / 100) * PITCH_L]
}

export function subLabel(dot: PlotDot): string | null {
  if (dot.from_gw !== null) return `from GW${dot.from_gw}`
  if (dot.replaces !== null) return 'auto-sub'
  return null
}

// Archivo at the condensed width used for labels averages about half an em per character.
const textWidth = (text: string, size: number) => text.length * size * 0.52

function labelBox(d: LaidDot): Box {
  const nameW = textWidth(d.dot.web_name, NAME_SIZE)
  const subW = d.sub ? textWidth(d.sub, SUB_SIZE) : 0
  const w = Math.max(nameW, subW)
  const h = NAME_SIZE + (d.sub ? SUB_SIZE + 0.4 : 0)
  const top = d.label.y - NAME_SIZE * 0.8
  const left =
    d.label.anchor === 'middle' ? d.label.x - w / 2 : d.label.anchor === 'start' ? d.label.x : d.label.x - w
  return { x0: left, y0: top, x1: left + w, y1: top + h }
}

const circleBox = (d: LaidDot): Box => ({
  x0: d.cx - d.r,
  y0: d.cy - d.r,
  x1: d.cx + d.r,
  y1: d.cy + d.r,
})

function separate(dots: LaidDot[]) {
  const origin = dots.map((d) => [d.cx, d.cy])
  for (let pass = 0; pass < 40; pass++) {
    let moved = false
    for (let i = 0; i < dots.length; i++) {
      for (let j = i + 1; j < dots.length; j++) {
        const a = dots[i]
        const b = dots[j]
        let dx = b.cx - a.cx
        let dy = b.cy - a.cy
        let dist = Math.hypot(dx, dy)
        if (dist >= MIN_GAP) continue
        if (dist < 1e-6) {
          // Same spot: split sideways.
          dx = 1
          dy = 0
          dist = 1
        }
        const push = (MIN_GAP - dist) / 2
        a.cx -= (dx / dist) * push
        a.cy -= (dy / dist) * push
        b.cx += (dx / dist) * push
        b.cy += (dy / dist) * push
        moved = true
      }
    }
    // Never stray far from the real position.
    dots.forEach((d, k) => {
      const [ox, oy] = origin[k]
      const off = Math.hypot(d.cx - ox, d.cy - oy)
      if (off > MAX_NUDGE) {
        d.cx = ox + ((d.cx - ox) / off) * MAX_NUDGE
        d.cy = oy + ((d.cy - oy) / off) * MAX_NUDGE
      }
    })
    if (!moved) break
  }
}

// A dot with another dot this close is "crowded": its label moves out of the
// cluster on a leader line, so it is clear which dot a name belongs to.
const CROWD_DIST = DOT_R * 4.2
const LABEL_GAP = 1.1
const CALLOUT_DISTANCES = [DOT_R + 4, DOT_R + 7, DOT_R + 10.5]

const area = (a: Box, b: Box) =>
  Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) *
  Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0))

type Segment = [number, number, number, number]

function segmentsCross([ax, ay, bx, by]: Segment, [cx, cy, dx, dy]: Segment) {
  const side = (px: number, py: number, qx: number, qy: number, rx: number, ry: number) =>
    Math.sign((qx - px) * (ry - py) - (qy - py) * (rx - px))
  return (
    side(ax, ay, bx, by, cx, cy) * side(ax, ay, bx, by, dx, dy) < 0 &&
    side(cx, cy, dx, dy, ax, ay) * side(cx, cy, dx, dy, bx, by) < 0
  )
}

// Distance from a circle centre to a segment, to catch leader lines through dots.
function segmentDistance([ax, ay, bx, by]: Segment, px: number, py: number) {
  const len2 = (bx - ax) ** 2 + (by - ay) ** 2
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / len2))
  return Math.hypot(ax + t * (bx - ax) - px, ay + t * (by - ay) - py)
}

// The label whose box touches point (px, py) on the side facing `angle` from the dot.
function labelAt(d: LaidDot, angle: number, px: number, py: number): LaidDot['label'] {
  const h = NAME_SIZE + (d.sub ? SUB_SIZE + 0.4 : 0)
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  if (cos > 0.4) return { x: px, y: py - h / 2 + NAME_SIZE * 0.8, anchor: 'start' }
  if (cos < -0.4) return { x: px, y: py - h / 2 + NAME_SIZE * 0.8, anchor: 'end' }
  return { x: px, y: sin > 0 ? py + NAME_SIZE * 0.8 : py - h + NAME_SIZE * 0.8, anchor: 'middle' }
}

function placeLabels(dots: LaidDot[]) {
  const placed: Box[] = []
  const lines: Segment[] = []
  const inside = (b: Box) => b.x0 >= 0 && b.x1 <= VIEW_W && b.y0 >= 0 && b.y1 <= VIEW_H
  const crowded = new Set(
    dots.filter((d) => dots.some((o) => o !== d && Math.hypot(o.cx - d.cx, o.cy - d.cy) < CROWD_DIST)),
  )
  // Lone dots first (they only need the space next to them), each group top first.
  const order = [...dots].sort((a, b) => Number(crowded.has(a)) - Number(crowded.has(b)) || a.cy - b.cy)

  for (const d of order) {
    type Option = { label: LaidDot['label']; leader: Segment | null }
    const options: Option[] = []
    if (!crowded.has(d)) {
      // Below, above, right, left, then the diagonals.
      const angles = [90, -90, 0, 180, 45, 135, -45, -135].map((a) => (a * Math.PI) / 180)
      for (const a of angles) {
        const reach = d.r + LABEL_GAP
        options.push({ label: labelAt(d, a, d.cx + Math.cos(a) * reach, d.cy + Math.sin(a) * reach), leader: null })
      }
    } else {
      // Away from the neighbours first, sweeping round to the other side.
      const near = dots.filter((o) => o !== d && Math.hypot(o.cx - d.cx, o.cy - d.cy) < CROWD_DIST)
      const mx = near.reduce((s, o) => s + o.cx, 0) / near.length
      const my = near.reduce((s, o) => s + o.cy, 0) / near.length
      const away = Math.hypot(d.cx - mx, d.cy - my) < 1e-6 ? Math.PI / 2 : Math.atan2(d.cy - my, d.cx - mx)
      const angles = Array.from({ length: 16 }, (_, i) => away + (Math.ceil(i / 2) * (i % 2 ? 1 : -1) * Math.PI) / 8)
      for (const dist of CALLOUT_DISTANCES) {
        for (const a of angles) {
          const px = d.cx + Math.cos(a) * dist
          const py = d.cy + Math.sin(a) * dist
          const leader: Segment = [d.cx + Math.cos(a) * d.r, d.cy + Math.sin(a) * d.r, px, py]
          options.push({ label: labelAt(d, a, px, py), leader })
        }
      }
    }

    // First option that collides with nothing, else the one with the least overlap.
    let chosen = options[0]
    let best = Infinity
    for (const o of options) {
      const box = labelBox({ ...d, label: o.label })
      let score =
        dots.reduce((sum, other) => sum + (other === d ? 0 : area(box, circleBox(other))), 0) +
        placed.reduce((sum, p) => sum + area(box, p) * 2, 0) +
        (inside(box) ? 0 : 1000)
      if (o.leader) {
        const leader = o.leader
        score += dots.filter((other) => other !== d && segmentDistance(leader, other.cx, other.cy) < other.r + 0.3).length * 20
        score += lines.filter((l) => segmentsCross(leader, l)).length * 20
        score += placed.filter((p) => segmentDistance(leader, (p.x0 + p.x1) / 2, (p.y0 + p.y1) / 2) < (p.y1 - p.y0) / 2).length * 20
      }
      if (score < best) {
        best = score
        chosen = o
      }
      if (score === 0) break
    }
    d.label = chosen.label
    d.leader = chosen.leader
    placed.push(labelBox(d))
    if (chosen.leader) lines.push(chosen.leader)
  }
}

export function layoutDots(dots: PlotDot[], depth: DepthMode = 'all'): Layout {
  const onPitch: LaidDot[] = []
  const ghosts: LaidDot[] = []
  dots.forEach((dot, i) => {
    const key = `${dot.fpl_id}-${i}`
    if (dot.is_ghost || dot.x === null || dot.y === null) {
      const cx = MARGIN.left + PITCH_W + MARGIN.right / 2
      const cy = MARGIN.top + PITCH_L * 0.3 + ghosts.length * GHOST_GAP
      ghosts.push({
        dot,
        key,
        cx,
        cy,
        r: GHOST_R,
        label: { x: cx, y: cy + GHOST_R + 1 + SUB_SIZE * 0.8, anchor: 'middle' },
        sub: null,
        leader: null,
      })
      return
    }
    const [cx, cy] = toSvg(dot.x, displayDepth(dot, dot.y, depth))
    onPitch.push({ dot, key, cx, cy, r: DOT_R, label: { x: cx, y: cy, anchor: 'middle' }, sub: subLabel(dot), leader: null })
  })

  separate(onPitch)
  placeLabels(onPitch)

  const links: [LaidDot, LaidDot][] = []
  const byGroup = new Map<number, LaidDot[]>()
  for (const d of onPitch) {
    if (d.dot.link_group === null) continue
    const group = byGroup.get(d.dot.link_group) ?? []
    group.push(d)
    byGroup.set(d.dot.link_group, group)
  }
  for (const group of byGroup.values()) {
    if (group.length === 2) links.push([group[0], group[1]])
  }

  return { dots: onPitch, ghosts, links }
}
