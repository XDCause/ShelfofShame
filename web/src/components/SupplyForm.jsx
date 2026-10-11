import { useEffect, useState } from 'react'
import { api, imageUrl, money, uploadPhoto } from '../api.js'
import PhotoUpload, { shrink } from './PhotoUpload.jsx'
import ScanButton from './ScanButton.jsx'

// Form state is all strings (that's what inputs hold); toPayload converts for the API.
const FIELDS = [
  'brand_id', 'product_code', 'name', 'category_id', 'paint_type', 'finish', 'size',
  'qty_on_hand', 'reorder_at', 'condition', 'unit_price', 'purchase_date', 'purchased_from',
  'location_id', 'used_for', 'notes',
]
const INTEGER_FIELDS = ['brand_id', 'category_id', 'location_id', 'qty_on_hand', 'reorder_at']

// New items start with your usual conventions: 1 on hand, reorder at 0, sealed, bought today.
function emptyForm(lookups) {
  const other = lookups.locations.find((l) => l.name === 'Other')
  const today = new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local time
  return {
    ...Object.fromEntries(FIELDS.map((f) => [f, ''])),
    qty_on_hand: '1',
    reorder_at: '0',
    condition: 'Sealed',
    purchase_date: today,
    location_id: other ? String(other.id) : '',
  }
}

const toForm = (supply) => Object.fromEntries(FIELDS.map((f) => [f, supply[f] == null ? '' : String(supply[f])]))

// Fill fields from a scan or Tamiya lookup result (`suggested` = best-guess values).
function applyResult(f, r) {
  const s = r.suggested ?? {}
  return {
    ...f,
    brand_id: r.brand_id != null ? String(r.brand_id) : f.brand_id,
    product_code: r.product_code ?? f.product_code,
    name: s.name ?? f.name,
    category_id: s.category_id != null ? String(s.category_id) : f.category_id,
    paint_type: s.paint_type ?? f.paint_type,
    finish: s.finish ?? f.finish,
    size: s.size ?? f.size,
  }
}

function toPayload(form) {
  return Object.fromEntries(
    FIELDS.map((f) => {
      const v = form[f].trim()
      if (v === '') return [f, null]
      return [f, INTEGER_FIELDS.includes(f) ? Number(v) : v] // price stays a string: exact cents
    }),
  )
}

