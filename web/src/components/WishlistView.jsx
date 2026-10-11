import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, imageUrl, money } from '../api.js'
import ScanButton from './ScanButton.jsx'
import WishForm from './WishForm.jsx'

const SHOP_KEY = 'hobby-inventory.lastShop'
const readShop = () => {
  try { return localStorage.getItem(SHOP_KEY) ?? '' } catch { return '' }
}
const saveShop = (shop) => {
  try { localStorage.setItem(SHOP_KEY, shop) } catch { /* private window etc. - not important */ }
}

// The shopping list. Built for a phone in the shop: big photos, tap a card to tick it off,
// then move everything ticked into inventory in one go.
// `initialScan` = {result, photo} handed over from the Inventory page's "Add to wishlist".
export default function WishlistView({ lookups, onChanged, initialScan }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [show, setShow] = useState('all')
  const [formFor, setFormFor] = useState(initialScan ? null : undefined) // undefined = closed, null = new, object = editing
  const [shop, setShop] = useState(readShop)
  const [confirmBuy, setConfirmBuy] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const [scanned, setScanned] = useState(initialScan ?? null) // {result, photo} -> form pre-filled

  const openForm = (wish, scan = null) => {
    setScanned(scan)
    setFormFor(wish)
  }

  // Barcode -> API -> open the form with whatever the API recognised.
  const onBarcode = async (barcode, photo) => {
    setMessage(null)
    const result = await api.scan(barcode)
    openForm(null, { result, photo })
  }

  const load = useCallback(() => {
    return api.listWishlist()
      .then(setItems)
      .catch((e) => setMessage({ type: 'error', text: e.message }))
      .finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  const ticked = items.filter((w) => w.got_it)
  const visible = useMemo(
    () => items.filter((w) => show === 'all' || (show === 'got' ? w.got_it : !w.got_it)),
    [items, show],
  )
  const tickedValue = ticked.reduce((s, w) => s + Number(w.est_price ?? 0) * w.qty_wanted, 0)

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
      setConfirmBuy(false)
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
      <div className="wish-head">
        <div className="progress" aria-label={`${ticked.length} of ${items.length} ticked`}>
          <span className="progress-text">
            <strong>{ticked.length}</strong> of {items.length} ticked
          </span>
          <span className="progress-bar">
            <span style={{ width: items.length ? `${(ticked.length / items.length) * 100}%` : 0 }} />
          </span>
        </div>
        <div className="segmented" role="group" aria-label="Show">
          {[['all', 'All'], ['needed', 'To find'], ['got', 'Ticked']].map(([key, label]) => (
            <button key={key} aria-pressed={show === key} onClick={() => setShow(key)}>{label}</button>
          ))}
        </div>
        {formFor === undefined && (
          <div className="head-buttons">
            <ScanButton onBarcode={onBarcode} />
            <button className="secondary" onClick={() => openForm(null)}>+ Add by hand</button>
          </div>
        )}
      </div>

      {message && <p className={`alert ${message.type}`} role="status">{message.text}</p>}

      {formFor !== undefined && (
        <WishForm
          key={formFor?.wish_id ?? scanned?.result?.barcode ?? 'new'}
          wish={formFor}
          scanned={scanned}
          lookups={lookups}
          onCancel={() => openForm(undefined)}
          onSaved={(saved, problems = []) => {
            openForm(undefined)
            setMessage(problems.length
              ? { type: 'low', text: `${saved.name} saved to your wishlist, but ${problems.join('; ')}.` }
              : { type: 'ok', text: `${saved.name} saved to your wishlist.` })
            load()
          }}
        />
      )}

      {!loading && visible.length === 0 && (
        <p className="empty card">
          {items.length === 0
            ? 'Your wishlist is empty. Add something you want to buy.'
            : show === 'got' ? 'Nothing ticked yet.' : 'Everything is ticked off.'}
        </p>
      )}

      <div className="wish-grid">
        {visible.map((w) => (
          <WishCard
            key={w.wish_id}
            wish={w}
            onToggle={() => toggle(w)}
            onEdit={() => openForm(w)}
            onRemove={() => remove(w)}
            onBuy={() => finishBuying(api.buyWish(w.wish_id, shop))}
            busy={busy}
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
          {!confirmBuy ? (
            <button className="primary" onClick={() => setConfirmBuy(true)} disabled={busy}>
              Add to inventory
            </button>
          ) : (
            <span className="confirm-buy">
              <button className="primary" onClick={() => finishBuying(api.buyTicked(shop))} disabled={busy}>
                {busy ? 'Adding...' : `Yes, add ${ticked.length}`}
              </button>
              <button className="link" onClick={() => setConfirmBuy(false)}>Cancel</button>
            </span>
          )}
        </div>
      )}
    </section>
  )
}

function WishCard({ wish, onToggle, onEdit, onRemove, onBuy, busy }) {
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
          {wish.owned_qty > 0 && <span className="badge low">You own {wish.owned_qty}</span>}
        </div>
        {wish.notes && <p className="wish-notes">{wish.notes}</p>}
      </div>

      <div className="wish-actions" onClick={(e) => e.stopPropagation()}>
        {!confirmRemove ? (
          <>
            <button className="link" onClick={stop(onBuy)} disabled={busy} title="Add to inventory now">
              Bought
            </button>
            <button className="link" onClick={stop(onEdit)}>Edit</button>
            <button className="danger-link" onClick={stop(() => setConfirmRemove(true))}>Remove</button>
          </>
        ) : (
          <>
            <span className="small">Remove from wishlist?</span>
            <button className="danger" onClick={stop(onRemove)}>Remove</button>
            <button className="link" onClick={stop(() => setConfirmRemove(false))}>Cancel</button>
          </>
        )}
      </div>
    </article>
  )
}
