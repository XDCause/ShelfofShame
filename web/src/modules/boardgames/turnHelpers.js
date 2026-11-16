// Pure helpers for the turn timer, the round-by-round score grid and play tags (LivePlay.jsx, turnParts.jsx).
// The numbers come from api/app/boardgames_live.py (turns) and boardgames_people.py (round_scores, tags).

// The turn limits offered (seconds): null = no limit.
export const TURN_LIMITS = [[null, 'No limit'], [30, '30 seconds'], [60, '1 minute'], [120, '2 minutes'], [300, '5 minutes']]

// Seconds each player has thought so far, and the current turn's seconds. `since` is how many seconds have passed
// since the server's answer arrived (the screen's own ticking); the server's `now` and the turn's start are on its clock.
export function turnClocks(turns, serverNow, since = 0) {
  if (!turns) return { totals: {}, current: 0 }
  const running = turns.running && turns.since && turns.current != null
  const extra = running ? Math.max(0, (Date.parse(serverNow) - Date.parse(turns.since)) / 1000 + since) : 0
  const totals = { ...turns.totals }
  if (running) totals[turns.current] = (totals[turns.current] ?? 0) + extra
  return { totals, current: (turns.cur_s ?? 0) + extra }
}

// Is the current turn past the limit? (The gentle warning.)
export const overLimit = (turns, currentSecs) => !!turns?.limit && currentSecs > turns.limit

// A player's time as words for a saved play: "4:05 over 6 turns (avg 0:41)".
export function turnLine(seat, clockText) {
  if (seat.turn_seconds == null) return null
  const n = seat.turn_count || 0
  const avg = n ? ` (avg ${clockText(seat.turn_seconds / n)})` : ''
  return `${clockText(seat.turn_seconds)}${n ? ` over ${n} turn${n === 1 ? '' : 's'}` : ''}${avg}${seat.turn_over ? `, ${seat.turn_over} over the limit` : ''}`
}

const num = (v) => (v === '' || v == null || Number.isNaN(Number(v)) ? null : Number(v))

// Each player's total from the grid (rows = rounds, each { "<player_id>": score }); null where they have no score.
export function roundTotals(rows, playerIds) {
  return Object.fromEntries(playerIds.map((id) => {
    const vals = (rows ?? []).map((r) => num(r[id])).filter((v) => v != null)
    return [id, vals.length ? vals.reduce((a, v) => a + v, 0) : null]
  }))
}

// Seats for showing and ranking: a seat with no score of its own takes its round-grid total.
export function withGrid(seats, rows) {
  if (!rows?.length) return seats
  const totals = roundTotals(rows, seats.map((s) => s.player_id))
  return seats.map((s) => {
    const own = s.score != null && s.score !== ''
    const taps = s.adds?.length > 0
    const parts = Object.values(s.parts ?? {}).some((v) => v !== '' && v != null)
    const t = totals[s.player_id]
    return !own && !taps && !parts && t != null ? { ...s, score: t } : s
  })
}

// The grid as the API wants it: blanks and non-numbers left out.
export const gridOut = (rows) => rows.map((r) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, num(v)]).filter(([, v]) => v != null)))

// A tag list with one more tag: trimmed, one space between words, no repeats (any case), at most 12.
export function addTag(tags, text) {
  const t = text.trim().replace(/\s+/g, ' ').slice(0, 40)
  if (!t || tags.length >= 12 || tags.some((x) => x.toLowerCase() === t.toLowerCase())) return tags
  return [...tags, t]
}

// Suggestions: tags used before (most used first) that aren't on this play yet and match what's typed.
export const tagSuggestions = (known, tags, typed = '') => {
  const have = new Set(tags.map((t) => t.toLowerCase()))
  const q = typed.trim().toLowerCase()
  return known.filter((k) => !have.has(k.tag.toLowerCase()) && k.tag.toLowerCase().includes(q)).map((k) => k.tag)
}
