// One gameweek graphic: team name, gameweek, score and chip, the pitch, the
// legend and the bench.
// Kept self-contained: the image export (exportImage.ts) draws exactly this card.

import { useEffect, useRef } from 'react'

import type { BenchPlayer, Plot, Role } from './api'
import { stateText } from './cardText'
import { exportFilename } from './exportImage'
import { MatchDetailsBox } from './MatchDetails'
import Pitch from './Pitch'
import ShareButton from './ShareButton'
import { type DetailsTrigger, ROLE_NAMES, useMatchDetails } from './useMatchDetails'

const CHIP_NAMES: Record<string, string> = {
  bboost: 'Bench Boost',
  '3xc': 'Triple Captain',
  freehit: 'Free Hit',
  wildcard: 'Wildcard',
  manager: 'Assistant Manager',
}

// Gameweeks the arrows go to (null = disabled). Left out for a static card.
export type GwNav = { prev: number | null; next: number | null; go: (gw: number) => void }

// Marked so the image export leaves the arrows out.
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
function Bench({ players, details }: { players: BenchPlayer[]; details: DetailsTrigger }) {
  return (
    <section className="bench" aria-label="Bench">
      <h3>Bench</h3>
      <ol>
        {players.map((p) => (
          <li key={p.fpl_id}>
            <span
              className={`bench-card role-${p.role}`}
              {...details(
                `bench-${p.fpl_id}`,
                { kind: 'bench', player: p },
                `${p.name} (${p.role}, ${p.club}): ${p.points} pts. Match details`,
              )}
            >
              <span className="bench-name">{p.web_name}</span>
              <span className="bench-points">{p.points}</span>
            </span>
            {p.subbed_off && <span className="bench-note">did not play</span>}
          </li>
        ))}
      </ol>
    </section>
  )
}

export default function PitchCard({ plot, nav }: { plot: Plot; nav?: GwNav }) {
  const card = useRef<HTMLElement>(null)
  // Wraps the card exactly; the details box sits in it, outside the card, so
  // the image export never draws it.
  const frame = useRef<HTMLDivElement>(null)
  const details = useMatchDetails(frame)
  // Another gameweek or team: the open box belongs to the old one.
  const { close } = details
  useEffect(() => close(), [plot, close])
  const state = stateText(plot)
  // The score against the gameweek's average of all FPL teams, beside the score.
  const average = plot.summary?.average_score ?? null
  const avgDiff = average === null ? null : plot.points - average
  const hasGhosts = plot.dots.some((d) => d.is_ghost)
  const hasLinks = plot.dots.some((d) => d.link_group !== null)
  return (
    <div className="pitch-card-frame" ref={frame}>
      <article className="pitch-card" ref={card}>
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
              {avgDiff !== null && (
                <span
                  className={avgDiff >= 0 ? 'score-vs-avg is-up' : 'score-vs-avg is-down'}
                  title={`${average} gameweek average`}
                >
                  ({avgDiff > 0 ? '+' : avgDiff < 0 ? '−' : '±'}
                  {Math.abs(avgDiff)})
                  <span className="sr-only"> against the gameweek average</span>
                </span>
              )}
            </p>
            {plot.transfers_cost > 0 && <p className="hit">−{plot.transfers_cost} transfer hit</p>}
            {plot.chip && <span className={`chip chip-${plot.chip}`}>{CHIP_NAMES[plot.chip] ?? plot.chip}</span>}
          </div>
        </header>

        <div className="pitch-wrap">
          <Pitch
            dots={plot.dots}
            chip={plot.chip}
            title={`${plot.team_name}, gameweek ${plot.gw}: real average positions`}
            details={details.trigger}
          />
          <ShareButton
            card={card}
            filename={exportFilename(plot.team_id, plot.gw)}
            title={`${plot.team_name}, GW${plot.gw}: Real Shape`}
          />
        </div>

        {/* Between the pitch and the bench: right beside the fixtures panel,
            whose role dots it also explains. */}
        <div className="card-legend">
          <ul className="legend">
            {(Object.keys(ROLE_NAMES) as Role[]).map((role) => (
              <li key={role}>
                <span className={`key role-${role}`} />
                {ROLE_NAMES[role]}
              </li>
            ))}
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
        </div>

        {plot.bench.length > 0 && <Bench players={plot.bench} details={details.trigger} />}

      </article>
      {details.open && (
        <MatchDetailsBox open={details.open} frame={frame} dots={plot.dots} onClose={details.close} />
      )}
    </div>
  )
}
