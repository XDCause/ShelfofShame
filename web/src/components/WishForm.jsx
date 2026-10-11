import { useEffect, useMemo, useState } from 'react'
import { api, imageUrl, uploadPhoto } from '../api.js'
import PhotoUpload, { shrink } from './PhotoUpload.jsx'

const FIELDS = [
  'brand_id', 'product_code', 'name', 'category_id', 'paint_type', 'finish', 'size',
  'qty_wanted', 'est_price', 'priority', 'notes',
]
const INTEGER_FIELDS = ['brand_id', 'category_id', 'qty_wanted']

function startForm(wish, lookups) {
  if (wish) return Object.fromEntries(FIELDS.map((f) => [f, wish[f] == null ? '' : String(wish[f])]))
  const tamiya = lookups.brands.find((b) => b.name === 'Tamiya')
  return {
    ...Object.fromEntries(FIELDS.map((f) => [f, ''])),
    brand_id: tamiya ? String(tamiya.id) : '',
    qty_wanted: '1',
    priority: 'Normal',
  }
}

function toPayload(form) {
  return Object.fromEntries(
    FIELDS.map((f) => {
      const v = form[f].trim()
      if (v === '') return [f, f === 'priority' ? 'Normal' : null]
      return [f, INTEGER_FIELDS.includes(f) ? Number(v) : v]
    }),
  )
}

// Fill the form from a lookup or scan result. `suggested` holds the best-guess field values.
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

function scanMessage(r) {
  if (r.match === 'known') return { tone: 'ok', text: 'Recognised from your own items.' }
  if (r.match === 'catalog') return { tone: 'ok', text: 'Identified from the barcode catalogue; details from tamiya.com.' }
  if (r.match === 'tamiya') {
    return { tone: 'low', text: 'Matched to a Tamiya item using the barcode digits. Check the photo and name are right before saving.' }
  }
  if (r.brand_id != null) {
    return { tone: 'low', text: "Tamiya barcode we haven't seen yet. Type the paint code from the label (e.g. XF-76) or the item number, and tap Look up. When you save, the barcode is remembered, so next time it scans straight away." }
  }
  return { tone: 'low', text: "New barcode. Pick the brand and enter the product code. When you save, it's remembered for next time." }
}

