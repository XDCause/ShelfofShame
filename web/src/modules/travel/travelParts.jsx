import { useEffect, useState } from 'react'
import { api, money, shortDate } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// Bits shared by Travel's pages and panels: the choice lists, countries (names and flags), how a trip's dates read,
// and the summary.

let listsCache = null
export function useTravelLists() {
  const [lists, setLists] = useState(listsCache)
  useEffect(() => {
    if (!listsCache) api.travelLists().then((l) => { listsCache = l; setLists(l) }).catch(() => {})
  }, [])
  return lists
}

export function useTravelSummary() {
  const { refreshKey } = useApp()
  return useShared(`travel-summary-${refreshKey}`, () => api.travelSummary())
}

// Every country (ISO 3166 codes); the browser knows their names in English.
const CODES = ('AD AE AF AG AI AL AM AO AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BW BY BZ CA CC CD '
  + 'CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG '
  + 'GH GI GL GM GN GP GQ GR GT GU GW GY HK HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY '
  + 'KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI '
  + 'NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SK SL SM SN SO SR '
  + 'SS ST SV SX SY SZ TC TD TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG US UY UZ VA VC VE VG VI VN VU WF WS XK YE YT ZA ZM ZW').split(' ')
let names = null
const regionName = (code) => {
  try {
    names ??= new Intl.DisplayNames(['en-AU'], { type: 'region' })
    return names.of(code)
  } catch {
    return code
  }
}
export const countryName = (code) => (code ? regionName(code) : '')
// A flag from its code: two "regional indicator" letters, which phones and most computers draw as the flag.
export const flag = (code) => (code && /^[A-Z]{2}$/.test(code)
  ? String.fromCodePoint(...[...code].map((c) => 0x1f1a5 + c.charCodeAt(0))) : '')
export const COUNTRIES = CODES.map((code) => ({ code, name: regionName(code) })).sort((a, b) => a.name.localeCompare(b.name))
export const codeFor = (text) => {
  const t = text.trim().toLowerCase()
  return COUNTRIES.find((c) => c.code.toLowerCase() === t || c.name.toLowerCase() === t)?.code ?? null
}

export const plural = (n, one, many = `${one}s`) => `${(n ?? 0).toLocaleString()} ${n === 1 ? one : many}`
export const PHASE_TONE = { now: 'ok', upcoming: 'tint', idea: 'purple', past: '', cancelled: 'out' }
export const PHASE_NAME = { now: 'Now', upcoming: 'Upcoming', idea: 'Idea', past: 'Been', cancelled: 'Cancelled' }

// "14 – 27 Nov 2026" (or "14 Nov 2026" for a day trip)
export function dates(t) {
  if (!t.start_date) return 'No dates yet'
  const s = new Date(`${t.start_date}T12:00:00`)
  const e = new Date(`${t.end_date ?? t.start_date}T12:00:00`)
  if (+s === +e) return shortDate(t.start_date)
  const sameYear = s.getFullYear() === e.getFullYear()
  const sameMonth = sameYear && s.getMonth() === e.getMonth()
  const opts = sameMonth ? { day: 'numeric' } : sameYear ? { day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short', year: 'numeric' }
  return `${s.toLocaleDateString('en-AU', opts)} – ${e.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}`
}

// Where the trip is in time: "in 12 days", "Day 3 of 9", "8 days" (been), "Idea".
export function when(t) {
  if (t.phase === 'upcoming') return t.starts_in === 1 ? 'Tomorrow' : `In ${plural(t.starts_in, 'day')}`
  if (t.phase === 'now') return t.days > 1 ? `Day ${t.day_number} of ${t.days}` : 'Today'
  if (t.phase === 'past') return plural(t.days, 'day')
  return PHASE_NAME[t.phase]
}

export const tripMeta = (t) => [dates(t), t.destination, t.countries?.map(flag).join(' ')].filter(Boolean).join(' · ')
export const aud = (n) => (n == null ? '—' : money(n))
// An amount in its own currency: "¥2,500" / "US$12.00" / "$45.00"
export function inCurrency(amount, currency) {
  if (amount == null) return '—'
  if (!currency || currency === 'AUD') return money(amount)
  try {
    return new Intl.NumberFormat('en-AU', { style: 'currency', currency }).format(amount)
  } catch {
    return `${amount.toLocaleString()} ${currency}`
  }
}
