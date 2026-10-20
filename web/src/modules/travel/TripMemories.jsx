import { useState } from 'react'
import { api, today } from '../../api.js'
import FitTextarea from '../../components/FitTextarea.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'
import { useApp } from '../../core/app-context.js'
import { readExif } from '../hiking/exif.js'
import TravelMap from './TravelMap.jsx'
import { dayLabel, tripDays } from './TripSections.jsx'
import { countryName, flag } from './travelParts.jsx'

// A trip's places (its stops, in order: the route) and its journal - a note for each day and the photos you took
// (placed on the map when they carry GPS, and on the day they were taken).

const STATUS_TONE = { Been: 'ok', Planned: 'tint', Want: 'purple' }
const STATUS_NAME = { Been: 'Been', Planned: 'Going', Want: 'Want to go' }

export function PlacesTab({ t, onClose, onTrip }) {
  const { openPanel, showToast } = useApp()
  const [viewing, setViewing] = useState(null)
  const open = (props) => { onClose(); openPanel('tplace', { tripId: t.trip_id, ...props }) }
  const move = async (i, by) => {
    const ids = t.places.map((p) => p.place_id)
    ;[ids[i], ids[i + by]] = [ids[i + by], ids[i]]
    try { onTrip(await api.orderTripStops(t.trip_id, ids)) } catch (e) { showToast(e.message) }
  }
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Places{t.places.length > 0 && ` · ${t.places.length}`}</h3>
        <button type="button" className="primary small" onClick={() => open({})}>+ Add a place</button>
      </div>
      {(t.places.some((p) => p.lat != null) || t.photos.some((p) => p.lat != null)) && (
        <TravelMap places={t.places} photos={t.photos} route={t.places.filter((p) => p.lat != null).length > 1}
          label={`Map of ${t.name}`} onPlace={(p) => open({ id: p.place_id })} onPhoto={setViewing} />
      )}
      {viewing && <PhotoView p={viewing} onClose={() => setViewing(null)} onTrip={onTrip} />}
      {t.places.length === 0 ? <p className="muted small">The towns, sights, beaches and campsites on this trip - in the order you go
        (a road trip's route). Each goes on your map of everywhere you've been.</p> : (
        <ol className="list plain-list trip-stops">{t.places.map((p, i) => (
          <li key={p.place_id}>
            <span className="trip-stop-n" aria-hidden="true">{i + 1}</span>
            <button type="button" className="row-button grow" onClick={() => open({ id: p.place_id })}>
              <span className="grow">
                <span className="item-title">{flag(p.country)} {p.name}</span>
                <span className="item-meta">{[p.kind, p.region || countryName(p.country), p.visit_on && dayLabel(p.visit_on, t)].filter(Boolean).join(' · ')}</span>
              </span>
              <span className={`pill ${STATUS_TONE[p.shown]}`}>{STATUS_NAME[p.shown]}</span>
            </button>
            <span className="trip-stop-move">
              <button type="button" className="plain small" disabled={i === 0} aria-label={`Move ${p.name} earlier`} onClick={() => move(i, -1)}>↑</button>
              <button type="button" className="plain small" disabled={i === t.places.length - 1} aria-label={`Move ${p.name} later`} onClick={() => move(i, 1)}>↓</button>
            </span>
          </li>))}</ol>
      )}
    </section>
  )
}

