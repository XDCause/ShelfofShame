// A game's status (api/app/videogames.py, 99_vg_backlog.sql): the one you set, else the API's guess.
export const STATUSES = [['backlog', 'Backlog'], ['playing', 'Playing'], ['finished', 'Finished'], ['dropped', 'Dropped']]
export const STATUS_LABEL = Object.fromEntries(STATUSES)
export const STATUS_TONE = { backlog: 'tint', playing: 'low', finished: 'ok', dropped: '' }

// How the "What next?" pick is chosen.
export const PICKS = [['shortest', 'Shortest'], ['achievements', 'Fewest achievements left'], ['random', 'Random']]

// What to say about a pick: the time it should take (SteamHunters' median, else your own median) and what's left.
export function pickDetail(game, median) {
  const parts = []
  if (game.estimate_minutes > 0) {
    const h = game.estimate_minutes / 60
    const text = h >= 1 ? `${Math.round(h * 10) / 10} h` : `${game.estimate_minutes} min`
    const why = game.estimate_source === 'yours' ? ' (your estimate)' : game.sh_median_minutes > 0 ? ' to 100% (SteamHunters)' : median ? ' (your median finished game)' : ''
    parts.push(`about ${text}${why}`)
  }
  if (game.achievements_total > 0) parts.push(`${game.left_to_get} of ${game.achievements_total} achievements left`)
  return parts.join(' · ')
}

// Time to beat (api/app/videogames.py with_estimate): your own guess, else SteamHunters' median, else your median.
export const ESTIMATE_SOURCE = { yours: 'your estimate', steamhunters: "SteamHunters' median to 100%", median: 'median of the games you finished' }

export function estimateText(game) {
  const m = game.estimate_minutes
  if (!(m > 0)) return null
  const h = m / 60
  const time = h >= 1 ? `${Math.round(h * 10) / 10} h` : `${m} min`
  return `${time} (${ESTIMATE_SOURCE[game.estimate_source] ?? 'a guess'})`
}

// The achievement you don't have yet that the most players have (unobtainable ones skipped), or null.
export function easiestLocked(achievements) {
  const open = (achievements ?? []).filter((a) => !a.achieved && !a.unobtainable && a.global_percent != null)
  return open.reduce((best, a) => (!best || Number(a.global_percent) > Number(best.global_percent) ? a : best), null)
}

// Money and cost per hour as text: "$0.60/h", or "not played yet".
export const perHourText = (v) => (v == null ? 'not played yet' : `$${Number(v).toFixed(2)}/h`)
export const moneyText = (v) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
