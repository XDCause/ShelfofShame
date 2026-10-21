import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, imageUrl, money, shortDate } from '../../api.js'
import { Swatch } from '../../components/supplyExtras.jsx'
import { useApp } from '../app-context.js'

// Supplies' tools (2026-10-21): places and their QR labels, a place's own page (where a label's QR code opens), shopping
// mode, stocktake and the value report. Reached from Supplies > Options > Tools.

const Back = () => <Link to="/supplies" className="plain sx-back">‹ Supplies</Link>
const thumb = (r) => (r.has_image ? <img className="thumb" src={imageUrl(r)} alt="" loading="lazy" /> : <span className="thumb thumb-empty" aria-hidden="true" />)

// ---------------------------------------------------------------- places
export function PlacesPage() {
  const { refreshKey, changed, showToast } = useApp()
  const [places, setPlaces] = useState(null)
  const [name, setName] = useState('')
  const [adding, setAdding] = useState(null)        // the place a new one goes inside (0 = top level)
  const [renaming, setRenaming] = useState(null)
  const [picked, setPicked] = useState([])
  const load = () => api.places().then(setPlaces).catch(() => setPlaces([]))
  useEffect(() => { load() }, [refreshKey])
  const add = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    try { await api.addPlace({ name: name.trim(), parent_id: adding || null }); setName(''); setAdding(null); changed() } catch (err) { showToast(err.message) }
  }
  const rename = async (p, value) => {
    setRenaming(null)
    if (value.trim() && value.trim() !== p.name) {
      try { await api.changePlace(p.id, { name: value.trim() }); changed() } catch (err) { showToast(err.message) }
    }
  }
  const remove = async (p) => { try { await api.deletePlace(p.id); changed() } catch (err) { showToast(err.message) } }
  const depth = (p) => p.path.split(' › ').length - 1
  const addForm = (
    <form className="sx-inline" onSubmit={add}>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder={adding ? 'e.g. Drawer 3' : 'e.g. Paint rack'} aria-label="New place's name" maxLength={60} autoFocus />
      <button type="submit" className="secondary">Add</button>
      <button type="button" className="plain" onClick={() => setAdding(null)}>Cancel</button>
    </form>
  )
  return (
    <section className="page sx-page">
      <div className="toolbar"><Back /><h2 className="sx-title">Places and labels</h2><span className="grow" />
        {picked.length > 0 && <Link className="primary sx-btnlink" to={`/supplies/labels?ids=${picked.join(',')}`}>Print {picked.length} label{picked.length === 1 ? '' : 's'}</Link>}
        <button type="button" className="secondary" onClick={() => setAdding(0)}>+ Place</button>
      </div>
      <p className="muted">Where things live: a rack, a drawer in it, a box in that. Tick places to print QR labels for them -
        scanning one with your phone shows what's inside (and lets you move things in).</p>
      {adding === 0 && addForm}
      {places?.length === 0 && <p className="empty card">No places yet. Add the first: a rack, a cupboard, a toolbox.</p>}
      <ul className="card sx-places">
        {(places ?? []).map((p) => (
          <li key={p.id} style={{ '--depth': depth(p) }}>
            <label className="sx-pick"><input type="checkbox" checked={picked.includes(p.id)} aria-label={`Label for ${p.path}`}
              onChange={() => setPicked((x) => (x.includes(p.id) ? x.filter((i) => i !== p.id) : [...x, p.id]))} /></label>
            {renaming === p.id ? (
              <input defaultValue={p.name} autoFocus aria-label={`Rename ${p.name}`} maxLength={60}
                onBlur={(e) => rename(p, e.target.value)} onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()} />
            ) : <Link to={`/supplies/place/${p.id}`} className="sx-place-name">{p.name}</Link>}
            <span className="muted small">{p.items} item{p.items === 1 ? '' : 's'}</span>
            <span className="grow" />
            <button type="button" className="plain small" onClick={() => setAdding(p.id)}>+ Inside</button>
            <button type="button" className="plain small" onClick={() => setRenaming(p.id)}>Rename</button>
            {!p.items && !p.children && <button type="button" className="plain small destructive" onClick={() => remove(p)}>Delete</button>}
            {adding === p.id && <div className="sx-place-add">{addForm}</div>}
          </li>
        ))}
      </ul>
    </section>
  )
}

