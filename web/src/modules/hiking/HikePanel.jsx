import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import PhotoPick from '../../components/PhotoPick.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'
import { useApp } from '../../core/app-context.js'
import { Stars } from '../reading/readingParts.jsx'
import { readExif } from './exif.js'
import HikeMap from './HikeMap.jsx'
import { ElevationProfile, HikeForm, PhotoViewer, Splits, hikeTime, km, metres, pace } from './hikingParts.jsx'

// One hike: the numbers; the route on a topographic or satellite map with its elevation profile (hover
// one, see where on the other); your photos, each pinned where it was taken; landmarks near the track
// and photos other people took there (Wikimedia Commons); every kilometre's split; your details and
// notes. With no id: log one by hand.
export default function HikePanel({ id: startId, onClose }) {
  const { changed } = useApp()
  const [id, setId] = useState(startId ?? null)
  const [hike, setHike] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [notes, setNotes] = useState('')
  const [saved, setSaved] = useState('')
  const [at, setAt] = useState(null)
  const [viewing, setViewing] = useState(null)        // index into hike.photos
  const [uploading, setUploading] = useState('')
  const show = useCallback((h) => { setHike(h); setNotes(h.notes ?? '') }, [])
  const reload = useCallback(() => api.hike(id).then(setHike), [id])
  useEffect(() => {
    if (id != null) api.hike(id).then(show).catch((e) => setError(e.message))
  }, [id, show])
  // Landmarks are looked up in the background after an import: check back until they're in.
  const looking = hike?.landmarks_looking
  useEffect(() => {
    if (!looking) return undefined
    const t = setTimeout(() => api.hike(id).then(setHike).catch(() => {}), 3000)
    return () => clearTimeout(t)
  }, [looking, hike, id])
  const openPhoto = useCallback((p) => setViewing(hike?.photos.findIndex((x) => x.photo_id === p.photo_id) ?? null), [hike])

  if (id == null) {
    return (
      <Drawer title="Log a hike" onClose={onClose}>
        <p className="panel-section small muted">For a hike without a GPS file. Recorded it on AllTrails? Import the GPX instead
          (Hiking → Hikes) and the numbers, map and landmarks come from the track.</p>
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
    if (!window.confirm(`Remove "${h.name}"? Its GPS track and photos go too.`)) return
    await api.deleteHike(h.hike_id)
    changed()
    onClose()
  }
  // Each photo: where and when it was taken (EXIF, read before shrinking drops it), then shrunk and sent.
  const addPhotos = async (files) => {
    setError('')
    const failed = []
    for (const [i, file] of [files].flat().entries()) {
      setUploading(`Adding ${i + 1} of ${[files].flat().length}...`)
      try {
        const exif = await readExif(file)
        await api.addHikePhoto(h.hike_id, await shrink(file, 1600), exif)
      } catch (e) {
        failed.push(`${file.name ?? 'photo'}: ${e.message}`)
      }
    }
    setUploading('')
    if (failed.length) setError(failed.join(' · '))
    await reload()
    changed()
  }
  const caption = async (p, text) => { await api.updateHikePhoto(p.photo_id, text); reload() }
  const removePhoto = async (p) => {
    await api.deleteHikePhoto(p.photo_id)
    setViewing(null)
    await reload()
    changed()
  }
  const lookAgain = async () => { await api.lookAgainHike(h.hike_id); reload() }

  const time = h.moving_s ?? h.elapsed_s
  const alltrails = h.trail_url?.includes('alltrails.com')
  const landmarks = h.landmarks ?? []
  const marks = [
    ...h.photos.map((p) => ({ key: `p${p.photo_id}`, along: p.along_m, title: p.caption ?? 'Your photo', onOpen: () => openPhoto(p) })),
    ...landmarks.map((lm) => ({ key: lm.osm, along: lm.along_m, title: lm.name ?? lm.label })),
  ]
  const footer = (
    <>
      {h.trail_url && <a className="button secondary" href={h.trail_url} target="_blank" rel="noreferrer">{alltrails ? 'On AllTrails ↗' : 'Trail page ↗'}</a>}
      {h.source === 'gpx' && <a className="button secondary" href={`/api/hiking/hikes/${h.hike_id}/gpx`} download>GPX file</a>}
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
          {time != null && <div><dt>{h.moving_s != null && h.elapsed_s != null ? 'Moving time' : 'Time'}</dt><dd>{hikeTime(time)}</dd></div>}
          {h.elapsed_s != null && <div><dt>Total time</dt><dd>{hikeTime(h.elapsed_s)}</dd></div>}
          {time != null && <div><dt>Pace</dt><dd>{pace(time, h.distance_m)}</dd></div>}
          {h.ascent_m != null && <div><dt>Climb</dt><dd>↑ {metres(h.ascent_m)}{h.descent_m != null && <span className="hike-down">↓ {metres(h.descent_m)} down</span>}</dd></div>}
          {h.max_ele_m != null && <div><dt>Highest point</dt><dd>{metres(h.max_ele_m)}<span className="muted"> (low {metres(h.min_ele_m)})</span></dd></div>}
        </dl>
      </section>

      {h.track?.length > 1 && (
        <section className="panel-section">
          <HikeMap track={h.track} waypoints={h.waypoints ?? []} photos={h.photos} landmarks={landmarks} at={at} loop={h.is_loop}
            onPhoto={openPhoto} />
          <ElevationProfile track={h.track} onHover={setAt} marks={marks} />
          <p className="muted small">{h.points?.toLocaleString()} GPS points{h.gpx_name && ` from ${h.gpx_name}`}
            {h.source === 'gpx' && time == null && ' · no times in this file (a planned route, not a recording), so no time or pace'}</p>
        </section>
      )}

      <section className="panel-section">
        <div className="section-head">
          <h3 className="section-title">Your photos</h3>
          {uploading ? <span className="muted small">{uploading}</span>
            : <PhotoPick onFile={addPhotos} multiple className="plain small" label="Add photos" />}
        </div>
        {h.photos.length === 0 ? (
          <p className="muted small">Add photos from the hike: ones from your phone go on the map where you took them (from the
            location saved in the photo, or the time it was taken).</p>
        ) : (
          <ul className="hike-gallery">
            {h.photos.map((p, i) => (
              <li key={p.photo_id}>
                <button type="button" className="hike-gallery-item" onClick={() => setViewing(i)} aria-label={`Open ${p.caption ?? `photo ${i + 1}`}`}>
                  <img src={p.url} alt="" loading="lazy" />
                  {(p.caption || p.along_m != null) && <span className="hike-gallery-caption">{p.caption ?? km(p.along_m)}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && <p className="alert error small">{error}</p>}
      </section>

      {h.track?.length > 1 && (
        <section className="panel-section">
          <div className="section-head">
            <h3 className="section-title">Along the way</h3>
            {looking ? <span className="muted small">Looking on OpenStreetMap...</span>
              : <button type="button" className="plain small" onClick={lookAgain}>Look again</button>}
          </div>
          {h.landmarks_error && <p className="alert error small">{h.landmarks_error}</p>}
          {!looking && h.landmarks_at && landmarks.length === 0 && <p className="muted small">No landmarks near the track on OpenStreetMap.</p>}
          {landmarks.length > 0 && (
            <ul className="hike-landmarks">
              {landmarks.map((lm) => (
                <li key={lm.osm}>
                  {lm.photo ? (
                    <a href={lm.photo.page} target="_blank" rel="noreferrer" className="hike-landmark-photo">
                      <img src={lm.photo.thumb} alt="" loading="lazy" referrerPolicy="no-referrer" /></a>
                  ) : <span className="hike-landmark-dot" aria-hidden="true" />}
                  <span className="grow">
                    <span className="item-title">{lm.name ?? lm.label}</span>
                    <span className="item-meta">{[lm.name && lm.label, lm.ele != null && metres(lm.ele), `${km(lm.along_m)} in`,
                      lm.off_m > 30 && `${metres(lm.off_m)} off the track`].filter(Boolean).join(' · ')}</span>
                    {lm.photo && <span className="hike-credit">{[lm.photo.author, lm.photo.licence].filter(Boolean).join(' · ')}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {h.nearby_photos?.length > 0 && (
            <Fold title="Photos other people took here" detail={`${h.nearby_photos.length} on Wikimedia Commons`}>
              <ul className="hike-gallery">
                {h.nearby_photos.map((p) => (
                  <li key={p.title}>
                    <a className="hike-gallery-item" href={p.page} target="_blank" rel="noreferrer">
                      <img src={p.thumb} alt={p.title.replace(/^File:|\.\w+$/g, '')} loading="lazy" referrerPolicy="no-referrer" />
                      <span className="hike-gallery-caption">{[p.author, p.licence].filter(Boolean).join(' · ') || 'Wikimedia Commons'}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </Fold>
          )}
          <p className="muted small">Landmarks © OpenStreetMap contributors · photos from Wikimedia Commons (each under its own licence).</p>
        </section>
      )}

      <HikeGear hike={h} onSaved={(x) => { setHike(x); changed() }} onLeave={onClose} />

      {h.splits?.length > 0 && (
        <section className="panel-section">
          <Fold title="Splits" detail={`${h.splits.length} km`}><Splits splits={h.splits} /></Fold>
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
            {h.waypoints?.length > 0 && <><dt>Waypoints</dt><dd>{h.waypoints.map((w) => w.name ?? 'Waypoint').join(', ')}</dd></>}
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

      {viewing != null && h.photos[viewing] && (
        <PhotoViewer photos={h.photos} index={viewing} setIndex={setViewing} onCaption={caption} onDelete={removePhoto}
          onClose={() => setViewing(null)} />
      )}
    </Drawer>
  )
}

// The gear you took: tick it from your hiking gear (in use, plus anything already on this hike), or
// "Same as last hike". Each piece then counts this hike's km (Hiking → Gear).
function HikeGear({ hike: h, onSaved, onLeave }) {
  const [all, setAll] = useState(null)
  const [picking, setPicking] = useState(false)
  const [picked, setPicked] = useState([])
  const [error, setError] = useState('')
  useEffect(() => { api.listGear('hiking').then(setAll).catch((e) => setError(e.message)) }, [h.hike_id])
  const save = async (ids) => {
    try {
      onSaved(await api.setHikeGear(h.hike_id, ids))
      setPicking(false)
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }
  const on = new Set(h.gear.map((g) => g.gear_id))
  const choices = (all ?? []).filter((g) => on.has(g.gear_id) || !['Wanted', 'Retired'].includes(g.condition))
  const start = () => { setPicked([...on]); setPicking(true) }
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Gear used</h3>
        {!picking && choices.length > 0 && (
          <span className="button-row">
            {h.gear.length === 0 && h.last_gear_ids.length > 0 && (
              <button type="button" className="plain small" onClick={() => save(h.last_gear_ids)}>Same as last hike</button>
            )}
            <button type="button" className="plain small" onClick={start}>{h.gear.length ? 'Change' : 'Choose gear'}</button>
          </span>
        )}
      </div>
      {all && choices.length === 0 && (
        <p className="muted small">Add your boots, pack and poles on <Link to="/hiking/gear" onClick={onLeave}>Hiking → Gear</Link>, then
          tick what you took - each piece adds up its hikes and kilometres.</p>
      )}
      {!picking && h.gear.length > 0 && (
        <ul className="hike-gear-chips">
          {h.gear.map((g) => <li key={g.gear_id} className="chip">{g.name}{g.kind && <span className="muted"> · {g.kind}</span>}</li>)}
        </ul>
      )}
      {picking && (
        <fieldset className="hike-gear-pick" aria-label="Gear used on this hike">
          {choices.map((g) => (
            <label key={g.gear_id} className="check-row">
              <input type="checkbox" checked={picked.includes(g.gear_id)}
                onChange={(e) => setPicked((p) => (e.target.checked ? [...p, g.gear_id] : p.filter((x) => x !== g.gear_id)))} />
              <span>{g.name}<span className="muted small">{[g.kind, g.condition !== 'Good' && g.condition].filter(Boolean).map((x) => ` · ${x}`).join('')}</span></span>
            </label>
          ))}
          <div className="button-row">
            <button type="button" className="primary small" onClick={() => save(picked)}>Save gear</button>
            <button type="button" className="plain small" onClick={() => setPicking(false)}>Cancel</button>
          </div>
        </fieldset>
      )}
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}
