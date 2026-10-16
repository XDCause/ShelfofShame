import { useCallback, useEffect, useState } from 'react'
import { api, money, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { RowPhoto } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { FormPanel } from './VolleyballPanels.jsx'

// Gear (shoes, knee pads, balls...): one piece's panel, and finding it at a shop (api/app/gear.py).
const GEAR_FIELDS = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Court shoes' },
  { name: 'kind', label: 'Kind', list: 'gear-kinds', placeholder: 'Shoes, Knee pads, Ball...' },
  { name: 'brand', label: 'Brand' },
  { name: 'size', label: 'Size' },
  { name: 'purchase_date', label: 'Bought on', type: 'date' },
  { name: 'price_paid', label: 'Price paid', type: 'money' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]
const GEAR_KINDS = ['Shoes', 'Knee pads', 'Ball', 'Clothing', 'Bag', 'Ankle brace', 'Water bottle']

// Find gear at Blue Sky Athletics (Way of Wade shoes; api/app/bluesky.py): search as you type, a row
// per product with its price, sizes in stock and picture; onPick(product).
function GearShopFind({ onPick, pickLabel }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const words = q.trim()
    if (words.length < 3) { setResults(null); return undefined }
    let live = true
    const wait = setTimeout(async () => {
      setBusy(true)
      try { const r = await api.gearLookup(words); if (live) { setResults(r); setError('') } } catch (e) { if (live) setError(e.message) } finally { if (live) setBusy(false) }
    }, 500)
    return () => { live = false; clearTimeout(wait) }
  }, [q])
  return (
    <section className="panel-section shop-find">
      <label className="field">Find it at Blue Sky Athletics (Way of Wade)
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. way of wade 12" />
      </label>
      {busy && <p className="muted small">Looking...</p>}
      {error && <p className="alert error small">{error}</p>}
      {results && !busy && results.length === 0 && <p className="muted small">Nothing by that name at Blue Sky Athletics.</p>}
      {results?.length > 0 && (
        <ul className="list plain-list shop-results">
          {results.map((r) => (
            <li key={r.id}>
              <div className="row-button static">
                {r.image ? <img className="thumb" src={`${r.image}&width=200`} alt="" loading="lazy" referrerPolicy="no-referrer" />
                  : <span className="thumb thumb-empty" />}
                <span className="grow">
                  <span className="item-title">{r.name}{!r.available && <span className="pill out">Sold out</span>}</span>
                  <span className="item-meta">{[r.price != null && money(r.price), r.sizes.length > 0 && `some sizes in stock: ${r.sizes.join(', ')}`]
                    .filter(Boolean).join(' · ')}</span>
                </span>
                {r.gear_id ? <span className="pill">In your gear</span>
                  : <button type="button" className="primary small" onClick={() => onPick(r)}>{pickLabel}</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// One piece of gear: photo, condition (tap to change), details, journal pages about it.
// wanted: a new piece you'd like to buy (condition Wanted); tapping a condition once you have it
// dates it bought today (the API), unless Bought on is filled in.
export function GearPanel({ id = null, wanted = false, onClose }) {
  const { lookups, changed, showToast, openPanel } = useApp()
  const [gear, setGear] = useState(null)
  const [condition, setCondition] = useState(wanted ? 'Wanted' : 'Good')
  // From the shop: a new piece is added straight away (then opened, to set your size); one you have is linked.
  const fromShop = async (product) => {
    try {
      if (gear) {
        setGear(await api.linkGearToShop(gear.gear_id, product.id))
        changed()
        showToast(`Linked to ${product.name}`)
      } else {
        const added = await api.addGear({ name: '', shop_id: product.id, condition })
        changed()
        showToast(condition === 'Wanted' ? `${added.name} is on your wanted list` : `Added ${added.name} to your gear`)
        onClose()
        openPanel('gear', { id: added.gear_id })
      }
    } catch (e) {
      showToast(e.message)
    }
  }
  const reload = useCallback(async () => {
    const g = await api.getGear(id)
    setGear(g)
    setCondition(g.condition)
  }, [id])
  useEffect(() => { if (id != null) reload().catch((e) => showToast(e.message)) }, [id, reload, showToast])
  if (id != null && !gear) return <Drawer title="Gear" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  const save = async (data) => {
    const body = { ...data, condition }
    if (gear) await api.updateGear(gear.gear_id, body)
    else await api.addGear(body)
    changed()
    showToast(gear ? 'Saved' : condition === 'Wanted' ? `${body.name} is on your wanted list` : `Added ${body.name} to your gear`)
    onClose()
  }
  return (
    <FormPanel title={gear ? gear.name : wanted ? 'Gear you want' : 'Add gear'} fields={GEAR_FIELDS} record={gear} onClose={onClose}
      onSave={save} saveLabel={gear ? 'Save' : wanted ? 'Add to wanted' : 'Add gear'}
      hide={condition === 'Wanted' ? ['purchase_date', 'price_paid'] : []}   // not bought yet
      onDelete={gear && (async () => { await api.deleteGear(gear.gear_id); changed(); onClose() })}
      before={<>{gear && (
        <div className="item-hero">
          <RowPhoto path={`/gear/${gear.gear_id}`} url={gear.photo_url}
            onChanged={(msg) => { reload(); changed(); showToast(msg) }} />
          <div>
            <h3 className="item-name">{gear.name}</h3>
            <p className="item-sub">{[gear.kind, gear.brand, gear.size].filter(Boolean).join(' · ')}</p>
            {gear.price_paid != null && <span className="chip">{money(gear.price_paid)}</span>}
            {gear.purchase_date && <span className="muted small"> Bought {shortDate(gear.purchase_date)}</span>}
            {gear.shop_url && <p className="small"><a href={gear.shop_url} target="_blank" rel="noreferrer">
              {gear.shop_name}{gear.shop_price != null && ` ${money(gear.shop_price)}`} ↗</a></p>}
          </div>
        </div>
      )}
      {!gear?.shop_id && <GearShopFind onPick={fromShop} pickLabel={gear ? 'Link' : condition === 'Wanted' ? 'Want this' : 'Add'} />}
      </>}>
      {() => (
        <>
          <datalist id="gear-kinds">{GEAR_KINDS.map((k) => <option key={k} value={k} />)}</datalist>
          <p className="field-label">Condition</p>
          <div className="condition-picker" role="group" aria-label="Condition">
            {lookups.gear_conditions.map((c) => (
              <button key={c} type="button" aria-pressed={condition === c}
                className={c === 'Needs replacing' ? 'warn' : c === 'Wanted' ? 'want' : ''}
                onClick={() => setCondition(c)}>{c}</button>
            ))}
          </div>
          {gear && <JournalMentions kind="gear" id={gear.gear_id} name={gear.name} onLeave={onClose} />}
        </>
      )}
    </FormPanel>
  )
}
