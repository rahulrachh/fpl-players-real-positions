// One gameweek graphic: team name, gameweek, the pitch and its legend.
// Kept self-contained so it can be exported as an image later (task 15).

import type { Plot, Role } from './api'
import Pitch from './Pitch'
import { type DepthMode, ROLE_LETTER } from './pitchLayout'

const DEPTH_NOTE: Record<DepthMode, string> = {
  true: 'Dashed lines: typical EPL depth by role.',
  stretch: 'Depth stretched for readability.',
  league: 'Height = how advanced compared with all EPL outfield players.',
}

const ROLE_NAMES: Record<Role, string> = {
  GK: 'Goalkeeper',
  DEF: 'Defender',
  MID: 'Midfielder',
  FWD: 'Forward',
}

const STATE_TEXT: Record<Plot['state'], { badge: string; note: string }> = {
  locked: { badge: 'Full time', note: 'Average positions in this gameweek, after auto-subs.' },
  preview: { badge: 'Preview', note: "Picked XI, each from his most recent match." },
}

function formatDate(iso: string) {
  // data_as_of is UTC without an offset.
  return new Date(`${iso}Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function PitchCard({ plot, depth = 'true' }: { plot: Plot; depth?: DepthMode }) {
  const state = STATE_TEXT[plot.state]
  const hasGhosts = plot.dots.some((d) => d.is_ghost)
  const hasLinks = plot.dots.some((d) => d.link_group !== null)
  return (
    <article className="pitch-card">
      <header className="card-head">
        <div className="card-team">
          <h2>{plot.team_name}</h2>
          <p>{plot.manager_name}</p>
        </div>
        <div className="card-gw">
          <div className="gw-line">
            <span className="gw-label">GW{plot.gw}</span>
            <span className={`state state-${plot.state}`}>{state.badge}</span>
          </div>
          <p className="score">
            <span className="score-number">{plot.points}</span>
            <span className="score-unit">pts</span>
          </p>
          {plot.transfers_cost > 0 && <p className="hit">−{plot.transfers_cost} transfer hit</p>}
        </div>
      </header>

      <Pitch
        dots={plot.dots}
        depth={depth}
        title={`${plot.team_name}, gameweek ${plot.gw}: real average positions`}
      />

      <footer className="card-foot">
        <ul className="legend">
          {(Object.keys(ROLE_NAMES) as Role[]).map((role) => (
            <li key={role}>
              <span className={`key role-${role}`}>{ROLE_LETTER[role]}</span>
              {ROLE_NAMES[role]}
            </li>
          ))}
          <li>
            <span className="key key-captain">C</span>
            Captain
          </li>
          {hasLinks && (
            <li>
              <span className="key key-link" />
              Double gameweek, both matches
            </li>
          )}
          {hasGhosts && (
            <li>
              <span className="key key-ghost" />
              No match, on the sideline
            </li>
          )}
        </ul>
        <p className="card-note">
          {state.note} Attacking upward. {DEPTH_NOTE[depth]}
          {plot.data_as_of && ` Positions as of ${formatDate(plot.data_as_of)}.`}
        </p>
      </footer>
    </article>
  )
}
