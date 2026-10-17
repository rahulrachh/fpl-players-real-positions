// Team ID → the latest (or ?gw=) gameweek graphic. Team and gameweek are kept in
// the URL: ?team=2020649&gw=6. The arrows under the team ID box (and the arrow
// keys) step through the team's gameweeks (the plot API says which exist).

import { type FormEvent, useEffect, useState } from 'react'

import { ApiError, fetchPlot, type Plot } from './api'
import PitchCard from './PitchCard'
import type { DepthMode } from './pitchLayout'

const ERROR_MESSAGES: Record<string, string> = {
  team_not_found: 'No FPL team has this ID.',
  gameweek_before_team_started: 'This team had not joined yet in this gameweek.',
  gameweek_not_started: "This gameweek's deadline has not passed yet, so its picks are private.",
  gameweek_out_of_range: 'This gameweek is not in the season.',
  fpl_unavailable: 'FPL is unavailable, try again shortly.',
}

// The answer to one request, keyed by "team/gw": while the key differs from
// the current team and gameweek, that request is still loading.
type Result = { key: string } & ({ plot: Plot } | { error: string })

function readUrl() {
  const params = new URLSearchParams(window.location.search)
  const num = (key: string) => {
    const value = Number(params.get(key))
    return Number.isInteger(value) && value > 0 ? value : null
  }
  const depth = params.get('depth')
  return {
    team: num('team'),
    gw: num('gw'),
    fixture: params.get('fixture'),
    depth: (depth === 'role' ? 'role' : 'all') as DepthMode,
  }
}

function writeUrl(team: number, gw: number) {
  const url = new URL(window.location.href)
  url.searchParams.set('team', String(team))
  url.searchParams.set('gw', String(gw))
  window.history.replaceState(null, '', url)
}

const DEPTH_VIEWS: { mode: DepthMode; label: string; hint: string }[] = [
  { mode: 'all', label: 'All outfield players', hint: 'Height: how far forward compared with every outfield player' },
  { mode: 'role', label: 'Same position', hint: 'Height: how far forward compared with players in the same FPL position' },
]

function writeDepth(depth: DepthMode) {
  const url = new URL(window.location.href)
  if (depth === 'all') url.searchParams.delete('depth')
  else url.searchParams.set('depth', depth)
  window.history.replaceState(null, '', url)
}

function App() {
  const initial = readUrl()
  const [input, setInput] = useState(initial.team ? String(initial.team) : '')
  const [teamId, setTeamId] = useState<number | null>(initial.team)
  const [gw, setGw] = useState<number | null>(initial.gw)
  const [depth, setDepth] = useState<DepthMode>(initial.depth)
  const [result, setResult] = useState<Result | null>(null)
  // The last graphic loaded for this team: stays on screen (dimmed) while the
  // next gameweek loads, and gives the prev / next gameweeks.
  const [shown, setShown] = useState<Plot | null>(null)
  const [inputError, setInputError] = useState<string | null>(null)
  const [fixture, setFixture] = useState<Plot | null>(null)
  const key = teamId !== null ? `${teamId}/${gw ?? 'latest'}` : null
  const current = result !== null && result.key === key ? result : null
  const loading = key !== null && current === null
  const failed = current !== null && 'error' in current
  const plot = fixture ?? (shown && shown.team_id === teamId && !failed ? shown : null)
  const prevGw = plot && !fixture && !loading ? plot.prev_gw : null
  const nextGw = plot && !fixture && !loading ? plot.next_gw : null

  // Left / right arrow keys step gameweeks too (not while typing a team ID).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.altKey || event.ctrlKey || event.metaKey) return
      if (event.key === 'ArrowLeft' && prevGw !== null) setGw(prevGw)
      if (event.key === 'ArrowRight' && nextGw !== null) setGw(nextGw)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [prevGw, nextGw])

  useEffect(() => {
    if (import.meta.env.DEV && initial.fixture === 'edges') {
      import('./fixtures/edgeCases').then((m) => setFixture(m.edgeCases))
    }
  }, [initial.fixture])

  useEffect(() => {
    if (teamId === null) return
    const requestKey = `${teamId}/${gw ?? 'latest'}`
    let cancelled = false
    fetchPlot(teamId, gw ?? 'latest')
      .then((plot) => {
        if (cancelled) return
        writeUrl(teamId, plot.gw)
        setResult({ key: requestKey, plot })
        setShown(plot)
      })
      .catch((err: Error) => {
        if (cancelled) return
        const code = err instanceof ApiError ? err.code : null
        setResult({ key: requestKey, error: (code && ERROR_MESSAGES[code]) || err.message })
      })
    return () => {
      cancelled = true
    }
  }, [teamId, gw])

  function submit(event: FormEvent) {
    event.preventDefault()
    const id = Number(input.trim())
    const valid = Number.isInteger(id) && id > 0
    setInputError(valid ? null : 'A team ID is a positive number.')
    if (valid && id !== teamId) {
      setTeamId(id)
      // A new team opens on its latest gameweek.
      setGw(null)
    }
  }

  return (
    <main>
      <header className="site-head">
        <h1>Real Shape</h1>
        <p>Where your FPL team actually played.</p>
      </header>

      <form className="team-form" onSubmit={submit}>
        <label htmlFor="team-id">FPL team ID</label>
        <input
          id="team-id"
          inputMode="numeric"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. 2020649"
        />
        <button type="submit">Show shape</button>
      </form>

      {inputError && <p className="error">{inputError}</p>}
      {plot && !fixture && (
        <nav className="gw-nav" aria-label="Gameweek">
          <GwArrow direction="prev" gw={prevGw} onGo={setGw} />
          <span className="gw-nav-current">Gameweek {loading && gw !== null ? gw : plot.gw}</span>
          <GwArrow direction="next" gw={nextGw} onGo={setGw} />
        </nav>
      )}
      {plot && (
        <div className="view-switch" role="group" aria-label="Depth view">
          {DEPTH_VIEWS.map((v) => (
            <button
              key={v.mode}
              type="button"
              title={v.hint}
              aria-pressed={depth === v.mode}
              onClick={() => {
                setDepth(v.mode)
                writeDepth(v.mode)
              }}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}
      {!fixture && current && 'error' in current && <p className="error">{current.error}</p>}
      {!plot && loading && <p className="muted">Loading…</p>}
      {plot && (
        <div className={loading && !fixture ? 'card-slot is-loading' : 'card-slot'} aria-busy={loading && !fixture}>
          <PitchCard plot={plot} depth={depth} />
        </div>
      )}
    </main>
  )
}

function GwArrow({
  direction,
  gw,
  onGo,
}: {
  direction: 'prev' | 'next'
  gw: number | null
  onGo: (gw: number) => void
}) {
  const label = direction === 'prev' ? 'Previous gameweek' : 'Next gameweek'
  return (
    <button
      type="button"
      className="gw-arrow"
      disabled={gw === null}
      onClick={() => gw !== null && onGo(gw)}
      aria-label={gw === null ? label : `${label} (GW${gw})`}
      title={gw === null ? label : `GW${gw}`}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d={direction === 'prev' ? 'M15 5 8 12l7 7' : 'M9 5l7 7-7 7'} />
      </svg>
    </button>
  )
}

export default App
