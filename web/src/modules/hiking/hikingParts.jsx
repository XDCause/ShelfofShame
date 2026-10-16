import { useState } from 'react'
import { api, duration } from '../../api.js'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// The Hiking hobby's shared pieces: number formats, the route drawn from the GPS track, the
// elevation profile, the GPX import and the hike form.

export const useHikingSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`hiking-summary-${refreshKey}`, () => api.hikingSummary())
}

export const km = (m) => (m == null ? '—' : `${(m / 1000).toFixed(m >= 100000 ? 0 : 1)} km`)
export const metres = (m) => (m == null ? '—' : `${Math.round(m).toLocaleString()} m`)
export const hikeTime = (s) => (s == null ? '—' : duration(s / 60))
// Minutes per kilometre: 742 s for 1000 m -> "12:22 /km"
export const pace = (s, m) => {
  if (!s || !m || m < 100) return '—'
  const perKm = Math.round(s / (m / 1000))
  return `${Math.floor(perKm / 60)}:${String(perKm % 60).padStart(2, '0')} /km`
}
export const hikeMeta = (h) => [km(h.distance_m), h.ascent_m != null && `↑ ${metres(h.ascent_m)}`,
  (h.moving_s ?? h.elapsed_s) != null && hikeTime(h.moving_s ?? h.elapsed_s)].filter((x) => x && x !== '—').join(' · ')

// The route, drawn from the track's points: east-west distances shrink away from the equator, so
// longitude is scaled by cos(latitude) to keep the shape true. North is up. `at` = a point to mark
// (where the elevation profile is being hovered).
export function RouteMap({ track, waypoints = [], at = null, loop = false }) {
  if (!track || track.length < 2) return null
  const lat0 = (track.reduce((a, p) => a + p[0], 0) / track.length) * (Math.PI / 180)
  const xy = ([lat, lon]) => [lon * Math.cos(lat0), -lat]
  const pts = track.map(xy)
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1])
  const minX = Math.min(...xs), minY = Math.min(...ys)
  const span = Math.max(Math.max(...xs) - minX, Math.max(...ys) - minY) || 1e-6
  const S = ([x, y]) => [((x - minX) / span) * 100, ((y - minY) / span) * 100]
  const scaled = pts.map(S)
  const w = Math.max(...scaled.map((p) => p[0])), h = Math.max(...scaled.map((p) => p[1]))
  const pad = 6
  // A scale bar: a round distance about a quarter of the way across.
  const metresAcross = (span * Math.PI / 180) * 6371000
  const bar = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000].find((m) => m >= metresAcross / 5) ?? 50000
  const barLen = (bar / metresAcross) * 100
  const mark = (p, cls, r, title) => {
    const [x, y] = S(xy(p))
    return <circle className={cls} cx={x} cy={y} r={r}>{title && <title>{title}</title>}</circle>
  }
  return (
    <figure className="hike-map-frame">
      <svg className="hike-map" viewBox={`${-pad} ${-pad} ${w + pad * 2} ${h + pad * 2 + 6}`} role="img"
        aria-label={`The route${loop ? ', a loop' : ''}`}>
        <polyline className="hike-route-casing" points={scaled.map((p) => p.join(',')).join(' ')} vectorEffect="non-scaling-stroke" />
        <polyline className="hike-route" points={scaled.map((p) => p.join(',')).join(' ')} vectorEffect="non-scaling-stroke" />
        {waypoints.map((wp, i) => <g key={i}>{mark([wp.lat, wp.lon], 'hike-waypoint', 1.6, wp.name ?? 'Waypoint')}</g>)}
        {!loop && mark(track[track.length - 1], 'hike-end', 2.2, 'Finish')}
        {mark(track[0], 'hike-start', 2.2, loop ? 'Start and finish' : 'Start')}
        {at != null && track[at] && mark(track[at], 'hike-here', 2.4)}
        <g className="hike-scale" transform={`translate(0 ${h + pad + 2})`}>
          <line x1="0" x2={barLen} y1="0" y2="0" vectorEffect="non-scaling-stroke" />
          <text x={barLen + 1.5} y="1.2">{bar >= 1000 ? `${bar / 1000} km` : `${bar} m`}</text>
        </g>
      </svg>
      <figcaption className="hike-map-key">
        <span><i className="hike-key-start" /> {loop ? 'Start / finish' : 'Start'}</span>
        {!loop && <span><i className="hike-key-end" /> Finish</span>}
        {waypoints.length > 0 && <span><i className="hike-key-waypoint" /> Waypoint</span>}
        <span className="muted">North is up</span>
      </figcaption>
    </figure>
  )
}

