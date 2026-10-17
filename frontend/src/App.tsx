// Team ID → the latest (or ?gw=) gameweek graphic. Team and gameweek are kept in
// the URL: ?team=2020649&gw=6; the last team loaded is remembered in this
// browser and opens next time. The arrows either side of "GW6" in the card
// header (and the arrow keys) step through the team's gameweeks (the plot API
// says which exist).

import { type FormEvent, useEffect, useState } from 'react'

import { ApiError, fetchPlot, type Plot } from './api'
import PitchCard from './PitchCard'
import ThemeToggle from './ThemeToggle'

const GW_ERRORS: Record<string, (gw: string) => string> = {
  gameweek_before_team_started: (gw) => `This team hadn't joined FPL yet in ${gw}.`,
  gameweek_not_started: (gw) => `${gw} hasn't started yet: picks stay private until the deadline.`,
  gameweek_out_of_range: (gw) => `${gw} isn't in this season.`,
}

// What went wrong with one request, and what the page offers next.
type Failure = { code: string | null; message: string; action: 'retry' | 'latest' | null }

function describeFailure(err: unknown, teamId: number, gw: number | null): Failure {
  const code = err instanceof ApiError ? err.code : null
  const label = gw === null ? 'The latest gameweek' : `GW${gw}`
  if (code === 'team_not_found') {
    return {
      code,
      message: `No FPL team has the ID ${teamId}. Your ID is the number in the address of your Points page on the FPL site.`,
      action: null,
    }
  }
  if (code && GW_ERRORS[code]) return { code, message: GW_ERRORS[code](label), action: 'latest' }
  if (code === 'fpl_unavailable') {
    return { code, message: "FPL isn't responding right now. It's often busy around deadlines.", action: 'retry' }
  }
  return { code, message: "Couldn't reach the Real Shape server.", action: 'retry' }
}

// The answer to one request, keyed by "team/gw": while the key differs from
// the current team and gameweek, that request is still loading.
type Result = { key: string } & ({ plot: Plot } | { failure: Failure })

// The last team that loaded, so the page opens on it next time. Storage can be
// unavailable (private windows, blocked site data): then nothing is remembered.
const STORED_TEAM = 'realshape.team'

function readStoredTeam(): number | null {
  try {
    const value = Number(window.localStorage.getItem(STORED_TEAM))
    return Number.isInteger(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

function storeTeam(team: number | null) {
  try {
    if (team === null) window.localStorage.removeItem(STORED_TEAM)
    else window.localStorage.setItem(STORED_TEAM, String(team))
  } catch {
    // Not remembered; the page still works.
  }
}

function readUrl() {
  const params = new URLSearchParams(window.location.search)
  const num = (key: string) => {
    const value = Number(params.get(key))
    return Number.isInteger(value) && value > 0 ? value : null
  }
  const team = num('team')
  // A gameweek in the URL only makes sense with its team.
  return { team: team ?? readStoredTeam(), gw: team ? num('gw') : null, fixture: params.get('fixture') }
}

function writeUrl(team: number, gw: number) {
  const url = new URL(window.location.href)
  url.searchParams.set('team', String(team))
  url.searchParams.set('gw', String(gw))
  window.history.replaceState(null, '', url)
}

function App() {
  const initial = readUrl()
  const [input, setInput] = useState(initial.team ? String(initial.team) : '')
  const [teamId, setTeamId] = useState<number | null>(initial.team)
  const [gw, setGw] = useState<number | null>(initial.gw)
  const [result, setResult] = useState<Result | null>(null)
  // Bumped by "Try again" to repeat the same request.
  const [attempt, setAttempt] = useState(0)
  // The last graphic loaded for this team: stays on screen (dimmed) while the
  // next gameweek loads, and gives the prev / next gameweeks.
  const [shown, setShown] = useState<Plot | null>(null)
  const [inputError, setInputError] = useState<string | null>(null)
  const [fixture, setFixture] = useState<Plot | null>(null)
  const key = teamId !== null ? `${teamId}/${gw ?? 'latest'}` : null
  const current = result !== null && result.key === key ? result : null
  const loading = key !== null && current === null
  const failure = current !== null && 'failure' in current ? current.failure : null
  const failed = failure !== null
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
    if (import.meta.env.DEV && (initial.fixture === 'edges' || initial.fixture === 'bboost')) {
      import('./fixtures/edgeCases').then((m) =>
        setFixture(initial.fixture === 'bboost' ? m.benchBoost : m.edgeCases),
      )
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
        storeTeam(teamId)
        setResult({ key: requestKey, plot })
        setShown(plot)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const failure = describeFailure(err, teamId, gw)
        // Don't reopen on a team that doesn't exist.
        if (failure.code === 'team_not_found' && readStoredTeam() === teamId) storeTeam(null)
        setResult({ key: requestKey, failure })
      })
    return () => {
      cancelled = true
    }
  }, [teamId, gw, attempt])

  function submit(event: FormEvent) {
    event.preventDefault()
    const id = Number(input.trim())
    const valid = Number.isInteger(id) && id > 0
    setInputError(valid ? null : 'A team ID is a positive number.')
    if (!valid) return
    // Opens on the team's latest gameweek; the same team again reloads it.
    setTeamId(id)
    setGw(null)
    setAttempt((n) => n + 1)
  }

  return (
    <main>
      <header className="site-head">
        <div>
          <h1>Real Shape</h1>
          <p>Where your FPL team actually played.</p>
        </div>
        <ThemeToggle />
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
      {!fixture && teamId === null && (
        <section className="notice">
          <h2>See where your team really played</h2>
          <p>
            Enter your FPL team ID to plot your players where they actually played, gameweek by gameweek. It's the
            number in the address of your Points page on the FPL site, for example
            fantasy.premierleague.com/entry/<strong>2020649</strong>/event/6.
          </p>
        </section>
      )}
      {!fixture && failure && (
        <section className="notice notice-error" role="alert">
          <p>{failure.message}</p>
          {failure.action === 'retry' && (
            <button type="button" onClick={() => setAttempt((n) => n + 1)}>
              Try again
            </button>
          )}
          {failure.action === 'latest' && gw !== null && (
            <button type="button" onClick={() => setGw(null)}>
              Show the latest gameweek
            </button>
          )}
        </section>
      )}
      {!plot && loading && (
        <div className="card-placeholder" aria-busy="true">
          <p>Loading {gw === null ? 'the latest gameweek' : `GW${gw}`}…</p>
        </div>
      )}
      {plot && (
        <div className={loading && !fixture ? 'card-slot is-loading' : 'card-slot'} aria-busy={loading && !fixture}>
          <PitchCard
            plot={plot}
            nav={fixture ? undefined : { prev: prevGw, next: nextGw, go: setGw }}
          />
        </div>
      )}

    </main>
  )
}

export default App