// `scanned` = {result, photo} when opened from a scan on the Inventory page.
export default function SupplyForm({ supplyId, scanned, lookups, onSaved, onNew, onDeleted, onBack }) {
  const startForm = () => (scanned ? applyResult(emptyForm(lookups), scanned.result) : emptyForm(lookups))
  const [form, setForm] = useState(startForm)
  const [saved, setSaved] = useState(null) // the supply as last loaded/saved
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null) // {type: 'ok' | 'error', text}
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [code, setCode] = useState('') // Tamiya paint code / item number to look up

  // Load the supply when editing; reset when adding.
  useEffect(() => {
    setConfirmDelete(false)
    if (supplyId == null) {
      setForm(startForm())
      setSaved(null)
      return
    }
    api
      .getSupply(supplyId)
      .then((s) => (setForm(toForm(s)), setSaved(s)))
      .catch((e) => setMessage({ type: 'error', text: e.message }))
    // lookups deliberately left out: reloading the dropdowns must not wipe what you've typed
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplyId])

  const set = (name) => (e) => {
    setForm((f) => ({ ...f, [name]: e.target.value }))
    setMessage(null)
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    let supply
    try {
      const payload = toPayload(form)
      supply = supplyId == null
        ? await api.createSupply(payload)
        : await api.updateSupply(supplyId, payload)
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
      setBusy(false)
      return
    }
    // Saved. If it came from a scan, remember the barcode and keep the photo you took.
    const problems = []
    if (supplyId == null && scanned && supply.brand_id && supply.product_code) {
      try {
        await api.setBarcode(supply.brand_id, supply.product_code, scanned.result.barcode)
      } catch (err) {
        problems.push(`barcode not remembered: ${err.message}`)
      }
      if (scanned.photo && !supply.has_image) {
        try {
          await uploadPhoto(supply.brand_id, supply.product_code, await shrink(scanned.photo))
        } catch (err) {
          problems.push(`your photo wasn't saved: ${err.message}`)
        }
      }
      supply = await api.getSupply(supply.supply_id)
    }
    setForm(toForm(supply))
    setSaved(supply)
    setMessage(problems.length
      ? { type: 'low', text: `Saved ${supply.item_ref} ${supply.name}, but ${problems.join('; ')}.` }
      : { type: 'ok', text: `Saved ${supply.item_ref} ${supply.name}.` })
    setBusy(false)
    onSaved(supply)
  }

  // Tamiya paint code (XF-76) or item number -> fill the form in.
  const lookupTamiya = async () => {
    if (!code.trim()) return
    setBusy(true)
    try {
      const r = await api.lookupTamiya(code.trim())
      setForm((f) => applyResult(f, r))
      setMessage(r.warning ? { type: 'error', text: r.warning }
        : r.owned_qty > 0 ? { type: 'low', text: `You already own ${r.owned_qty} of these.` }
        : { type: 'ok', text: `Filled in from tamiya.com: ${r.title}` })
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  // Link a barcode to this existing item, so scanning it finds it from now on.
  const linkBarcode = async (barcode) => {
    await api.setBarcode(saved.brand_id, saved.product_code, barcode)
    setSaved(await api.getSupply(supplyId))
    setMessage({ type: 'ok', text: `Barcode linked. Scanning it will now find ${saved.name}.` })
  }

  const remove = async () => {
    setBusy(true)
    try {
      await api.deleteSupply(supplyId)
      onDeleted()
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
      setBusy(false)
    }
  }

  const startNew = () => {
    setMessage(null)
    if (supplyId == null) setForm(emptyForm(lookups))
    onNew()
  }

  // Fetch (or re-fetch) this item's photo from tamiya.com, then reload to show it.
  const getPhoto = async () => {
    setBusy(true)
    try {
      await api.lookupTamiya(saved.product_code, saved.has_image)
      setSaved(await api.getSupply(supplyId))
      setMessage({ type: 'ok', text: 'Photo updated from tamiya.com.' })
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  const isNew = supplyId == null
  const value = Number(form.qty_on_hand || 0) * Number(form.unit_price || 0)
  const canGetPhoto = !isNew && saved?.brand === 'Tamiya' && saved?.product_code

  return (
    <form className="card supply-form" onSubmit={submit}>
      <div className="card-head">
        <h2>{isNew ? 'Add a supply' : `Edit ${saved?.item_ref ?? ''}`}</h2>
        <div className="head-actions">
          {!isNew && <button type="button" className="link" onClick={startNew}>+ New supply</button>}
          <button type="button" className="link" onClick={onBack}>Back to inventory</button>
        </div>
      </div>

      {!isNew && saved && (
        <div className="preview">
          {saved.has_image
            ? <img src={imageUrl(saved)} alt={saved.name} />
            : <div className="photo-missing">No photo yet</div>}
          <div>
            {saved.product_description && <p className="preview-desc">{saved.product_description}</p>}
            <div className="photo-actions">
              {canGetPhoto && (
                <button type="button" className="secondary" onClick={getPhoto} disabled={busy}>
                  {saved.has_image ? 'Refresh from tamiya.com' : 'Get photo from tamiya.com'}
                </button>
              )}
              <PhotoUpload
                brandId={saved.brand_id}
                productCode={saved.product_code}
                hasPhoto={saved.has_image}
                onChanged={async (text) => {
                  setSaved(await api.getSupply(supplyId))
                  setMessage({ type: 'ok', text })
                }}
              />
            </div>
            <div className="barcode-line">
              {saved.brand_id && saved.product_code ? (
                <>
                  <span className="small">
                    Barcode: {saved.barcode ? <span className="mono">{saved.barcode}</span> : <span className="muted">not linked yet</span>}
                  </span>
                  <ScanButton onBarcode={linkBarcode} className="secondary"
                    label={saved.barcode ? 'Change barcode' : 'Link barcode'} />
                </>
              ) : (
                <span className="hint">Set a brand and product code to link a barcode.</span>
              )}
            </div>
          </div>
        </div>
      )}

      {isNew && scanned && (
        <p className={`alert ${scanned.result.match === 'unknown' ? 'low' : 'ok'} small`} role="status">
          Barcode <span className="mono">{scanned.result.barcode}</span>.{' '}
          {scanned.result.match === 'unknown'
            ? "Not known yet. Fill in the details (for Tamiya paints, look up the code on the label). The barcode is remembered when you save."
            : 'Details filled in. Check them, then save.'}
        </p>
      )}

      {isNew && (
        <div className="lookup-row">
          <label className="field">
            <span className="field-label">Tamiya paint code or item number (optional)</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. XF-76 or 81776"
              autoCapitalize="characters"
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookupTamiya() } }} />
          </label>
          <button type="button" className="secondary" onClick={lookupTamiya} disabled={busy || !code.trim()}>
            Look up
          </button>
        </div>
      )}

      <fieldset>
        <legend>Item</legend>
        <Field label="Name / colour" required>
          <input value={form.name} onChange={set('name')} required placeholder="e.g. Acrylic XF1 Flat Black" />
        </Field>
        <Field label="Category" required>
          <select value={form.category_id} onChange={set('category_id')} required>
            <option value="">Choose...</option>
            {lookups.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Brand">
          <select value={form.brand_id} onChange={set('brand_id')}>
            <option value="">—</option>
            {lookups.brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </Field>
        <Field label="Product code">
          <input value={form.product_code} onChange={set('product_code')} placeholder="e.g. T81701" />
        </Field>
      </fieldset>

      <fieldset>
        <legend>Details</legend>
        <Field label="Paint type">
          <ChoiceSelect value={form.paint_type} onChange={set('paint_type')} options={lookups.paint_types} />
        </Field>
        <Field label="Finish">
          <ChoiceSelect value={form.finish} onChange={set('finish')} options={lookups.finishes} />
        </Field>
        <Field label="Size">
          <input value={form.size} onChange={set('size')} placeholder="e.g. 10ml, 18m" />
        </Field>
        <Field label="Condition">
          <ChoiceSelect value={form.condition} onChange={set('condition')} options={lookups.conditions} />
        </Field>
      </fieldset>

      <fieldset>
        <legend>Stock</legend>
        <Field label="Qty on hand">
          <input type="number" min="0" step="1" value={form.qty_on_hand} onChange={set('qty_on_hand')} />
        </Field>
        <Field label="Reorder at" hint="Flag as Low at or below this">
          <input type="number" min="0" step="1" value={form.reorder_at} onChange={set('reorder_at')} />
        </Field>
        <Field label="Location">
          <select value={form.location_id} onChange={set('location_id')}>
            <option value="">—</option>
            {lookups.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </Field>
      </fieldset>

      <fieldset>
        <legend>Purchase</legend>
        <Field label="Unit price ($)" hint={value ? `Total value ${money(value)}` : ''}>
          <input type="number" min="0" step="0.01" value={form.unit_price} onChange={set('unit_price')} />
        </Field>
        <Field label="Purchase date">
          <input type="date" value={form.purchase_date} onChange={set('purchase_date')} />
        </Field>
        <Field label="Purchased from">
          <input value={form.purchased_from} onChange={set('purchased_from')} placeholder="e.g. Hobbyrama" />
        </Field>
      </fieldset>

      <fieldset>
        <legend>Notes</legend>
        <Field label="Used for / project">
          <input value={form.used_for} onChange={set('used_for')} />
        </Field>
        <Field label="Notes" wide>
          <textarea rows="3" value={form.notes} onChange={set('notes')} />
        </Field>
      </fieldset>

      {message && <p className={`alert ${message.type}`} role="status">{message.text}</p>}

      <div className="form-actions">
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Saving...' : isNew ? 'Add supply' : 'Save changes'}
        </button>
        {!isNew && !confirmDelete && (
          <button type="button" className="danger-link" onClick={() => setConfirmDelete(true)}>Delete...</button>
        )}
        {!isNew && confirmDelete && (
          <span className="confirm">
            Delete {saved?.name} permanently?
            <button type="button" className="danger" onClick={remove} disabled={busy}>Yes, delete</button>
            <button type="button" className="link" onClick={() => setConfirmDelete(false)}>Cancel</button>
          </span>
        )}
      </div>
    </form>
  )
}

function Field({ label, required, hint, wide, children }) {
  return (
    <label className={wide ? 'field wide' : 'field'}>
      <span className="field-label">
        {label}
        {required && <span className="req" aria-hidden="true"> *</span>}
      </span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  )
}

function ChoiceSelect({ value, onChange, options }) {
  return (
    <select value={value} onChange={onChange}>
      <option value="">—</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}
