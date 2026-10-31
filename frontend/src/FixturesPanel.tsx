// The gameweek's matches beside the pitch card (below it on a phone): one row
// per match with its score, each opening to the match's top 3 players by FPL
// points. The team's starters are highlighted, from the plot shown on the card
// (the fixtures endpoint is the same for every team). Not part of the
// exported image: it sits outside the card.

import { useEffect, useMemo, useState } from 'react'

import { ApiError, fetchGameweekFixtures, type FixtureSummary, type GameweekFixtures, type Plot } from './api'
import { ROLE_NAMES } from './useMatchDetails'

// Answers kept for the page's lifetime, by gameweek (the arrows go back and forth).
const loaded = new Map<number, GameweekFixtures>()

type State = { gw: number } & ({ data: GameweekFixtures } | { error: string })

function kickoffText(iso: string | null) {
  if (!iso) return 'TBC'
  return new Date(iso).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit' })
}

function MatchRow({ fixture, starters }: { fixture: FixtureSummary; starters: Set<number> }) {
  const [open, setOpen] = useState(false)
  const started = fixture.state !== 'not_started'
  const home = fixture.home_club.short_name
  const away = fixture.away_club.short_name
  const yours = fixture.top_players.filter((p) => starters.has(p.id)).length
  const listId = `fx-top-${fixture.id}`
  const centre = started ? `${fixture.home_score ?? 0} – ${fixture.away_score ?? 0}` : kickoffText(fixture.kickoff)
  const label =
    `${fixture.home_club.name} ${started ? `${fixture.home_score ?? 0}, ${fixture.away_club.name} ${fixture.away_score ?? 0}` : `v ${fixture.away_club.name}, ${centre}`}` +
    (fixture.state === 'live' ? ', live' : '') +
    (yours ? `, ${yours === 1 ? 'one of your starters' : `${yours} of your starters`} in the top 3` : '')

  return (
    <li className={open ? 'fx is-open' : 'fx'}>
      <button
        type="button"
        className="fx-row"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="fx-club fx-home">{home}</span>
        <span className={started ? 'fx-score' : 'fx-score fx-kickoff'}>{centre}</span>
        <span className="fx-club fx-away">{away}</span>
        <span className="fx-tags">
          {fixture.state === 'live' && <span className="fx-live">Live</span>}
          {yours > 0 && (
            <span className="fx-yours" title="One of your starters is in this match's top 3">
              Your XI
            </span>
          )}
        </span>
        <svg className="fx-chevron" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div id={listId} className="fx-detail">
          {!started ? (
            <p className="fx-empty">Not played yet</p>
          ) : fixture.top_players.length === 0 ? (
            <p className="fx-empty">No points yet</p>
          ) : (
            <ol className="fx-top" aria-label={`Top players, ${home} v ${away}`}>
              {fixture.top_players.map((p) => {
                const mine = starters.has(p.id)
                return (
                  <li key={p.id} className={mine ? `fx-player is-yours role-${p.role}` : 'fx-player'}>
                    <span className={`fx-role role-${p.role}`} title={ROLE_NAMES[p.role]} aria-hidden="true" />
                    <span className="fx-name">
                      {p.web_name}
                      {mine && <span className="sr-only"> (your team)</span>}
                    </span>
                    <span className="fx-pclub">{p.club}</span>
                    <span className="fx-points">
                      {p.points}
                      <span className="sr-only"> points</span>
                    </span>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      )}
    </li>
  )
}

export default function FixturesPanel({ plot }: { plot: Plot }) {
  const gw = plot.gw
  const [state, setState] = useState<State | null>(null)
  const [attempt, setAttempt] = useState(0)
  // The team's starters: the XI drawn on the pitch, not Bench Boost's bench.
  const starters = useMemo(() => new Set(plot.dots.filter((d) => !d.from_bench).map((d) => d.fpl_id)), [plot])

  useEffect(() => {
    if (loaded.has(gw)) return
    let cancelled = false
    fetchGameweekFixtures(gw)
      .then((data) => {
        // Unfinished gameweeks change: only a checked one is kept.
        if (data.data_checked) loaded.set(gw, data)
        if (!cancelled) setState({ gw, data })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const busy = err instanceof ApiError && err.code === 'fpl_unavailable'
        setState({ gw, error: busy ? "FPL isn't responding right now." : "Couldn't load the matches." })
      })
    return () => {
      cancelled = true
    }
  }, [gw, attempt])

  const cached = loaded.get(gw)
  const current: State | null = cached ? { gw, data: cached } : state && state.gw === gw ? state : null
  // The previous gameweek's matches stay (dimmed) while the next one loads.
  const shown = current && 'data' in current ? current.data : state && 'data' in state ? state.data : null
  const loading = current === null

  return (
    <section className="fixtures-panel" aria-labelledby="fixtures-title" aria-busy={loading}>
      <h3 id="fixtures-title">GW{gw} matches</h3>
      <p className="fx-note">Tap a match for its top 3 players by FPL points.</p>
      {current && 'error' in current ? (
        <div className="fx-error" role="alert">
          <p>{current.error}</p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </button>
        </div>
      ) : shown ? (
        <ul className={loading ? 'fx-list is-loading' : 'fx-list'}>
          {shown.fixtures.map((f) => (
            // Keyed by gameweek too, so every row starts collapsed in a new gameweek.
            <MatchRow key={`${shown.gw}-${f.id}`} fixture={f} starters={starters} />
          ))}
        </ul>
      ) : (
        <p className="fx-empty">Loading matches…</p>
      )}
      {shown && !loading && shown.fixtures.length === 0 && <p className="fx-empty">No matches this gameweek.</p>}
    </section>
  )
}
