import { useRef, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'

// Import dives from a dive computer's export (UDDF, or a Subsurface file): choose the file, the API reads it
// (POST /scuba/import?dry=1) and shows what it found, then Import saves the new ones (dives already imported are
// skipped by the file's own ids, so importing the same file twice is safe).
const HELP = [
  ['Subsurface', 'File > Export > Subsurface XML (or Save as .ssrf). Subsurface reads most dive computers and exports from the others.'],
  ['Shearwater Cloud', 'Dive log > select dives > Export > UDDF.'],
  ['Suunto', 'In Suunto app / DM5: export the dives as UDDF; or open them in Subsurface and export from there.'],
  ['Garmin Dive', 'Garmin Connect: export the activity (FIT); open it in Subsurface (File > Import) and export UDDF or Subsurface XML from there.'],
  ['Other brands', 'Look for "Export" and UDDF in the brand\'s software; if there is none, import into Subsurface first.'],
]

function DiveRows({ dives }) {
  return (
    <ul className="scuba-import-list">
      {dives.map((d, i) => (
        <li key={`${d.dived_on}-${d.time_in}-${i}`}>
          <strong>{shortDate(d.dived_on)}</strong>{d.time_in ? ` ${String(d.time_in).slice(0, 5)}` : ''} · {d.max_depth ?? '—'} m · {d.minutes ?? '—'} min
          {d.site ? ` · ${d.site}` : ''}
        </li>
      ))}
    </ul>
  )
}

export function ImportPanel({ onClose }) {
  const { changed } = useApp()
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const choose = async (e) => {
    const f = e.target.files?.[0]
    setPreview(null)
    setResult(null)
    setError('')
    setFile(f ?? null)
    if (!f) return
    setBusy('read')
    try {
      setPreview(await api.scubaImport(f, true))
    } catch (err) {
      setError(err.message)
    }
    setBusy('')
  }
  const save = async () => {
    setBusy('save')
    setError('')
    try {
      setResult(await api.scubaImport(file, false))
      setPreview(null)
      changed()
    } catch (err) {
      setError(err.message)
    }
    setBusy('')
  }
  const again = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    if (input.current) input.current.value = ''
  }

  return (
    <Drawer title="Import dives" onClose={onClose}>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!result && (
        <label className="field">A dive file (.uddf, .ssrf or .xml)
          <input ref={input} type="file" accept=".uddf,.ssrf,.xml,application/xml,text/xml" onChange={choose} disabled={!!busy} /></label>
      )}
      {busy === 'read' && <p className="muted loading">Reading {file?.name}...</p>}
      {preview && (
        <section className="scuba-import-preview">
          <p>
            <strong>{preview.found}</strong> {preview.found === 1 ? 'dive' : 'dives'} found in this {preview.format} file:{' '}
            <strong>{preview.found - (preview.skipped ?? 0)}</strong> new{preview.skipped > 0 && <>, {preview.skipped} already in your log</>}.
          </p>
          {preview.dives?.length > 0 && <DiveRows dives={preview.dives} />}
          <div className="scuba-form-actions">
            <button type="button" className="primary" onClick={save} disabled={busy === 'save' || preview.found - (preview.skipped ?? 0) === 0}>
              {busy === 'save' ? 'Importing...' : 'Import'}</button>
            <button type="button" className="secondary" onClick={again} disabled={busy === 'save'}>Choose another file</button>
          </div>
        </section>
      )}
      {result && (
        <section className="scuba-import-preview">
          <p className="alert ok" role="status">
            Imported {result.added} {result.added === 1 ? 'dive' : 'dives'}{result.skipped > 0 && ` (${result.skipped} were already there)`}.
          </p>
          {result.dives?.length > 0 && <DiveRows dives={result.dives} />}
          <div className="scuba-form-actions">
            <button type="button" className="primary" onClick={onClose}>Done</button>
            <button type="button" className="secondary" onClick={again}>Import another file</button>
          </div>
        </section>
      )}
      <details className="scuba-help">
        <summary>How do I get a file from my dive computer?</summary>
        <p className="muted small">Every brand&apos;s software can export UDDF, and Subsurface can read almost any computer.</p>
        <dl className="scuba-help-list">
          {HELP.map(([name, how]) => <div key={name}><dt>{name}</dt><dd>{how}</dd></div>)}
        </dl>
      </details>
      <p className="muted small">Your file is read here and by your own app only. Dive numbers carry on from your last dive, and new sites are added by name.</p>
    </Drawer>
  )
}
