import { useEffect, useMemo, useState } from 'react'
import { api, imageUrl } from '../api.js'
import Drawer from './Drawer.jsx'
import PhotoUpload, { shrink } from './PhotoUpload.jsx'
import ScanButton from './ScanButton.jsx'
import SimilarItems from './SimilarItems.jsx'
import { applyResult, Choice, Field } from './SupplyFields.jsx'

const FIELDS = [
  'brand_id', 'product_code', 'name', 'category_id', 'paint_type', 'finish', 'size',
  'qty_wanted', 'est_price', 'priority', 'notes',
]
const INTEGER_FIELDS = ['brand_id', 'category_id', 'qty_wanted']

function startForm(wish) {
  if (wish) return Object.fromEntries(FIELDS.map((f) => [f, wish[f] == null ? '' : String(wish[f])]))
  return { ...Object.fromEntries(FIELDS.map((f) => [f, ''])), qty_wanted: '1', priority: 'Normal' }
}

function toPayload(form) {
  return Object.fromEntries(FIELDS.map((f) => {
    const v = form[f].trim()
    if (v === '') return [f, f === 'priority' ? 'Normal' : null]
    return [f, INTEGER_FIELDS.includes(f) ? Number(v) : v]
  }))
}

function scanMessage(r) {
  if (r.match === 'known') return { tone: 'ok', text: 'Recognised from your own items.' }
  if (r.match === 'catalog') return { tone: 'ok', text: 'Identified from the barcode catalogue.' }
  if (r.match === 'tamiya') return { tone: 'low', text: 'Matched using the barcode digits. Check the photo and name are right.' }
  if (r.brand_id != null) return { tone: 'low', text: "A Tamiya barcode we haven't seen. Type the paint code from the label (e.g. XF-76) below and tap Look up." }
  return { tone: 'low', text: "New barcode. Fill in the details; it's remembered when you save." }
}