// The labels to print: each place's QR code (opens its page in the app) and its name.
export function LabelsPage() {
  const [params] = useSearchParams()
  const ids = (params.get('ids') ?? '').split(',').map(Number).filter(Boolean)
  const [places, setPlaces] = useState([])
  useEffect(() => { api.places().then((all) => setPlaces(all.filter((p) => ids.includes(p.id)))).catch(() => {}) }, [params]) // eslint-disable-line react-hooks/exhaustive-deps -- (ids comes from params)
  return (
    <section className="page sx-page">
      <div className="toolbar sx-noprint"><Link to="/supplies/places" className="plain">‹ Places</Link><span className="grow" />
        <button type="button" className="primary" onClick={() => window.print()}>Print labels</button></div>
      <p className="muted sx-noprint">Cut them out and stick each on its drawer or box. The codes open this app, so they work on your home Wi-Fi (or Tailscale).</p>
      <div className="sx-labels">
        {places.map((p) => (
          <figure key={p.id} className="sx-label">
            <img src={api.placeQrUrl(p.id, `${window.location.origin}/supplies/place/${p.id}`)} alt={`QR code for ${p.path}`} />
            <figcaption><strong>{p.name}</strong>{p.path !== p.name && <span>{p.path}</span>}</figcaption>
          </figure>
        ))}
      </div>
    </section>
  )
}

