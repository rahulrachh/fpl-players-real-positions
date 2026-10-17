// Interim list view of a team's gameweek (until the pitch view, tasks 13-14).
// Team and gameweek are kept in the URL: ?team=2020649&gw=6.

import { type FormEvent, useEffect, useState } from 'react'

import {
  ApiError,
  fetchLatestGameweeks,
  fetchTeamGameweek,
  type Role,
  type TeamGameweek,
  type TeamPick,
} from './api'

const ROLES: Role[] = ['GK', 'DEF', 'MID', 'FWD']
const ROLE_NAMES: Record<Role, string> = {
  GK: 'Goalkeeper',
  DEF: 'Defenders',
  MID: 'Midfielders',
  FWD: 'Forwards',
}
const CHIP_NAMES: Record<string, string> = {
  bboost: 'Bench Boost',
  '3xc': 'Triple Captain',
  freehit: 'Free Hit',
  wildcard: 'Wildcard',
  manager: 'Assistant Manager',
}
const ERROR_MESSAGES: Record<string, string> = {
  team_not_found: 'No FPL team has this ID.',
  gameweek_before_team_started: 'This team had not joined yet in this gameweek.',
  gameweek_not_started: "This gameweek's deadline has not passed yet, so its picks are private.",
  gameweek_out_of_range: 'This gameweek is not in the season.',
  fpl_unavailable: 'FPL is unavailable, try again shortly.',
}

// The answer to one request, keyed by "team/gw": while the key differs from
// the current team and gameweek, that request is still loading.
type Result = { key: string } & ({ team: TeamGameweek } | { error: string })

function readUrl(): { team: number | null; gw: number | null } {
  const params = new URLSearchParams(window.location.search)
  const num = (key: string) => {
    const value = Number(params.get(key))
    return Number.isInteger(value) && value > 0 ? value : null
  }
  return { team: num('team'), gw: num('gw') }
}

function writeUrl(team: number, gw: number) {
  const url = new URL(window.location.href)
  url.searchParams.set('team', String(team))
  url.searchParams.set('gw', String(gw))
  window.history.replaceState(null, '', url)
}

const money = (tenths: number) => `£${(tenths / 10).toFixed(1)}m`

export default function TeamList() {
  const initial = readUrl()
  const [input, setInput] = useState(initial.team ? String(initial.team) : '')
  const [teamId, setTeamId] = useState<number | null>(initial.team)
  const [gw, setGw] = useState<number | null>(initial.gw)
  const [latest, setLatest] = useState<number | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [inputError, setInputError] = useState<string | null>(null)
  const key = teamId !== null && gw !== null ? `${teamId}/${gw}` : null
  const current = result !== null && result.key === key ? result : null

  useEffect(() => {
    fetchLatestGameweeks()
      .then(({ latest }) => {
        setLatest(latest)
        setGw((current) => current ?? latest)
      })
      .catch(() => setLatest(null))
  }, [])

  useEffect(() => {
    if (teamId === null || gw === null) return
    const requestKey = `${teamId}/${gw}`
    let cancelled = false
    writeUrl(teamId, gw)
    fetchTeamGameweek(teamId, gw)
      .then((team) => !cancelled && setResult({ key: requestKey, team }))
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
    <section>
      <form className="team-form" onSubmit={submit}>
        <label htmlFor="team-id">FPL team ID</label>
        <input
          id="team-id"
          inputMode="numeric"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. 2020649"
        />
        <button type="submit">Load</button>
      </form>

      {teamId !== null && gw !== null && (
        <nav className="gw-nav" aria-label="Gameweek">
          <button type="button" onClick={() => setGw(gw - 1)} disabled={gw <= 1}>
            ← GW{gw - 1}
          </button>
          <strong>Gameweek {gw}</strong>
          <button
            type="button"
            onClick={() => setGw(gw + 1)}
            disabled={latest !== null && gw >= latest}
          >
            GW{gw + 1} →
          </button>
        </nav>
      )}

      {inputError && <p className="error">{inputError}</p>}
      {key !== null && current === null && <p className="muted">Loading…</p>}
      {current && 'error' in current && <p className="error">{current.error}</p>}
      {current && 'team' in current && <TeamDetails team={current.team} />}
    </section>
  )
}

function TeamDetails({ team }: { team: TeamGameweek }) {
  const starters = team.picks.filter((p) => p.starter)
  const bench = team.picks.filter((p) => !p.starter)
  const formation = ROLES.slice(1)
    .map((role) => starters.filter((p) => p.role === role).length)
    .join('-')
  const names = new Map(team.picks.map((p) => [p.player.id, p.player.web_name]))

  return (
    <>
      <header className="team-header">
        <h2>{team.team_name}</h2>
        <p className="muted">{team.manager_name}</p>
        <dl className="facts">
          <div>
            <dt>Status</dt>
            <dd>
              {team.status === 'in_progress' ? 'In progress' : 'Finished'}
              {team.status === 'finished' && !team.data_checked && ' (points provisional)'}
            </dd>
          </div>
          <div>
            <dt>Formation</dt>
            <dd>{formation}</dd>
          </div>
          <div>
            <dt>Chip</dt>
            <dd>{team.chip ? (CHIP_NAMES[team.chip] ?? team.chip) : 'None'}</dd>
          </div>
          <div>
            <dt>Bank</dt>
            <dd>{money(team.bank)}</dd>
          </div>
          <div>
            <dt>Squad value</dt>
            <dd>{money(team.squad_value)}</dd>
          </div>
        </dl>
        {team.automatic_subs.length > 0 && (
          <p className="subs">
            Auto-subs:{' '}
            {team.automatic_subs
              .map((s) => `${names.get(s.player_in)} on for ${names.get(s.player_out)}`)
              .join(', ')}
          </p>
        )}
        {team.effective_captain_id !== null && team.effective_captain_id !== team.captain_id && (
          <p className="subs">
            Captain did not play: {names.get(team.effective_captain_id)} (vice) took the armband.
          </p>
        )}
      </header>

      <h3>Starting XI</h3>
      {ROLES.map((role) => {
        const group = starters.filter((p) => p.role === role)
        return (
          group.length > 0 && (
            <div key={role}>
              <h4>{ROLE_NAMES[role]}</h4>
              <PickList picks={group} />
            </div>
          )
        )
      })}

      <h3>Bench</h3>
      <PickList picks={bench} />
    </>
  )
}

function PickList({ picks }: { picks: TeamPick[] }) {
  return (
    <ul className="picks">
      {picks.map((p) => (
        <li key={p.player.id}>
          <span className="role">{p.role}</span>
          <span className="name" title={`${p.player.first_name} ${p.player.second_name}`}>
            {p.player.web_name}
          </span>
          <span className="club">{p.player.club.short_name}</span>
          <span className="badges">
            {p.is_captain && <Badge kind="captain">{p.multiplier === 3 ? 'TC' : 'C'}</Badge>}
            {p.is_vice_captain && <Badge kind="vice">V</Badge>}
            {p.auto_sub === 'in' && <Badge kind="sub-in">Sub on</Badge>}
            {p.auto_sub === 'out' && <Badge kind="sub-out">Subbed off</Badge>}
            {p.multiplier > 1 && <span className="mult">×{p.multiplier}</span>}
          </span>
        </li>
      ))}
    </ul>
  )
}

function Badge({ kind, children }: { kind: string; children: string }) {
  return <span className={`badge badge-${kind}`}>{children}</span>
}
