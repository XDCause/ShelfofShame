// Small helpers for the board-game stats and the Unplayed nudge.

// Owned base games never played, and ones not played for a year. today = 'YYYY-MM-DD' (the PC's day).
export function unplayedGames(games, today) {
  const cutoff = `${Number(today.slice(0, 4)) - 1}${today.slice(4)}`
  const mine = games.filter((g) => g.kind === 'game' && g.status === 'Owned')
  return {
    never: mine.filter((g) => !g.plays),
    stale: mine.filter((g) => g.plays > 0 && g.last_played && g.last_played < cutoff)
      .sort((a, b) => a.last_played.localeCompare(b.last_played)),
  }
}

// "Went first and won 7 of 12 (58%) - chance alone gives 25%".
export function firstPlayerText(f) {
  if (!f || !f.plays) return null
  return `Won ${f.wins} of ${f.plays} (${f.rate}%) - chance alone would give about ${f.chance}%`
}

// A streak as words: "3 in a row", "none".
export const streakText = (n) => (n > 0 ? `${n} in a row` : 'none')
