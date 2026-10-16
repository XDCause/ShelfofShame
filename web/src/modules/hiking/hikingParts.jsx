import { useEffect, useRef, useState } from 'react'
import { api, duration } from '../../api.js'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// The Hiking hobby's shared pieces: number formats, the elevation profile, the photo viewer, the
// GPX import and the hike form. (The map is HikeMap.jsx.)

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

// Height along the way: distance across, elevation up. Hovering shows the distance, height and
// time at that point, and marks it on the map (onHover gets the track index). `marks` = your photos
// and landmarks at their distance along the track (a photo's mark opens it).
export function ElevationProfile({ track, onHover, marks = [] }) {
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
        {marks.filter((m) => m.along != null).map((m) => {
          let near = idx[0]
          for (const i of idx) if (Math.abs(track[i][4] - m.along) < Math.abs(track[near][4] - m.along)) near = i
          const style = { left: `${X(m.along)}%`, top: `${Y(track[near][2])}%` }
          return m.onOpen
            ? <button key={m.key} type="button" className="hike-mark photo" style={style} title={m.title} aria-label={m.title} onClick={m.onOpen} />
            : <span key={m.key} className="hike-mark landmark" style={style} title={m.title} />
        })}
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

// One of your photos, big, with what's known about it: its caption (saved when you leave the box),
// when and where on the track it was taken, and the next / previous ones. Escape closes it (only it).
export function PhotoViewer({ photos, index, setIndex, onCaption, onDelete, onClose }) {
  const box = useRef(null)
  const p = photos[index]
  const [caption, setCaption] = useState(p?.caption ?? '')
  useEffect(() => { setCaption(p?.caption ?? '') }, [p?.photo_id, p?.caption])
  useEffect(() => { box.current?.focus() }, [])
  if (!p) return null
  const go = (n) => setIndex((index + n + photos.length) % photos.length)
  const keys = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); onClose() }
    else if (e.key === 'ArrowRight' && e.target.tagName !== 'INPUT') go(1)
    else if (e.key === 'ArrowLeft' && e.target.tagName !== 'INPUT') go(-1)
  }
  const when = p.taken_at && new Date(p.taken_at).toLocaleString('en-AU', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
  const where = p.along_m != null ? `${km(p.along_m)} along the track` : p.lat != null ? 'off the track' : 'no location in the photo'
  return (
    <div className="hike-viewer" role="dialog" aria-modal="true" aria-label="Photo" tabIndex={-1} ref={box} onKeyDown={keys}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="hike-viewer-card">
        <img src={p.url} alt={p.caption ?? ''} />
        <div className="hike-viewer-bar">
          {photos.length > 1 && <button type="button" className="plain" onClick={() => go(-1)} aria-label="Previous photo">‹</button>}
          <input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Add a caption"
            aria-label="Caption" onBlur={() => caption !== (p.caption ?? '') && onCaption(p, caption)} />
          {photos.length > 1 && <button type="button" className="plain" onClick={() => go(1)} aria-label="Next photo">›</button>}
        </div>
        <p className="muted small">{[when, where, p.located === 'time' && 'placed by the time it was taken',
          `${index + 1} of ${photos.length}`].filter(Boolean).join(' · ')}</p>
        <div className="button-row">
          <button type="button" className="plain destructive" onClick={() => onDelete(p)}>Remove photo</button>
          <span className="spacer" />
          <button type="button" className="secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