// One place (where a label's QR code leads): what's in it and the places inside it; move things in from here.
export function PlacePage() {
  const { id } = useParams()
  const { refreshKey, openItem, changed, showToast } = useApp()
  const [place, setPlace] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [all, setAll] = useState([])
  useEffect(() => { api.place(id).then(setPlace).catch((e) => setError(e.message)) }, [id, refreshKey])
  useEffect(() => { api.listSupplies().then(setAll).catch(() => {}) }, [refreshKey])
  const matches = useMemo(() => (q.trim().length < 2 ? [] : all.filter((s) => s.location_id !== Number(id)
    && [s.name, s.product_code, s.brand].some((v) => v && v.toLowerCase().includes(q.trim().toLowerCase()))).slice(0, 8)), [q, all, id])
  const move = async (s) => {
    try { await api.moveToPlace(id, [s.supply_id]); showToast(`${s.name} is now in ${place.name}`); setQ(''); changed() } catch (e) { showToast(e.message) }
  }
  if (error) return <p className="alert error">{error} <Back /></p>
  if (!place) return <p className="muted loading">Loading...</p>
  return (
    <section className="page sx-page">
      <div className="toolbar"><Link to="/supplies/places" className="plain">‹ Places</Link></div>
      <h2 className="sx-title">🗄️ {place.path}</h2>
      {place.inside.length > 0 && (
        <div className="chips">{place.inside.map((p) => <Link key={p.id} className="chip-filter" to={`/supplies/place/${p.id}`}>{p.name} <span className="chip-count">{p.items}</span></Link>)}</div>
      )}
      <div className="card">
        <h3 className="home-card-title">In here · {place.supplies.length}</h3>
        {place.supplies.length === 0 ? <p className="muted small">Nothing yet.</p> : (
          <ul className="list plain-list">
            {place.supplies.map((s) => (
              <li key={s.supply_id}>
                <button type="button" className="row-button" onClick={() => openItem(s.supply_id)}>
                  {thumb(s)}
                  <span className="grow"><span className="item-title"><Swatch hex={s.swatch} /> {s.name}</span>
                    <span className="item-meta">{[s.brand, s.product_code, s.location_id !== Number(id) && s.location_path].filter(Boolean).join(' · ')}</span></span>
                  <span className="muted">×{s.qty_on_hand}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="card">
        <h3 className="home-card-title">Move something here</h3>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your supplies" aria-label="Find a supply to move here" />
        {matches.length > 0 && (
          <ul className="list plain-list">
            {matches.map((s) => (
              <li key={s.supply_id}>
                <button type="button" className="row-button" onClick={() => move(s)}>
                  {thumb(s)}<span className="grow"><span className="item-title">{s.name}</span>
                    <span className="item-meta">{s.location_path ? `now in ${s.location_path}` : 'no place yet'}</span></span>
                  <span className="pill tint">Move here</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- shopping mode
// One screen for a trip to the shop: your wishlist, then what's Low / Out and what'll run out soon. A tick buys it
// (adds it to your supplies, takes it off the wishlist).
function ShopRow({ name, detail, done, onTick }) {
  return (
    <li className={done ? 'sx-shop-row done' : 'sx-shop-row'}>
      <button type="button" className="sx-tick" aria-pressed={done} disabled={done} onClick={onTick} aria-label={`Bought ${name}`}>{done ? '✓' : ''}</button>
      <span className="grow"><strong>{name}</strong>{detail && <span className="muted small"> {detail}</span>}</span>
    </li>
  )
}

export function ShopMode() {
  const { refreshKey, changed, showToast } = useApp()
  const [list, setList] = useState(null)
  const [done, setDone] = useState([])
  useEffect(() => { api.shopList().then(setList).catch(() => setList({ wishlist: [], low: [], soon: [] })) }, [refreshKey])
  const tick = async (key, fn, name) => {
    try { await fn(); setDone((d) => [...d, key]); showToast(`Bought: ${name}`); changed() } catch (e) { showToast(e.message) }
  }
  if (!list) return <p className="muted loading">Loading...</p>
  const empty = !list.wishlist.length && !list.low.length && !list.soon.length
  return (
    <section className="page sx-page sx-shop">
      <div className="toolbar"><Back /><h2 className="sx-title">🛒 Shopping at {list.shop}</h2></div>
      {empty && <p className="empty card">Nothing to buy - everything's stocked and your wishlist is empty.</p>}
      {list.wishlist.length > 0 && (
        <div className="card"><h3 className="home-card-title">On your wishlist · {list.wishlist.length}</h3>
          <ul className="sx-shop-list">{list.wishlist.map((w) => (
            <ShopRow key={`w${w.wish_id}`} done={done.includes(`w${w.wish_id}`)} name={w.name}
              detail={[w.brand, w.product_code, w.qty_wanted > 1 && `×${w.qty_wanted}`, w.price != null && money(w.price)].filter(Boolean).join(' · ')}
              onTick={() => tick(`w${w.wish_id}`, () => api.buyWish(w.wish_id), w.name)} />
          ))}</ul></div>
      )}
      {list.low.length > 0 && (
        <div className="card"><h3 className="home-card-title">Low or out · {list.low.length}</h3>
          <ul className="sx-shop-list">{list.low.map((s) => (
            <ShopRow key={`s${s.supply_id}`} done={done.includes(`s${s.supply_id}`)} name={s.name} detail={[s.brand, s.product_code, s.stock_status].filter(Boolean).join(' · ')}
              onTick={() => tick(`s${s.supply_id}`, () => api.adjustQty(s.supply_id, 1), s.name)} />
          ))}</ul></div>
      )}
      {list.soon.length > 0 && (
        <div className="card"><h3 className="home-card-title">Likely to run out this month · {list.soon.length}</h3>
          <ul className="sx-shop-list">{list.soon.map((s) => (
            <ShopRow key={`s${s.supply_id}`} done={done.includes(`s${s.supply_id}`)} name={s.name} detail={`about ${shortDate(s.out_by)}`}
              onTick={() => tick(`s${s.supply_id}`, () => api.adjustQty(s.supply_id, 1), s.name)} />
          ))}</ul></div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- stocktake
// One item at a time, the least recently counted first: still the same, one less, empty, or type the count.
export function Stocktake() {
  const { changed, showToast } = useApp()
  const [items, setItems] = useState(null)
  const [i, setI] = useState(0)
  const [n, setN] = useState(0)
  const [counted, setCounted] = useState(0)
  useEffect(() => { api.stocktake().then(setItems).catch(() => setItems([])) }, [])
  const item = items?.[i]
  useEffect(() => { if (item) setN(item.qty_on_hand) }, [item])
  const save = async (qty) => {
    try {
      await api.countSupply(item.supply_id, qty)
    } catch (e) {
      showToast(`Not saved: ${e.message}`)               // (stays on this one, to try again)
      return
    }
    setCounted((c) => c + 1)
    changed()
    setI((x) => x + 1)
  }
  if (!items) return <p className="muted loading">Loading...</p>
  return (
    <section className="page sx-page sx-count">
      <div className="toolbar"><Back /><h2 className="sx-title">✅ Stocktake</h2><span className="grow" />
        <span className="muted">{Math.min(i + 1, items.length)} of {items.length}</span></div>
      {!item ? (
        <div className="card sx-count-done"><p>All counted{counted ? ` - ${counted} checked` : ''}. Nice.</p><Back /></div>
      ) : (
        <div className="card sx-count-card">
          <div className="sx-count-photo">{item.has_image ? <img src={imageUrl(item)} alt="" /> : <span className="photo-missing">No photo</span>}</div>
          <h3><Swatch hex={item.swatch} size={16} /> {item.name}</h3>
          <p className="muted">{[item.brand, item.product_code, item.location_path && `📍 ${item.location_path}`].filter(Boolean).join(' · ')}</p>
          <p className="small muted">{item.counted_at ? `Last counted ${shortDate(item.counted_at.slice(0, 10))}` : 'Never counted'}</p>
          <div className="sx-count-qty">
            <button type="button" className="step" aria-label="One less" onClick={() => setN(Math.max(0, n - 1))}>−</button>
            <strong aria-live="polite">{n}</strong>
            <button type="button" className="step" aria-label="One more" onClick={() => setN(n + 1)}>+</button>
          </div>
          <div className="button-row sx-count-actions">
            <button type="button" className="primary" onClick={() => save(n)}>{n === item.qty_on_hand ? `✓ Still ${n}` : `Save: ${n}`}</button>
            <button type="button" className="secondary" onClick={() => save(0)}>Empty</button>
            <button type="button" className="plain" onClick={() => setI(i + 1)}>Skip</button>
          </div>
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- value report
// What you own and what it cost, per hobby - to print or save as a PDF for insurance.
export function ValueReport() {
  const [r, setR] = useState(null)
  useEffect(() => { api.valueReport().then(setR).catch(() => setR({ sections: [], total: 0, unpriced: 0 })) }, [])
  if (!r) return <p className="muted loading">Loading...</p>
  return (
    <section className="page sx-page sx-report">
      <div className="toolbar sx-noprint"><Back /><span className="grow" /><button type="button" className="primary" onClick={() => window.print()}>Print or save as PDF</button></div>
      <header className="sx-report-head">
        <p className="jx-print-kicker">Off the Clock · what I own</p>
        <h2 className="sx-title">{money(r.total)}</h2>
        <p className="muted">As of {shortDate(r.on)} · what was paid, from each hobby's records{r.unpriced ? ` · ${r.unpriced} thing${r.unpriced === 1 ? '' : 's'} with no price (counted as $0)` : ''}</p>
      </header>
      {r.sections.map((s) => (
        <section key={s.title} className="card sx-report-part">
          <h3 className="home-card-title">{s.title}<span className="muted small"> {s.count} · {money(s.total)}</span></h3>
          <table className="table compact">
            <thead><tr><th>Item</th><th className="hide-xs">Details</th><th className="num">Qty</th><th className="num">Value</th></tr></thead>
            <tbody>{s.items.map((x, k) => (
              <tr key={k}><td>{x.name}</td><td className="hide-xs muted">{x.detail}</td><td className="num">{x.qty}</td>
                <td className="num">{x.value == null ? <span className="muted">no price</span> : money(x.value)}</td></tr>
            ))}</tbody>
          </table>
        </section>
      ))}
    </section>
  )
}
