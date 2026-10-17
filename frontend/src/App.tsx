// Team ID → the latest (or ?gw=) gameweek graphic. Team and gameweek are kept in
// the URL: ?team=2020649&gw=6. Navigation between gameweeks comes in task 14.

import { type FormEvent, useEffect, useState } from 'react'

import { ApiError, fetchPlot, type Plot } from './api'
import PitchCard from './PitchCard'

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
  return { team: num('team'), gw: num('gw'), fixture: params.get('fixture') }
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
  const [gw] = useState<number | null>(initial.gw)
  const [result, setResult] = useState<Result | null>(null)
  const [inputError, setInputError] = useState<string | null>(null)
  const [fixture, setFixture] = useState<Plot | null>(null)
  const key = teamId !== null ? `${teamId}/${gw ?? 'latest'}` : null
  const current = result !== null && result.key === key ? result : null

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
    if (valid) setTeamId(id)
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
      {fixture && <PitchCard plot={fixture} />}
      {!fixture && key !== null && current === null && <p className="muted">Loading…</p>}
      {!fixture && current && 'error' in current && <p className="error">{current.error}</p>}
      {!fixture && current && 'plot' in current && <PitchCard plot={current.plot} />}
    </main>
  )
}

export default App
