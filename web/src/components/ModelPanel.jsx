import { useEffect, useState } from 'react'
import { api, imageUrl } from '../api.js'
import Drawer from './Drawer.jsx'
import PhotoUpload from './PhotoUpload.jsx'
import { Field } from './SupplyFields.jsx'

const blank = { name: '', brand_id: '', product_code: '', scale: '', status: 'Not started' }
const fromModel = (m) => ({ name: m.name ?? '', brand_id: m.brand_id != null ? String(m.brand_id) : '',
  product_code: m.product_code ?? '', scale: m.scale ?? '', status: m.status })
const toBody = (f) => ({ name: f.name.trim(), brand_id: f.brand_id ? Number(f.brand_id) : null,
  product_code: f.product_code.trim() || null, scale: f.scale.trim() || null, status: f.status })

// One model (kit): photo, status, notes and its paint checklist. Also used to add a new model
// (modelId = null). Paints you own are ticked automatically; others can be ticked by hand.
export default function ModelPanel({ modelId, lookups, onClose, onChanged, onCreated, onOpenSupply }) {
  const [model, setModel] = useState(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [editing, setEditing] = useState(modelId == null)
  const [form, setForm] = useState(blank)
  const [kitCode, setKitCode] = useState('')
  const [kitMaker, setKitMaker] = useState('Tamiya') // whose kit number it is
  const [kitFound, setKitFound] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [notes, setNotes] = useState('')
  const [paint, setPaint] = useState({ text: '', purpose: '' })
  const [pasting, setPasting] = useState(false)
  const [pasted, setPasted] = useState('')
  const [supplies, setSupplies] = useState([]) // for the "pick from inventory" list

  const show = (m) => { setModel(m); setNotes(m.notes ?? '') }
  const flash = (msg) => { setNote(msg); setTimeout(() => setNote(''), 2500) }
  const run = async (fn) => {
    setError('')
    try { return await fn() } catch (e) { setError(e.message) }
  }

  useEffect(() => {
    if (modelId != null) run(async () => show(await api.getModel(modelId)))
    api.listSupplies().then(setSupplies).catch(() => {})
  }, [modelId])

  const changedModel = (m, msg) => { show(m); onChanged(); if (msg) flash(msg) }
  const save = (data, msg = 'Saved ✓') => run(async () => changedModel(await api.updateModel(model.model_id, data), msg))

  // Kit number -> name, scale and box photo from the maker's website.
  const lookupKit = () => run(async () => {
    setBusy(true)
    try {
      let name, scale, r
      if (kitMaker === 'Hasegawa') {
        r = await api.lookupHasegawa(kitCode.trim()) // series code (JT86) or item number (09086)
        name = r.name
        scale = r.scale ?? ''
        onChanged() // Hasegawa may have just been added to your brands
      } else {
        r = await api.lookupTamiya(kitCode.trim())
        // Tamiya kit titles look like "1/48 SCALE MITSUBISHI A6M3/3A ZERO (ZEKE)": split off the scale.
        scale = r.title?.match(/^\s*(1\/\d+)/)?.[1] ?? ''
        name = (r.suggested?.name ?? r.title ?? '').replace(/^\s*1\/\d+\s*(scale\s+)?/i, '')
      }
      setKitFound(r)
      setForm((f) => ({ ...f, name: name || f.name, scale: scale || f.scale,
        brand_id: String(r.brand_id), product_code: r.product_code }))
    } finally {
      setBusy(false)
    }
  })

  const submitDetails = (e) => {
    e.preventDefault()
    run(async () => {
      setBusy(true)
      try {
        if (model) {
          changedModel(await api.updateModel(model.model_id, toBody(form)), 'Saved ✓')
          setEditing(false)
        } else {
          const created = await api.addModel(toBody(form))
          onChanged()
          onCreated(created.model_id)
        }
      } finally {
        setBusy(false)
      }
    })
  }

  const addPaints = (text, purpose) => run(async () => {
    const m = await api.addModelPaints(model.model_id, text, purpose)
    changedModel(m)
    setPaint({ text: '', purpose: '' })
    setPasted('')
    setPasting(false)
  })

  const wishMissing = () => run(async () => {
    const r = await api.wishMissingPaints(model.model_id)
    changedModel(r.model)
    flash(r.added.length ? `Added to wishlist: ${r.added.join(', ')}.` : 'Nothing new to add.')
    if (r.skipped.length) setError(`Not added (no brand + code to buy by): ${r.skipped.join(', ')}.`)
  })

  const remove = () => run(async () => {
    await api.deleteModel(model.model_id)
    onChanged()
    onClose()
  })

  // ---------------- Adding a model, or editing its details ----------------
  if (editing) {
    // Keys: see ItemPanel - stops "Edit details" turning into a submit button mid-click.
    const footer = (
      <>
        <button key="save" type="submit" form="model-form" className="primary" disabled={busy || !form.name.trim()}>
          {model ? 'Save details' : 'Add model'}
        </button>
        <button key="cancel" type="button" className="link" onClick={() => (model ? setEditing(false) : onClose())}>Cancel</button>
      </>
    )
    const set = (f) => (e) => setForm((x) => ({ ...x, [f]: e.target.value }))
    return (
      <Drawer title={model ? 'Edit model' : 'Add a model'} onClose={onClose} footer={footer}>
        {error && <p className="alert error" role="alert">{error}</p>}
        {!model && (
          <section className="panel-section">
            <span className="field-label">Look up a kit (optional)</span>
            <div className="segmented maker" role="group" aria-label="Kit maker">
              {['Tamiya', 'Hasegawa'].map((m) => (
                <button key={m} type="button" aria-pressed={kitMaker === m}
                  onClick={() => { setKitMaker(m); setKitFound(null) }}>{m}</button>
              ))}
            </div>
            <div className="lookup-row">
              <label className="field">
                <span className="field-label">
                  {kitMaker === 'Hasegawa' ? 'Series code or item number from the box' : 'Kit number'}
                </span>
                <input value={kitCode} onChange={(e) => setKitCode(e.target.value)}
                  placeholder={kitMaker === 'Hasegawa' ? 'e.g. JT86 or 09086' : 'e.g. 61108'}
                  autoCapitalize="characters"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookupKit() } }} />
              </label>
              <button type="button" className="secondary" onClick={lookupKit} disabled={busy || !kitCode.trim()}>
                {busy ? 'Looking up...' : 'Look up'}
              </button>
            </div>
            {kitFound && (
              <div className="preview">
                {kitFound.has_image ? <img src={imageUrl(kitFound)} alt="" /> : <div className="photo-missing">No photo</div>}
                <div><p className="preview-title">{kitFound.title}</p></div>
              </div>
            )}
          </section>
        )}
        <form id="model-form" onSubmit={submitDetails}>
          <fieldset>
            <Field label="Model name" required wide>
              <input value={form.name} onChange={set('name')} required placeholder="e.g. Mitsubishi A6M3 Zero" />
            </Field>
            <Field label="Brand">
              <select value={form.brand_id} onChange={set('brand_id')}>
                <option value="">—</option>
                {lookups.brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </Field>
            <Field label="Kit code" hint="Needed for a photo">
              <input value={form.product_code} onChange={set('product_code')} placeholder="e.g. T61108" />
            </Field>
            <Field label="Scale">
              <input value={form.scale} onChange={set('scale')} placeholder="e.g. 1/48" />
            </Field>
            <Field label="Status">
              <select value={form.status} onChange={set('status')}>
                {lookups.model_statuses.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
          </fieldset>
        </form>
      </Drawer>
    )
  }

  if (!model) {
    return <Drawer title="Model" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  }

  // ---------------- Viewing a model ----------------
  const missing = model.paints.filter((p) => !p.have)
  const buyable = missing.filter((p) => p.brand_id && p.product_code && !p.on_wishlist)
  const footer = confirmDelete ? (
    <span className="confirm">
      Delete {model.name} and its paint list?
      <button type="button" className="danger" onClick={remove}>Yes, delete</button>
      <button type="button" className="link" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="edit" type="button" className="secondary" onClick={() => { setForm(fromModel(model)); setEditing(true) }}>Edit details</button>
      <span className="spacer" />
      <button type="button" className="danger-link" onClick={() => setConfirmDelete(true)}>Delete</button>
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
          <p className="item-sub">{[model.scale, model.brand, model.product_code].filter(Boolean).join(' · ')}</p>
          {model.source_url && (
            <a className="small" href={model.source_url} target="_blank" rel="noreferrer">
              View on {model.brand === 'Hasegawa' ? 'hasegawa-model.co.jp' : 'tamiya.com'} ↗
            </a>
          )}
        </div>
      </div>

      <section className="panel-section">
        <div className="condition-picker statuses" role="group" aria-label="Status">
          {lookups.model_statuses.map((s) => (
            <button key={s} type="button" aria-pressed={model.status === s}
              onClick={() => model.status !== s && save({ status: s })}>{s}</button>
          ))}
        </div>
      </section>

      <section className="panel-section">
        <div className="checklist-head">
          <h4 className="section-title">Paints {model.paints_total > 0 && `· ${model.paints_have}/${model.paints_total}`}</h4>
          {buyable.length > 0 && (
            <button type="button" className="chip-btn" onClick={wishMissing}>Add {buyable.length} missing to wishlist</button>
          )}
        </div>
        {model.paints_total > 0 && (
          <span className="progress-bar"><span style={{ width: `${(model.paints_have / model.paints_total) * 100}%` }} /></span>
        )}

        <ul className="checklist">
          {model.paints.map((p) => (
            <PaintRow key={p.model_paint_id} paint={p} onOpenSupply={onOpenSupply}
              onChange={(data) => {
                // Show a tick straight away; the server's answer then replaces it (or the
                // reload after an error puts it back).
                if ('have_it' in data) {
                  setModel((m) => ({ ...m, paints: m.paints.map((x) => (x.model_paint_id === p.model_paint_id
                    ? { ...x, have_it: data.have_it, have: x.in_inventory || data.have_it } : x)) }))
                }
                run(async () => {
                  try {
                    changedModel(await api.updateModelPaint(p.model_paint_id, data))
                  } catch (e) {
                    show(await api.getModel(model.model_id))
                    throw e
                  }
                })
              }}
              onRemove={() => run(async () => changedModel(await api.deleteModelPaint(p.model_paint_id)))} />
          ))}
        </ul>

        {!pasting ? (
          <div className="add-paint">
            <input list="inventory-codes" value={paint.text} placeholder="Paint, e.g. XF-76"
              onChange={(e) => setPaint((x) => ({ ...x, text: e.target.value }))} aria-label="Paint" />
            <input value={paint.purpose} placeholder="What it's for" aria-label="What it's for"
              onChange={(e) => setPaint((x) => ({ ...x, purpose: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter' && paint.text.trim()) addPaints(paint.text, paint.purpose) }} />
            <button type="button" className="secondary" disabled={!paint.text.trim()}
              onClick={() => addPaints(paint.text, paint.purpose)}>Add</button>
            <datalist id="inventory-codes">
              {supplies.filter((s) => s.product_code).map((s) => (
                <option key={s.supply_id} value={s.product_code}>{s.name}</option>
              ))}
            </datalist>
            <button type="button" className="link" onClick={() => setPasting(true)}>Paste a list</button>
          </div>
        ) : (
          <div className="paste-list">
            <label className="field">
              <span className="field-label">One paint per line, then a tab (or " - ") and what it's for</span>
              <textarea rows="7" value={pasted} onChange={(e) => setPasted(e.target.value)} autoFocus
                placeholder={'XF-76 Grey Green (IJN)\tThe whole exterior\nXF-71 Cockpit Green (IJN) - Cockpit interior'} />
            </label>
            <div className="form-actions">
              <button type="button" className="primary" disabled={!pasted.trim()} onClick={() => addPaints(pasted)}>Add paints</button>
              <button type="button" className="link" onClick={() => setPasting(false)}>Cancel</button>
            </div>
          </div>
        )}
      </section>

      <section className="panel-section">
        <label className="field">
          <span className="field-label">Notes</span>
          <textarea rows="3" value={notes} placeholder="Build notes, decals, references..."
            onChange={(e) => setNotes(e.target.value)}
            onBlur={() => notes.trim() !== (model.notes ?? '') && save({ notes: notes.trim() || null })} />
        </label>
      </section>

      <section className="panel-section">
        <h4 className="section-title">Photo</h4>
        <div className="photo-actions">
          {['Tamiya', 'Hasegawa'].includes(model.brand) && model.product_code && (
            <button type="button" className="secondary" disabled={busy}
              onClick={() => run(async () => {
                const lookup = model.brand === 'Hasegawa' ? api.lookupHasegawa : api.lookupTamiya
                await lookup(model.product_code, model.has_image)
                changedModel(await api.getModel(model.model_id), 'Photo updated ✓')
              })}>
              {model.has_image ? 'Refresh photo' : 'Get photo'} from {model.brand === 'Hasegawa' ? 'hasegawa-model.co.jp' : 'tamiya.com'}
            </button>
          )}
          <PhotoUpload brandId={model.brand_id} productCode={model.product_code} hasPhoto={model.has_image}
            onChanged={async (msg) => changedModel(await api.getModel(model.model_id), `${msg} ✓`)} />
        </div>
      </section>
    </Drawer>
  )
}

// One checklist line. Owned paints are ticked and locked (your inventory says you have it);
// anything else can be ticked by hand. "What it's for" saves when you leave the field.
function PaintRow({ paint, onChange, onRemove, onOpenSupply }) {
  const [purpose, setPurpose] = useState(paint.purpose ?? '')
  useEffect(() => setPurpose(paint.purpose ?? ''), [paint.purpose])
  const lowOrOut = paint.in_inventory && paint.stock_status !== 'OK'

  return (
    <li className={paint.have ? 'have' : ''}>
      <label className="check" title={paint.in_inventory ? 'In your inventory' : 'Tick if you have it'}>
        <input type="checkbox" checked={paint.have} disabled={paint.in_inventory}
          onChange={(e) => onChange({ have_it: e.target.checked })} aria-label={`Have ${paint.paint_name}`} />
        <span aria-hidden="true">✓</span>
      </label>
      {paint.has_image ? <img className="thumb small-thumb" src={imageUrl(paint)} alt="" loading="lazy" /> : <span className="thumb small-thumb thumb-empty" />}
      <div className="paint-main">
        <div className="paint-name">
          {paint.supply_id
            ? <button type="button" className="link-plain" onClick={() => onOpenSupply(paint.supply_id)}>{paint.paint_name}</button>
            : <span>{paint.paint_name}</span>}
          {paint.in_inventory && !lowOrOut && <span className="tag ok">In inventory</span>}
          {lowOrOut && <span className={`badge ${paint.stock_status.toLowerCase()}`}>{paint.condition ?? paint.stock_status}</span>}
          {!paint.have && paint.on_wishlist && <span className="tag">On wishlist</span>}
          {!paint.have && !paint.on_wishlist && paint.product_code && <span className="tag warn">Need to buy</span>}
          {!paint.product_code && <span className="tag" title="No brand + code, so it can't be matched to your inventory">Not linked</span>}
        </div>
        {/* A textarea that grows with the text, so long descriptions wrap instead of being cut off. */}
        <textarea className="purpose" value={purpose} placeholder="What it's for"
          rows={Math.min(4, Math.max(1, Math.ceil(purpose.length / 42)))}
          onChange={(e) => setPurpose(e.target.value)}
          onBlur={() => purpose.trim() !== (paint.purpose ?? '') && onChange({ purpose: purpose.trim() || null })} />
      </div>
      <button type="button" className="icon-btn remove-paint" onClick={onRemove} aria-label={`Remove ${paint.paint_name}`}>✕</button>
    </li>
  )
}