// Add or edit a wishlist item, in a side panel like adding a supply: scan or type a code
// first, check what was filled in, then save. `scanned` = {result, photo} from a Scan button.
export default function WishForm({ wish, lookups, scanned, onSaved, onCancel }) {
  const [scan, setScan] = useState(scanned ?? null)
  const [form, setForm] = useState(() => {
    const start = startForm(wish)
    return scanned ? applyResult(start, scanned.result) : start
  })
  const [code, setCode] = useState('')
  const [found, setFound] = useState(scanned?.result?.match !== 'unknown' ? scanned?.result ?? null : null)
  const [busy, setBusy] = useState('') // '' | 'lookup' | 'save'
  const [error, setError] = useState('')
  const [current, setCurrent] = useState(wish) // the saved item, refreshed after a photo change
  const [note, setNote] = useState('')
  const [supplies, setSupplies] = useState([]) // for "You already own"
  useEffect(() => { api.listSupplies().then(setSupplies).catch(() => {}) }, [])

  const photo = found?.has_image ? found : current?.has_image ? current : null
  const yourPhotoUrl = useMemo(() => (scan?.photo ? URL.createObjectURL(scan.photo) : null), [scan])
  useEffect(() => () => yourPhotoUrl && URL.revokeObjectURL(yourPhotoUrl), [yourPhotoUrl])

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }))

  const onBarcode = async (barcode, photoFile) => {
    const result = await api.scan(barcode)
    setScan({ result, photo: photoFile })
    if (result.match !== 'unknown') setFound(result)
    setForm((f) => applyResult(f, result))
  }

  const lookup = async () => {
    if (!code.trim()) return
    setBusy('lookup')
    setError('')
    try {
      const r = await api.lookupTamiya(code.trim())
      setFound(r)
      setForm((f) => applyResult(f, r))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const refreshCurrent = async (text) => {
    const all = await api.listWishlist()
    setCurrent(all.find((w) => w.wish_id === wish.wish_id) ?? current)
    setNote(text)
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
    // Saved. Now the extras from a scan; if one fails the item is still on the list.
    const problems = []
    if (scan && !(saved.brand_id && saved.product_code)) {
      problems.push("the barcode isn't remembered because the item has no brand and product code")
    } else if (scan) {
      try {
        await api.setBarcode(saved.brand_id, saved.product_code, scan.result.barcode)
      } catch (err) {
        problems.push(`barcode not remembered: ${err.message}`)
      }
      if (scan.photo && !saved.has_image) {
        try {
          await api.uploadPhoto(saved.brand_id, saved.product_code, await shrink(scan.photo))
        } catch (err) {
          problems.push(`your photo wasn't saved: ${err.message}`)
        }
      }
    }
    onSaved(saved, problems)
  }

  const footer = (
    <>
      <button key="save" type="submit" form="wish-form" className="primary" disabled={busy !== ''}>
        {busy === 'save' ? 'Saving...' : wish ? 'Save changes' : 'Add to wishlist'}
      </button>
      <button key="cancel" type="button" className="plain" onClick={onCancel}>Cancel</button>
    </>
  )

  return (
    <Drawer title={wish ? 'Edit wishlist item' : 'Add to wishlist'} onClose={onCancel} footer={footer}>
      {!wish && (
        <section className="panel-section add-start">
          <ScanButton onBarcode={onBarcode} label={scan ? 'Scan again' : 'Scan barcode'} />
          <div className="lookup-row">
            <label className="field">
              <span className="field-label">or Tamiya paint code / item number</span>
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. XF-76 or 81776"
                autoCapitalize="characters"
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookup() } }} />
            </label>
            <button type="button" className="secondary" onClick={lookup} disabled={busy !== '' || !code.trim()}>
              {busy === 'lookup' ? 'Looking up...' : 'Look up'}
            </button>
          </div>
        </section>
      )}

      {scan && (
        <p className={`alert ${scanMessage(scan.result).tone} small`} role="status">
          Barcode <span className="mono">{scan.result.barcode}</span>. {scanMessage(scan.result).text}
        </p>
      )}
      {found?.warning && <p className="alert error small">{found.warning}</p>}
      {found?.on_wishlist_id && <p className="alert low small">This is already on your wishlist.</p>}
      {error && <p className="alert error small" role="alert">{error}</p>}

      {(photo || yourPhotoUrl || found?.title || wish) && (
        <div className="preview">
          {photo ? <img src={imageUrl(photo)} alt="" />
            : yourPhotoUrl ? <img src={yourPhotoUrl} alt="" />
            : <div className="photo-missing">No photo</div>}
          <div>
            {found?.title && <p className="preview-title">{found.title}</p>}
            {(found?.description ?? current?.description) && (
              <p className="preview-desc">{found?.description ?? current?.description}</p>
            )}
            {!photo && yourPhotoUrl && <p className="hint">Your photo will be saved as the item photo.</p>}
            {(found?.source_url ?? current?.source_url) && (
              <a className="small" href={found?.source_url ?? current?.source_url} target="_blank" rel="noreferrer">
                View on tamiya.com ↗
              </a>
            )}
            {wish && (
              <PhotoUpload brandId={current?.brand_id} productCode={current?.product_code}
                hasPhoto={current?.has_image} onChanged={refreshCurrent} />
            )}
            {note && <p className="alert ok small">{note}</p>}
          </div>
        </div>
      )}

      <SimilarItems supplies={supplies} name={form.name} productCode={form.product_code}
        brandId={form.brand_id} label="You already own" />

      <form id="wish-form" onSubmit={submit}>
        <fieldset>
          <Field label="Name" required wide>
            <input value={form.name} onChange={set('name')} required />
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
          <Field label="Size">
            <input value={form.size} onChange={set('size')} placeholder="e.g. 10ml" />
          </Field>
          <Field label="Paint type">
            <Choice value={form.paint_type} onChange={set('paint_type')} options={lookups.paint_types} />
          </Field>
          <Field label="Finish">
            <Choice value={form.finish} onChange={set('finish')} options={lookups.finishes} />
          </Field>
        </fieldset>
        <fieldset>
          <legend>Buying</legend>
          <Field label="How many">
            <input type="number" min="1" step="1" inputMode="numeric" value={form.qty_wanted} onChange={set('qty_wanted')} />
          </Field>
          <Field label="Expected price ($)">
            <input type="number" min="0" step="0.01" inputMode="decimal" value={form.est_price} onChange={set('est_price')} />
          </Field>
          <Field label="Priority">
            <select value={form.priority} onChange={set('priority')}>
              {lookups.priorities.map((o) => <option key={o}>{o}</option>)}
            </select>
          </Field>
          <Field label="Notes" wide>
            <textarea rows="2" value={form.notes} onChange={set('notes')} />
          </Field>
        </fieldset>
      </form>
    </Drawer>
  )
}