// Add or edit a wishlist item. For Tamiya, "Look up" fetches the product from tamiya.com
// (via our API) and fills the form in; everything stays editable before saving.
// `scanned` = {result, photo} when opened from the Scan button.
export default function WishForm({ wish, lookups, scanned, onSaved, onCancel }) {
  const scanResult = scanned?.result
  const [form, setForm] = useState(() => {
    const start = startForm(wish, lookups)
    if (!scanResult) return start
    // An unknown barcode has no brand yet: don't assume Tamiya.
    return applyResult(scanResult.match === 'unknown' ? { ...start, brand_id: '' } : start, scanResult)
  })
  const [code, setCode] = useState(wish?.product_code ?? '')
  const [found, setFound] = useState(scanResult?.match !== 'unknown' ? scanResult ?? null : null)
  const [busy, setBusy] = useState('') // '' | 'lookup' | 'save'
  const [error, setError] = useState('')

  const [current, setCurrent] = useState(wish) // the saved item, refreshed after a photo change
  const [note, setNote] = useState('')

  const tamiyaId = String(lookups.brands.find((b) => b.name === 'Tamiya')?.id ?? '')
  const isTamiya = form.brand_id !== '' && form.brand_id === tamiyaId
  const photo = found?.has_image ? found : current?.has_image ? current : null

  // Show the photo you took while there's no manufacturer photo; free the memory afterwards.
  const yourPhotoUrl = useMemo(() => (scanned?.photo ? URL.createObjectURL(scanned.photo) : null), [scanned])
  useEffect(() => () => yourPhotoUrl && URL.revokeObjectURL(yourPhotoUrl), [yourPhotoUrl])

  const refreshCurrent = async (text) => {
    const all = await api.listWishlist()
    setCurrent(all.find((w) => w.wish_id === wish.wish_id) ?? current)
    setNote(text)
  }

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }))

  const lookup = async (e) => {
    e?.preventDefault()
    if (!code.trim()) return
    setBusy('lookup')
    setError('')
    try {
      const r = await api.lookupTamiya(code.trim())
      setFound(r)
      setForm((f) => applyResult(f, r))
    } catch (err) {
      setFound(null)
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy('save')
    setError('')
    let saved
    try {
      saved = wish ? await api.updateWish(wish.wish_id, toPayload(form)) : await api.addWish(toPayload(form))
    } catch (err) {
      setError(err.message)
      setBusy('')
      return
    }
    // The item is saved. Now the extras from a scan; if one fails the item is still on the list.
    const problems = []
    if (scanned && saved.brand_id && saved.product_code) {
      if (scanResult?.barcode) {
        try {
          await api.setBarcode(saved.brand_id, saved.product_code, scanResult.barcode)
        } catch (err) {
          problems.push(`barcode not remembered: ${err.message}`)
        }
      }
      if (scanned.photo && !saved.has_image) {
        try {
          await uploadPhoto(saved.brand_id, saved.product_code, await shrink(scanned.photo))
        } catch (err) {
          problems.push(`your photo wasn't saved: ${err.message}`)
        }
      }
    }
    onSaved(saved, problems)
  }

  return (
    <div className="card wish-form">
      <div className="card-head">
        <h2>{wish ? 'Edit wishlist item' : 'Add to wishlist'}</h2>
        <button type="button" className="link" onClick={onCancel}>Close</button>
      </div>

      {scanResult && (
        <p className={`alert ${scanMessage(scanResult).tone} small`} role="status">
          Barcode <span className="mono">{scanResult.barcode}</span>. {scanMessage(scanResult).text}
        </p>
      )}

      {isTamiya && !wish && (!scanResult || scanResult.match === 'unknown') && (
        <form className="lookup-row" onSubmit={lookup}>
          <label className="field">
            <span className="field-label">Tamiya paint code or item number</span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. XF-76 or 81776"
              autoCapitalize="characters"
              inputMode="text"
              autoFocus
            />
          </label>
          <button type="submit" className="primary" disabled={busy !== '' || !code.trim()}>
            {busy === 'lookup' ? 'Looking up...' : 'Look up'}
          </button>
        </form>
      )}

      {(found || wish || yourPhotoUrl) && (
        <div className="preview">
          {photo ? (
            <img src={imageUrl(photo)} alt="" />
          ) : yourPhotoUrl ? (
            <figure className="your-photo">
              <img src={yourPhotoUrl} alt="" />
              <figcaption className="hint">Your photo: saved as the item photo</figcaption>
            </figure>
          ) : (
            <div className="photo-missing">No photo</div>
          )}
          <div>
            {found && <p className="preview-title">{found.title}</p>}
            {found?.series && <p className="muted small">{found.series}</p>}
            {(found?.description ?? wish?.description) && (
              <p className="preview-desc">{found?.description ?? wish?.description}</p>
            )}
            {found?.warning && <p className="alert error small">{found.warning}</p>}
            {found?.owned_qty > 0 && (
              <p className="alert low small">You already own {found.owned_qty} of these.</p>
            )}
            {found?.on_wishlist_id && <p className="alert low small">This is already on your wishlist.</p>}
            {(found?.source_url ?? wish?.source_url) && (
              <a className="small" href={found?.source_url ?? wish?.source_url} target="_blank" rel="noreferrer">
                View on tamiya.com ↗
              </a>
            )}
            {wish && (
              <PhotoUpload
                brandId={current?.brand_id}
                productCode={current?.product_code}
                hasPhoto={current?.has_image}
                onChanged={refreshCurrent}
              />
            )}
            {note && <p className="alert ok small">{note}</p>}
          </div>
        </div>
      )}

      <form onSubmit={submit}>
        <fieldset>
          <label className="field wide">
            <span className="field-label">Name<span className="req" aria-hidden="true"> *</span></span>
            <input value={form.name} onChange={set('name')} required />
          </label>
          <label className="field">
            <span className="field-label">Category<span className="req" aria-hidden="true"> *</span></span>
            <select value={form.category_id} onChange={set('category_id')} required>
              <option value="">Choose...</option>
              {lookups.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Brand</span>
            <select value={form.brand_id} onChange={set('brand_id')}>
              <option value="">—</option>
              {lookups.brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Product code</span>
            <input value={form.product_code} onChange={set('product_code')} placeholder="e.g. T81701" />
          </label>
          <label className="field">
            <span className="field-label">Size</span>
            <input value={form.size} onChange={set('size')} placeholder="e.g. 10ml" />
          </label>
          <label className="field">
            <span className="field-label">Paint type</span>
            <select value={form.paint_type} onChange={set('paint_type')}>
              <option value="">—</option>
              {lookups.paint_types.map((o) => <option key={o}>{o}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Finish</span>
            <select value={form.finish} onChange={set('finish')}>
              <option value="">—</option>
              {lookups.finishes.map((o) => <option key={o}>{o}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">How many</span>
            <input type="number" min="1" step="1" value={form.qty_wanted} onChange={set('qty_wanted')} />
          </label>
          <label className="field">
            <span className="field-label">Expected price ($)</span>
            <input type="number" min="0" step="0.01" value={form.est_price} onChange={set('est_price')} />
          </label>
          <label className="field">
            <span className="field-label">Priority</span>
            <select value={form.priority} onChange={set('priority')}>
              {lookups.priorities.map((o) => <option key={o}>{o}</option>)}
            </select>
          </label>
          <label className="field wide">
            <span className="field-label">Notes</span>
            <textarea rows="2" value={form.notes} onChange={set('notes')} />
          </label>
        </fieldset>

        {error && <p className="alert error" role="status">{error}</p>}

        <div className="form-actions">
          <button type="submit" className="primary" disabled={busy !== ''}>
            {busy === 'save' ? 'Saving...' : wish ? 'Save changes' : 'Add to wishlist'}
          </button>
          <button type="button" className="link" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  )
}
