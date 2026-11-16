import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { api, imageUrl, shortDate } from '../../api.js'
import { FAMILIES } from '../../components/supplyExtras.jsx'
import { useApp } from '../app-context.js'
import { rackBrands, rackGroups } from './rack.js'

// More Supplies tools (2026-11-16), reached from Supplies > Options > Tools:
//   StockReport   Out and Low supplies (one tap puts them on the wishlist) and opened ones past, or near, their shelf life
//   PaintRack     your paints as a grid of swatches by brand and code

const Back = () => <Link to="/supplies" className="plain sx-back">‹ Supplies</Link>
const thumb = (r) => (r.has_image ? <img className="thumb" src={imageUrl(r)} alt="" loading="lazy" /> : <span className="thumb thumb-empty" aria-hidden="true" />)

export function StockReport() {
  const { refreshKey, changed, showToast, openItem } = useApp()
  const [r, setR] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.stockReport().then(setR).catch(() => setR({ out: [], low: [], old: [], to_add: 0 })) }, [refreshKey])
  if (!r) return <p className="muted loading">Loading...</p>
  const addAll = async () => {
    setBusy(true)
    try {
      const done = await api.stockReportToWishlist()
      showToast(done.added.length ? `Added to the wishlist: ${done.added.join(', ')}` : 'Nothing new to add')
      changed()
    } catch (e) { showToast(e.message) } finally { setBusy(false) }
  }
  const row = (s, detail) => (
    <li key={s.supply_id}>
      <button type="button" className="row-button" onClick={() => openItem(s.supply_id)}>
        {thumb(s)}
        <span className="grow"><span className="item-title">{s.name}</span>
          <span className="item-meta">{[s.brand, s.product_code, detail].filter(Boolean).join(' · ')}</span></span>
        {s.on_wishlist && <span className="tag">On wishlist</span>}
      </button>
    </li>
  )
  const empty = !r.out.length && !r.low.length && !r.old.length
  return (
    <section className="page sx-page">
      <div className="toolbar"><Back /><h2 className="sx-title">Low, out and getting old</h2><span className="grow" />
        {r.to_add > 0 && <button type="button" className="primary" disabled={busy} onClick={addAll}>Add the {r.to_add} to the wishlist</button>}</div>
      {empty && <p className="empty card">Everything is stocked and nothing is past its shelf life.</p>}
      {r.out.length > 0 && <div className="card"><h3 className="home-card-title">Out · {r.out.length}</h3>
        <ul className="list plain-list">{r.out.map((s) => row(s, s.condition))}</ul></div>}
      {r.low.length > 0 && <div className="card"><h3 className="home-card-title">Low · {r.low.length}</h3>
        <ul className="list plain-list">{r.low.map((s) => row(s, `${s.qty_on_hand} left`))}</ul></div>}
      <div className="card">
        <h3 className="home-card-title">Getting old · {r.old.length}</h3>
        <p className="muted small">Opened supplies whose shelf life is up or ends within a month. Set "opened on" and "check after" on a supply.</p>
        {r.old.length === 0 ? <p className="muted small">Nothing yet.</p>
          : <ul className="list plain-list">{r.old.map((s) => row(s, s.check_due ? `check it: due ${shortDate(s.check_by)}` : `check by ${shortDate(s.check_by)}`))}</ul>}
      </div>
    </section>
  )
}

// The colour comes from the paint's swatch, else its photo, else a plain chip.
export function PaintRack() {
  const { refreshKey, openItem } = useApp()
  const [supplies, setSupplies] = useState(null)
  const [f, setF] = useState({ brand: '', family: '', text: '', attention: false })
  useEffect(() => { api.listSupplies().then(setSupplies).catch(() => setSupplies([])) }, [refreshKey])
  const groups = useMemo(() => (supplies ? rackGroups(supplies, f) : []), [supplies, f])
  if (!supplies) return <p className="muted loading">Loading...</p>
  const set = (patch) => setF((x) => ({ ...x, ...patch }))
  return (
    <section className="page sx-page">
      <div className="toolbar"><Back /><h2 className="sx-title">Paint rack</h2></div>
      <div className="toolbar rack-filters">
        <input type="search" value={f.text} onChange={(e) => set({ text: e.target.value })} placeholder="Find a paint or code" aria-label="Find a paint" />
        <select value={f.brand} onChange={(e) => set({ brand: e.target.value })} aria-label="Brand">
          <option value="">All brands</option>
          {rackBrands(supplies).map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <label className="rack-check"><input type="checkbox" checked={f.attention} onChange={(e) => set({ attention: e.target.checked })} /> Low or out only</label>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Colour">
        {FAMILIES.map((c) => (
          <button key={c} type="button" className="chip-filter" aria-pressed={f.family === c} onClick={() => set({ family: f.family === c ? '' : c })}>{c}</button>
        ))}
      </div>
      {groups.length === 0 && <p className="empty card">No paints match.</p>}
      {groups.map((g) => (
        <div key={g.brand} className="card rack-brand">
          <h3 className="home-card-title">{g.brand}<span className="muted small"> {g.items.length}</span></h3>
          <ul className="rack-grid">
            {g.items.map((s) => (
              <li key={s.supply_id}>
                <button type="button" className={s.stock_status === 'OK' ? 'rack-tile' : 'rack-tile rack-attention'} onClick={() => openItem(s.supply_id)}
                  aria-label={`${s.name}${s.product_code ? `, ${s.product_code}` : ''}, ${s.qty_on_hand} in stock`}>
                  <span className="rack-chip" style={s.swatch ? { background: s.swatch } : undefined}>
                    {!s.swatch && s.has_image && <img src={imageUrl(s)} alt="" loading="lazy" />}
                    {s.stock_status !== 'OK' && <span className="rack-flag">{s.stock_status}</span>}
                  </span>
                  <span className="rack-code">{s.product_code ?? '-'}</span>
                  <span className="rack-name">{s.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
