import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { api, imageUrl, money } from '../api.js'
import Notice from './Notice.jsx'
import OwnedBadge from './OwnedBadge.jsx'
import WishForm from './WishForm.jsx'
import EmptyState from '../core/EmptyState.jsx'
import { useApp } from '../core/app-context.js'
import { ExtraTags, extraOf } from './wishExtras.jsx'
import { CartIcon } from '../components/icons.jsx'

const SHOP_KEY = 'hobby-inventory.lastShop'
const readShop = () => {
  try { return localStorage.getItem(SHOP_KEY) ?? '' } catch { return '' }
}
const saveShop = (shop) => {
  try { localStorage.setItem(SHOP_KEY, shop) } catch { /* private window etc. - not important */ }
}

// The shopping list. Built for a phone in the shop: big photos, tap a card to tick it off as you
// put it in the basket, then "Add N to inventory" moves everything ticked across in one go (that's
// the only way to buy - one item is just one tick). "+ Add" opens a side panel that searches
// Tamiya, reads a barcode or takes the details by hand.
export default function WishlistView({ lookups, settings, refreshKey, onChanged, extras = {} }) {
  const { openPanel } = useApp()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [show, setShow] = useState('all')
  const [formFor, setFormFor] = useState(undefined) // undefined = closed, null = new, object = editing
  const [shop, setShop] = useState(() => readShop() || settings.default_shop || '')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const [scanned, setScanned] = useState(null) // {result, photo} -> form pre-filled
  const [params, setParams] = useSearchParams()

  const openForm = (wish, scan = null) => {
    setScanned(scan)
    setFormFor(wish)
    if (wish === undefined && params.has('add')) setParams({}, { replace: true })
  }
  // /wishlist?add=1 (Home's "Shop Tamiya") opens the add panel straight away.
  useEffect(() => { if (params.get('add') === '1') setFormFor(null) }, [params])
  const clearMessage = useCallback(() => setMessage(null), [])

  const load = useCallback(() => {
    return api.listWishlist()
      .then(setItems)
      .catch((e) => setMessage({ type: 'error', text: e.message }))
      .finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load, refreshKey])

  const ticked = items.filter((w) => w.got_it)
  const visible = useMemo(
    () => items.filter((w) => show === 'all' || (show === 'got' ? w.got_it : !w.got_it)),
    [items, show],
  )
  const cost = (ws) => ws.reduce((s, w) => s + Number(w.est_price ?? 0) * w.qty_wanted, 0)
  const tickedValue = cost(ticked)
  const toFind = items.filter((w) => !w.got_it)
  const unpriced = toFind.filter((w) => w.est_price == null).length

  // Tick/untick instantly on screen, then tell the API; undo on screen if the API says no.
  const toggle = async (wish) => {
    const got_it = !wish.got_it
    setItems((ws) => ws.map((w) => (w.wish_id === wish.wish_id ? { ...w, got_it } : w)))
    try {
      await api.updateWish(wish.wish_id, { got_it })
    } catch (e) {
      setItems((ws) => ws.map((w) => (w.wish_id === wish.wish_id ? { ...w, got_it: !got_it } : w)))
      setMessage({ type: 'error', text: e.message })
    }
  }

  const remove = async (wish) => {
    try {
      await api.deleteWish(wish.wish_id)
      setItems((ws) => ws.filter((w) => w.wish_id !== wish.wish_id))
      setMessage(null)
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    }
  }

  const describe = (results) =>
    results.map((r) => (r.merged ? `${r.item_ref} ${r.name} (now ${r.qty_on_hand})` : `${r.item_ref} ${r.name}`)).join(', ')

  const finishBuying = async (promise) => {
    setBusy(true)
    saveShop(shop)
    try {
      const results = [].concat(await promise)
      setMessage({ type: 'ok', text: `Added to inventory: ${describe(results)}.` })
      await load()
      onChanged()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={ticked.length ? 'wishlist has-bar' : 'wishlist'}>
      {/* One line: what's left to find and roughly what it costs; tap a card to tick it (user, 2026-10-21: tidier) */}
      <div className="wish-head">
        <p className="wish-sum">
          {items.length > 0 ? <>
            <strong>{toFind.length}</strong> to find · about <strong>{money(cost(toFind))}</strong>
            {unpriced > 0 && <span className="muted"> ({unpriced} without a price)</span>}
            {ticked.length > 0 && <span className="muted"> · {ticked.length} ticked</span>}
          </> : <span className="muted">Nothing on your list yet.</span>}
        </p>
        {ticked.length > 0 && (
          <div className="segmented" role="group" aria-label="Show">
            {[['all', 'All'], ['needed', 'To find'], ['got', 'Ticked']].map(([key, label]) => (
              <button key={key} aria-pressed={show === key} onClick={() => setShow(key)}>{label}</button>
            ))}
          </div>
        )}
        <button className="primary" onClick={() => openForm(null)}>+ Add</button>
      </div>

      {message && <Notice type={message.type} onClose={clearMessage}>{message.text}</Notice>}

      {formFor !== undefined && (
        <WishForm
          key={formFor?.wish_id ?? scanned?.result?.barcode ?? 'new'}
          wish={formFor}
          scanned={scanned}
          lookups={lookups}
          onCancel={() => openForm(undefined)}
          onCatalogAdded={() => {
            load()
            setTimeout(load, 10000) // the photo and size arrive from tamiya.com in the background
          }}
          onSaved={(saved, problems = []) => {
            openForm(undefined)
            setMessage(problems.length
              ? { type: 'low', text: `${saved.name} saved to your wishlist, but ${problems.join('; ')}.` }
              : { type: 'ok', text: `${saved.name} saved to your wishlist.` })
            load()
          }}
        />
      )}

      {!loading && visible.length === 0 && (items.length === 0 ? (
        <EmptyState Icon={CartIcon} title="Your wishlist is empty" action="+ Add" onAction={() => openForm(null)}>
          Add what you want to buy - search Tamiya, scan a barcode, or type it in. Low supplies land here by themselves.</EmptyState>
      ) : <p className="empty card">{show === 'got' ? 'Nothing ticked yet.' : 'Everything is ticked off.'}</p>)}

      {visible.length > 0 && <h3 className="section-title wish-sub">Supplies</h3>}
      <div className="wish-grid">
        {visible.map((w) => (
          <WishCard
            key={w.wish_id}
            wish={w}
            onToggle={() => toggle(w)}
            onEdit={() => openForm(w)}
            onRemove={() => remove(w)}
            extra={extraOf(extras, 'wish', w.wish_id)}
            onDetails={() => openPanel('wanted', { kind: 'wish', wantedRef: w.wish_id, name: w.name })}
          />
        ))}
      </div>

      {ticked.length > 0 && (
        <div className="buy-bar">
          <div className="buy-summary">
            <strong>{ticked.length} ticked</strong>
            {tickedValue > 0 && <span className="muted"> · about {money(tickedValue)}</span>}
          </div>
          <input
            value={shop}
            onChange={(e) => setShop(e.target.value)}
            placeholder="Shop (e.g. Hobbyrama)"
            aria-label="Bought from"
          />
          <button className="primary" onClick={() => finishBuying(api.buyTicked(shop))} disabled={busy}>
            {busy ? 'Adding...' : `Add ${ticked.length} to inventory`}
          </button>
        </div>
      )}
    </section>
  )
}

function WishCard({ wish, onToggle, onEdit, onRemove, extra, onDetails }) {
  const [confirmRemove, setConfirmRemove] = useState(false)
  const stop = (fn) => (e) => {
    e.stopPropagation()
    fn()
  }

  return (
    <article
      className={wish.got_it ? 'wish-card got' : 'wish-card'}
      onClick={onToggle}
      aria-label={`${wish.name}${wish.got_it ? ', ticked' : ''}`}
    >
      <div className="wish-photo">
        {wish.has_image ? (
          <img src={imageUrl(wish)} alt="" loading="lazy" />
        ) : wish.catalog_thumb ? (
          // Tamiya's small picture while the full photo is still being fetched
          <img src={wish.catalog_thumb} alt="" loading="lazy" referrerPolicy="no-referrer" />
        ) : (
          <span className="photo-missing">{wish.category}</span>
        )}
        <label className="tick" onClick={(e) => e.stopPropagation()}>
          <input type="checkbox" checked={wish.got_it} onChange={onToggle} aria-label={`Got ${wish.name}`} />
          <span aria-hidden="true">✓</span>
        </label>
        {wish.priority === 'High' && <span className="badge out prio">High priority</span>}
      </div>

      <div className="wish-body">
        <h3>{wish.name}</h3>
        <p className="wish-codes">
          {[wish.brand, wish.product_code].filter(Boolean).join(' · ')}
        </p>
        <p className="wish-meta">
          {[wish.category, wish.size, wish.finish !== 'N/A' && wish.finish].filter(Boolean).join(' · ')}
        </p>
        <div className="wish-chips">
          {wish.qty_wanted > 1 && <span className="chip">×{wish.qty_wanted}</span>}
          {wish.est_price != null && <span className="chip">{money(wish.est_price)}</span>}
          <OwnedBadge wish={wish} />
        </div>
        {wish.notes && <p className="wish-notes">{wish.notes}</p>}
        <ExtraTags x={extra} />
      </div>

      <div className="wish-actions" onClick={(e) => e.stopPropagation()}>
        {!confirmRemove ? (
          <>
            <button className="plain small" onClick={stop(onEdit)}>Edit</button>
            <button className="plain small" onClick={stop(onDetails)}>Details</button>
            <button className="plain small destructive" onClick={stop(() => setConfirmRemove(true))}>Remove</button>
          </>
        ) : (
          <>
            <span className="small">Remove it?</span>
            <button className="danger small" onClick={stop(onRemove)}>Remove</button>
            <button className="plain small" onClick={stop(() => setConfirmRemove(false))}>Cancel</button>
          </>
        )}
      </div>
    </article>
  )
}
