import { useEffect, useState } from 'react'
import { api, imageUrl, money, shortDate } from '../api.js'
import JournalMentions from '../core/journal/JournalMentions.jsx'
import BuildLog from './BuildLog.jsx'
import BuildSteps from './BuildSteps.jsx'
import Drawer from './Drawer.jsx'
import ModelForm from './ModelForm.jsx'
import { modelMeta, statusClass } from './ModelsView.jsx'
import PaintChecklist from './PaintChecklist.jsx'
import PhotoUpload from './PhotoUpload.jsx'
import TimeTracker from './TimeTracker.jsx'

// Where each maker's kit details and box photos come from.
const SOURCES = {
  Tamiya: { site: 'tamiya.com', lookup: api.lookupTamiya },
  Hasegawa: { site: 'hasegawa-model.co.jp', lookup: api.lookupHasegawa },
  Bandai: { site: 'hlj.com', lookup: api.lookupBandai },
}

// Opens Scalemates' own search in your browser (the app itself never fetches Scalemates).
const scalematesSearch = (m) => {
  const digits = (m.product_code ?? '').replace(/^\D+/, '')
  const q = [m.brand, digits, m.name].filter(Boolean).join(' ')
  return `https://www.scalemates.com/search.php?q=${encodeURIComponent(q)}`
}

// One model (kit): status, what you paid, time spent, paint checklist, build log, notes and
// photo. Also used to add a new model (modelId = null).
export default function ModelPanel({ modelId, lookups, settings, onClose, onChanged, onCreated, onOpenSupply }) {
  const [model, setModel] = useState(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [editing, setEditing] = useState(modelId == null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [notes, setNotes] = useState('')

  const flash = (msg) => { setNote(msg); setTimeout(() => setNote(''), 2500) }
  const run = async (fn) => {
    setError('')
    try { return await fn() } catch (e) { setError(e.message) }
  }
  // Every change returns the whole model; show it, and tell the pages behind (unless it's
  // only an on-screen preview).
  const onModel = (m, msg, tell = true) => {
    setModel(m)
    setNotes(m.notes ?? '')
    if (tell) onChanged()
    if (msg) flash(msg)
  }
  const reload = async (msg) => onModel(await api.getModel(modelId ?? model.model_id), msg)

  useEffect(() => {
    if (modelId != null) run(async () => onModel(await api.getModel(modelId), null, false))
  }, [modelId])

  if (editing) {
    return (
      <ModelForm model={model} lookups={lookups} settings={settings} onClose={onClose}
        onCancel={() => (model ? setEditing(false) : onClose())}
        onSaved={(m) => {
          if (model) { onModel(m, 'Saved ✓'); setEditing(false) } else { onChanged(); onCreated(m.model_id) }
        }} />
    )
  }
  if (!model) {
    return <Drawer title="Model" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  }

  const save = (data, msg = 'Saved ✓') => run(async () => onModel(await api.updateModel(model.model_id, data), msg))
  const stash = [
    model.price_paid != null && `Paid ${money(model.price_paid)}`,
    model.purchase_date && `bought ${shortDate(model.purchase_date)}`,
    model.purchased_from && `from ${model.purchased_from}`,
  ].filter(Boolean).join(' ')
  const dates = [model.started_on && `Started ${shortDate(model.started_on)}`,
    model.finished_on && `finished ${shortDate(model.finished_on)}`].filter(Boolean).join(', ')

  const footer = confirmDelete ? (
    <span className="confirm">
      Delete {model.name}, its paint list, time and build log?
      <button type="button" className="danger" onClick={() => run(async () => {
        await api.deleteModel(model.model_id)
        onChanged()
        onClose()
      })}>Yes, delete</button>
      <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="edit" type="button" className="secondary" onClick={() => setEditing(true)}>Edit details</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>Delete</button>
    </>
  )

  return (
    <Drawer title="Model" onClose={onClose} footer={footer} wide>
      {error && <p className="alert error" role="alert">{error}</p>}
      <p className="save-flash" role="status" aria-live="polite">{note}</p>

      <div className="item-hero">
        <div className="item-photo">
          {model.has_image ? <img src={imageUrl(model)} alt="" /> : <span className="photo-missing">No photo</span>}
        </div>
        <div>
          <h3 className="item-name">{model.name}</h3>
          <p className="item-sub">{modelMeta(model)}</p>
          {(stash || dates) && <p className="item-sub small">{[stash, dates].filter(Boolean).join(' · ')}</p>}
          <div className="model-links">
            {model.source_url && (
              <a className="small" href={model.source_url} target="_blank" rel="noreferrer">
                {SOURCES[model.brand]?.site ?? 'Website'} ↗
              </a>
            )}
            {model.scalemates_url
              ? <a className="small" href={model.scalemates_url} target="_blank" rel="noreferrer">Scalemates ↗</a>
              : model.hobby !== 'Warhammer' && (
                <a className="small" href={scalematesSearch(model)} target="_blank" rel="noreferrer"
                  title="Find it on Scalemates, then paste its address into Edit details">Search Scalemates ↗</a>
              )}
          </div>
        </div>
      </div>

      <section className="panel-section">
        <div className="status-picker" role="group" aria-label="Status">
          {lookups.model_statuses.map((s) => (
            <button key={s} type="button" aria-pressed={model.status === s}
              className={model.status === s ? statusClass(s) : ''}
              onClick={() => model.status !== s && save({ status: s })}>{s}</button>
          ))}
        </div>
      </section>

      {model.status !== 'Wanted' && <BuildSteps model={model} stages={lookups.stages} save={save} />}
      <TimeTracker model={model} onModel={onModel} run={run} />
      <PaintChecklist model={model} onModel={onModel} run={run} flash={flash} onOpenSupply={onOpenSupply} />
      <BuildLog modelId={model.model_id} entries={model.log} reload={reload} run={run} />
      <JournalMentions kind="model" id={model.model_id} name={model.name} onLeave={onClose} />

      <section className="panel-section">
        <label className="field">
          <span className="field-label">Notes</span>
          <textarea rows="3" value={notes} placeholder="Decals, references, ideas..."
            onChange={(e) => setNotes(e.target.value)}
            onBlur={() => notes.trim() !== (model.notes ?? '') && save({ notes: notes.trim() || null })} />
        </label>
      </section>

      <section className="panel-section">
        <h4 className="section-title">Box photo</h4>
        <div className="button-row">
          {SOURCES[model.brand] && model.product_code && (
            <button type="button" className="secondary"
              onClick={() => run(async () => {
                await SOURCES[model.brand].lookup(model.product_code, model.has_image)
                await reload('Photo updated ✓')
              })}>
              {model.has_image ? 'Refresh photo' : 'Get photo'} from {SOURCES[model.brand].site}
            </button>
          )}
          <PhotoUpload brandId={model.brand_id} productCode={model.product_code} hasPhoto={model.has_image}
            onChanged={(msg) => reload(`${msg} ✓`)} />
        </div>
      </section>
    </Drawer>
  )
}
