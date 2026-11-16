// Small pure helpers for the hiking pages (tested in web/src/tests/hikingMath.test.js).

// The steepest climb over `window` metres of a track. A track point is [lat, lon, elevation, seconds, metres
// along]. Answers { fromM, toM, gain, grade (a fraction: 0.12 = 12%), seconds } or null for a track too
// short, or without heights.
export function steepestStretch(track, window = 500) {
  const pts = (track ?? []).filter((p) => p[2] != null && p[4] != null)
  let best = null
  let j = 0
  for (let i = 0; i < pts.length; i++) {
    if (j < i) j = i
    while (j < pts.length - 1 && pts[j][4] - pts[i][4] < window) j++
    const run = pts[j][4] - pts[i][4]
    if (run < window) break
    const gain = pts[j][2] - pts[i][2]
    if (gain > 0 && (!best || gain / run > best.grade)) {
      const seconds = pts[i][3] != null && pts[j][3] != null ? pts[j][3] - pts[i][3] : null
      best = { fromM: pts[i][4], toM: pts[j][4], gain, grade: gain / run, seconds }
    }
  }
  return best
}

// "1 h 05 min" style, from seconds, rounded to the minute.
export function hoursMinutes(s) {
  if (s == null) return '—'
  const mins = Math.round(s / 60)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return h ? `${h} h ${String(m).padStart(2, '0')} min` : `${m} min`
}

// "+1:20" / "-0:05" / "same": a time gap in seconds as minutes:seconds, signed (slower is +).
export function gapLabel(s) {
  if (s == null) return '—'
  if (s === 0) return 'same'
  const a = Math.abs(Math.round(s))
  return `${s > 0 ? '+' : '-'}${Math.floor(a / 60)}:${String(a % 60).padStart(2, '0')}`
}

// How many km were quicker / slower than the best run, from the API's split gaps.
export function splitTally(gaps) {
  const g = gaps ?? []
  return { quicker: g.filter((x) => x.gap_s < 0).length, slower: g.filter((x) => x.gap_s > 0).length, level: g.filter((x) => x.gap_s === 0).length }
}
