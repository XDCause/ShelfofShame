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
  const [editing, setEditing] = useState(null)   // the entry_id being changed

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
              {editing !== e.entry_id && (
                <span className="log-actions">
                  <button type="button" className="plain small" onClick={() => setEditing(e.entry_id)}
                    aria-label={`Edit the entry from ${shortDate(e.entry_date)}`}>Edit</button>
                  <button type="button" className="icon-btn small" aria-label="Delete log entry"
                    onClick={() => run(async () => { await api.deleteLogEntry(e.entry_id); await reload() })}>✕</button>
                </span>
              )}
            </div>
            {editing === e.entry_id ? (
              <EditEntry entry={e} run={run} reload={reload} onDone={() => setEditing(null)} />
            ) : (
              <>
                {e.text && <p>{e.text}</p>}
                <EntryPhotos entry={e} />
              </>
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

// An entry's photos: one shows big, several as a grid of squares. With onRemove each gets a ✕.
function EntryPhotos({ entry: e, onRemove }) {
  if (!e.photos.length) return null
  return (
    <ul className={e.photos.length === 1 ? 'log-photos one' : 'log-photos'}>
      {e.photos.map((id, i) => (
        <li key={id}>
          <a href={logPhotoUrl(id)} target="_blank" rel="noreferrer">
            <img src={logPhotoUrl(id)} alt={`${e.text ?? 'Build photo'} (${i + 1} of ${e.photos.length})`} loading="lazy" />
          </a>
          {onRemove && <button type="button" className="photo-remove" aria-label={`Remove photo ${i + 1}`}
            onClick={() => onRemove(id)}>✕</button>}
        </li>
      ))}
    </ul>
  )
}

// Changing an entry: its note and day, removing photos, adding more. Photos marked for removal
// and new ones are only saved with Save; Cancel leaves the entry as it was.
function EditEntry({ entry, run, reload, onDone }) {
  const [text, setText] = useState(entry.text ?? '')
  const [day, setDay] = useState(String(entry.entry_date).slice(0, 10))
  const [removed, setRemoved] = useState([])
  const [added, setAdded] = useState([])
  const [busy, setBusy] = useState(false)
  const save = (ev) => {
    ev.preventDefault()
    setBusy(true)
    run(async () => {
      try {
        await api.updateLogEntry(entry.entry_id, { text, entry_date: day })
        for (const id of removed) await api.deleteLogPhoto(id)
        for (const file of added) await api.addLogPhoto(entry.entry_id, await shrink(file, 1600))
        await reload('Build log entry saved ✓')   // reload first: closing before it would show a deleted photo
        onDone()
      } finally {
        setBusy(false)
      }
    })
  }
  const kept = { ...entry, photos: entry.photos.filter((id) => !removed.includes(id)) }
  return (
    <form className="log-form log-edit" onSubmit={save}>
      <textarea rows="3" value={text} onChange={(e) => setText(e.target.value)} autoFocus aria-label="Edit the note" />
      <EntryPhotos entry={kept} onRemove={(id) => setRemoved([...removed, id])} />
      {added.length > 0 && (
        <ul className="log-photos picked" aria-label="Photos to add">
          {added.map((f, i) => (
            <li key={`${f.name}-${f.lastModified}-${i}`}>
              <Preview file={f} />
              <button type="button" className="photo-remove" aria-label={`Don't add ${f.name}`}
                onClick={() => setAdded(added.filter((_, j) => j !== i))}>✕</button>
            </li>
          ))}
        </ul>
      )}
      <div className="button-row">
        <input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label="Date" required />
        <PhotoPick multiple onFile={(files) => setAdded([...added, ...files])} label="Add photos" />
        <button type="submit" className="primary" disabled={busy}>{busy ? 'Saving...' : 'Save'}</button>
        <button type="button" className="plain" onClick={onDone} disabled={busy}>Cancel</button>
      </div>
    </form>
  )
}
