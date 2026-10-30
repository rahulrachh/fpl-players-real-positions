// The match details box: who a player played, for how long and how his FPL
// points add up. Used for pitch dots and bench cards; ghosts and "from GWx"
// dots have none. Opened and closed by `useMatchDetails`.
//
// The box is drawn beside the card, not inside it, so the image export (which
// copies the card) never contains it.

import { type ReactNode, type RefObject, useLayoutEffect, useRef, useState } from 'react'

import type { BenchPlayer, PickMatch, PlotDot, Role } from './api'
import { type Anchor, type Open, ROLE_NAMES } from './useMatchDetails'

// Gap between the box and what it points at, and from the card's edges.
const GAP = 6
const EDGE = 8

// Below the anchor if it fits in the card, else above, else wherever it is
// least cut off; centred on the anchor, kept inside the card's sides.
function place(anchor: Anchor, w: number, h: number, frameW: number, frameH: number) {
  const below = anchor.top + anchor.height + GAP
  const above = anchor.top - GAP - h
  let top = below + h <= frameH - EDGE ? below : above >= EDGE ? above : Math.max(EDGE, frameH - EDGE - h)
  top = Math.max(0, top)
  const centre = anchor.left + anchor.width / 2
  const left = Math.min(Math.max(EDGE, centre - w / 2), Math.max(EDGE, frameW - EDGE - w))
  return { top, left }
}

export function MatchDetailsBox({
  open,
  frame,
  dots,
  onClose,
}: {
  open: Open
  frame: RefObject<HTMLElement | null>
  dots: PlotDot[]
  onClose: () => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  useLayoutEffect(() => {
    const el = box.current
    const f = frame.current
    if (!el || !f) return
    setPos(place(open.anchor, el.offsetWidth, el.offsetHeight, f.clientWidth, f.clientHeight))
  }, [open, frame])

  return (
    <div
      ref={box}
      className={open.via === 'hover' ? 'details details-hover' : 'details'}
      role="dialog"
      aria-label="Match details"
      // Measured first, then shown in place.
      style={pos ? { top: pos.top, left: pos.left } : { top: 0, left: 0, visibility: 'hidden' }}
      onClick={(e) => {
        e.stopPropagation()
        onClose()
      }}
    >
      {open.content.kind === 'dot' ? (
        <DotDetails dot={open.content.dot} dots={dots} />
      ) : (
        <BenchDetails player={open.content.player} />
      )}
    </div>
  )
}

// "Maxim De Cuyper", "Ezri Konsa", "João Pedro": the first word of the first
// name and FPL's short name, or the short name alone when it already holds
// the first name. Initials FPL adds to short names ("J.Timber", "Tóth.A",
// "Bruno G.") are dropped.
function boxName(name: string, webName: string) {
  const first = name.split(' ')[0]
  const short = webName
    .replace(/(^|\s)(?:\p{L}{1,2}\.)+(?=\p{L})/gu, '$1')
    .replace(/\.\p{L}{1,2}$/u, '')
    .replace(/\s\p{L}\.$/u, '')
    .trim()
  return short.split(' ').includes(first) ? short : `${first} ${short}`
}

function Header({ name, webName, club, role }: { name: string; webName: string; club: string; role: Role }) {
  return (
    <header className="details-head">
      <span className={`details-role role-${role}`} aria-hidden="true" />
      <div>
        <p className="details-name">{boxName(name, webName)}</p>
        <p className="details-sub">
          {club} · {ROLE_NAMES[role]}
        </p>
      </div>
    </header>
  )
}

function signed(points: number) {
  return points > 0 ? `+${points}` : points < 0 ? `−${-points}` : '0'
}

// The minutes are the first breakdown row, so only a match without one says
// why. `label` names the match in a double gameweek.
function MatchBlock({ m, label }: { m: PickMatch; label: string | null }) {
  return (
    <section className="details-match">
      {label && <p className="details-minutes">{label}</p>}
      {m.state === 'not_started' && <p className="details-minutes">Not played yet</p>}
      {m.state !== 'not_started' && m.minutes === 0 && <p className="details-minutes">Did not play</p>}
      {m.stats.length > 0 && (
        <table className="details-stats">
          <tbody>
            {m.stats.map((s) => (
              <tr key={s.identifier}>
                <th scope="row">{s.label}</th>
                <td className="details-value">{s.value}</td>
                <td className="details-pts">{signed(s.points)}</td>
              </tr>
            ))}
            {label && (
              <tr className="details-subtotal">
                <th scope="row">Match</th>
                <td />
                <td className="details-pts">{m.points}</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}

function Line({ label, value, strong }: { label: ReactNode; value: ReactNode; strong?: boolean }) {
  return (
    <p className={strong ? 'details-line details-total' : 'details-line'}>
      <span>{label}</span>
      <span>{value}</span>
    </p>
  )
}

function Matches({ matches }: { matches: PickMatch[] }) {
  if (matches.length === 0) return <p className="details-minutes">No match this gameweek</p>
  return (
    <>
      {matches.map((m, i) => (
        <MatchBlock key={m.fixture_id} m={m} label={matches.length > 1 ? `Match ${i + 1}` : null} />
      ))}
    </>
  )
}

function DotDetails({ dot, dots }: { dot: PlotDot; dots: PlotDot[] }) {
  // A double-gameweek dot on one flank carries its own match; the other
  // match is on the linked dot, and the circle shows both.
  const own = new Set(dot.matches.map((m) => m.fixture_id))
  const other =
    dot.link_group === null
      ? []
      : dots
          .filter((d) => d.link_group === dot.link_group && d !== dot)
          .flatMap((d) => d.matches)
          .filter((m) => !own.has(m.fixture_id))
  const base = [...dot.matches, ...other].reduce((sum, m) => sum + m.points, 0)
  return (
    <>
      <Header name={dot.name} webName={dot.web_name} club={dot.club} role={dot.role} />
      <Matches matches={dot.matches} />
      <footer className="details-foot">
        {other.map((m) => (
          <Line key={m.fixture_id} label="Other match" value={signed(m.points)} />
        ))}
        {dot.multiplier > 1 && (
          <Line
            label={dot.multiplier === 3 ? 'Triple captain' : 'Captain'}
            value={`${base} × ${dot.multiplier}`}
          />
        )}
        <Line label="Total" value={`${dot.points} pts`} strong />
      </footer>
    </>
  )
}

function BenchDetails({ player }: { player: BenchPlayer }) {
  return (
    <>
      <Header name={player.name} webName={player.web_name} club={player.club} role={player.role} />
      <Matches matches={player.matches} />
      <footer className="details-foot">
        <Line label="Total" value={`${player.points} pts`} strong />
      </footer>
    </>
  )
}
