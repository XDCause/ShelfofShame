// Scuba's plain helpers (no React, no API: tested in web/src/tests/scubaFormat.test.js): how a depth, a time, a gas and
// the no-fly countdown read. Metric throughout (m, bar, litres, deg C).

export const num = (v, digits = 1) => (v == null || v === '' ? '—' : Number(v).toFixed(digits).replace(/\.0+$/, ''))
export const plural = (n, one, many = `${one}s`) => `${(n ?? 0).toLocaleString()} ${n === 1 ? one : many}`
export const metres = (v) => (v == null ? '—' : `${num(v)} m`)
export const degrees = (v) => (v == null ? '—' : `${num(v)}°C`)

// A figure the API may send as a plain number or as {dives, minutes, ...}: read one key of it.
export const field = (x, key) => (x != null && typeof x === 'object' ? x[key] : x)

// 85 -> "1 h 25 min"; 45 -> "45 min"; 120 -> "2 h"
export function minutesText(total) {
  if (total == null || total === '') return '—'
  const t = Math.round(Number(total))
  const h = Math.floor(t / 60)
  const m = t % 60
  return h === 0 ? `${m} min` : m === 0 ? `${h} h` : `${h} h ${m} min`
}

// The hours underwater, for a big total: 5025 min -> "83.8 h"
export const hoursText = (minutes) => (minutes == null ? '—' : `${num(Number(minutes) / 60)} h`)

// The gas in the tank: 21 is air, 32 is "EAN32" (nitrox), 100 oxygen.
export const gasName = (o2) => (o2 == null || Number(o2) === 21 ? 'Air' : Number(o2) >= 100 ? 'Oxygen' : `EAN${o2}`)

export const SUITS = ['3 mm shorty', '3 mm wetsuit', '5 mm wetsuit', '7 mm wetsuit', 'Drysuit', 'Skin / lycra']
export const CURRENTS = [['none', 'None'], ['light', 'Light'], ['moderate', 'Moderate'], ['strong', 'Strong']]
export const ENTRIES = [['boat', 'Boat'], ['shore', 'Shore']]
export const SITE_KINDS = ['Reef', 'Wreck', 'Wall', 'Drift', 'Pinnacle', 'Cave', 'Muck', 'Lake', 'Quarry', 'Training']
export const TAG_IDEAS = ['night', 'drift', 'deep', 'wreck', 'training', 'photo', 'shore', 'boat', 'nitrox', 'wall']
export const SERVICE_IDEAS = ['Annual service', 'Visual inspection', 'Hydro test', 'Battery change', 'Repair']

// "night, wreck" -> ['night', 'wreck'] (blank and repeated tags dropped, lower case)
export const tagsFromText = (text) => [...new Set(String(text ?? '').split(/[,;]+/).map((t) => t.trim().toLowerCase()).filter(Boolean))]

// 4 -> "★★★★☆"
export const stars = (n) => (n == null ? '' : '★'.repeat(n) + '☆'.repeat(5 - n))

// "Dive 123": the logbook number (a dive without one, "Dive")
export const diveName = (d) => (d?.dive_no != null ? `Dive ${d.dive_no}` : 'Dive')

// "HH:MM:SS" -> "08:30"
export const timeText = (t) => (t ? String(t).slice(0, 5) : '')

// The no-fly time (the API says when: 12 h after a single dive, 18 h after repeat dives - DAN's guideline). Left to go
// from `now`: {clear: true} when it has passed (or there is none), else {clear: false, ms, text: "5 h 12 min"}.
export function noFlyLeft(iso, now = Date.now()) {
  if (!iso) return { clear: true }
  const ms = new Date(iso).getTime() - now
  if (Number.isNaN(ms) || ms <= 0) return { clear: true }
  const mins = Math.ceil(ms / 60000)
  return { clear: false, ms, text: minutesText(mins) }
}

// "Tue 7:30 pm"
export const clockText = (iso) => new Date(iso).toLocaleString('en-AU', { weekday: 'short', hour: 'numeric', minute: '2-digit', hour12: true })

// Points for a line chart: one a day (the last that day wins), oldest first.
export function oneADay(rows) {
  const by = new Map()
  rows.forEach((r) => by.set(r.x, r))
  return [...by.values()]
}

// An alert's days until due -> "overdue" / "due today" / "in 12 days" (due: YYYY-MM-DD)
export function dueText(due, now = new Date()) {
  if (!due) return ''
  const days = Math.round((new Date(`${due}T12:00:00`) - new Date(`${now.toLocaleDateString('en-CA')}T12:00:00`)) / 86400000)
  return days < 0 ? `overdue by ${plural(-days, 'day')}` : days === 0 ? 'due today' : `due in ${plural(days, 'day')}`
}
