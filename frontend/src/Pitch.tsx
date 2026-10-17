// The pitch graphic: real average positions of a team's XI, attacking upward.
// Drawn in metres (68 x 105 pitch) so markings are to scale.

import { useMemo } from 'react'

import type { PlotDot } from './api'
import {
  type DepthMode,
  type LaidDot,
  layoutDots,
  MARGIN,
  NAME_SIZE,
  PITCH_L,
  ROLE_LETTER,
  PITCH_W,
  SUB_SIZE,
  VIEW_H,
  VIEW_W,
} from './pitchLayout'

const L = MARGIN.left
const T = MARGIN.top
const MID_Y = T + PITCH_L / 2
const STRIPES = 14

function Markings() {
  const box = (width: number, depth: number, top: boolean) => (
    <rect
      x={L + (PITCH_W - width) / 2}
      y={top ? T : T + PITCH_L - depth}
      width={width}
      height={depth}
    />
  )
  // Penalty arc: the part of the 9.15 m circle around the spot outside the box.
  const arcDy = 16.5 - 11
  const arcDx = Math.sqrt(9.15 ** 2 - arcDy ** 2)
  const arc = (top: boolean) => {
    const y = top ? T + 16.5 : T + PITCH_L - 16.5
    return (
      <path
        d={`M ${L + PITCH_W / 2 - arcDx} ${y} A 9.15 9.15 0 0 ${top ? 0 : 1} ${L + PITCH_W / 2 + arcDx} ${y}`}
      />
    )
  }
  const corner = 1
  return (
    <g className="pitch-lines">
      <rect x={L} y={T} width={PITCH_W} height={PITCH_L} />
      <line x1={L} y1={MID_Y} x2={L + PITCH_W} y2={MID_Y} />
      <circle cx={L + PITCH_W / 2} cy={MID_Y} r={9.15} />
      <circle className="spot" cx={L + PITCH_W / 2} cy={MID_Y} r={0.35} />
      {[true, false].map((top) => (
        <g key={String(top)}>
          {box(40.32, 16.5, top)}
          {box(18.32, 5.5, top)}
          {arc(top)}
          <circle className="spot" cx={L + PITCH_W / 2} cy={top ? T + 11 : T + PITCH_L - 11} r={0.35} />
          <rect
            className="goal"
            x={L + (PITCH_W - 7.32) / 2}
            y={top ? T - 1.6 : T + PITCH_L}
            width={7.32}
            height={1.6}
          />
        </g>
      ))}
      <path
        d={[
          `M ${L + corner} ${T} A ${corner} ${corner} 0 0 1 ${L} ${T + corner}`,
          `M ${L + PITCH_W - corner} ${T} A ${corner} ${corner} 0 0 0 ${L + PITCH_W} ${T + corner}`,
          `M ${L} ${T + PITCH_L - corner} A ${corner} ${corner} 0 0 1 ${L + corner} ${T + PITCH_L}`,
          `M ${L + PITCH_W} ${T + PITCH_L - corner} A ${corner} ${corner} 0 0 0 ${L + PITCH_W - corner} ${T + PITCH_L}`,
        ].join(' ')}
      />
    </g>
  )
}

function Label({ d }: { d: LaidDot }) {
  const { x, y, anchor } = d.label
  return (
    <text className="label" x={x} y={y} textAnchor={anchor}>
      <tspan fontSize={NAME_SIZE}>{d.dot.web_name}</tspan>
      {d.sub && (
        <tspan className="label-sub" x={x} dy={SUB_SIZE + 0.4} fontSize={SUB_SIZE}>
          {d.sub}
        </tspan>
      )}
    </text>
  )
}

function Dot({ d }: { d: LaidDot }) {
  const { dot, cx, cy, r } = d
  return (
    <g className={`dot role-${dot.role}`}>
      <title>{`${dot.name} (${dot.role}, ${dot.club})${dot.is_captain ? ', captain' : ''}`}</title>
      <circle className="dot-body" cx={cx} cy={cy} r={r} />
      <text className="dot-letter" x={cx} y={cy + 0.75} fontSize={2.1} textAnchor="middle">
        {ROLE_LETTER[dot.role]}
      </text>
      {dot.is_captain && (
        <g className="armband">
          <circle cx={cx + r * 0.85} cy={cy - r * 0.85} r={1.35} />
          <text x={cx + r * 0.85} y={cy - r * 0.85 + 0.62} fontSize={1.75} textAnchor="middle">
            C
          </text>
        </g>
      )}
    </g>
  )
}

function Ghost({ d }: { d: LaidDot }) {
  const why = d.dot.ghost_reason === 'no_mapping' ? 'no position data linked' : 'did not play'
  return (
    <g className="ghost">
      <title>{`${d.dot.name} (${d.dot.role}, ${d.dot.club}): ${why}`}</title>
      <circle cx={d.cx} cy={d.cy} r={d.r} />
      <text className="label" x={d.label.x} y={d.label.y} fontSize={SUB_SIZE} textAnchor="middle">
        {d.dot.web_name}
      </text>
    </g>
  )
}

export default function Pitch({
  dots,
  title,
  depth = 'all',
}: {
  dots: PlotDot[]
  title: string
  depth?: DepthMode
}) {
  const layout = useMemo(() => layoutDots(dots, depth), [dots, depth])
  return (
    <svg className="pitch" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} role="img" aria-label={title}>
      <rect className="pitch-surround" x={0} y={0} width={VIEW_W} height={VIEW_H} rx={2} />
      {Array.from({ length: STRIPES }, (_, i) => (
        <rect
          key={i}
          className={i % 2 ? 'stripe stripe-dark' : 'stripe'}
          x={L}
          y={T + (PITCH_L / STRIPES) * i}
          width={PITCH_W}
          height={PITCH_L / STRIPES}
        />
      ))}
      <Markings />
      {layout.links.map(([a, b]) => (
        <line key={`${a.key}-link`} className="link" x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} />
      ))}
      {layout.dots.map(
        (d) =>
          d.leader && (
            <line
              key={`${d.key}-leader`}
              className="leader"
              x1={d.leader[0]}
              y1={d.leader[1]}
              x2={d.leader[2]}
              y2={d.leader[3]}
            />
          ),
      )}
      {layout.dots.map((d) => (
        <Dot key={d.key} d={d} />
      ))}
      {layout.dots.map((d) => (
        <Label key={`${d.key}-label`} d={d} />
      ))}
      {layout.ghosts.map((d) => (
        <Ghost key={d.key} d={d} />
      ))}
    </svg>
  )
}