export function JournalTab({ t, onTrip }) {
  const { showToast } = useApp()
  const [uploading, setUploading] = useState('')
  const [viewing, setViewing] = useState(null)
  // The days so far (all of them once it's over); days with a note or photos outside the dates too.
  const days = [...new Set([...tripDays(t).filter((d) => t.phase === 'past' || d <= today()),
    ...t.entries.map((e) => e.day), ...t.photos.filter((p) => p.day).map((p) => p.day)])].sort()
  // A photo with no time of its own (a screenshot, an edited copy) goes on today, while the trip's on.
  const fallback = tripDays(t).includes(today()) ? today() : null
  const addPhotos = async (files) => {
    const failed = []
    let next = null
    for (const [i, file] of [...files].entries()) {
      setUploading(`Adding ${i + 1} of ${files.length}...`)
      try {
        const exif = await readExif(file)
        next = await api.addTripPhoto(t.trip_id, await shrink(file, 1600), { ...exif, day: exif.taken ? null : fallback })
      } catch (e) {
        failed.push(`${file.name ?? 'photo'}: ${e.message}`)
      }
    }
    setUploading('')
    if (next) onTrip(next)
    if (failed.length) showToast(failed.join(' · '))
  }
  const undated = t.photos.filter((p) => !p.day)
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Journal</h3>
        <label className="button secondary small">
          {uploading || '+ Add photos'}
          <input type="file" accept="image/*" multiple hidden disabled={!!uploading}
            onChange={(e) => { const f = [...e.target.files]; e.target.value = ''; if (f.length) addPhotos(f) }} />
        </label>
      </div>
      {t.phase === 'upcoming' || t.phase === 'idea' ? (
        <p className="muted small">Once the trip starts, each day gets a page here: what you did, and your photos (they find their own day,
          and their place on the map, from the camera's details).</p>
      ) : days.length === 0 && <p className="muted small">Give the trip dates to keep a journal of it.</p>}
      {days.map((d) => (
        <JournalDay key={d} t={t} day={d} photos={t.photos.filter((p) => p.day === d)} onTrip={onTrip} onPhoto={setViewing} />
      ))}
      {undated.length > 0 && (
        <div className="trip-day">
          <h4 className="trip-day-head">Photos with no date</h4>
          <Thumbs photos={undated} onPhoto={setViewing} />
        </div>
      )}
      {viewing && <PhotoView p={t.photos.find((p) => p.photo_id === viewing.photo_id) ?? viewing} days={tripDays(t)} trip={t}
        onClose={() => setViewing(null)} onTrip={onTrip} />}
    </section>
  )
}

function JournalDay({ t, day, photos, onTrip, onPhoto }) {
  const { showToast } = useApp()
  const saved = t.entries.find((e) => e.day === day)?.text ?? ''
  const [text, setText] = useState(saved)
  const [state, setState] = useState('')
  const save = async () => {
    if (text.trim() === saved) return
    setState('Saving...')
    try {
      onTrip(await api.saveTripEntry(t.trip_id, day, text))
      setState('Saved ✓')
    } catch (e) {
      setState('')
      showToast(e.message)
    }
  }
  return (
    <div className={`trip-day${day === today() ? ' today' : ''}`}>
      <h4 className="trip-day-head">{dayLabel(day, t)}{state && <span className="muted small"> {state}</span>}</h4>
      <FitTextarea value={text} onChange={(e) => { setText(e.target.value); setState('') }} onBlur={save}
        placeholder="What did you do? What was good?" aria-label={`Journal for ${dayLabel(day, t)}`} />
      {photos.length > 0 && <Thumbs photos={photos} onPhoto={onPhoto} />}
    </div>
  )
}

function Thumbs({ photos, onPhoto }) {
  return (
    <ul className="trip-thumbs">{photos.map((p) => (
      <li key={p.photo_id}><button type="button" onClick={() => onPhoto(p)} aria-label={p.caption ?? 'Photo'}>
        <img src={p.url} alt={p.caption ?? ''} loading="lazy" /></button></li>))}</ul>
  )
}

function PhotoView({ p, onClose, onTrip, days = [], trip = null }) {
  const { showToast } = useApp()
  const [caption, setCaption] = useState(p.caption ?? '')
  const call = async (fn, close = false) => {
    try { onTrip(await fn()); if (close) onClose() } catch (e) { showToast(e.message) }
  }
  return (
    <figure className="trip-photo-view card">
      <img src={p.url} alt={p.caption ?? ''} />
      <figcaption>
        <input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Caption" aria-label="Caption" maxLength={1000}
          onBlur={() => caption !== (p.caption ?? '') && call(() => api.updateTripPhoto(p.photo_id, { caption }))} />
        {trip && days.length > 0 && (
          <select value={p.day ?? ''} aria-label="Day" onChange={(e) => call(() => api.updateTripPhoto(p.photo_id, { day: e.target.value || null }))}>
            <option value="">No day</option>
            {days.map((d) => <option key={d} value={d}>{dayLabel(d, trip)}</option>)}
          </select>
        )}
        <span className="spacer" />
        <button type="button" className="plain destructive small" onClick={() => call(() => api.deleteTripPhoto(p.photo_id), true)}>Remove</button>
        <button type="button" className="plain small" onClick={onClose}>Close</button>
      </figcaption>
    </figure>
  )
}
