import { useState } from 'react'
import { api } from '../api.js'
import Fold from './Fold.jsx'

// Kits (api/app/supplies.py): a part says which kit it came in; a kit lists its parts, offers the ones its title
// says it comes with ("Includes Nipper, Hobby Knife...") to add in one go, and takes any other part by name. Each
// part is a supply of its own (its own stock, condition, search), with the kit's brand, purchase and photo.
export default function KitParts({ item, onOpenItem, onChanged, setItem }) {
  const suggested = item.suggested_parts ?? []
  const parts = item.parts ?? []
  const [ticked, setTicked] = useState(() => new Set(suggested))
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (item.part_of) {
    return (
      <p className="small kit-of">Part of{' '}
        <button type="button" className="link-title" onClick={() => onOpenItem(item.part_of)}>{item.kit_name}</button>
        {item.kit_code && <span className="muted"> ({item.kit_code})</span>}</p>
    )
  }
  const add = async (list) => {
    setBusy(true)
    setError('')
    try {
      setItem(await api.addSupplyParts(item.supply_id, list.map((n) => ({ name: n }))))
      setName('')
      onChanged()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  const chosen = suggested.filter((p) => ticked.has(p))
  const toggle = (p) => setTicked((s) => { const n = new Set(s); if (n.has(p)) n.delete(p); else n.add(p); return n })
  const body = (
    <>
      {parts.length > 0 && (
        <ul className="list plain-list kit-list">{parts.map((p) => (
          <li key={p.supply_id}>
            <button type="button" className="row-button" onClick={() => onOpenItem(p.supply_id)}>
              <span className="grow"><span className="item-title">{p.name}</span>
                <span className="item-meta">{[p.category, `${p.qty_on_hand} on hand`].join(' · ')}</span></span>
              {p.stock_status !== 'OK' && <span className="pill low">{p.stock_status}</span>}
            </button>
          </li>))}</ul>
      )}
      {suggested.length > 0 && (
        <div className="kit-suggest">
          <p className="small">{parts.length ? 'It also comes with:' : 'It says it comes with - add them as parts, so you can find each one:'}</p>
          {suggested.map((p) => (
            <label key={p} className="tick-row"><input type="checkbox" checked={ticked.has(p)} onChange={() => toggle(p)} /> {p}</label>
          ))}
          <button type="button" className="secondary small" disabled={busy || !chosen.length}
            onClick={() => add(chosen)}>Add {chosen.length} part{chosen.length === 1 ? '' : 's'}</button>
        </div>
      )}
      <form className="kit-add" onSubmit={(e) => { e.preventDefault(); if (name.trim()) add([name.trim()]) }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sanding Stick #400" aria-label="Part name" maxLength={200} />
        <button type="submit" className="plain small" disabled={busy || !name.trim()}>+ Add a part</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
    </>
  )
  if (!parts.length && !suggested.length) {
    return <section className="panel-section"><Fold title="A kit? Its parts" detail="each part its own supply">{body}</Fold></section>
  }
  return (
    <section className="panel-section" aria-label="In this kit">
      <h3 className="section-title">In this kit{parts.length ? ` · ${parts.length}` : ''}</h3>
      {body}
    </section>
  )
}
