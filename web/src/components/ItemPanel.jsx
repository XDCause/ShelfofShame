import { useEffect, useState } from 'react'
import { api, imageUrl, money } from '../api.js'
import JournalMentions from '../core/journal/JournalMentions.jsx'
import { FillBar, fillOf } from '../modules/models/fill.jsx'
import ColourMatches from './ColourMatches.jsx'
import Drawer from './Drawer.jsx'
import Fold from './Fold.jsx'
import PhotoUpload from './PhotoUpload.jsx'
import ScanButton from './ScanButton.jsx'
import StockHistory from './StockHistory.jsx'
import SupplyFields, { DETAIL_FIELDS, toForm, toPayload } from './SupplyFields.jsx'

const longDate = (iso) =>
  iso ? new Date(`${iso}T00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }) : ''

// Everything about one supply in a side panel. Everyday changes (stock, condition, reorder,
// location, last purchased, notes) save as you make them; what the item IS sits behind
// "Edit details".
// reloadKey changes when something outside the panel (an Undo) changed this item.
export default function ItemPanel({ supplyId, lookups, reloadKey, onClose, onChanged, onAdjusted, onRemoved, onOpenModel, onOpenItem }) {
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('') // short "Saved" confirmation
  const [editing, setEditing] = useState(false)
  const [details, setDetails] = useState(null) // form while editing details
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  // Text fields are edited locally and saved when you leave the field.
  const [text, setText] = useState({ notes: '', purchased_from: '', purchase_date: '' })

  const show = (supply) => {
    setItem(supply)
    setText({ notes: supply.notes ?? '', purchased_from: supply.purchased_from ?? '',
      purchase_date: supply.purchase_date ?? '' })
  }

  useEffect(() => {
    api.getSupply(supplyId).then(show).catch((e) => setError(e.message))
  }, [supplyId, reloadKey])

  const flash = (msg = 'Saved ✓') => {
    setSaved(msg)
    setTimeout(() => setSaved(''), 1800)
  }

  // Save one or more fields straight away. If that made it Low/Out, the API put it on the
  // wishlist - say so.
  const save = async (changes) => {
    setError('')
    try {
      const updated = await api.updateSupply(supplyId, changes)
      show(updated)
      flash(updated.auto_wish_id ? 'Saved ✓ · added to your wishlist' : 'Saved ✓')
      onChanged()
    } catch (e) {
      setError(e.message)
    }
  }

  const addToWishlist = async () => {
    setError('')
    try {
      show(await api.addSupplyToWishlist(supplyId))
      flash('Added to your wishlist ✓')
      onChanged()
    } catch (e) {
      setError(e.message)
    }
  }

  const saveText = (field) => {
    const value = text[field].trim()
    if (value === (item[field] ?? '')) return
    save({ [field]: value || null })
  }

  const adjust = async (delta) => {
    setError('')
    try {
      const before = item
      const updated = await api.adjustQty(supplyId, delta)
      show(updated)
      onChanged()
      onAdjusted(before, delta, updated.auto_wish_id) // "Used one: ... · Undo"
    } catch (e) {
      setError(e.message)
    }
  }

  const saveDetails = async (e) => {
    e.preventDefault()
    setBusy(true)
    await save(toPayload(details, DETAIL_FIELDS))
    setBusy(false)
    setEditing(false)
  }

  const getTamiyaPhoto = async () => {
    setBusy(true)
    try {
      await api.lookupTamiya(item.product_code, item.has_image)
      show(await api.getSupply(supplyId))
      flash('Photo updated ✓')
      onChanged()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const linkBarcode = async (barcode) => {
    await api.setBarcode(item.brand_id, item.product_code, barcode)
    show(await api.getSupply(supplyId))
    flash('Barcode linked ✓')
  }

  const remove = async () => {
    setBusy(true)
    try {
      // Running out put it on the wishlist; removing it means you're not replacing it.
      await api.deleteSupply(supplyId, item.on_wishlist)
      onChanged()
      onRemoved?.(item)
      onClose()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  if (!item) {
    return (
      <Drawer title="Item" onClose={onClose}>
        {error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}
      </Drawer>
    )
  }

  const canLink = item.brand_id && item.product_code
  const usedUp = item.qty_on_hand === 0 || (item.qty_on_hand === 1 && ['Empty', 'Dried out'].includes(item.condition))
  // The keys matter: without them React reuses the "Edit details" button as "Save details",
  // turning it into a submit button mid-click, so the browser submits (saves) straight away.
  const footer = editing ? (
    <>
      <button key="save" type="submit" form="details-form" className="primary" disabled={busy}>Save details</button>
      <button key="cancel" type="button" className="plain" onClick={() => setEditing(false)}>Cancel</button>
    </>
  ) : confirmDelete ? (
    <span className="confirm">
      Remove {item.name} from your inventory{item.on_wishlist ? ' and your wishlist' : ''}?
      <button type="button" className="danger" onClick={remove} disabled={busy}>Yes, remove</button>
      <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="edit" type="button" className="secondary"
        onClick={() => { setDetails(toForm(item)); setEditing(true) }}>Edit details</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>Remove</button>
    </>
  )

  return (
    <Drawer title={item.item_ref} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <p className="save-flash" role="status" aria-live="polite">{saved}</p>

      {editing ? (
        <form id="details-form" onSubmit={saveDetails}>
          <SupplyFields form={details} lookups={lookups} reorder
            set={(f) => (e) => setDetails((d) => ({ ...d, [f]: e.target.value }))} />
        </form>
      ) : (
        <>
          <div className="item-hero">
            <div className="item-photo">
              {item.has_image ? <img src={imageUrl(item)} alt="" /> : <span className="photo-missing">No photo</span>}
            </div>
            <div>
              <h3 className="item-name">{item.name}</h3>
              <p className="item-sub mono">{[item.brand, item.product_code].filter(Boolean).join(' · ')}</p>
              <div className="chips">
                {[item.category, item.paint_type, item.finish, item.size]
                  .filter((v) => v && v !== 'N/A').map((v) => <span key={v} className="chip">{v}</span>)}
              </div>
            </div>
          </div>

          <section className="panel-section">
            <div className="stock-row">
              <button type="button" className="step" aria-label="Use one" onClick={() => adjust(-1)}
                disabled={item.qty_on_hand <= 0}>−</button>
              <div className="stock-count">
                <strong>{item.qty_on_hand}</strong>
                <span className="muted small">on hand</span>
              </div>
              <button type="button" className="step" aria-label="Add one (sets last purchased to today)"
                onClick={() => adjust(1)}>+</button>
              <span className={`badge ${item.stock_status.toLowerCase()}`}>{item.stock_status}</span>
              {item.unit_price != null && (
                <span className="muted small stock-value">{money(item.unit_price)} each · {money(item.total_value)}</span>
              )}
              <span className="wish-action">
                {item.on_wishlist
                  ? <span className="tag ok">On wishlist ✓</span>
                  : <button type="button" className="chip-btn" onClick={addToWishlist}>+ Add to wishlist</button>}
              </span>
            </div>
          </section>

          {usedUp && (
            <section className="panel-section used-up">
              <p>
                <strong>{item.qty_on_hand === 0 ? 'All used up.' : `Your last one is ${item.condition.toLowerCase()}.`}</strong>{' '}
                Not replacing it? Remove it from your inventory
                {item.on_wishlist ? ' (and your wishlist)' : ''}. Its stock history is kept.
                {item.used_on.length > 0 && ` Still on the paint list for ${item.used_on.map((m) => m.name).join(', ')}.`}
              </p>
              <button type="button" className="danger" onClick={() => setConfirmDelete(true)}
                disabled={confirmDelete}>Remove from inventory</button>
            </section>
          )}

          {item.used_on.length > 0 && (
            <section className="panel-section">
              <h4 className="section-title">Used on</h4>
              <div className="chips">
                {item.used_on.map((m) => (
                  <button key={m.model_id} type="button" className="chip-filter" onClick={() => onOpenModel(m.model_id)}>
                    {m.name} <span className="chip-count">{m.status}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          <section className="panel-section">
            <div className="section-head">
              <h4 className="section-title" id="condition-label">Condition</h4>
              <span className="muted small">{item.qty_on_hand <= 0 ? 'None left' : `About ${fillOf(item)}% left`}</span>
            </div>
            <FillBar percent={fillOf(item)} />
            <div className="condition-picker" role="group" aria-labelledby="condition-label">
              {lookups.conditions.map((c) => (
                <button key={c} type="button" aria-pressed={item.condition === c}
                  className={['Nearly empty', 'Empty', 'Dried out'].includes(c) ? 'warn' : ''}
                  onClick={() => item.condition !== c && save({ condition: c })}>{c}</button>
              ))}
            </div>
            {item.qty_on_hand === 1 && ['Nearly empty', 'Empty', 'Dried out'].includes(item.condition) && (
              <p className="hint">Your last one is {item.condition.toLowerCase()}, so it shows as Low.</p>
            )}
          </section>

          <section className="panel-section quick-grid">
            <label className="field">
              <span className="field-label">Location</span>
              <select value={item.location_id ?? ''} onChange={(e) => save({ location_id: e.target.value ? Number(e.target.value) : null })}>
                <option value="">—</option>
                {lookups.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Last purchased</span>
              <input type="date" value={text.purchase_date}
                onChange={(e) => setText((t) => ({ ...t, purchase_date: e.target.value }))}
                onBlur={() => saveText('purchase_date')} />
            </label>
            <label className="field wide">
              <span className="field-label">Last bought from</span>
              <input value={text.purchased_from} placeholder="e.g. Hobbyrama"
                onChange={(e) => setText((t) => ({ ...t, purchased_from: e.target.value }))}
                onBlur={() => saveText('purchased_from')} />
            </label>
            <label className="field wide">
              <span className="field-label">Notes</span>
              <textarea rows="3" value={text.notes} placeholder="Anything worth remembering"
                onChange={(e) => setText((t) => ({ ...t, notes: e.target.value }))}
                onBlur={() => saveText('notes')} />
            </label>
          </section>

          {item.product_description && (
            <section className="panel-section">
              <h4 className="section-title">From the manufacturer</h4>
              <p className="detail-desc">{item.product_description}</p>
              {item.source_url && <a className="small" href={item.source_url} target="_blank" rel="noreferrer">View on tamiya.com ↗</a>}
            </section>
          )}

          <section className="panel-section">
            <h4 className="section-title">Photo &amp; barcode</h4>
            <div className="button-row">
              {item.brand === 'Tamiya' && item.product_code && (
                <button type="button" className="secondary" onClick={getTamiyaPhoto} disabled={busy}>
                  {item.has_image ? 'Refresh from tamiya.com' : 'Get photo from tamiya.com'}
                </button>
              )}
              <PhotoUpload brandId={item.brand_id} productCode={item.product_code} hasPhoto={item.has_image}
                onChanged={async (msg) => { show(await api.getSupply(supplyId)); flash(`${msg} ✓`); onChanged() }} />
            </div>
            <div className="barcode-line">
              {canLink ? (
                <>
                  <span className="small">
                    Barcode: {item.barcode ? <span className="mono">{item.barcode}</span> : <span className="muted">not linked</span>}
                  </span>
                  <ScanButton onBarcode={linkBarcode} className="secondary"
                    label={item.barcode ? 'Change barcode' : 'Link barcode'} />
                </>
              ) : (
                <span className="hint">Add a brand and product code (Edit details) to link a barcode.</span>
              )}
            </div>
          </section>

          {item.product_code && item.brand_id && (
            <section className="panel-section">
              <Fold title="Colour matches" detail="same colour, other paints">
                <ColourMatches brandId={item.brand_id} productCode={item.product_code} name={item.name}
                  onOpenItem={onOpenItem} onChanged={onChanged} />
              </Fold>
            </section>
          )}

          <section className="panel-section">
            <StockHistory supplyId={item.supply_id} version={`${item.qty_on_hand}-${item.updated_at}`} />
          </section>
          <JournalMentions kind="supply" id={item.supply_id} name={item.name} onLeave={onClose} />
        </>
      )}
    </Drawer>
  )
}
