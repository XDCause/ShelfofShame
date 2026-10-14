import { useState } from 'react'
import { api, logPhotoUrl, shortDate, today } from '../api.js'
import PhotoPick from './PhotoPick.jsx'
import { shrink } from './PhotoUpload.jsx'

// The build log: dated notes, each with an optional photo (phones offer the camera).
// `entries` come with the model; after a change `reload()` fetches the model again.
export default function BuildLog({ modelId, entries, reload, run }) {
  const [text, setText] = useState('')
  const [day, setDay] = useState(today())
  const [photo, setPhoto] = useState(null)
  const [busy, setBusy] = useState(false)

  const add = (e) => {
    e.preventDefault()
    setBusy(true)
    run(async () => {
      try {
        const entry = await api.addLogEntry(modelId, { text: text.trim() || null, entry_date: day })
        if (photo) await api.addLogPhoto(entry.entry_id, await shrink(photo, 1600))
        setText('')
        setPhoto(null)
        setDay(today())
        await reload('Added to the build log ✓')
      } finally {
        setBusy(false)
      }
    })
  }

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">Build log</h4>
        <span className="muted small">{entries.length} {entries.length === 1 ? 'entry' : 'entries'}</span>
      </div>
      <form className="log-form" onSubmit={add}>
        <textarea rows="2" value={text} onChange={(e) => setText(e.target.value)}
          placeholder="What did you do today? e.g. Primed the hull, tracks assembled" aria-label="Build log note" />
        <div className="button-row">
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label="Date" />
          <PhotoPick onFile={setPhoto} label={photo ? 'Photo ✓' : 'Add photo'} />
          {photo && <span className="muted small">Photo ✓ <button type="button" className="icon-btn small"
            aria-label="Don't add the photo" onClick={() => setPhoto(null)}>✕</button></span>}
          <button type="submit" className="primary" disabled={busy || (!text.trim() && !photo)}>
            {busy ? 'Saving...' : 'Add to log'}
          </button>
        </div>
      </form>
      <ol className="log">
        {entries.map((e) => (
          <li key={e.entry_id}>
            <div className="log-head">
              <time dateTime={e.entry_date}>{shortDate(e.entry_date)}</time>
              <button type="button" className="icon-btn small" aria-label="Delete log entry"
                onClick={() => run(async () => { await api.deleteLogEntry(e.entry_id); await reload() })}>✕</button>
            </div>
            {e.text && <p>{e.text}</p>}
            {e.has_photo && (
              <a href={logPhotoUrl(e)} target="_blank" rel="noreferrer">
                <img src={logPhotoUrl(e)} alt={e.text ?? 'Build photo'} loading="lazy" />
              </a>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
