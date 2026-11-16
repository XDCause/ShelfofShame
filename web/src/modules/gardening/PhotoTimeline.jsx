import { useState } from 'react'
import { shortDate } from '../../api.js'
import { dayLabel, firstPair, photosByDate, spanText } from './photoTimeline.js'

// A plant's photos in date order, and a before / after slider for any two of them: drag the handle to wipe from the
// earlier photo to the later one. The photos come from the plant's notes (the panel already has them).
export default function PhotoTimeline({ logs, startedOn }) {
  const photos = photosByDate(logs)
  const [pair, setPair] = useState(null)             // [beforeId, afterId] once you pick; else the oldest and newest
  const [reveal, setReveal] = useState(50)
  if (photos.length < 2) return null
  const [beforeId, afterId] = pair ?? firstPair(photos)
  const before = photos.find((p) => p.photo_id === beforeId) ?? photos[0]
  const after = photos.find((p) => p.photo_id === afterId) ?? photos[photos.length - 1]
  const pick = (which) => (e) => setPair(which === 'before' ? [Number(e.target.value), after.photo_id] : [before.photo_id, Number(e.target.value)])
  const label = (p) => [shortDate(p.on), dayLabel(p.on, startedOn)].filter(Boolean).join(' · ')
  // tapping a thumbnail moves the nearer end of the pair: "before" if it is earlier than the before photo, else "after"
  const tap = (p) => setPair(p.on <= before.on ? [p.photo_id, after.photo_id] : [before.photo_id, p.photo_id])
  return (
    <div className="garden-phototl">
      <ol className="garden-phototl-strip" aria-label="Photos in date order">
        {photos.map((p) => (
          <li key={p.photo_id}>
            <button type="button" className={`garden-phototl-thumb ${p.photo_id === before.photo_id ? 'is-before' : ''} ${p.photo_id === after.photo_id ? 'is-after' : ''}`}
              onClick={() => tap(p)} aria-label={`Photo from ${label(p)}`}>
              <img src={p.url} alt="" loading="lazy" />
            </button>
            <span className="small muted">{dayLabel(p.on, startedOn) || shortDate(p.on)}</span>
          </li>
        ))}
      </ol>
      <div className="garden-phototl-pick">
        <label className="field">Before
          <select value={before.photo_id} onChange={pick('before')}>
            {photos.map((p) => <option key={p.photo_id} value={p.photo_id}>{label(p)}</option>)}
          </select></label>
        <label className="field">After
          <select value={after.photo_id} onChange={pick('after')}>
            {photos.map((p) => <option key={p.photo_id} value={p.photo_id}>{label(p)}</option>)}
          </select></label>
      </div>
      <figure className="garden-phototl-compare">
        <div className="garden-phototl-stage">
          <img className="garden-phototl-under" src={before.url} alt={`Before: ${label(before)}`} />
          <img className="garden-phototl-over" src={after.url} alt={`After: ${label(after)}`} style={{ clipPath: `inset(0 0 0 ${reveal}%)` }} />
          <span className="garden-phototl-handle" style={{ left: `${reveal}%` }} aria-hidden="true" />
        </div>
        <input type="range" min="0" max="100" value={reveal} onChange={(e) => setReveal(Number(e.target.value))}
          aria-label="Slide between the before and after photo" className="garden-phototl-range" />
        <figcaption className="small muted">Left: {label(before)} · Right: {label(after)} · {spanText(before.on, after.on)} apart</figcaption>
      </figure>
    </div>
  )
}
