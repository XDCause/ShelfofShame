import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, money, photoFromUrl, shortDate } from '../api.js'
import { useApp } from '../core/app-context.js'
import { MODULES } from '../modules/index.js'
import Drawer from './Drawer.jsx'
import { shrink } from './PhotoUpload.jsx'

// More for the wishlist (2026-10-21): the little notes on a card, a wanted thing's details panel (what it's for, target
// price, saving up, its price history, asking its shop), adding one from a shop link, what you've bought, the gift list.
// Things you want live in five places, so each is (kind, ref): wish (a supply), model, game, gear, garden.

export const hobbyName = (id) => MODULES.find((m) => m.id === id)?.name ?? id
export const extraOf = (extras, kind, ref) => extras?.[`${kind}:${ref}`]

// The notes on a card: how long it's waited, what it's for, a price under your target, stock, money saved.
export function ExtraTags({ x }) {
  if (!x) return null
  const target = x.save_for
  return (
    <span className="wx-tags">
      {x.days >= 1 && <span className={x.days >= 30 ? 'tag wx-wait' : 'tag'} title={`On your list since ${shortDate(x.added)}`}>
        {x.days} day{x.days === 1 ? '' : 's'}{x.days >= 30 ? ' · still want it?' : ''}</span>}
      {x.for_model && <span className="tag">🔖 {x.for_model}</span>}
      {x.for_goal && <span className="tag">🎯 {x.for_goal}</span>}
      {x.below_target && <span className="tag wx-good">Under your {money(x.target_price)} ✓</span>}
      {x.in_stock === false && <span className="tag wx-warn">Out of stock</span>}
      {x.in_stock === true && <span className="tag wx-good">In stock</span>}
      {x.saved > 0 && (
        <span className="wx-saved" title={`Saved ${money(x.saved)}${target ? ` of ${money(target)}` : ''}`}>
          <span className="wx-saved-bar" aria-hidden="true"><i style={{ width: `${target ? Math.min(100, (x.saved / target) * 100) : 100}%` }} /></span>
          <span className="small">Saved {money(x.saved)}{target ? ` of ${money(target)}` : ''}</span>
        </span>
      )}
    </span>
  )
}

