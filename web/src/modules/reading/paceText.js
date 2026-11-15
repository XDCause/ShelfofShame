// Words for the reading pace: a book's forecast (api/app/reading.py pace_forecast) and the year's goal.
const plural = (n, one) => `${n} ${one}${n === 1 ? '' : 's'}`

// "12 pages a day lately · finish around Fri 20 Nov"
export function forecastText(f) {
  if (!f) return ''
  const rate = `${Number.isInteger(f.pages_per_day) ? f.pages_per_day : f.pages_per_day.toFixed(1)} pages a day lately`
  if (!f.finish_on) return rate
  const day = new Date(`${f.finish_on}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
  return `${rate} · finish around ${day}`
}

// "On track for 14 books" / "3 books behind at your pace (on track for 9)" - or '' when there's no goal or no pace yet
export function goalPaceText(g) {
  if (!g || !g.goal || g.reached || g.projected == null) return ''
  const total = Math.round(g.projected)
  if (g.behind_by > 0) return `${plural(g.behind_by, 'book')} behind at your pace (on track for ${total})`
  return `On track for ${total} ${total === 1 ? 'book' : 'books'} this year`
}
