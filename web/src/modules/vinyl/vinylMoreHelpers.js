// Small pure helpers for Vinyl's care, value history and year pages (tested in web/src/tests/vinylMore.test.js).

// { days: 30, change: 12.5, percent: 2.1 } -> "+$12.50 (+2.1%) in the last month"
const PERIODS = { 30: 'month', 90: '3 months', 365: 'year' }
export function changeText(c) {
  const sign = c.change < 0 ? '−' : '+'
  const amount = `${sign}$${Math.abs(c.change).toFixed(2)}`
  const pct = c.percent == null ? '' : ` (${c.percent < 0 ? '−' : '+'}${Math.abs(c.percent)}%)`
  return `${amount}${pct} in the last ${PERIODS[c.days] ?? `${c.days} days`}`
}

// The stylus: "312 of 800 hours" and what to do about it.
export function stylusText(s) {
  const base = `${s.hours} of ${s.limit_hours} hours`
  if (s.due) return `${base} - time to replace it`
  if (s.soon) return `${base} - ${s.hours_left} hours left, order a new one`
  return `${base} - ${s.hours_left} hours left`
}

// Days out on loan -> "3 days", "today", "5 weeks"
export function loanTime(days) {
  if (days <= 0) return 'today'
  if (days === 1) return '1 day'
  if (days < 14) return `${days} days`
  return `${Math.floor(days / 7)} weeks`
}

// Last cleaned: the newest of the care entries (null when there are none)
export function lastCleaned(care) {
  const done = (care ?? []).filter((c) => c.kind === 'clean').map((c) => c.done_on).sort()
  return done.length ? done[done.length - 1] : null
}
