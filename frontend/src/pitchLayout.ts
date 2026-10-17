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
}

export type Layout = {
  dots: LaidDot[]
  ghosts: LaidDot[]
  // Pairs of laid dots of the same double-gameweek player on opposite flanks.
  links: [LaidDot, LaidDot][]
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

function placeLabels(dots: LaidDot[]) {
  const placed: Box[] = []
  const bounds: Box = { x0: 0, y0: 0, x1: VIEW_W, y1: VIEW_H }
  const inside = (b: Box) => b.x0 >= bounds.x0 && b.x1 <= bounds.x1 && b.y0 >= bounds.y0 && b.y1 <= bounds.y1
  // Top of the pitch first, so attackers get first pick of the space below them.
  const order = [...dots].sort((a, b) => a.cy - b.cy)
  for (const d of order) {
    const lines = d.sub ? NAME_SIZE + SUB_SIZE + 0.4 : NAME_SIZE
    const gap = 1.1
    const candidates: LaidDot['label'][] = [
      { x: d.cx, y: d.cy + d.r + gap + NAME_SIZE * 0.8, anchor: 'middle' },
      { x: d.cx, y: d.cy - d.r - gap - lines + NAME_SIZE * 0.8, anchor: 'middle' },
      { x: d.cx + d.r + gap, y: d.cy + NAME_SIZE * 0.3, anchor: 'start' },
      { x: d.cx - d.r - gap, y: d.cy + NAME_SIZE * 0.3, anchor: 'end' },
      { x: d.cx + d.r * 0.7, y: d.cy + d.r + gap + NAME_SIZE * 0.8, anchor: 'start' },
      { x: d.cx - d.r * 0.7, y: d.cy + d.r + gap + NAME_SIZE * 0.8, anchor: 'end' },
      { x: d.cx + d.r * 0.7, y: d.cy - d.r - gap - lines + NAME_SIZE * 0.8, anchor: 'start' },
      { x: d.cx - d.r * 0.7, y: d.cy - d.r - gap - lines + NAME_SIZE * 0.8, anchor: 'end' },
    ]
    // First spot that collides with nothing, else the one with the least overlap.
    const area = (a: Box, b: Box) =>
      Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) *
      Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0))
    let chosen = candidates[0]
    let best = Infinity
    for (const c of candidates) {
      const box = labelBox({ ...d, label: c })
      const score =
        dots.reduce((sum, o) => sum + (o === d ? 0 : area(box, circleBox(o))), 0) +
        placed.reduce((sum, p) => sum + area(box, p) * 2, 0) +
        (inside(box) ? 0 : 1000)
      if (score < best) {
        best = score
        chosen = c
      }
      if (score === 0) break
    }
    d.label = chosen
    placed.push(labelBox(d))
  }
}

export function layoutDots(dots: PlotDot[]): Layout {
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
      })
      return
    }
    const [cx, cy] = toSvg(dot.x, dot.y)
    onPitch.push({ dot, key, cx, cy, r: DOT_R, label: { x: cx, y: cy, anchor: 'middle' }, sub: subLabel(dot) })
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