// ---------------------------------------------------------------- one wanted thing's details
export function WantedPanel({ kind, wantedRef: ref, name, onClose }) {
  const { refreshKey, changed, showToast, openThing } = useApp()
  const [x, setX] = useState(null)
  const [history, setHistory] = useState([])
  const [models, setModels] = useState([])
  const [goals, setGoals] = useState([])
  const [amount, setAmount] = useState('')
  const [seen, setSeen] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api.wantedExtras().then((all) => setX(all[`${kind}:${ref}`] ?? null)).catch(() => setX(null))
    api.wantedPrices(kind, ref).then(setHistory).catch(() => setHistory([]))
  }, [kind, ref, refreshKey])
  useEffect(() => {
    api.listModels().then((all) => setModels(all.filter((m) => !['Wanted', 'Finished', 'Gone'].includes(m.status)))).catch(() => {})
    api.goals('active').then((r) => setGoals(Array.isArray(r) ? r : r.goals ?? [])).catch(() => {})
  }, [])
  const run = async (fn, said) => {
    setBusy(true)
    try { const got = await fn(); if (got) setX(got); if (said) showToast(said); changed() } catch (e) { showToast(e.message) } finally { setBusy(false) }
  }
  if (!x) return <Drawer title={name ?? 'Wanted'} onClose={onClose}><p className="muted">Loading...</p></Drawer>
  return (
    <Drawer title={name ?? 'Wanted'} onClose={onClose}>
      <section className="panel-section">
        <p className="muted small">On your list for {x.days} day{x.days === 1 ? '' : 's'} (since {shortDate(x.added)}) · {hobbyName(x.hobby)}</p>
        {kind !== 'wish' && <button type="button" className="plain small" onClick={() => { onClose(); openThing(kind === 'garden' ? 'garden' : kind, ref) }}>Open its own page ›</button>}
      </section>
      <section className="panel-section quick-grid">
        <label className="field">
          <span className="field-label">For a build</span>
          <select value={x.for_model_id ?? ''} onChange={(e) => run(() => api.setWantedExtras(kind, ref, { for_model_id: e.target.value ? Number(e.target.value) : null }))}>
            <option value="">—</option>
            {models.map((m) => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field-label">For a goal</span>
          <select value={x.for_goal_id ?? ''} onChange={(e) => run(() => api.setWantedExtras(kind, ref, { for_goal_id: e.target.value ? Number(e.target.value) : null }))}>
            <option value="">—</option>
            {goals.map((g) => <option key={g.goal_id} value={g.goal_id}>{g.title}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Tell me when it's under</span>
          <input type="number" min="0" step="0.01" defaultValue={x.target_price ?? ''} placeholder="$"
            onBlur={(e) => run(() => api.setWantedExtras(kind, ref, { target_price: e.target.value === '' ? null : e.target.value }))} />
        </label>
        {x.below_target && <p className="field small wx-good-text">It's {money(x.last_price ?? x.price)} - under your target ✓</p>}
      </section>
      <section className="panel-section">
        <h4 className="section-title">Saving up</h4>
        <p className="small">Saved <strong>{money(x.saved)}</strong>{x.save_for ? <> of <strong>{money(x.save_for)}</strong></> : ''}</p>
        {x.save_for > 0 && <span className="wx-saved-bar big" aria-hidden="true"><i style={{ width: `${Math.min(100, (x.saved / x.save_for) * 100)}%` }} /></span>}
        <form className="sx-inline" onSubmit={(e) => { e.preventDefault(); if (amount) run(() => api.saveForWanted(kind, ref, amount), `Put ${money(amount)} aside`); setAmount('') }}>
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="$ (- to take back)" aria-label="Amount to put aside" />
          <button type="submit" className="secondary" disabled={busy}>Put aside</button>
        </form>
      </section>
      <section className="panel-section">
        <h4 className="section-title">Prices seen</h4>
        {history.length === 0 ? <p className="muted small">None yet.</p> : (
          <ul className="wx-prices">
            {history.map((p, i) => <li key={i}><strong>{money(p.price)}</strong> <span className="muted small">{p.source} · {shortDate(p.seen_at.slice(0, 10))}</span></li>)}
          </ul>
        )}
        {x.lowest_price != null && x.prices > 1 && <p className="small muted">Lowest seen: {money(x.lowest_price)}</p>}
        <div className="sx-inline">
          <form className="sx-inline" onSubmit={(e) => { e.preventDefault(); if (seen) run(() => api.addWantedPrice(kind, ref, seen), 'Price kept'); setSeen('') }}>
            <input type="number" min="0" step="0.01" value={seen} onChange={(e) => setSeen(e.target.value)} placeholder="$ you saw" aria-label="A price you saw" />
            <button type="submit" className="secondary" disabled={busy}>Add price</button>
          </form>
          {(kind === 'gear' || kind === 'game') && (
            <button type="button" className="plain" disabled={busy} onClick={() => run(() => api.checkWanted(kind, ref), 'Checked the shop')}>Check the shop now</button>
          )}
        </div>
        {x.stock_checked && <p className="small muted">{x.in_stock ? 'In stock' : 'Out of stock'} when checked {shortDate(x.stock_checked.slice(0, 10))}</p>}
        {x.link && <p className="small"><a href={x.link} target="_blank" rel="noreferrer">Where it came from ↗</a></p>}
      </section>
    </Drawer>
  )
}

// ---------------------------------------------------------------- add from a link
const AS = [['wish', 'A supply (paint, glue, tools…)'], ['model', 'A kit'], ['game', 'A board game'], ['gear:volleyball', 'Volleyball gear'],
  ['gear:hiking', 'Hiking gear'], ['garden', 'For the garden']]
const PHOTO_PATH = { gear: (id) => `/gear/${id}`, game: (id) => `/board-games/${id}`, garden: (id) => `/garden/items/${id}` }

export function LinkPanel({ onClose }) {
  const { lookups, changed, showToast } = useApp()
  const [url, setUrl] = useState('')
  const [found, setFound] = useState(null)
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [as, setAs] = useState('wish')
  const [category, setCategory] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const read = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const f = await api.peekLink(url.trim())
      setFound(f)
      setName(f.title ?? '')
      setPrice(f.price ?? '')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const save = async () => {
    const [kind, hobby] = as.split(':')
    if (kind === 'wish' && !category) { setError('Pick its category.'); return }
    setBusy(true)
    setError('')
    try {
      const made = await api.saveLink({ url: found.url, kind, hobby: hobby ?? null, name: name.trim(), price: price === '' ? null : price,
        category_id: kind === 'wish' ? Number(category) : null, site: found.site })
      if (found.image && PHOTO_PATH[kind]) {
        try { await api.uploadRowPhoto(PHOTO_PATH[kind](made.ref), await shrink(await photoFromUrl(found.image))) } catch { /* no picture: fine */ }
      }
      changed()
      showToast(`${name.trim()} is on your wishlist`)
      onClose()
    } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <Drawer title="Add from a link" onClose={onClose}>
      <form className="sx-inline wx-link" onSubmit={read}>
        <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://… a product page" aria-label="Product link" required />
        <button type="submit" className="primary" disabled={busy || !url.trim()}>{busy && !found ? 'Reading…' : 'Read it'}</button>
      </form>
      <p className="hint">The app reads that one page once (its name, price and picture), and only if the site allows it.</p>
      {error && <p className="alert error" role="alert">{error}</p>}
      {found && (
        <section className="panel-section wx-found">
          {found.image && <img src={found.image} alt="" referrerPolicy="no-referrer" />}
          <label className="field"><span className="field-label">Name</span><input value={name} onChange={(e) => setName(e.target.value)} maxLength={200} /></label>
          <label className="field"><span className="field-label">Price {found.currency && found.currency !== 'AUD' ? `(${found.currency})` : ''}</span>
            <input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
          <label className="field"><span className="field-label">What is it</span>
            <select value={as} onChange={(e) => setAs(e.target.value)}>{AS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          {as === 'wish' && (
            <label className="field"><span className="field-label">Category</span>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">Pick one</option>
                {lookups.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select></label>
          )}
          <p className="small muted">From {found.site}</p>
          <button type="button" className="primary" disabled={busy || !name.trim()} onClick={save}>Add to my wishlist</button>
        </section>
      )}
    </Drawer>
  )
}

// ---------------------------------------------------------------- bought history
export function WishHistory() {
  const { refreshKey } = useApp()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.wantedHistory().then(setRows).catch(() => setRows([])) }, [refreshKey])
  if (!rows) return <p className="muted loading">Loading...</p>
  if (!rows.length) return <p className="empty card">Nothing bought from your wishlist yet. Tick something when you buy it.</p>
  const spent = rows.reduce((s, r) => s + (r.paid ?? 0), 0)
  return (
    <section className="card">
      <h3 className="home-card-title">Bought from your wishlist · {rows.length}<span className="muted small"> · {money(spent)}</span></h3>
      <table className="table compact wx-history">
        <thead><tr><th>Bought</th><th>What</th><th className="hide-xs">Where</th><th className="num">Expected</th><th className="num">Paid</th><th className="num hide-xs">Waited</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.history_id}>
            <td>{shortDate(r.bought_on)}</td><td>{r.name}<span className="muted small"> · {hobbyName(r.hobby)}</span></td>
            <td className="hide-xs">{r.shop ?? '—'}</td>
            <td className="num">{r.expected != null ? money(r.expected) : '—'}</td>
            <td className={`num${r.paid != null && r.expected != null && r.paid < r.expected ? ' wx-good-text' : ''}`}>{r.paid != null ? money(r.paid) : '—'}</td>
            <td className="num hide-xs">{r.waited != null ? `${r.waited} d` : '—'}</td>
          </tr>
        ))}</tbody>
      </table>
    </section>
  )
}

