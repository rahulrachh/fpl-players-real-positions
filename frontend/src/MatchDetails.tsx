// The match details box: the match(es) a player played and how his FPL
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

// Name, club and role; with a single match its scoreline goes right under
// them, above the line. Two matches keep a scoreline on each breakdown so
// the points stay with their match.
function Header({
  name,
  webName,
  club,
  role,
  matches,
}: {
  name: string
  webName: string
  club: string
  role: Role
  matches: PickMatch[]
}) {
  return (
    <header className="details-head">
      <div className="details-id">
        <span className={`details-role role-${role}`} aria-hidden="true" />
        <div>
          <p className="details-name">{boxName(name, webName)}</p>
          <p className="details-sub">
            {club} · {ROLE_NAMES[role]}
          </p>
        </div>
      </div>
      {matches.length === 1 && <Fixture m={matches[0]} club={club} />}
    </header>
  )
}

function signed(points: number) {
  return points > 0 ? `+${points}` : points < 0 ? `−${-points}` : '0'
}

function kickoffText(iso: string | null) {
  if (!iso) return 'TBC'
  return new Date(iso).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit' })
}

function scoreline(m: PickMatch) {
  const centre = m.state === 'not_started' ? 'v' : `${m.home_score ?? 0} – ${m.away_score ?? 0}`
  return `${m.home_club} ${centre} ${m.away_club}`
}

// A small scoreboard above each breakdown, set apart from the points: the
// two clubs (the player's in bold) around the score in a dark chip (red while
// live), or "v" and the kickoff time before the match.
function Fixture({ m, club }: { m: PickMatch; club: string }) {
  const started = m.state !== 'not_started'
  const side = (c: string, cls: string) => <span className={c === club ? `${cls} is-own` : cls}>{c}</span>
  const label =
    `${m.home_club} ${started ? `${m.home_score ?? 0}, ${m.away_club} ${m.away_score ?? 0}` : `v ${m.away_club}`}` +
    (m.state === 'live' ? ', live' : '')
  return (
    <div className="details-fixture">
      <p className="details-scoreline" aria-label={label}>
        {side(m.home_club, 'details-club details-home')}
        <span className={m.state === 'live' ? 'details-score is-live' : started ? 'details-score' : 'details-score is-v'}>
          {started ? `${m.home_score ?? 0}–${m.away_score ?? 0}` : 'v'}
        </span>
        {side(m.away_club, 'details-club details-away')}
      </p>
      {m.state === 'live' && <p className="details-when">Live</p>}
      {!started && <p className="details-when">{kickoffText(m.kickoff)}</p>}
    </div>
  )
}

// The minutes are the first breakdown row, so only a match without one says
// why. In a double gameweek each match gets a subtotal.
function MatchBlock({ m, club, several }: { m: PickMatch; club: string; several: boolean }) {
  const didNotPlay = m.state !== 'not_started' && m.minutes === 0
  // An unstarted single match has nothing under its scoreline in the header.
  if (!several && !didNotPlay && m.stats.length === 0) return null
  return (
    <section className="details-match">
      {several && <Fixture m={m} club={club} />}
      {didNotPlay && <p className="details-minutes">Did not play</p>}
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
            {several && (
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

function Matches({ matches, club }: { matches: PickMatch[]; club: string }) {
  if (matches.length === 0) return <p className="details-minutes">No match this gameweek</p>
  return (
    <>
      {matches.map((m) => (
        <MatchBlock key={m.fixture_id} m={m} club={club} several={matches.length > 1} />
      ))}
    </>
  )
}

function DotDetails({ dot, dots }: { dot: PlotDot; dots: PlotDot[] }) {
  // A double-gameweek dot on one flank carries its own match; the other
  // match is on the linked dot, and the circle shows both: its scoreline
  // and points go in the footer.
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
      <Header name={dot.name} webName={dot.web_name} club={dot.club} role={dot.role} matches={dot.matches} />
      <Matches matches={dot.matches} club={dot.club} />
      <footer className="details-foot">
        {other.map((m) => (
          <Line key={m.fixture_id} label={scoreline(m)} value={signed(m.points)} />
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
      <Header
        name={player.name}
        webName={player.web_name}
        club={player.club}
        role={player.role}
        matches={player.matches}
      />
      <Matches matches={player.matches} club={player.club} />
      <footer className="details-foot">
        <Line label="Total" value={`${player.points} pts`} strong />
      </footer>
    </>
  )
}
