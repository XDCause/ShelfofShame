import { useState } from 'react'
import { api, imageUrl, today } from '../api.js'
import Drawer from './Drawer.jsx'
import { Field } from './SupplyFields.jsx'

const FIELDS = ['name', 'brand_id', 'product_code', 'scale', 'status', 'scalemates_url', 'price_paid',
  'purchase_date', 'purchased_from', 'started_on', 'finished_on']

const toForm = (m) => Object.fromEntries(FIELDS.map((f) => [f, m[f] == null ? '' : String(m[f])]))
const toBody = (f, editing) => Object.fromEntries(FIELDS
  .filter((k) => editing || !['started_on', 'finished_on'].includes(k))
  .map((k) => {
    const v = f[k].trim()
    return [k, v === '' ? null : k === 'brand_id' ? Number(v) : v]
  }))

// Adding a model (look the kit up by its number first, optionally) or editing its details.
export default function ModelForm({ model, lookups, settings, onClose, onCancel, onSaved }) {
  const [form, setForm] = useState(() => (model ? toForm(model) : {
    ...toForm({}), status: 'In stash', purchase_date: today(), purchased_from: settings.default_shop ?? '',
  }))
  const [kitCode, setKitCode] = useState('')
  const [maker, setMaker] = useState('Tamiya') // whose kit number it is
  const [found, setFound] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (f) => (e) => setForm((x) => ({ ...x, [f]: e.target.value }))
  const wanted = form.status === 'Wanted'

  // Kit number -> name, scale and box photo from the maker's website.
  const lookup = async () => {
    setBusy(true)
    setError('')
    try {
      let r, name, scale
      if (maker === 'Hasegawa') {
        r = await api.lookupHasegawa(kitCode.trim()) // series code (JT86) or item number (09086)
        name = r.name
        scale = r.scale ?? ''
      } else {
        r = await api.lookupTamiya(kitCode.trim())
        // Tamiya kit titles look like "1/48 SCALE MITSUBISHI A6M3/3A ZERO (ZEKE)": split off the scale.
        scale = r.title?.match(/^\s*(1\/\d+)/)?.[1] ?? ''
        name = (r.suggested?.name ?? r.title ?? '').replace(/^\s*1\/\d+\s*(scale\s+)?/i, '')
      }
      setFound(r)
      setForm((f) => ({ ...f, name: name || f.name, scale: scale || f.scale,
        brand_id: String(r.brand_id), product_code: r.product_code }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = toBody(form, !!model)
      if (body.status === 'Wanted') Object.assign(body, { price_paid: null, purchase_date: null, purchased_from: null })
      onSaved(model ? await api.updateModel(model.model_id, body) : await api.addModel(body))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  // Keys: see ItemPanel - stops a button turning into the submit button mid-click.
  const footer = (
    <>
      <button key="save" type="submit" form="model-form" className="primary" disabled={busy || !form.name.trim()}>
        {model ? 'Save details' : 'Add model'}
      </button>
      <button key="cancel" type="button" className="plain" onClick={onCancel}>Cancel</button>
    </>
  )

  return (
    <Drawer title={model ? 'Edit model' : 'Add a model'} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!model && (
        <section className="panel-section">
          <span className="field-label">Look up a kit (optional)</span>
          <div className="segmented maker" role="group" aria-label="Kit maker">
            {['Tamiya', 'Hasegawa'].map((m) => (
              <button key={m} type="button" aria-pressed={maker === m}
                onClick={() => { setMaker(m); setFound(null) }}>{m}</button>
            ))}
          </div>
          <div className="lookup-row">
            <label className="field">
              <span className="field-label">{maker === 'Hasegawa' ? 'Series code or item number from the box' : 'Kit number'}</span>
              <input value={kitCode} onChange={(e) => setKitCode(e.target.value)}
                placeholder={maker === 'Hasegawa' ? 'e.g. JT86 or 09086' : 'e.g. 32595'} autoCapitalize="characters"
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookup() } }} />
            </label>
            <button type="button" className="secondary" onClick={lookup} disabled={busy || !kitCode.trim()}>
              {busy ? 'Looking up...' : 'Look up'}
            </button>
          </div>
          {found && (
            <div className="preview">
              {found.has_image ? <img src={imageUrl(found)} alt="" /> : <div className="photo-missing">No photo</div>}
              <p className="preview-title">{found.title}</p>
            </div>
          )}
        </section>
      )}
      <form id="model-form" onSubmit={submit}>
        <fieldset>
          <legend>Kit</legend>
          <Field label="Model name" required wide>
            <input value={form.name} onChange={set('name')} required placeholder="e.g. M4A3E8 Sherman" />
          </Field>
          <Field label="Brand">
            <select value={form.brand_id} onChange={set('brand_id')}>
              <option value="">—</option>
              {lookups.brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </Field>
          <Field label="Kit code" hint="Needed for a photo">
            <input value={form.product_code} onChange={set('product_code')} placeholder="e.g. T32595" />
          </Field>
          <Field label="Scale">
            <input value={form.scale} onChange={set('scale')} placeholder="e.g. 1/48" />
          </Field>
          <Field label="Status">
            <select value={form.status} onChange={set('status')}>
              {lookups.model_statuses.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Scalemates link" wide hint="Paste the kit's page address from scalemates.com">
            <input type="url" value={form.scalemates_url} onChange={set('scalemates_url')}
              placeholder="https://www.scalemates.com/kits/..." />
          </Field>
        </fieldset>
        {!wanted && (
          <fieldset>
            <legend>Stash</legend>
            <Field label="Price paid ($)">
              <input type="number" min="0" step="0.01" inputMode="decimal" value={form.price_paid} onChange={set('price_paid')} />
            </Field>
            <Field label="Bought on">
              <input type="date" value={form.purchase_date} onChange={set('purchase_date')} />
            </Field>
            <Field label="Bought from" wide>
              <input value={form.purchased_from} onChange={set('purchased_from')} placeholder="e.g. Hobbyrama" />
            </Field>
            {model && (
              <>
                <Field label="Started"><input type="date" value={form.started_on} onChange={set('started_on')} /></Field>
                <Field label="Finished"><input type="date" value={form.finished_on} onChange={set('finished_on')} /></Field>
              </>
            )}
          </fieldset>
        )}
      </form>
    </Drawer>
  )
}
