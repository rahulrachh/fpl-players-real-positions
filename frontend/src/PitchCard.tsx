// One gameweek graphic: team name, gameweek, the pitch and its legend.
// Kept self-contained so it can be exported as an image later (task 15).

import type { Plot, Role } from './api'
import Pitch from './Pitch'
import { ROLE_LETTER } from './pitchLayout'

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

// Gameweeks the arrows go to (null = disabled). Left out for a static card.
export type GwNav = { prev: number | null; next: number | null; go: (gw: number) => void }

// Marked so the image export (task 15) leaves the arrows out.
function GwArrow({ direction, nav }: { direction: 'prev' | 'next'; nav: GwNav }) {
  const gw = direction === 'prev' ? nav.prev : nav.next
  const label = direction === 'prev' ? 'Previous gameweek' : 'Next gameweek'
  return (
    <button
      type="button"
      className="gw-arrow"
      data-export-ignore
      disabled={gw === null}
      onClick={() => gw !== null && nav.go(gw)}
      aria-label={gw === null ? label : `${label} (GW${gw})`}
      title={gw === null ? label : `GW${gw}`}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d={direction === 'prev' ? 'M15 5 8 12l7 7' : 'M9 5l7 7-7 7'} />
      </svg>
    </button>
  )
}

export default function PitchCard({ plot, nav }: { plot: Plot; nav?: GwNav }) {
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
          {nav && <GwArrow direction="prev" nav={nav} />}
          <div className="gw-center">
            <span className="gw-label">GW{plot.gw}</span>
            <span className={`state state-${plot.state}`}>{state.badge}</span>
          </div>
          {nav && <GwArrow direction="next" nav={nav} />}
        </div>
        <div className="card-score">
          <p className="score">
            <span className="score-number">{plot.points}</span>
            <span className="score-unit">pts</span>
          </p>
          {plot.transfers_cost > 0 && <p className="hit">−{plot.transfers_cost} transfer hit</p>}
        </div>
      </header>

      <Pitch
        dots={plot.dots}
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
          {state.note} Attacking upward. Height: how far forward compared with every Premier League outfield player.
          {plot.data_as_of && ` Positions as of ${formatDate(plot.data_as_of)}.`}
        </p>
      </footer>
    </article>
  )
}
