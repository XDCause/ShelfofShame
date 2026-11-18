// Fishing's plain helpers (no React, no API: tested in web/src/tests/fishingFormat.test.js): how a length, a weight, a
// trip's date and time and a rule read. Metric throughout (cm, kg, m, km/h, hPa, deg C).

export const num = (v, digits = 1) => (v == null || v === '' ? '—' : Number(v).toFixed(digits).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, ''))
export const plural = (n, one, many = `${one}s`) => `${(n ?? 0).toLocaleString()} ${n === 1 ? one : many}`
export const cm = (v) => (v == null ? '—' : `${num(v)} cm`)
export const kg = (v) => (v == null ? '—' : `${num(v, 2)} kg`)

export const PLATFORMS = [['shore', 'Shore'], ['jetty', 'Jetty'], ['boat', 'Boat'], ['kayak', 'Kayak'], ['wading', 'Wading']]
export const FATES = [['released', 'Released'], ['kept', 'Kept'], ['tagged', 'Tagged and released'], ['died', 'Died']]
export const WATERS = [['salt', 'Salt'], ['estuary', 'Estuary'], ['fresh', 'Fresh']]
export const SPECIES_WATERS = [...WATERS, ['any', 'Any']]
export const LURE_KINDS = [['lure', 'Lure'], ['soft plastic', 'Soft plastic'], ['bait', 'Bait'], ['live bait', 'Live bait'], ['fly', 'Fly'], ['jig', 'Jig'], ['other', 'Other']]
export const SPOT_KINDS = ['Beach', 'Rocks', 'Jetty', 'Boat ramp', 'River', 'Creek', 'Canal', 'Dam', 'Reef', 'Offshore', 'Fishing spot']
export const METHODS = ['Casting', 'Trolling', 'Bottom bashing', 'Drifting', 'Jigging', 'Fly', 'Float', 'Bait', 'Crabbing']
export const MOON_PHASES = ['New moon', 'Waxing crescent', 'First quarter', 'Waxing gibbous', 'Full moon', 'Waning gibbous', 'Last quarter', 'Waning crescent']
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const label = (list, v) => list.find(([k]) => k === v)?.[1] ?? v
export const platformName = (v) => (v ? label(PLATFORMS, v) : '')
export const fateName = (v) => label(FATES, v)

// 4 -> "★★★★☆"
export const stars = (n) => (n == null ? '' : '★'.repeat(n) + '☆'.repeat(5 - n))

// 85 -> "1 h 25 min"; 45 -> "45 min"; 120 -> "2 h"
export function minutesText(total) {
  if (total == null || total === '') return '—'
  const t = Math.round(Number(total))
  const h = Math.floor(t / 60)
  const m = t % 60
  return h === 0 ? `${m} min` : m === 0 ? `${h} h` : `${h} h ${m} min`
}
export const hoursText = (hours) => (hours == null ? '—' : `${num(hours)} h`)

// A time on the water, started -> ended (ISO strings): "2 h 10 min", or "" while it runs / unknown.
export function tripMinutes(t) {
  if (!t?.started_at || !t?.ended_at) return null
  return Math.max(0, Math.round((new Date(t.ended_at) - new Date(t.started_at)) / 60000))
}

// ISO -> the local date "YYYY-MM-DD" and time "HH:MM" (the phone and the PC are on Brisbane time); back again.
export const dateOf = (iso) => (iso ? new Date(iso).toLocaleDateString('en-CA') : '')
export const timeOf = (iso) => (iso ? new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '')
export function toIso(date, time) {
  if (!date) return null
  const d = new Date(`${date}T${time || '00:00'}`)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}
