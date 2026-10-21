import { useEffect, useState } from 'react'
import { api, imageUrl, money, shortDate } from '../api.js'
import { useApp } from '../core/app-context.js'
import { MODULES } from '../modules/index.js'
import { FillBar, fillOf } from '../modules/models/fill.jsx'
import { Swatch } from './supplyExtras.jsx'

// The Supplies page's parts (split out of InventoryView.jsx, 2026-10-22): a hobby's section heading, the tables of
// supplies and of other hobbies' kit, a row's tags, the Select-several bar, the condition and category pills.
export const hobbyName = (id) => MODULES.find((m) => m.id === id)?.name ?? id

// A hobby's part of the page: its heading (name, how many, and "N need attention" - for the model supplies, a button
// that shows just those), then its groups. With every hobby showing, the heading also folds the hobby away (remembered).
export function HobbySection({ fold, id, count, attention, attentionOn, onAttention, open, onToggle, children }) {
  const title = <><span className="inv-hobby-title">{hobbyName(id)}</span><span className="muted small">{count} item{count === 1 ? '' : 's'}</span></>
  return (
    <section className="inv-hobby" aria-label={hobbyName(id)}>
      <div className="inv-hobby-head">
        {fold ? (
          <button type="button" className="inv-hobby-fold" aria-expanded={open} onClick={() => onToggle(id, !open)}>
            <span className="inv-chevron" aria-hidden="true">▾</span>{title}
          </button>
        ) : <span className="inv-hobby-fold">{title}</span>}
        {attention > 0 && (onAttention
          ? <button type="button" className="chip-filter attention inv-attn" aria-pressed={attentionOn} onClick={onAttention}>{attention} need attention</button>
          : <span className="badge low">{attention} need attention</span>)}
      </div>
      {(!fold || open) && children}
    </section>
  )
}

