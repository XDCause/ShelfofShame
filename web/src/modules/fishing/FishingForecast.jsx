import { useEffect, useState } from 'react'
import { api, keptAt } from '../../api.js'

// Fishing > Forecast: seven days for a spot (or where you stand) from the API (GET /fishing/forecast): the solunar
// periods and a day rating (our own astronomy, no outside site), the moon, sunrise and sunset, the tide highs and lows and
// the wind and pressure (Open-Meteo), and the windows where they line up. Any single day (a past trip's too) can be looked
// up with the date picker (GET /fishing/solunar). Solunar tables are an old angling theory, not science: your own
// log (Stats) shows what works for you. Not for navigation.
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
const compass = (deg) => (deg == null ? '' : COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16])
const val = (v, unit, d = 0) => (v == null ? '—' : `${Number(v).toFixed(d)}${unit}`)
export const dayName = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
// a time as the API sends it ("2026-11-18T05:12", "05:12" or "05:12:00") -> "05:12", and minutes after midnight
export const hm = (t) => {
  const s = String(t ?? '')
  return (s.includes('T') ? s.split('T')[1] : s).slice(0, 5)
}
export const minutesOf = (t) => {
  const text = hm(t)
  if (!text) return null
  const [h, m] = text.split(':').map(Number)
  return Number.isFinite(h) ? h * 60 + (m || 0) : null
}
const TREND = { rising: 'rising', falling: 'falling', steady: 'steady' }

// A period [start, end] on the 24 h bar: one box, or two when it runs over midnight
export function spans(start, end) {
  const a = minutesOf(start)
  const b = minutesOf(end)
  if (a == null || b == null) return []
  return b >= a ? [[a, b]] : [[a, 1440], [0, b]]
}

// ---------------------------------------------------------------- pictures

// The day's rating as fish (1-4)
export function RatingFish({ rating, of = 4 }) {
  const n = Math.max(0, Math.min(of, Number(rating) || 0))
  return (
    <span className="fst-fish" role="img" aria-label={`Day rating ${n} of ${of}`}>
      {Array.from({ length: of }, (_, i) => (
        <svg key={i} viewBox="0 0 24 20" width="22" height="18" aria-hidden="true" className={i < n ? 'fst-fish-on' : 'fst-fish-off'}>
          <path d="M2 10 C6 2 14 2 18 10 C14 18 6 18 2 10 Z M17 10 L23 4 V16 Z" />
        </svg>
      ))}
    </span>
  )
}

// The moon as it looks from here. We're in the southern hemisphere: a waxing moon is lit on its LEFT (the north-hemisphere
// pictures are the other way round). pct = illuminated percent; phase = the name ('Waxing crescent'...).
export function moonPath(pct, waxing, r = 10, c = 12) {
  const f = Math.max(0, Math.min(1, (Number(pct) || 0) / 100))
  if (f <= 0.01) return ''
  if (f >= 0.99) return `M${c - r} ${c} A${r} ${r} 0 1 1 ${c + r} ${c} A${r} ${r} 0 1 1 ${c - r} ${c} Z`
  const right = !waxing                                           // lit side: waxing -> left (south), waning -> right
  const rx = Math.abs(1 - 2 * f) * r
  const outer = right ? 1 : 0
  const term = (f > 0.5) === right ? 1 : 0
  return `M${c} ${c - r} A${r} ${r} 0 0 ${outer} ${c} ${c + r} A${rx.toFixed(2)} ${r} 0 0 ${term} ${c} ${c - r} Z`
}
export function MoonPhase({ phase, pct, size = 28 }) {
  const waxing = /^(waxing|first)/i.test(phase ?? '')
  const d = moonPath(pct, waxing)
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} role="img" aria-label={`${phase ?? 'Moon'}, ${Math.round(pct ?? 0)}% lit`} className="fst-moon">
      <circle cx="12" cy="12" r="10" className="fst-moon-dark" />
      {d && <path d={d} className="fst-moon-lit" />}
    </svg>
  )
}

const W = 480
const x = (min) => (min / 1440) * W

