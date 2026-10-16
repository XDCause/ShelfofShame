import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import { RowPhoto } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import { Stars } from '../reading/readingParts.jsx'
import { ElevationProfile, HikeForm, RouteMap, Splits, hikeTime, km, metres, pace } from './hikingParts.jsx'

// One hike: the numbers, the route and its elevation profile (hover one, see where on the other),
// every kilometre's split, waypoints, your details and notes, a photo. With no id: log one by hand.
export default function HikePanel({ id: startId, onClose }) {
  const { changed } = useApp()
  const [id, setId] = useState(startId ?? null)
  const [hike, setHike] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [notes, setNotes] = useState('')
  const [saved, setSaved] = useState('')
  const [at, setAt] = useState(null)
  const show = (h) => { setHike(h); setNotes(h.notes ?? '') }
  useEffect(() => {
    if (id != null) api.hike(id).then((h) => { setHike(h); setNotes(h.notes ?? '') }).catch((e) => setError(e.message))
  }, [id])

  if (id == null) {
    return (
      <Drawer title="Log a hike" onClose={onClose}>
        <p className="panel-section small muted">For a hike without a GPS file. Recorded it on AllTrails? Import the GPX instead
          (Hiking → Hikes) and the numbers and route come from the track.</p>
        <section className="panel-section">
          <HikeForm onSaved={(h) => { show(h); setId(h.hike_id); changed() }} onCancel={onClose} />
        </section>
      </Drawer>
    )
  }
  if (!hike) return <Drawer title="Hike" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const h = hike
  const saveNotes = async () => {
    if ((h.notes ?? '') === notes) return
    show(await api.updateHike(h.hike_id, { notes }))
    setSaved('Saved ✓')
    changed()
  }
  const remove = async () => {
    if (!window.confirm(`Remove "${h.name}"? Its GPS track goes too.`)) return
    await api.deleteHike(h.hike_id)
    changed()
    onClose()
  }
  const time = h.moving_s ?? h.elapsed_s
  const alltrails = h.trail_url?.includes('alltrails.com')
  const footer = (
    <>
      {h.trail_url && <a className="button secondary" href={h.trail_url} target="_blank" rel="noreferrer">{alltrails ? 'On AllTrails ↗' : 'Trail page ↗'}</a>}
      {h.source === 'gpx' && <a className="button secondary" href={`/api/hiking/hikes/${h.hike_id}/gpx`} download>GPX file</a>}
      {h.start_lat != null && (
        <a className="button plain" target="_blank" rel="noreferrer"
          href={`https://www.openstreetmap.org/?mlat=${h.start_lat}&mlon=${h.start_lon}#map=14/${h.start_lat}/${h.start_lon}`}>Map ↗</a>
      )}
      <span className="spacer" />
      {!editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>}
      <button type="button" className="plain destructive" onClick={remove}>Remove</button>
    </>
  )
  const started = h.started_at && new Date(h.started_at).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })
  return (
    <Drawer title={h.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="section-head">
          <strong>{shortDate(h.hiked_on)}{started && ` · started ${started}`}</strong>
          <span className="hike-pills">
            {h.difficulty && <span className={`pill ${{ Easy: 'ok', Moderate: 'low', Hard: 'out' }[h.difficulty]}`}>{h.difficulty}</span>}
            {h.is_loop != null && h.source === 'gpx' && <span className="pill teal">{h.is_loop ? 'Loop' : 'One way'}</span>}
            <span className="pill">{h.source === 'gpx' ? 'From GPX' : 'Logged by hand'}</span>
          </span>
        </div>
        {h.rating && <Stars value={h.rating} />}
        <dl className="hike-numbers">
          <div><dt>Distance</dt><dd>{km(h.distance_m)}</dd></div>
          <div><dt>{h.moving_s != null && h.elapsed_s != null ? 'Moving time' : 'Time'}</dt><dd>{hikeTime(time)}</dd></div>
          {h.elapsed_s != null && <div><dt>Total time</dt><dd>{hikeTime(h.elapsed_s)}</dd></div>}
          <div><dt>Pace</dt><dd>{pace(time, h.distance_m)}</dd></div>
          <div><dt>Climb</dt><dd>↑ {metres(h.ascent_m)}{h.descent_m != null && <span className="muted"> ↓ {metres(h.descent_m)}</span>}</dd></div>
          {h.max_ele_m != null && <div><dt>Highest point</dt><dd>{metres(h.max_ele_m)}<span className="muted"> (low {metres(h.min_ele_m)})</span></dd></div>}
        </dl>
      </section>

      {h.track?.length > 1 && (
        <section className="panel-section">
          <h3 className="section-title">Route</h3>
          <RouteMap track={h.track} waypoints={h.waypoints ?? []} at={at} loop={h.is_loop} />
          <ElevationProfile track={h.track} onHover={setAt} />
          <p className="muted small">{h.points?.toLocaleString()} GPS points{h.gpx_name && ` from ${h.gpx_name}`}</p>
        </section>
      )}

      {h.splits?.length > 0 && (
        <section className="panel-section">
          <Fold title="Splits" detail={`${h.splits.length} km`}><Splits splits={h.splits} /></Fold>
        </section>
      )}

      {h.waypoints?.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Waypoints</h3>
          <ul className="hike-waypoints">
            {h.waypoints.map((w, i) => <li key={i}>{w.name ?? 'Waypoint'}{w.ele != null && <span className="muted"> · {metres(w.ele)}</span>}</li>)}
          </ul>
        </section>
      )}

      <section className="panel-section">
        {editing ? (
          <HikeForm hike={h} onSaved={(x) => { show(x); setEditing(false); changed() }} onCancel={() => setEditing(false)} />
        ) : (
          <dl className="hike-facts">
            <dt>Trail</dt><dd>{h.trail_name ?? <span className="muted">—</span>}</dd>
            <dt>Where</dt><dd>{h.location ?? <span className="muted">—</span>}</dd>
            {h.companions && <><dt>Who with</dt><dd>{h.companions}</dd></>}
            {h.weather && <><dt>Weather</dt><dd>{h.weather}</dd></>}
          </dl>
        )}
      </section>

      <section className="panel-section">
        <label className="field">Notes
          <textarea rows={3} value={notes} onChange={(e) => { setNotes(e.target.value); setSaved('') }} onBlur={saveNotes}
            placeholder="How it went, what to remember next time..." />
        </label>
        {saved && <span className="muted small">{saved}</span>}
      </section>

      <section className="panel-section">
        <RowPhoto path={`/hiking/hikes/${h.hike_id}`} url={h.photo_url} label="photo"
          onChanged={() => { api.hike(h.hike_id).then(show); changed() }} />
      </section>
    </Drawer>
  )
}