// ---------------------------------------------------------------- gift list
// Everything you want, by hobby, to print (or save as a PDF) or copy as text - for family before a birthday.
export function GiftList() {
  const [list, setList] = useState(null)
  const { showToast } = useApp()
  useEffect(() => {
    Promise.all([api.wanted(), api.listWishlist(), api.wantedExtras()]).then(([w, wishes, extras]) => {
      const items = [
        ...wishes.filter((x) => !x.got_it).map((x) => ({ key: `wish:${x.wish_id}`, name: x.name, detail: [x.brand, x.product_code, x.size].filter(Boolean).join(' · '),
          price: x.est_price, shop: w.default_shop, hobby: 'models', link: extras[`wish:${x.wish_id}`]?.link })),
        ...w.shops.flatMap((s) => s.items.map((x) => ({ key: `${x.kind}:${x.id}`, name: x.name, detail: x.detail, price: x.price,
          shop: s.shop === 'No shop yet' ? null : s.shop, hobby: extras[`${x.kind}:${x.id}`]?.hobby, link: x.url ?? extras[`${x.kind}:${x.id}`]?.link }))),
      ]
      const by = {}
      for (const it of items) (by[it.hobby ?? 'other'] ??= []).push(it)
      setList(by)
    }).catch(() => setList({}))
  }, [])
  if (!list) return <p className="muted loading">Loading...</p>
  const text = Object.entries(list).map(([h, items]) => `${hobbyName(h)}\n${items.map((i) => `- ${i.name}${i.detail ? ` (${i.detail})` : ''}${i.price != null ? `, about ${money(i.price)}` : ''}${i.shop ? ` at ${i.shop}` : ''}${i.link ? ` ${i.link}` : ''}`).join('\n')}`).join('\n\n')
  return (
    <section className="page sx-page wx-gift">
      <div className="toolbar sx-noprint"><Link to="/wishlist" className="plain sx-back">‹ Wishlist</Link><span className="grow" />
        <button type="button" className="secondary" onClick={() => navigator.clipboard?.writeText(text).then(() => showToast('Copied - paste it in a message')).catch(() => showToast("Couldn't copy"))}>Copy as text</button>
        <button type="button" className="primary" onClick={() => window.print()}>Print or save as PDF</button>
      </div>
      <header className="sx-report-head"><p className="jx-print-kicker">Gift ideas</p><h2 className="sx-title">Things I'd love</h2></header>
      {Object.keys(list).length === 0 && <p className="empty card">Your wishlist is empty.</p>}
      {Object.entries(list).map(([h, items]) => (
        <section key={h} className="card">
          <h3 className="home-card-title">{hobbyName(h)}</h3>
          <ul className="wx-gift-list">{items.map((i) => (
            <li key={i.key}><strong>{i.name}</strong>{i.detail && <span className="muted"> · {i.detail}</span>}
              {i.price != null && <span> · about {money(i.price)}</span>}{i.shop && <span className="muted"> at {i.shop}</span>}
              {i.link && <> · <a href={i.link} target="_blank" rel="noreferrer">link</a></>}</li>
          ))}</ul>
        </section>
      ))}
    </section>
  )
}