// Another hobby's kit: its photo, name and details, its state, and how many (where it counts them).
export function OwnedTable({ rows, onOpen }) {
  return (
    <table className="inventory">
      <thead className="quiet">
        <tr>
          <th className="thumb-col"><span className="visually-hidden">Photo</span></th>
          <th>Item</th>
          <th className="col-condition hide-xs">State</th>
          <th className="col-stock num">Have</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((o) => (
          <tr key={`${o.open}-${o.id}`} className={o.attention ? 'row attention' : 'row'} onClick={() => onOpen(o)} tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onOpen(o)}>
            <td className="thumb-col">
              {o.photo_url ? <img className="thumb" src={o.photo_url} alt="" loading="lazy" /> : <span className="thumb thumb-empty" aria-hidden="true" />}
            </td>
            <td className="item-cell">
              <span className="item-title">{o.name}</span>
              <span className="item-meta">{o.detail}<span className="show-xs"> {o.status}</span></span>
            </td>
            <td className="hide-xs"><span className={o.attention ? 'condition inv-warn' : 'condition'}>{o.status}</span></td>
            <td className="num">{o.amount ?? ''}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// One table of supplies: the whole list, or one group. Every group's table has the same fixed
// column widths, so the columns line up down the page. Grouped by category, the Category column
// is left out (every row in a "Paint" group says Paint).
export function SupplyTable({ rows, showHead = false, showCategory = false, onOpen, adjust, selected = null }) {
  return (
    <table className="inventory">
      <thead className={showHead ? '' : 'quiet'}>
        <tr>
          {selected && <th className="inv-pick-col"><span className="visually-hidden">Selected</span></th>}
          <th className="thumb-col"><span className="visually-hidden">Photo</span></th>
          <th>Item</th>
          {showCategory && <th className="col-category hide-sm">Category</th>}
          <th className="col-condition hide-xs">Condition</th>
          <th className="col-stock num">Stock</th>
          <th className="col-value num hide-sm">Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.supply_id} className={`${r.stock_status === 'OK' ? 'row' : 'row attention'}${selected?.includes(r.supply_id) ? ' picked' : ''}`}
            onClick={() => onOpen(r.supply_id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpen(r.supply_id)}>
            {selected && (
              <td className="inv-pick-col">
                <input type="checkbox" checked={selected.includes(r.supply_id)} readOnly tabIndex={-1} aria-label={`Select ${r.name}`} />
              </td>
            )}
            <td className="thumb-col">
              {r.has_image
                ? <img className="thumb" src={imageUrl(r)} alt="" loading="lazy" />
                : <span className="thumb thumb-empty" aria-hidden="true" />}
            </td>
            <td className="item-cell">
              <span className="item-title"><Swatch hex={r.swatch} /> {r.name}</span>
              <RowTags row={r} />
              <span className="item-meta">
                {[r.brand, r.product_code, r.size, r.kit_name && `in ${r.kit_name}`, r.part_count > 0 && `kit · ${r.part_count} parts`].filter(Boolean).join(' · ')}
                {/* On phones the Condition column is hidden, so show it here instead */}
                <span className="show-xs"><Condition row={r} /></span>
              </span>
            </td>
            {showCategory && <td className="hide-sm"><CategoryPill name={r.category} /></td>}
            <td className="hide-xs"><Condition row={r} /><FillBar percent={fillOf(r)} /></td>
            <td className="num">
              <span className="qty" onClick={(e) => e.stopPropagation()}>
                <button aria-label={`Use one ${r.name}`} disabled={r.qty_on_hand <= 0} onClick={() => adjust(r, -1)}>−</button>
                <span>{r.qty_on_hand}</span>
                <button aria-label={`Add one ${r.name}`} onClick={() => adjust(r, 1)}>+</button>
              </span>
            </td>
            <td className="num hide-sm">{money(r.total_value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// The little notes on a row: set aside for a build, check it (opened a while ago), running out soon, warranty ending.
export function RowTags({ row: r }) {
  const soon = r.out_by && (new Date(`${r.out_by}T12:00:00`) - Date.now()) / 86400000 <= 45
  if (!r.reserved_for && !r.check_due && !soon && !r.warranty_soon) return null
  return (
    <span className="inv-tags">
      {r.reserved_for && <span className="tag">🔖 {r.reserved_for}</span>}
      {r.check_due && <span className="tag inv-tag-warn">Check it</span>}
      {soon && <span className="tag inv-tag-warn">Out ~{shortDate(r.out_by)}</span>}
      {r.warranty_soon && <span className="tag inv-tag-warn">Warranty ending</span>}
    </span>
  )
}

// Several supplies picked: do one thing to all of them.
export function BulkBar({ selected, onDone, onCancel, onAll }) {
  const { lookups, changed, showToast } = useApp()
  const [models, setModels] = useState([])
  const [confirm, setConfirm] = useState(false)
  useEffect(() => { api.listModels().then((all) => setModels(all.filter((m) => !['Wanted', 'Finished', 'Gone'].includes(m.status)))).catch(() => {}) }, [])
  const run = async (action, value = null, said = '') => {
    try {
      const r = await api.bulkSupplies(selected, action, value)
      showToast(`${r.changed} ${said}`)
      changed()
      onDone()
    } catch (e) {
      showToast(e.message)
    }
  }
  const pick = (action, said) => (e) => { const v = e.target.value; e.target.value = ''; if (v !== '') run(action, v === 'none' ? null : Number(v), said) }
  return (
    <div className="inv-bulk" role="region" aria-label="Selected supplies">
      <strong>{selected.length} selected</strong>
      <button type="button" className="plain small" onClick={onAll}>Select all shown</button>
      {selected.length > 0 && <>
        <select defaultValue="" aria-label="Move the selected to" onChange={pick('move', 'moved')}>
          <option value="">Move to…</option>
          {lookups.locations.map((l) => <option key={l.id} value={l.id}>{l.path ?? l.name}</option>)}
        </select>
        <select defaultValue="" aria-label="Change the selected category" onChange={pick('category', 'changed')}>
          <option value="">Category…</option>
          {lookups.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select defaultValue="" aria-label="Set the selected aside for" onChange={pick('reserve', 'set aside')}>
          <option value="">Set aside for…</option>
          <option value="none">(nothing)</option>
          {models.map((m) => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
        </select>
        <button type="button" className="secondary small" onClick={() => run('wishlist', null, 'added to the wishlist')}>+ Wishlist</button>
        {confirm ? (
          <span className="confirm">Remove {selected.length}?
            <button type="button" className="danger small" onClick={() => run('delete', null, 'removed')}>Remove</button>
            <button type="button" className="plain small" onClick={() => setConfirm(false)}>No</button>
          </span>
        ) : <button type="button" className="plain small destructive" onClick={() => setConfirm(true)}>Remove</button>}
      </>}
      <span className="grow" />
      <button type="button" className="plain small" onClick={onCancel}>Done</button>
    </div>
  )
}

// Condition, plus a Low / Out badge only when it applies, and "On wishlist" when it is.
export function Condition({ row }) {
  return (
    <span className="condition">
      {row.condition ?? <span className="muted">—</span>}
      {row.stock_status !== 'OK' && <span className={`badge ${row.stock_status.toLowerCase()}`}>{row.stock_status}</span>}
      {row.on_wishlist && <span className="tag">On wishlist</span>}
    </span>
  )
}

// Each category always gets the same colour (from its name), so they're easy to tell apart.
export const PILL_TONES = ['tint', 'purple', 'teal', 'low', 'ok', 'out']
export function CategoryPill({ name }) {
  if (!name) return null
  const tone = PILL_TONES[[...name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % PILL_TONES.length]
  return <span className={`pill ${tone}`}>{name}</span>
}
