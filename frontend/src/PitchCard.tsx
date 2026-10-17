// One gameweek graphic: team name, gameweek, score and chip, the pitch, the
// bench and the legend.
// Kept self-contained so it can be exported as an image later (task 15).

import type { BenchPlayer, Plot, Role } from './api'
import Pitch from './Pitch'

const ROLE_NAMES: Record<Role, string> = {
  GK: 'Goalkeeper',
  DEF: 'Defender',
  MID: 'Midfielder',
  FWD: 'Forward',
}

const CHIP_NAMES: Record<string, string> = {
  bboost: 'Bench Boost',
  '3xc': 'Triple Captain',
  freehit: 'Free Hit',
  wildcard: 'Wildcard',
  manager: 'Assistant Manager',
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

// Empty under Bench Boost (everyone is on the pitch), so not shown then.
function Bench({ players }: { players: BenchPlayer[] }) {
  return (
    <section className="bench" aria-label="Bench">
      <h3>Bench</h3>
      <ol>
        {players.map((p) => (
          <li key={p.fpl_id} title={`${p.name} (${p.role}, ${p.club})`}>
            <span className={`bench-dot role-${p.role}`}>{p.points}</span>
            <span className="bench-name">{p.web_name}</span>
            {p.subbed_off && <span className="bench-note">did not play</span>}
          </li>
        ))}
      </ol>
    </section>
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
          {plot.chip && <span className={`chip chip-${plot.chip}`}>{CHIP_NAMES[plot.chip] ?? plot.chip}</span>}
        </div>
      </header>

      <Pitch
        dots={plot.dots}
        chip={plot.chip}
        title={`${plot.team_name}, gameweek ${plot.gw}: real average positions`}
      />

      {plot.bench.length > 0 && <Bench players={plot.bench} />}

      <footer className="card-foot">
        <ul className="legend">
          {(Object.keys(ROLE_NAMES) as Role[]).map((role) => (
            <li key={role}>
              <span className={`key role-${role}`} />
              {ROLE_NAMES[role]}
            </li>
          ))}
          <li>
            {plot.chip === '3xc' ? (
              <>
                <span className="key key-captain key-triple">TC</span>
                Triple captain
              </>
            ) : (
              <>
                <span className="key key-captain">C</span>
                Captain
              </>
            )}
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
          {state.note} Attacking upward. Height: how far forward compared with every Premier League outfield
          player. Circles show the points each player scored for the team (the captain's multiplied); bigger
          circle, more points within this team this gameweek.
          {plot.data_as_of && ` Positions as of ${formatDate(plot.data_as_of)}.`}
        </p>
      </footer>
    </article>
  )
}
