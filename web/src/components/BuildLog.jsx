import { useEffect, useState } from 'react'
import { api, logPhotoUrl, shortDate, today } from '../api.js'
import PhotoPick from './PhotoPick.jsx'
import { shrink } from './PhotoUpload.jsx'

// The build log: dated notes, each with any number of photos (pick several from the gallery, or
// take them one after another with the camera - they show as thumbnails until you add the entry).
// `entries` come with the model; after a change `reload()` fetches the model again.
export default function BuildLog({ modelId, entries, reload, run }) {
  const [text, setText] = useState('')
  const [day, setDay] = useState(today())
  const [photos, setPhotos] = useState([])
  const [busy, setBusy] = useState(false)

  const add = (e) => {
    e.preventDefault()
    setBusy(true)
    run(async () => {
      try {
        const entry = await api.addLogEntry(modelId, { text: text.trim() || null, entry_date: day })
        for (const file of photos) await api.addLogPhoto(entry.entry_id, await shrink(file, 1600))
        setText('')
        setPhotos([])
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
          <PhotoPick multiple onFile={(files) => setPhotos([...photos, ...files])} label={photos.length ? 'Add more photos' : 'Add photos'} />
          <button type="submit" className="primary" disabled={busy || (!text.trim() && !photos.length)}>
            {busy ? (photos.length ? `Saving ${photos.length} photo${photos.length === 1 ? '' : 's'}...` : 'Saving...') : 'Add to log'}
          </button>
        </div>
        {photos.length > 0 && (
          <ul className="log-photos picked" aria-label="Photos to add">
            {photos.map((f, i) => (
              <li key={`${f.name}-${f.lastModified}-${i}`}>
                <Preview file={f} />
                <button type="button" className="photo-remove" aria-label={`Don't add ${f.name}`}
                  onClick={() => setPhotos(photos.filter((_, j) => j !== i))}>✕</button>
              </li>
            ))}
          </ul>
        )}
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
            {e.photos.length > 0 && (
              <ul className={e.photos.length === 1 ? 'log-photos one' : 'log-photos'}>
                {e.photos.map((id, i) => (
                  <li key={id}>
                    <a href={logPhotoUrl(id)} target="_blank" rel="noreferrer">
                      <img src={logPhotoUrl(id)} alt={`${e.text ?? 'Build photo'} (${i + 1} of ${e.photos.length})`} loading="lazy" />
                    </a>
                    <button type="button" className="photo-remove" aria-label={`Remove photo ${i + 1}`}
                      onClick={() => run(async () => { await api.deleteLogPhoto(id); await reload() })}>✕</button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}

// A picked photo before it's uploaded (an object URL, let go when it's removed).
function Preview({ file }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    const u = URL.createObjectURL(file)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [file])
  return url ? <img src={url} alt={file.name} /> : null
}
