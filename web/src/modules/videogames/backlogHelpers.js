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
    parts.push(`about ${text}${game.sh_median_minutes > 0 ? ' to 100% (SteamHunters)' : median ? ' (your median finished game)' : ''}`)
  }
  if (game.achievements_total > 0) parts.push(`${game.left_to_get} of ${game.achievements_total} achievements left`)
  return parts.join(' · ')
}
