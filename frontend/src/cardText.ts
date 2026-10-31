// The words around the gameweek graphic: the state badge, and how to read the
// graphic (shown in the info tip beside the page title).

import type { Plot } from './api'

export function stateText(plot: Plot): { badge: string; note: string } {
  if (plot.state === 'locked') {
    return { badge: 'Full time', note: 'Average positions in this gameweek, after auto-subs.' }
  }
  if (plot.status === 'finished') {
    return {
      badge: 'Preview',
      note: `GW${plot.gw} has finished, but its positions aren't in yet, so each player of the picked XI is shown from his most recent match.`,
    }
  }
  return {
    badge: 'Preview',
    note: 'Gameweek in progress: the picked XI, each from his most recent match. Points are live.',
  }
}

export const HOW_TO_READ =
  'Attacking upward. Height: how far forward compared with every Premier League outfield player.'

// What the graphic shows, for the info tip beside the page title.
export function cardNote(plot: Plot): string {
  const asOf = plot.data_as_of ? ` Positions as of ${formatDate(plot.data_as_of)}.` : ''
  return `${stateText(plot).note} ${HOW_TO_READ}${asOf}`
}

function formatDate(iso: string) {
  // data_as_of is UTC without an offset.
  return new Date(`${iso}Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
