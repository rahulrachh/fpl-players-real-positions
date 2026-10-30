// The pitch graphic: where a team's XI played, attacking upward; each circle
// shows the player's points and is sized by them.
// Drawn in metres (68 x 105 pitch) so markings are to scale.

import { useMemo } from 'react'

import type { PlotDot } from './api'
import type { DetailsTrigger } from './useMatchDetails'
import {
  type LaidDot,
  layoutDots,
  MARGIN,
  NAME_SIZE,
  PITCH_L,
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

function Dot({ d, details }: { d: LaidDot; details?: DetailsTrigger }) {
  const { dot, cx, cy, r } = d
  // Two characters (10+, or a minus) need a smaller size to fit the circle.
  const size = String(dot.points).length > 1 ? r * 0.9 : r * 1.05
  const summary = `${dot.name} (${dot.role}, ${dot.club}): ${dot.points} pts${dot.is_captain ? ', captain' : ''}`
  // A "from GWx" dot shows an earlier match, so it has no details box.
  const trigger =
    details && dot.from_gw === null ? details(d.key, { kind: 'dot', dot }, `${summary}. Match details`) : null
  return (
    <g className={`dot role-${dot.role}`} {...trigger}>
      {!trigger && <title>{summary}</title>}
      <circle className="dot-body" cx={cx} cy={cy} r={r} />
      <text className="dot-points" x={cx} y={cy + size * 0.36} fontSize={size} textAnchor="middle">
        {dot.points}
      </text>
    </g>
  )
}

// Drawn after every dot so a neighbouring dot never covers it. Triple
// Captain gets a wider gold "TC" tag instead of the "C".
function Armband({ d, triple }: { d: LaidDot; triple: boolean }) {
  const x = d.cx + d.r * 0.8
  const y = d.cy - d.r * 0.8
  const width = triple ? 4 : 2.7
  return (
    <g className={triple ? 'armband armband-triple' : 'armband'}>
      <rect x={x - width / 2} y={y - 1.35} width={width} height={2.7} rx={1.35} />
      <text x={x} y={y + 0.62} fontSize={1.75} textAnchor="middle">
        {triple ? 'TC' : 'C'}
      </text>
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

type Props = { dots: PlotDot[]; title: string; chip: string | null; details?: DetailsTrigger }

export default function Pitch({ dots, title, chip, details }: Props) {
  const layout = useMemo(() => layoutDots(dots), [dots])
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
      {/* Biggest first, so a small circle is never hidden under a big one. */}
      {[...layout.dots]
        .sort((a, b) => b.r - a.r)
        .map((d) => (
          <Dot key={d.key} d={d} details={details} />
        ))}
      {layout.dots.map(
        (d) => d.dot.is_captain && <Armband key={`${d.key}-armband`} d={d} triple={chip === '3xc'} />,
      )}
      {layout.dots.map((d) => (
        <Label key={`${d.key}-label`} d={d} />
      ))}
      {layout.ghosts.map((d) => (
        <Ghost key={d.key} d={d} />
      ))}
    </svg>
  )
}