// Height along the way: distance across, elevation up. Hovering shows the distance, height and
// time at that point, and marks it on the route (onHover gets the track index).
export function ElevationProfile({ track, onHover }) {
  const [hover, setHover] = useState(null)
  const idx = track ? track.map((p, i) => i).filter((i) => track[i][2] != null) : []
  if (idx.length < 2) return null
  const d1 = track[idx[idx.length - 1]][4] || 1
  const eles = idx.map((i) => track[i][2])
  const raw = [Math.min(...eles), Math.max(...eles)]
  const pad = Math.max(10, (raw[1] - raw[0]) * 0.1)
  const lo = Math.floor((raw[0] - pad) / 10) * 10, hi = Math.ceil((raw[1] + pad) / 10) * 10
  const X = (d) => (100 * d) / d1
  const Y = (e) => 100 - (100 * (e - lo)) / (hi - lo || 1)
  const line = idx.map((i) => `${X(track[i][4])},${Y(track[i][2])}`).join(' ')
  const pick = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const d = ((e.clientX - box.left) / box.width) * d1
    let best = idx[0]
    for (const i of idx) if (Math.abs(track[i][4] - d) < Math.abs(track[best][4] - d)) best = i
    setHover(best)
    onHover?.(best)
  }
  const leave = () => { setHover(null); onHover?.(null) }
  const p = hover != null ? track[hover] : null
  return (
    <figure className="hike-profile" aria-label={`Elevation: ${Math.round(raw[0])} to ${Math.round(raw[1])} m over ${km(d1)}`}>
      <div className="hike-profile-plot">
        <span className="hike-profile-axis top">{hi} m</span>
        <span className="hike-profile-axis bottom">{lo} m</span>
        <svg className="hike-profile-svg" viewBox="0 0 100 100" preserveAspectRatio="none" role="presentation"
          onMouseMove={pick} onMouseLeave={leave}>
          <polygon className="hike-profile-area" points={`0,100 ${line} 100,100`} />
          <polyline className="hike-profile-line" points={line} vectorEffect="non-scaling-stroke" />
          {p && <line className="hike-profile-cross" x1={X(p[4])} x2={X(p[4])} y1="0" y2="100" vectorEffect="non-scaling-stroke" />}
        </svg>
        {p && (
          <span className="chart-tip hike-profile-tip" role="tooltip" style={{ left: `${Math.min(85, Math.max(15, X(p[4])))}%` }}>
            <strong>{metres(p[2])}</strong> high<br />
            <span>{km(p[4])}{p[3] != null && ` · ${hikeTime(p[3])} in`}</span>
          </span>
        )}
      </div>
      <div className="hike-profile-labels" aria-hidden="true"><span>0 km</span><span>{km(d1)}</span></div>
    </figure>
  )
}

