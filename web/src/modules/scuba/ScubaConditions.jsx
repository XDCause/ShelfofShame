import { useEffect, useState } from 'react'
import { api } from '../../api.js'

// Dive-day conditions: seven days of verdicts for a dive site (or where you stand) from Open-Meteo Marine through the
// API (GET /scuba/conditions): swell, waves, wind, sea temperature and the tide's highs and lows. A guide to the day,
// not a go / no-go: the dive operator, the skipper and your own judgement decide. Not for navigation.
const VERDICT = { good: 'Good', fair: 'Fair', poor: 'Poor' }
const BADGE = { good: 'ok', fair: 'low', poor: 'out' }
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
const compass = (deg) => (deg == null ? '' : COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16])
const val = (v, unit, d = 1) => (v == null ? '—' : `${Number(v).toFixed(d)}${unit}`)
const dayName = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
const timeOf = (t) => (String(t).includes('T') ? String(t).split('T')[1].slice(0, 5) : String(t).slice(0, 5))

function DayCard({ day }) {
  const tides = day.tide ?? []
  return (
    <li className="card scuba-day">
      <div className="scuba-day-head">
        <h3 className="scuba-h3">{dayName(day.date)}</h3>
        <span className={`badge ${BADGE[day.verdict] ?? ''}`}>{VERDICT[day.verdict] ?? day.verdict}</span>
      </div>
      {day.why && <p className="muted small scuba-why">{day.why}</p>}
      <dl className="scuba-numbers">
        <div><dt>Swell</dt><dd>{val(day.swell_max, ' m')}<span className="muted small"> {val(day.swell_period, ' s', 0)} {compass(day.swell_dir)}</span></dd></div>
        <div><dt>Waves</dt><dd>{val(day.wave_max, ' m')}</dd></div>
        <div><dt>Wind</dt><dd>{val(day.wind_max_kmh, ' km/h', 0)}</dd></div>
        <div><dt>Sea</dt><dd>{val(day.sst, ' °C')}</dd></div>
      </dl>
      {tides.length > 0 && (
        <ul className="scuba-tides" aria-label="Tides">
          {tides.map((t) => (
            <li key={t.time}><span className="muted">{timeOf(t.time)}</span> {t.type ?? (t.high ? 'high' : '')} {val(t.height, ' m', 2)}</li>
          ))}
        </ul>
      )}
    </li>
  )
}

export function ConditionsView() {
  const [sites, setSites] = useState(null)
  const [siteId, setSiteId] = useState('')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.scubaToolSites().then(setSites).catch(() => setSites([])) }, [])
  const withPosition = (sites ?? []).filter((s) => s.lat != null && s.lon != null)

  const load = async (params) => {
    setBusy(true)
    setError('')
    try {
      setData(await api.scubaConditions(params))
    } catch (e) {
      setError(e.message)
      setData(null)
    }
    setBusy(false)
  }
  const pick = (id) => {
    setSiteId(id)
    if (id) load({ site_id: id })
  }
  const near = () => {
    if (!navigator.geolocation) { setError("This browser can't tell where you are: pick a site instead."); return }
    setBusy(true)
    setError('')
    navigator.geolocation.getCurrentPosition(
      (p) => { setSiteId(''); load({ lat: p.coords.latitude.toFixed(4), lon: p.coords.longitude.toFixed(4) }) },
      () => { setBusy(false); setError("Couldn't get your location (allowed in the browser? on HTTPS?). Pick a site instead.") },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 })
  }
  if (!sites) return <p className="muted loading">Loading...</p>
  return (
    <section className="page scuba-tools">
      <div className="toolbar scuba-cond-bar">
        <label className="field">Dive site
          <select value={siteId} onChange={(e) => pick(e.target.value)} disabled={busy}>
            <option value="">Choose a site...</option>
            {withPosition.map((s) => <option key={s.site_id} value={s.site_id}>{s.name}</option>)}
          </select></label>
        <button type="button" className="secondary" onClick={near} disabled={busy}>Near me</button>
      </div>
      {withPosition.length === 0 && <p className="muted small">None of your sites has a position yet: add one to a site (or find sites near you on the Sites page), or use Near me.</p>}
      {error && <p className="alert error" role="alert">{error}</p>}
      {busy && <p className="muted loading">Asking Open-Meteo...</p>}
      {data && !busy && (
        <>
          <h2 className="home-card-title scuba-place">{data.place ?? 'Conditions'}</h2>
          {data.kept_since && <p className="alert low small">Open-Meteo couldn&apos;t be reached: this is the last forecast kept, from {data.kept_since}.</p>}
          {data.days?.length ? (
            <ul className="scuba-days">{data.days.map((d) => <DayCard key={d.date} day={d} />)}</ul>
          ) : <p className="empty card">No forecast came back for that spot (the marine forecast covers the sea, not the shore).</p>}
        </>
      )}
      <p className="muted small">
        Marine forecast by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>. A guide to the day, not a go / no-go -
        your operator and skipper decide. Not for navigation.
      </p>
    </section>
  )
}