export const clockText = (iso) => (iso ? new Date(iso).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit', hour12: true }) : '')

// "5-01" style rule dates: 'MM-DD' -> "1 Nov"
export function monthDay(md) {
  if (!md) return ''
  const [m, d] = md.split('-').map(Number)
  return `${d} ${MONTHS[m - 1] ?? ''}`.trim()
}

// The rules you typed for a species, as short facts: ["min 30 cm", "max 70 cm", "bag 5", "closed 1 Jun - 31 Aug", "no take"]
export function ruleFacts(s) {
  if (!s) return []
  return [
    s.no_take && 'no take',
    s.min_cm != null && `min ${num(s.min_cm)} cm`,
    s.max_cm != null && `max ${num(s.max_cm)} cm`,
    s.bag != null && !s.no_take && `bag ${s.bag}`,
    s.closed_from && s.closed_to && `closed ${monthDay(s.closed_from)} - ${monthDay(s.closed_to)}`,
  ].filter(Boolean)
}
export const hasRules = (s) => ruleFacts(s).length > 0

// Is a 'YYYY-MM-DD' date inside a yearly closed season ('MM-DD' to 'MM-DD', may wrap over New Year)?
export function inClosedSeason(day, from, to) {
  if (!day || !from || !to) return false
  const md = day.slice(5)
  return from <= to ? md >= from && md <= to : md >= from || md <= to
}

// "month / year" of the rules' check: 'rules checked on 3 Nov 2026' (or "never checked")
export const checkedText = (iso, fmt) => (iso ? `checked on ${fmt(iso)}` : 'never checked')

// A date's days until due -> "overdue by 3 days" / "due today" / "due in 12 days" (due: YYYY-MM-DD)
export function dueText(due, now = new Date()) {
  if (!due) return ''
  const days = Math.round((new Date(`${due}T12:00:00`) - new Date(`${now.toLocaleDateString('en-CA')}T12:00:00`)) / 86400000)
  return days < 0 ? `overdue by ${plural(-days, 'day')}` : days === 0 ? 'due today' : `due in ${plural(days, 'day')}`
}

// A catch's name: the list's species, else what was typed.
export const catchName = (c) => c?.species_name ?? c?.species ?? 'Fish'

// "Dusky flathead 52 cm, released"
export const catchLine = (c) => [catchName(c), c.length_cm != null && cm(c.length_cm)].filter(Boolean).join(' ')

// A trip's title in a list: the spot, else the target, else "Fishing trip".
export const tripName = (t) => t?.spot_name ?? t?.target ?? 'Fishing trip'

// Seasons heat grid: 12 counts -> 0..4 shade steps against the grid's biggest cell.
export function heatLevel(count, max) {
  if (!count || !max) return 0
  return Math.min(4, Math.max(1, Math.ceil((count / max) * 4)))
}

// The year picker's choices: this year back `n` years.
export const yearChoices = (n = 8, now = new Date()) => Array.from({ length: n }, (_, i) => now.getFullYear() - i)

// "1 Nov" style month label from 'YYYY-MM'
export const monthLabel = (ym, opts = { month: 'short', year: '2-digit' }) => new Date(`${ym}-15T12:00:00`).toLocaleDateString('en-AU', opts)

// A conditions snapshot (jsonb, written by the API) as short facts for a trip's panel; unknown parts are left out.
export function conditionFacts(c) {
  if (!c || typeof c !== 'object') return []
  const tides = Array.isArray(c.tide) ? c.tide : []
  return [
    c.moon_phase && { label: 'Moon', value: c.moon_phase, sub: c.moon_pct != null ? `${Math.round(c.moon_pct)}% lit` : null },
    c.rating != null && { label: 'Solunar day', value: `${c.rating} of 4` },
    c.sunrise && { label: 'Sunrise', value: String(c.sunrise).slice(-5), sub: c.sunset ? `sunset ${String(c.sunset).slice(-5)}` : null },
    tides.length > 0 && { label: 'Tide', value: tides.map((x) => `${x.kind === 'high' ? 'H' : 'L'} ${String(x.time).slice(-5)}`).join(' · ') },
    c.wind_kmh != null && { label: 'Wind', value: `${num(c.wind_kmh, 0)} km/h`, sub: c.wind_dir != null ? `${Math.round(c.wind_dir)}°` : null },
    c.pressure_hpa != null && { label: 'Pressure', value: `${num(c.pressure_hpa, 0)} hPa`, sub: c.pressure_trend ?? null },
    c.sst != null && { label: 'Sea', value: `${num(c.sst)}°C` },
  ].filter(Boolean)
}

// Points for a line chart: one a day (the last that day wins), oldest first. rows: [{x: 'YYYY-MM-DD', y, tip}]
export function oneADay(rows) {
  const by = new Map()
  rows.forEach((r) => by.set(r.x, r))
  return [...by.values()]
}
