// Small pure helpers for the clock chart, skill scores and puzzles (chess_insights.py's numbers) - tested in tests/insightHelpers.test.js.

// 75 -> "1m 15s", 8.5 -> "8.5s"
export function fmtSecs(s) {
  if (s == null) return ''
  if (s >= 60) return `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`
  return `${Number.isInteger(s) ? s : s.toFixed(1)}s`
}

// Does this review have clock times? (Games without a clock hide all the clock bits.)
export const hasClock = (moves) => moves.some((m) => m.clock != null)

const BAD = new Set(['mistake', 'miss', 'blunder'])

// One move's time in words: "Took 8s, 1m 02s left" and, for a bad move made in a hurry, "time trouble".
export function timeNote(m) {
  if (m.clock == null) return ''
  const took = m.spent != null ? `Took ${fmtSecs(m.spent)}, ` : ''
  const trouble = m.low && BAD.has(m.kind) ? ' - a mistake in time trouble' : m.low ? ' - short of time' : ''
  return `${took}${fmtSecs(m.clock)} left${trouble}`
}

// The bars of time spent per move: height 0-100 (a long think is capped at the 90th percentile so one bar can't flatten the rest).
export function paceBars(moves) {
  const spent = moves.map((m) => m.spent).filter((s) => s != null).sort((a, b) => a - b)
  if (!spent.length) return []
  const cap = Math.max(5, spent[Math.floor((spent.length - 1) * 0.9)])
  return moves.map((m) => ({
    ply: m.ply, colour: m.colour, low: !!m.low, bad: BAD.has(m.kind), spent: m.spent,
    h: m.spent == null ? 0 : Math.max(3, Math.round((100 * Math.min(m.spent, cap)) / cap)),
  }))
}

// A skill's score lately against before: {text, tone} ('up' | 'down' | 'same'); nothing to say without both.
export function skillChange(skill) {
  if (skill.recent == null || skill.before == null) return { text: '', tone: 'same' }
  const d = Math.round(skill.recent - skill.before)
  if (Math.abs(d) < 2) return { text: 'about the same as before', tone: 'same' }
  return { text: `${d > 0 ? 'up' : 'down'} ${Math.abs(d)} on before`, tone: d > 0 ? 'up' : 'down' }
}

// The weakest skill that has a score (what to work on).
export function weakestSkill(skills) {
  return skills.filter((s) => s.score != null).sort((a, b) => a.score - b.score)[0] ?? null
}

// "2 won - 1 drawn - 3 lost"
export const recordText = (e) => [`${e.win} won`, `${e.draw} drawn`, `${e.loss} lost`].join(' · ')