// The day on a 24 h bar: night shaded, majors (tall) and minors (short) as bands, the tide curve under it.
export function DayBar({ day }) {
  const rise = minutesOf(day.sunrise)
  const set = minutesOf(day.sunset)
  const tides = (day.tide ?? []).map((t) => ({ m: minutesOf(t.time), h: Number(t.height), kind: t.kind })).filter((t) => t.m != null && Number.isFinite(t.h))
    .sort((a, b) => a.m - b.m)
  const lo = Math.min(...tides.map((t) => t.h))
  const hi = Math.max(...tides.map((t) => t.h))
  const ty = (h) => 78 - (hi === lo ? 0.5 : (h - lo) / (hi - lo)) * 26
  // the curve: a cosine between each pair of highs / lows, flat before the first and after the last
  let curve = ''
  if (tides.length) {
    const pts = [[0, ty(tides[0].h)]]
    tides.forEach((t, i) => {
      if (i > 0) {
        const p = tides[i - 1]
        for (let k = 1; k <= 8; k += 1) {
          const u = k / 8
          const h = p.h + (t.h - p.h) * (1 - Math.cos(Math.PI * u)) / 2
          pts.push([x(p.m + (t.m - p.m) * u), ty(h)])
        }
      } else pts.push([x(t.m), ty(t.h)])
    })
    pts.push([W, ty(tides[tides.length - 1].h)])
    curve = pts.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)} ${py.toFixed(1)}`).join(' ')
  }
  const label = [
    ...(day.majors ?? []).map((p) => `major ${hm(p.start)} to ${hm(p.end)}`),
    ...(day.minors ?? []).map((p) => `minor ${hm(p.start)} to ${hm(p.end)}`),
    ...tides.map((t) => `${t.kind ?? 'tide'} ${val(t.h, ' m', 1)}`),
  ].join(', ')
  return (
    <svg viewBox={`0 0 ${W} 92`} className="fst-bar" role="img" aria-label={`Day timeline: ${label || 'no periods'}`}>
      <rect x="0" y="0" width={W} height="52" className="fst-bar-night" />
      {rise != null && set != null && <rect x={x(rise)} y="0" width={Math.max(0, x(set) - x(rise))} height="52" className="fst-bar-day" />}
      {[6, 12, 18].map((h) => <line key={h} x1={x(h * 60)} x2={x(h * 60)} y1="0" y2="52" className="fst-bar-grid" />)}
      {(day.minors ?? []).flatMap((p, i) => spans(p.start, p.end).map(([a, b], j) => (
        <rect key={`n${i}-${j}`} x={x(a)} y="16" width={Math.max(2, x(b) - x(a))} height="20" rx="3" className="fst-bar-minor" />)))}
      {(day.majors ?? []).flatMap((p, i) => spans(p.start, p.end).map(([a, b], j) => (
        <rect key={`j${i}-${j}`} x={x(a)} y="6" width={Math.max(2, x(b) - x(a))} height="40" rx="3" className="fst-bar-major" />)))}
      {curve && <path d={curve} className="fst-bar-tide" fill="none" />}
      {tides.map((t, i) => <circle key={i} cx={x(t.m)} cy={ty(t.h)} r="3" className={t.kind === 'high' ? 'fst-tide-high' : 'fst-tide-low'} />)}
      {[0, 6, 12, 18, 24].map((h) => (
        <text key={h} x={Math.min(W - 8, Math.max(8, x(h * 60)))} y="91" textAnchor="middle" className="fst-bar-axis">{h}</text>))}
    </svg>
  )
}

// ---------------------------------------------------------------- a day

const times = (list) => (list ?? []).map((p) => `${hm(p.start)}-${hm(p.end)}`).join(', ') || '—'

// One day's card. compact (the live trip page's "today"): the rating, the periods and the next tide only.
export function DayCard({ day, compact = false }) {
  const tides = day.tide ?? []
  const moon = day.moon ?? {}
  return (
    <li className={`card fst-day${compact ? ' fst-day-compact' : ''}`}>
      <div className="fst-day-head">
        <h3 className="fst-h3">{dayName(day.date)}</h3>
        <RatingFish rating={day.rating} />
        {day.score != null && <span className="badge fst-score">{day.score} / 5</span>}
      </div>
      {day.why && !compact && <p className="muted small fst-why">{day.why}</p>}
      <DayBar day={day} />
      <dl className="fst-times">
        <div><dt>Major</dt><dd>{times(day.majors)}</dd></div>
        <div><dt>Minor</dt><dd>{times(day.minors)}</dd></div>
        {tides.length > 0 && (
          <div><dt>Tide</dt><dd>{tides.map((t) => `${hm(t.time)} ${t.kind === 'low' ? 'low' : 'high'} ${val(t.height, ' m', 1)}`).join(' · ')}</dd></div>)}
      </dl>
      {(day.best ?? []).length > 0 && (
        <ul className="fst-best" aria-label="Best times">
          {day.best.map((b, i) => <li key={i}><strong>{hm(b.start)}-{hm(b.end)}</strong> <span className="muted small">{b.why}</span></li>)}
        </ul>
      )}
      {!compact && (
        <dl className="fst-numbers">
          <div><dt>Moon</dt><dd className="fst-moonrow"><MoonPhase phase={moon.phase} pct={moon.pct} /> <span>{moon.phase ?? '—'}</span></dd></div>
          <div><dt>Sun</dt><dd>{hm(day.sunrise) || '—'} / {hm(day.sunset) || '—'}</dd></div>
          {day.wind_max != null && (
            <div><dt>Wind</dt><dd>{val(day.wind_max, ' km/h')} {compass(day.wind_dir)}<span className="muted small"> gusts {val(day.gusts, '')}</span></dd></div>)}
          {day.pressure_mean != null && (
            <div><dt>Pressure</dt><dd>{val(day.pressure_mean, ' hPa')}<span className="muted small"> {TREND[day.pressure_trend] ?? ''}</span></dd></div>)}
          {day.rain_mm != null && <div><dt>Rain</dt><dd>{val(day.rain_mm, ' mm', 1)}</dd></div>}
          {day.sst != null && <div><dt>Sea</dt><dd>{val(day.sst, ' °C', 1)}</dd></div>}
          {day.swell_max != null && <div><dt>Swell</dt><dd>{val(day.swell_max, ' m', 1)}</dd></div>}
        </dl>
      )}
    </li>
  )
}

// A single day from /fishing/solunar (the same fields, no weather): fill in what a day card expects.
const fromSolunar = (s, date) => ({ ...s, date, moon: s.moon ?? { phase: s.moon_phase, pct: s.moon_pct } })

// ---------------------------------------------------------------- the page

export function ForecastView() {
  const [spots, setSpots] = useState(null)
  const [spotId, setSpotId] = useState('')
  const [where, setWhere] = useState(null)             // {lat, lon, label}: the position the date lookup uses
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [date, setDate] = useState('')
  const [one, setOne] = useState(null)
  useEffect(() => { api.fishingLiveSpots().then(setSpots).catch(() => setSpots([])) }, [])
  const withPosition = (spots ?? []).filter((s) => s.lat != null && s.lon != null)

  const load = async (params, place) => {
    setBusy(true)
    setError('')
    setOne(null)
    try {
      const r = await api.fishingForecast(params)
      setData(r)
      setWhere(place)
    } catch (e) {
      setError(e.message)
      setData(null)
    }
    setBusy(false)
  }
  const pick = (id) => {
    setSpotId(id)
    const s = withPosition.find((p) => String(p.spot_id) === String(id))
    if (s) load({ spot_id: s.spot_id }, { lat: s.lat, lon: s.lon, label: s.name })
  }
  const near = () => {
    if (!navigator.geolocation) { setError("This browser can't tell where you are: pick a spot instead."); return }
    setBusy(true)
    setError('')
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const lat = p.coords.latitude.toFixed(4)
        const lon = p.coords.longitude.toFixed(4)
        setSpotId('')
        load({ lat, lon }, { lat, lon, label: 'Where you are' })
      },
      () => { setBusy(false); setError("Couldn't get your location (allowed in the browser? on HTTPS?). Pick a spot instead.") },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 })
  }
  const lookUp = async (iso) => {
    setDate(iso)
    setOne(null)
    if (!iso || !where) return
    setError('')
    try {
      setOne(fromSolunar(await api.fishingSolunar({ lat: where.lat, lon: where.lon, date: iso }), iso))
    } catch (e) {
      setError(e.message)
    }
  }
  if (!spots) return <p className="muted loading">Loading...</p>
  return (
    <section className="page fishing-tools">
      <div className="toolbar fst-bar-tools">
        <label className="field">Spot
          <select value={spotId} onChange={(e) => pick(e.target.value)} disabled={busy}>
            <option value="">Choose a spot...</option>
            {withPosition.map((s) => <option key={s.spot_id} value={s.spot_id}>{s.name}</option>)}
          </select></label>
        <button type="button" className="secondary" onClick={near} disabled={busy}>Near me</button>
      </div>
      {withPosition.length === 0 && <p className="muted small">None of your spots has a position yet: add one to a spot (or find boat ramps near you on the Spots page), or use Near me.</p>}
      {error && <p className="alert error" role="alert">{error}</p>}
      {busy && <p className="muted loading">Working out the days...</p>}
      {data && !busy && (
        <>
          <h2 className="home-card-title fst-place">{data.place ?? where?.label ?? 'Forecast'}</h2>
          {data.kept_since && <p className="alert low small">Open-Meteo couldn&apos;t be reached: the weather is the last forecast kept, from {keptAt(data.kept_since)}.</p>}
          {data.days?.length ? (
            <ul className="fst-days">{data.days.map((d) => <DayCard key={d.date} day={d} />)}</ul>
          ) : <p className="empty card">No forecast came back for that spot.</p>}
          <div className="card fst-lookup">
            <label className="field">Any other day (a past trip too)
              <input type="date" value={date} onChange={(e) => lookUp(e.target.value)} /></label>
            {one && <ul className="fst-days"><DayCard day={one} /></ul>}
          </div>
        </>
      )}
      <p className="muted small fst-note">
        Solunar tables (the moon&apos;s majors and minors) are an old angling theory, not science: your own log (Stats) shows what
        works for you. Weather{data?.water === 'fresh' ? '' : ' and tides'} from{' '}
        <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> (CC BY 4.0). Sun and moon times are our own
        calculation, good to a few minutes. Not for navigation - check the official tide tables and the weather warnings.
      </p>
    </section>
  )
}
