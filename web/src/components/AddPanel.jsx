import { useEffect, useMemo, useState } from 'react'
import { api, imageUrl } from '../api.js'
import Drawer from './Drawer.jsx'
import { shrink } from './PhotoUpload.jsx'
import ScanButton from './ScanButton.jsx'
import SimilarItems from './SimilarItems.jsx'
import SupplyFields, { applyResult, emptyForm, toPayload } from './SupplyFields.jsx'

function scanMessage(r) {
  if (r.match === 'catalog') return { tone: 'ok', text: 'Identified from the barcode catalogue.' }
  if (r.match === 'known') return { tone: 'ok', text: 'Recognised from your saved barcodes.' }
  if (r.match === 'tamiya') return { tone: 'low', text: 'Matched using the barcode digits. Check the photo and name are right.' }
  if (r.brand_id != null) return { tone: 'low', text: "A Tamiya barcode we haven't seen. Type the paint code from the label (e.g. XF-76) below and tap Look up." }
  return { tone: 'low', text: "New barcode. Fill in the details; it's remembered when you add the item." }
}

// Add a supply: scan or type a code first, check what was filled in, then add it to your
// inventory - or to the wishlist instead, if you're standing in a shop.
// `scanned` = {result, photo} when opened from the Inventory page's Scan button.
export default function AddPanel({ lookups, settings, scanned: initialScan, onClose, onAdded, onWished, onOpen }) {
  const [scan, setScan] = useState(initialScan ?? null)
  const [found, setFound] = useState(initialScan?.result?.match !== 'unknown' ? initialScan?.result : null)
  const [form, setForm] = useState(() => {
    const start = emptyForm(lookups, settings)
    if (!initialScan) return start
    const r = initialScan.result
    return applyResult(r.match === 'unknown' && r.brand_id == null ? { ...start, brand_id: '' } : start, r)
  })
  const [code, setCode] = useState('')
  const [choices, setChoices] = useState(null) // both makers have this number: their results, to pick from
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState(null)
  const [supplies, setSupplies] = useState([]) // for "Already in your inventory"
  useEffect(() => { api.listSupplies().then(setSupplies).catch(() => {}) }, [])

  const yourPhotoUrl = useMemo(() => (scan?.photo ? URL.createObjectURL(scan.photo) : null), [scan])
  useEffect(() => () => yourPhotoUrl && URL.revokeObjectURL(yourPhotoUrl), [yourPhotoUrl])

  const set = (f) => (e) => setForm((x) => ({ ...x, [f]: e.target.value }))

  // A new scan inside the panel: something you own opens it (like Scan in the nav bar);
  // anything else fills in the form.
  const onBarcode = async (barcode, photo) => {
    const result = await api.scan(barcode)
    if (result.supply_id) return onOpen(result.supply_id)
    setScan({ result, photo })
    setMessage(null)
    if (result.match !== 'unknown') setFound(result)
    setForm((f) => applyResult(f, result))
  }

  const lookup = async () => {
    if (!code.trim()) return
    setBusy('lookup')
    setMessage(null)
    try {
      // The API asks Tamiya and / or Trumpeter (a plain number could be either's); both found = you pick.
      const { found: hits, missed, choices: matches } = await api.lookupItem(code.trim())
      if (matches) {                           // words: Stedi's tools that match - you pick one
        setChoices(matches)
        setFound(null)
        return
      }
      const unsure = missed.filter((m) => ![404, 409, 422].includes(m.status)).map((m) => `${m.maker}: ${m.message}`)
      if (hits.length > 1) {
        setChoices(hits)
        setFound(null)
      } else {
        pick(hits[0], hits.length + missed.length > 1, unsure)
      }
    } catch (e) {
      setMessage({ tone: 'error', text: e.message })
    } finally {
      setBusy('')
    }
  }

  const pick = async (r, say = false, unsure = []) => {
    if (r.sku && !r.product_code) {            // a Stedi search result: look that tool up properly first
      setBusy('lookup')
      try {
        r = (await api.lookupItem(r.sku)).found[0]
      } catch (e) {
        setMessage({ tone: 'error', text: e.message })
        return
      } finally {
        setBusy('')
      }
      say = true
    }
    const { maker } = r
    setChoices(null)
    setFound(r)
    setForm((f) => applyResult(f, r))
    if (r.warning) setMessage({ tone: 'error', text: r.warning })
    else if (maker === 'Trumpeter' && r.is_tool === false) {
      setMessage({ tone: 'low', text: `That's a Trumpeter kit (${r.item_type ?? 'a model'}) - kits usually go in Models.` })
    } else if (unsure.length) setMessage({ tone: 'low', text: `Found at ${maker}. Couldn't check the other site (${unsure.join('; ')}).` })
    else if (r.price_usd != null) setMessage({ tone: 'ok', text: `Found at Stedi: US$${r.price_usd.toFixed(2)} on steditools.com (US dollars - put in what you paid).` })
    else if (say) setMessage({ tone: 'ok', text: `Found at ${maker}.` })
  }

  // After saving: remember the scanned barcode and keep your photo if there's no other.
  const extras = async (brandId, productCode, hasImage) => {
    const problems = []
    if (!scan) return problems
    if (!brandId || !productCode) {
      // A barcode is remembered against brand + code; without them it can't be.
      return ['the barcode isn\'t remembered because the item has no brand and product code (add them with Edit details, then Link barcode)']
    }
    try {
      await api.setBarcode(brandId, productCode, scan.result.barcode)
    } catch (e) {
      problems.push(`barcode not remembered (${e.message})`)
    }
    if (scan.photo && !hasImage) {
      try {
        await api.uploadPhoto(brandId, productCode, await shrink(scan.photo))
      } catch (e) {
        problems.push(`your photo wasn't saved (${e.message})`)
      }
    }
    return problems
  }

  const addToInventory = async (e) => {
    e.preventDefault()
    setBusy('save')
    setMessage(null)
    try {
      const supply = await api.createSupply(toPayload(form))
      const problems = await extras(supply.brand_id, supply.product_code, supply.has_image)
      onAdded(supply, problems)
    } catch (err) {
      setMessage({ tone: 'error', text: err.message })
      setBusy('')
    }
  }

  const addToWishlist = async () => {
    if (!form.name.trim() || !form.category_id) {
      setMessage({ tone: 'error', text: 'Name and category are needed for the wishlist too.' })
      return
    }
    setBusy('wish')
    setMessage(null)
    try {
      const p = toPayload(form)
      const wish = await api.addWish({
        brand_id: p.brand_id, product_code: p.product_code, name: p.name, category_id: p.category_id,
        paint_type: p.paint_type, finish: p.finish, size: p.size, qty_wanted: Math.max(1, p.qty_on_hand ?? 1),
        est_price: p.unit_price, notes: p.notes,
      })
      const problems = await extras(wish.brand_id, wish.product_code, wish.has_image)
      onWished(wish, problems)
    } catch (err) {
      setMessage({ tone: 'error', text: err.message })
      setBusy('')
    }
  }

  const photo = found?.has_image ? found : null
  const owned = found?.supply_id
  const footer = (
    <>
      <button type="submit" form="add-form" className="primary" disabled={busy !== ''}>
        {busy === 'save' ? 'Adding...' : 'Add to inventory'}
      </button>
      <button type="button" className="secondary" onClick={addToWishlist} disabled={busy !== ''}>
        {busy === 'wish' ? 'Adding...' : 'Add to wishlist'}
      </button>
      <button type="button" className="plain" onClick={onClose}>Cancel</button>
    </>
  )

  return (
    <Drawer title="Add a supply" onClose={onClose} footer={footer}>
      <section className="panel-section add-start">
        <ScanButton onBarcode={onBarcode} label={scan ? 'Use another barcode' : 'Use barcode'} />
        <div className="lookup-row">
          <label className="field">
            <span className="field-label">or item number, paint code - or a Stedi tool</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. XF-76, 81776, 08005, MS-106 or nipper"
              autoCapitalize="characters"
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookup() } }} />
          </label>
          <button type="button" className="secondary" onClick={lookup} disabled={busy !== '' || !code.trim()}>
            {busy === 'lookup' ? 'Looking up...' : 'Look up'}
          </button>
        </div>
      </section>

      {scan && (
        <p className={`alert ${scanMessage(scan.result).tone} small`} role="status">
          Barcode <span className="mono">{scan.result.barcode}</span>. {scanMessage(scan.result).text}
        </p>
      )}
      {owned && (
        <p className="alert low small">
          You already own {found.owned_qty} of these.{' '}
          <button type="button" className="plain" onClick={() => onOpen(owned)}>Open it</button> to add stock with +.
        </p>
      )}
      {message && <p className={`alert ${message.tone} small`} role="alert">{message.text}</p>}
      {choices && (
        <section className="panel-section" aria-label="Which one">
          <p className="hint">{choices[0]?.sku ? `${choices.length} Stedi tool${choices.length > 1 ? 's' : ''} match. Which is yours?`
            : `Tamiya and Trumpeter both have item ${code.trim()}. Which is yours?`}</p>
          <ul className="list kit-choices">
            {choices.map((c) => (
              <li key={c.sku ?? c.maker}>
                <button type="button" className="row-button" onClick={() => pick(c)}>
                  {c.has_image ? <img className="thumb" src={imageUrl(c)} alt="" loading="lazy" />
                    : c.image ? <img className="thumb" src={c.image} alt="" loading="lazy" referrerPolicy="no-referrer" />
                      : <span className="thumb thumb-empty" aria-hidden="true" />}
                  <span><strong>{c.sku ?? c.maker}</strong> · {c.name ?? c.title}{c.version && <span className="muted"> · {c.version}</span>}
                    {c.price_usd != null && <span className="muted small"> · US${c.price_usd.toFixed(2)}</span>}
                    {c.available === false && <span className="muted small"> · sold out</span>}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(photo || yourPhotoUrl || found?.title) && (
        <div className="preview">
          {photo ? <img src={imageUrl(photo)} alt="" />
            : yourPhotoUrl ? <img src={yourPhotoUrl} alt="" />
            : <div className="photo-missing">No photo</div>}
          <div>
            {found?.title && <p className="preview-title">{found.title}</p>}
            {found?.description && <p className="preview-desc">{found.description}</p>}
            {!photo && yourPhotoUrl && <p className="hint">Your photo will be saved as the item photo.</p>}
          </div>
        </div>
      )}

      {!owned && (
        <SimilarItems supplies={supplies} name={form.name} productCode={form.product_code}
          brandId={form.brand_id} onOpen={onOpen} />
      )}

      <form id="add-form" onSubmit={addToInventory}>
        <SupplyFields form={form} set={set} lookups={lookups} stock />
      </form>
    </Drawer>
  )
}
