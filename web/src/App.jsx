import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { readBarcode } from './barcode.js'
import AddPanel from './components/AddPanel.jsx'
import Drawer from './components/Drawer.jsx'
import InventoryView from './components/InventoryView.jsx'
import ItemPanel from './components/ItemPanel.jsx'
import ListsManager from './components/ListsManager.jsx'
import ModelPanel from './components/ModelPanel.jsx'
import ModelsView from './components/ModelsView.jsx'
import WishlistView from './components/WishlistView.jsx'

// Three pages - Inventory, Wishlist, Models - plus panels that slide in on top:
//   item   one supply: stock, quick settings, notes, photo/barcode, history, edit details
//   add    add a supply (scan or type a code first), to inventory or the wishlist
//   model  one model (kit): status, paint checklist, notes, photo - or adding a new one
//   lists  manage brands / categories / locations (the gear button)
// Also here: the Undo bar after any -/+, and the floating Scan button on phones.
export default function App() {
  const [tab, setTab] = useState('inventory')
  const [panel, setPanel] = useState(null) // {type: 'item', id} | {type: 'add', scan} | {type: 'model', id} | {type: 'lists'}
  const [lookups, setLookups] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null) // {type, text} shown under the header
  const [refreshKey, setRefreshKey] = useState(0) // bump to reload the lists
  const [undoKey, setUndoKey] = useState(0) // bump when an undo changes an item behind an open panel
  const [toast, setToast] = useState(null) // {text, actions: [{label, run}]}
  const toastTimer = useRef(null)

  const loadLookups = useCallback(() => {
    api.lookups().then(setLookups).catch((e) => setError(`Can't reach the API: ${e.message}`))
  }, [])
  useEffect(loadLookups, [loadLookups])

  const changed = useCallback(() => {
    setRefreshKey((n) => n + 1)
    loadLookups() // usage counts in Manage lists
  }, [loadLookups])

  const close = useCallback(() => setPanel(null), [])
  const show = (type, text) => setFlash({ type, text })

  const showToast = useCallback((text, ...actions) => {
    clearTimeout(toastTimer.current)
    setToast({ text, actions })
    toastTimer.current = setTimeout(() => setToast(null), 6000)
  }, [])

  // After any -/+ (list or panel): "Used one: XF-1 · Undo". Undo puts back the quantity AND the
  // last-purchased date (+1 sets it to today), and is logged as "undo" in the stock history.
  // If the change put the item on the wishlist (it just ran out), Undo takes it back off.
  // Used the last one: also offer "Not replacing?", which opens the item to remove it.
  const adjusted = useCallback((before, delta, autoWishId = null) => {
    const wished = autoWishId ? ' · added to your wishlist' : ''
    const last = delta < 0 && before.qty_on_hand + delta === 0
    const notReplacing = { label: 'Not replacing?', run: () => {
      setToast(null)
      setPanel({ type: 'item', id: before.supply_id })
    } }
    showToast(`${delta < 0 ? (last ? 'Used the last one' : 'Used one') : 'Added one'}: ${before.name}${wished}`, {
      label: 'Undo',
      run: async () => {
        setToast(null)
        try {
          await api.adjustQty(before.supply_id, -delta,
            { undo: true, purchase_date: before.purchase_date, remove_wish_id: autoWishId })
          setUndoKey((n) => n + 1)
          changed()
        } catch (e) {
          showToast(`Couldn't undo: ${e.message}`)
        }
      },
    }, ...(last ? [notReplacing] : []))
  }, [changed, showToast])

  // Scan from anywhere: something you own opens its panel; anything else opens Add.
  const scanned = useCallback(async (barcode, photo) => {
    const result = await api.scan(barcode)
    if (result.supply_id) setPanel({ type: 'item', id: result.supply_id })
    else setPanel({ type: 'add', scan: { result, photo } })
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <h1>Shelf of Shame</h1>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'inventory'} onClick={() => setTab('inventory')}>Inventory</button>
          <button role="tab" aria-selected={tab === 'wishlist'} onClick={() => setTab('wishlist')}>Wishlist</button>
          <button role="tab" aria-selected={tab === 'models'} onClick={() => setTab('models')}>Models</button>
        </nav>
        <button type="button" className="icon-btn gear" onClick={() => setPanel({ type: 'lists' })}
          aria-label="Manage lists" title="Manage lists (brands, categories, locations)">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor"
            strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </header>

      {error && <p className="alert error">{error}</p>}
      {flash && (
        <p className={`alert ${flash.type}`} role="status">
          {flash.text} <button className="link" onClick={() => setFlash(null)}>Dismiss</button>
        </p>
      )}

      <main>
        {!lookups ? (
          !error && <p className="muted">Loading...</p>
        ) : tab === 'inventory' ? (
          <InventoryView lookups={lookups} refreshKey={refreshKey} onAdjusted={adjusted}
            onOpen={(id) => setPanel({ type: 'item', id })}
            onAdd={(scan) => setPanel({ type: 'add', scan })} />
        ) : tab === 'wishlist' ? (
          <WishlistView lookups={lookups} onChanged={changed} />
        ) : (
          <ModelsView refreshKey={refreshKey} onOpen={(id) => setPanel({ type: 'model', id })} />
        )}
      </main>

      {lookups && panel?.type === 'item' && (
        <ItemPanel key={panel.id} supplyId={panel.id} lookups={lookups} reloadKey={undoKey}
          onClose={close} onChanged={changed} onAdjusted={adjusted}
          onRemoved={(item) => show('ok', `${item.name} removed from your inventory.`)} />
      )}
      {lookups && panel?.type === 'add' && (
        <AddPanel key={panel.scan?.result?.barcode ?? 'add'} lookups={lookups} scanned={panel.scan}
          onClose={close}
          onOpen={(id) => setPanel({ type: 'item', id })}
          onAdded={(supply, problems) => {
            changed()
            if (problems.length) show('low', `${supply.name} added, but ${problems.join('; ')}.`)
            setPanel({ type: 'item', id: supply.supply_id })
          }}
          onWished={(wish, problems) => {
            changed()
            show(problems.length ? 'low' : 'ok',
              `${wish.name} added to your wishlist${problems.length ? `, but ${problems.join('; ')}` : ''}.`)
            close()
          }} />
      )}
      {lookups && panel?.type === 'model' && (
        <ModelPanel key={panel.id ?? 'new-model'} modelId={panel.id} lookups={lookups} onClose={close}
          onChanged={changed}
          onCreated={(id) => setPanel({ type: 'model', id })}
          onOpenSupply={(id) => setPanel({ type: 'item', id })} />
      )}
      {lookups && panel?.type === 'lists' && (
        <Drawer title="Manage lists" onClose={close}>
          <ListsManager lookups={lookups} onChanged={loadLookups} />
        </Drawer>
      )}

      {lookups && !panel && <ScanFab onBarcode={scanned} onUnreadable={() => {
        setPanel({ type: 'add', scan: null })
        showToast("Couldn't find a barcode in that photo. Try again, or use \"Type a barcode\".")
      }} onError={(msg) => showToast(msg)} />}

      {toast && (
        <div className="toast" role="status" aria-live="polite">
          <span>{toast.text}</span>
          {toast.actions.map((a) => <button key={a.label} type="button" onClick={a.run}>{a.label}</button>)}
          <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => setToast(null)}>✕</button>
        </div>
      )}
    </div>
  )
}

// Phones only (hidden by CSS on wider screens): a round Scan button that's always in reach.
function ScanFab({ onBarcode, onUnreadable, onError }) {
  const input = useRef(null)
  const [busy, setBusy] = useState(false)

  const onPhoto = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    try {
      const barcode = await readBarcode(file).catch(() => null)
      if (barcode) await onBarcode(barcode, file)
      else onUnreadable()
    } catch (err) {
      onError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <input ref={input} type="file" accept="image/*" capture="environment" onChange={onPhoto} hidden />
      <button type="button" className="fab" onClick={() => input.current.click()} disabled={busy}
        aria-label="Scan a barcode">
        {busy ? <span className="fab-busy" aria-hidden="true" /> : (
          <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round">
            <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" />
            <path d="M7 8v8M10 8v8M13 8v8M17 8v8" />
          </svg>
        )}
      </button>
    </>
  )
}
