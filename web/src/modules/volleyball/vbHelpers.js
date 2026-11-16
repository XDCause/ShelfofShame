// Small pure helpers for Volleyball's ratings, rotations, clips and drills (tested in web/src/tests/volleyballMore.test.js).

export const SCORE_NAMES = ['Error', 'Poor', 'Ok', 'Perfect']          // the 0-3 scale
export const SKILLS = ['serve', 'pass', 'set', 'attack', 'block', 'dig']
export const OUTCOMES = [['good', 'Good'], ['error', 'Error']]

// A trend (last games against the games before): "Up 0.3" / "Down 0.2" / "Steady"
export function trendText(t) {
  if (t == null) return 'Not enough games for a trend yet'
  if (Math.abs(t) < 0.05) return 'Steady'
  return `${t > 0 ? 'Up' : 'Down'} ${Math.abs(t).toFixed(1)} on the games before`
}

// 78 -> "78%", null -> "–"
export const percentText = (p) => (p == null ? '–' : `${p}%`)

// The rotation to suggest after a rally: you rotate when you win the serve back (side-out), so the next rotation
// follows a won rally you were receiving; otherwise it stays.
export function nextRotation(rotation, serving, won) {
  if (!serving && won) return rotation === 6 ? 1 : rotation + 1
  return rotation
}

// "serve" + "error" -> "Serve errors"; "dig" + "good" -> "Good digs"; a skill alone -> "Serves"
export function clipFilterName(skill, outcome) {
  const plural = skill ? `${skill}s` : 'clips'
  const noun = plural.charAt(0).toUpperCase() + plural.slice(1)
  if (outcome === 'error') return skill ? `${noun.slice(0, -1)} errors` : 'Errors'
  if (outcome === 'good') return skill ? `Good ${plural}` : 'Good clips'
  return skill ? noun : 'All clips'
}

// 12 reps, 25 minutes -> "12 reps · 25 min"; best 14 with a label "in a row" -> "14 in a row"
export function resultText(value, label) {
  if (value == null) return '–'
  return `${Number(value).toLocaleString()}${label ? ` ${label}` : ''}`
}