// Every kilometre: moving time, pace, metres up and down.
export function Splits({ splits }) {
  if (!splits?.length) return null
  const fastest = Math.min(...splits.filter((s) => s.seconds && s.metres >= 900).map((s) => s.seconds / s.metres))
  return (
    <table className="hike-splits">
      <thead><tr><th scope="col">Km</th><th scope="col">Time</th><th scope="col">Pace</th><th scope="col">Up</th><th scope="col">Down</th></tr></thead>
      <tbody>
        {splits.map((s) => (
          <tr key={s.km} className={s.seconds && s.seconds / s.metres === fastest ? 'fastest' : ''}>
            <td>{s.metres < 950 ? `${s.km - 1}–${(s.km - 1 + s.metres / 1000).toFixed(1)}` : s.km}</td>
            <td>{s.seconds == null ? '—' : hikeTime(s.seconds)}</td>
            <td>{pace(s.seconds, s.metres)}</td>
            <td>{metres(s.ascent)}</td>
            <td>{metres(s.descent)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// GPX files from AllTrails (or any GPS app): pick one or many; each is read on the server and
// becomes a hike. A file imported before is skipped (and says so).
export function GpxImport({ compact = false }) {
  const { changed, openPanel } = useApp()
  const [results, setResults] = useState([])
  const [busy, setBusy] = useState('')
  const pick = async (e) => {
    const files = [...(e.target.files ?? [])]
    e.target.value = ''
    if (!files.length) return
    const done = []
    for (const [i, file] of files.entries()) {
      setBusy(files.length > 1 ? `Importing ${i + 1} of ${files.length}...` : 'Importing...')
      try {
        const h = await api.importHike(file)
        done.push({ file: file.name, hike: h, status: h.duplicate ? 'duplicate' : 'added' })
      } catch (err) {
        done.push({ file: file.name, status: 'error', message: err.message })
      }
    }
    setBusy('')
    setResults(done)
    if (done.some((r) => r.status === 'added')) changed()
    if (files.length === 1 && done[0].hike) openPanel('hike', { id: done[0].hike.hike_id })
  }
  return (
    <div className="gpx-import">
      {!compact && (
        <p className="small muted">On the AllTrails website, open one of your recordings and download it as a <strong>GPX</strong> file.
          Then pick the file here - or several at once. GPX files from Strava, Garmin or any GPS app work too. Distance, climb,
          times, splits and the route are worked out from the track.</p>
      )}
      <label className="button secondary">{busy || 'Choose GPX files'}
        <input type="file" accept=".gpx,application/gpx+xml" multiple onChange={pick} hidden disabled={!!busy} /></label>
      {results.length > 0 && (
        <ul className="gpx-results">
          {results.map((r) => (
            <li key={r.file} className={r.status}>
              {r.status === 'error' ? <><strong>{r.file}</strong>: {r.message}</> : (
                <button type="button" className="plain small" onClick={() => openPanel('hike', { id: r.hike.hike_id })}>
                  {r.status === 'added' ? 'Added' : 'Already imported'}: {r.hike.name} · {km(r.hike.distance_m)}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const RATINGS = [5, 4, 3, 2, 1].map((n) => [String(n), '★'.repeat(n)])
export const DETAIL_FIELDS = [
  { name: 'name', label: 'Name', required: true, wide: true },
  { name: 'hiked_on', label: 'Date', type: 'date', required: true },
  { name: 'trail_name', label: 'Trail', placeholder: 'As on AllTrails' },
  { name: 'location', label: 'Where', placeholder: 'Park, town or region' },
  { name: 'difficulty', label: 'Difficulty', type: 'select', options: ['Easy', 'Moderate', 'Hard'] },
  { name: 'rating', label: 'Your rating', type: 'select', options: RATINGS },
  { name: 'companions', label: 'Who with' },
  { name: 'weather', label: 'Weather' },
  { name: 'trail_url', label: 'Trail link', type: 'url', wide: true, placeholder: 'https://www.alltrails.com/trail/...' },
]
// Only for hikes logged by hand: a GPX file's numbers come from the track.
const NUMBER_FIELDS = [
  { name: 'distance_km', label: 'Distance (km)', type: 'number', step: 0.1 },
  { name: 'moving_min', label: 'Time (minutes)', type: 'number' },
  { name: 'ascent_m', label: 'Climb (m)', type: 'number' },
]

// Add a hike by hand (no hike yet) or change one's details.
export function HikeForm({ hike, onSaved, onCancel }) {
  const manual = !hike || hike.source === 'manual'
  const fields = [...DETAIL_FIELDS, ...(manual ? NUMBER_FIELDS : []), ...(hike ? [] : [{ name: 'notes', label: 'Notes', type: 'textarea' }])]
  const record = hike && {
    ...hike, rating: hike.rating, distance_km: hike.distance_m != null ? hike.distance_m / 1000 : null,
    moving_min: hike.moving_s != null ? Math.round(hike.moving_s / 60) : null,
  }
  const { form, set, payload } = useRecordForm(fields, record, { hiked_on: new Date().toLocaleDateString('en-CA') })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    const p = payload()
    if (p.rating != null) p.rating = Number(p.rating)
    setBusy(true)
    setError('')
    try {
      onSaved(hike ? await api.updateHike(hike.hike_id, p) : await api.addHike(p))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <form className="hike-form" onSubmit={submit}>
      <RecordFields fields={fields} form={form} set={set} />
      {error && <p className="alert error small">{error}</p>}
      <div className="button-row">
        <button type="submit" className="primary" disabled={busy}>{hike ? 'Save' : 'Add hike'}</button>
        {onCancel && <button type="button" className="plain" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}
