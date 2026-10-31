// The team's gameweek in numbers (score against the average, ranks, captain,
// most captained, player of the week, transfers, money, bench) and a strip of
// its points in every gameweek of the season, ten at a time; a bar opens that
// gameweek. On wide screens the summary sits beside the matches (as tall as
// them) and the strip runs under both; on a phone both follow the matches.
// Not part of the exported image.

import { type ReactNode, useState } from 'react'

import type { GameweekSummary, Plot } from './api'

const CHIP_SHORT: Record<string, string> = {
  bboost: 'BB',
  '3xc': 'TC',
  freehit: 'FH',
  wildcard: 'WC',
  manager: 'AM',
}

const number = (n: number | null) => (n === null ? '—' : n.toLocaleString('en-GB'))
const money = (tenths: number) => `£${(tenths / 10).toFixed(1)}m`

// Overall rank change since the team's previous gameweek (lower is better).
function Movement({ now, before }: { now: number | null; before: number | null }) {
  if (now === null || before === null || now === before) return null
  const up = now < before
  const diff = Math.abs(before - now).toLocaleString('en-GB')
  return (
    <span className={up ? 'sm-move is-up' : 'sm-move is-down'} title={`${up ? 'Up' : 'Down'} ${diff} places`}>
      <span aria-hidden="true">{up ? '▲' : '▼'}</span>
      <span className="sr-only">{up ? 'up' : 'down'}</span> {diff}
    </span>
  )
}

// Gameweeks shown at once in the season strip; the arrows page through the rest.
const WINDOW = 10

// The season strip, under the summary: a window of gameweeks with ‹ › to page
// through the whole season. It opens on the window holding the gameweek shown
// (near its right end, so earlier weeks are in view). Played gameweeks are bars
// you can click to open; unplayed ones (before the team joined, or still to
// come) are 0, a baseline only, and not clickable. Bar heights use the whole
// season's best score, so paging does not rescale them.
function SeasonStrip({
  summary,
  gw,
  go,
}: {
  summary: GameweekSummary
  gw: number
  go?: (gw: number) => void
}) {
  const season = summary.season
  const lastStart = Math.max(0, season.length - WINDOW)
  const [start, setStart] = useState(() => Math.min(lastStart, Math.max(0, gw - (WINDOW - 2))))
  const shown = season.slice(start, start + WINDOW)
  const max = Math.max(1, ...season.map((g) => g.points))
  const first = shown[0]?.gw
  const last = shown[shown.length - 1]?.gw
  return (
    <section className="season-strip" aria-labelledby="season-title">
      <div className="ss-head">
        <h3 id="season-title">Season</h3>
        {season.length > WINDOW && (
          <div className="ss-nav">
            <button
              type="button"
              className="ss-arrow"
              disabled={start === 0}
              onClick={() => setStart((n) => Math.max(0, n - WINDOW))}
              aria-label="Earlier gameweeks"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M15 5 8 12l7 7" />
              </svg>
            </button>
            <span className="ss-range" aria-live="polite">
              GW{first}–{last}
            </span>
            <button
              type="button"
              className="ss-arrow"
              disabled={start >= lastStart}
              onClick={() => setStart((n) => Math.min(lastStart, n + WINDOW))}
              aria-label="Later gameweeks"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <ol className="ss-bars">
        {shown.map((g) => {
          const chip = g.chip ? (CHIP_SHORT[g.chip] ?? g.chip) : null
          const current = g.gw === gw
          const label = g.played ? `GW${g.gw}: ${g.points} points${chip ? `, ${chip}` : ''}` : `GW${g.gw}: not played`
          const bar = (
            <>
              <span className="ss-points">{g.played ? g.points : ''}</span>
              <span
                className={g.played ? 'ss-bar' : 'ss-bar ss-empty'}
                style={g.played ? { height: `${Math.max(3, (g.points / max) * 100)}%` } : undefined}
              />
              <span className="ss-gw">{g.gw}</span>
              <span className="ss-chip">{chip}</span>
            </>
          )
          const classes = [current && 'is-current', !g.played && 'is-unplayed']
          return (
            <li key={g.gw} className={classes.filter(Boolean).join(' ') || undefined}>
              {go && g.played && !current ? (
                <button type="button" className="ss-col" onClick={() => go(g.gw)} aria-label={label} title={label}>
                  {bar}
                </button>
              ) : (
                <span className="ss-col" aria-label={label} aria-current={current ? 'true' : undefined} title={label}>
                  {bar}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

// A small "✓" after a name: the team did the same / has the player.
function Tick({ title }: { title: string }) {
  return (
    <span className="sm-tick" title={title}>
      <span aria-hidden="true">✓</span>
      <span className="sr-only"> ({title.toLowerCase()})</span>
    </span>
  )
}

const pct = (p: number | null) => (p === null ? null : `(top ${p < 10 ? p.toFixed(1) : Math.round(p)}%)`)

export default function SummaryPanel({ plot, go }: { plot: Plot; go?: (gw: number) => void }) {
  const summary = plot.summary
  if (!summary) return null
  const gw = plot.gw
  const captain = plot.dots.find((d) => d.is_captain) ?? null
  const xi = new Set(plot.dots.map((d) => d.fpl_id))
  const bench = new Set(plot.bench.map((b) => b.fpl_id))
  const top = summary.top_player
  const rows: [string, ReactNode][] = [
    ['Average', number(summary.average_score)],
    ['Highest', number(summary.highest_score)],
    [
      'GW rank',
      <>
        {number(summary.gw_rank)}
        {pct(summary.gw_rank_pct) && <span className="sm-pct"> {pct(summary.gw_rank_pct)}</span>}
      </>,
    ],
    [
      'Overall rank',
      // Two by two: rank | (top x%), then the movement under the rank.
      <span key="overall" className="sm-quad">
        <span className="sm-quad-rank">{number(summary.overall_rank)}</span>
        <span className="sm-pct">{pct(summary.overall_rank_pct)}</span>
        <span className="sm-quad-move">
          <Movement now={summary.overall_rank} before={summary.previous_overall_rank} />
        </span>
      </span>,
    ],
    ['Your captain', captain ? captain.web_name : '—'],
    [
      'Most captained',
      summary.most_captained ? (
        <>
          {summary.most_captained.web_name}
          {captain?.fpl_id === summary.most_captained.id && <Tick title="Your captain too" />}
        </>
      ) : (
        '—'
      ),
    ],
    [
      'Player of the week',
      top ? (
        <>
          <span className="sm-nowrap">
            {top.web_name} ({top.points})
          </span>
          {xi.has(top.id) && <Tick title="In your team" />}
          {bench.has(top.id) && <span className="sm-pct">your bench</span>}
        </>
      ) : (
        '—'
      ),
    ],
    ['Total points', number(summary.total_points)],
    [
      'Transfers',
      <>
        {summary.transfers}
        {summary.transfers_cost > 0 && <span className="sm-hit"> (−{summary.transfers_cost})</span>}
      </>,
    ],
    ['Bench points', summary.points_on_bench],
    ['Bank', money(summary.bank)],
    ['Squad value', money(summary.squad_value)],
  ]
  return (
    <>
      <section className="summary-panel" aria-labelledby="summary-title">
        <h3 id="summary-title">GW{gw} in numbers</h3>
        <dl>
          {rows.map(([label, value]) => (
            <div key={label} className="sm-row">
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      {summary.season.length > 1 && <SeasonStrip key={gw} summary={summary} gw={gw} go={go} />}
    </>
  )
}
