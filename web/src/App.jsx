import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { readBarcode } from './barcode.js'
import AddPanel from './components/AddPanel.jsx'
import ColoursView from './components/ColoursView.jsx'
import Elapsed from './components/Elapsed.jsx'
import { BoxIcon, CartIcon, DropsIcon, GearIcon, PlaneIcon, ScanIcon, TimerIcon } from './components/icons.jsx'
import InventoryView from './components/InventoryView.jsx'
import ItemPanel from './components/ItemPanel.jsx'
import ModelPanel from './components/ModelPanel.jsx'
import ModelsView from './components/ModelsView.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import WishlistView from './components/WishlistView.jsx'

const TABS = [
  { id: 'inventory', label: 'Inventory', Icon: BoxIcon },
  { id: 'wishlist', label: 'Wishlist', Icon: CartIcon },
  { id: 'models', label: 'Models', Icon: PlaneIcon },
  { id: 'colours', label: 'Colours', Icon: DropsIcon },
]

// Four pages - Inventory, Wishlist, Models, Colours - plus panels that slide over them:
//   item      one supply: stock, condition, used on, colour matches, photo, history, details
//   add       add a supply (scan or type a code first), to inventory or the wishlist
//   model     one kit: status, timer, paint checklist, build log - or adding a new one
//   settings  spending, price guide, default shop, backups, export, catalogue, lists
// Also here: the Undo bar after any -/+, the running-timer banner, and Scan in the nav bar.
export default function App() {
  const [tab, setTab] = useState('inventory')
  const [panel, setPanel] = useState(null) // {type: 'item', id} | {type: 'add', scan} | {type: 'model', id} | {type: 'settings'}
  const [lookups, setLookups] = useState(null)
  const [settings, setSettings] = useState({ default_shop: 'Hobbyrama' })
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null) // {type, text} shown under the nav bar
  const [refreshKey, setRefreshKey] = useState(0) // bump to reload the pages
  const [undoKey, setUndoKey] = useState(0) // bump when an undo changes an item behind an open panel
  const [timer, setTimer] = useState(null) // {model_id, name, started_at} while a timer runs
  const [toast, setToast] = useState(null) // {text, actions: [{label, run}]}
  const toastTimer = useRef(null)

  const loadLookups = useCallback(() => {
    api.lookups().then(setLookups).catch((e) => setError(`Can't reach the API: ${e.message}`))
  }, [])
  useEffect(() => {
    loadLookups()
    api.settings().then(setSettings).catch(() => {})
  }, [loadLookups])
  useEffect(() => { api.runningTimer().then(setTimer).catch(() => {}) }, [refreshKey])

  const changed = useCallback(() => {
    setRefreshKey((n) => n + 1)
    loadLookups() // usage counts in Settings
  }, [loadLookups])

  const close = useCallback(() => setPanel(null), [])
  const openModel = useCallback((id) => setPanel({ type: 'model', id }), [])
  const openItem = useCallback((id) => setPanel({ type: 'item', id }), [])
  const show = (type, text) => setFlash({ type, text })

  const showToast = useCallback((text, ...actions) => {
    clearTimeout(toastTimer.current)
    setToast({ text, actions })
    toastTimer.current = setTimeout(() => setToast(null), 6000)
  }, [])

  // After any -/+ (list or panel): "Used one: XF-1 · Undo". Undo puts back the quantity AND the
  // last-purchased date (+1 sets it to today), and is logged as "undo" in the stock history.
  // If the change put the item on the wishlist (it just ran out), Undo takes it back off.
  // Using the last one also offers "Not replacing?", which opens the item to remove it.
  const adjusted = useCallback((before, delta, autoWishId = null) => {
    const last = delta < 0 && before.qty_on_hand + delta === 0
    const what = delta > 0 ? 'Added one' : last ? 'Used the last one' : 'Used one'
    const undo = {
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
    }
    const notReplacing = { label: 'Not replacing?', run: () => { setToast(null); openItem(before.supply_id) } }
    showToast(`${what}: ${before.name}${autoWishId ? ' · added to your wishlist' : ''}`,
      undo, ...(last ? [notReplacing] : []))
  }, [changed, showToast, openItem])

  // Scan from anywhere: something you own opens its panel; anything else opens Add.
  const scanned = useCallback(async (barcode, photo) => {
    const result = await api.scan(barcode)
    if (result.supply_id) openItem(result.supply_id)
    else setPanel({ type: 'add', scan: { result, photo } })
  }, [openItem])

  const page = !lookups ? (!error && <p className="muted loading">Loading...</p>)
    : tab === 'inventory' ? (
      <InventoryView lookups={lookups} refreshKey={refreshKey} onAdjusted={adjusted} onOpen={openItem}
        onAdd={(scan) => setPanel({ type: 'add', scan })} />
    ) : tab === 'wishlist' ? (
      <WishlistView lookups={lookups} settings={settings} refreshKey={refreshKey} onChanged={changed} />
    ) : tab === 'models' ? (
      <ModelsView lookups={lookups} refreshKey={refreshKey} onOpen={openModel} />
    ) : (
      <ColoursView refreshKey={refreshKey} onChanged={changed} onOpenItem={openItem} onOpenModel={openModel} />
    )

  return (
    <div className="app">
      <header className="navbar">
        <div className="navbar-row">
          <h1>Shelf of Shame</h1>
          <nav className="tabs segmented" role="tablist" aria-label="Pages">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
            ))}
          </nav>
          <div className="navbar-actions">
            {lookups && !panel && <ScanButtonNav onBarcode={scanned} onError={showToast}
              onUnreadable={() => {
                setPanel({ type: 'add', scan: null })
                showToast("Couldn't find a barcode in that photo. Try again, or use \"Type a barcode\".")
              }} />}
            <button type="button" className="icon-btn" onClick={() => setPanel({ type: 'settings' })}
              aria-label="Settings" title="Settings: spending, prices, backups, export, lists">
              <GearIcon />
            </button>
          </div>
        </div>
      </header>

      <div className="content">
        {timer && (
          <button type="button" className="timer-banner" onClick={() => openModel(timer.model_id)}>
            <TimerIcon size={18} /> Working on <strong>{timer.name}</strong>
            <Elapsed since={timer.started_at} />
          </button>
        )}
        {error && <p className="alert error">{error}</p>}
        {flash && (
          <p className={`alert ${flash.type}`} role="status">
            {flash.text} <button className="plain" onClick={() => setFlash(null)}>Dismiss</button>
          </p>
        )}

        <main>{page}</main>
      </div>

      <nav className="tabbar" aria-label="Pages">
        {TABS.map(({ id, label, Icon }) => (
          <button key={id} type="button" aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>
            <Icon /><span>{label}</span>
          </button>
        ))}
      </nav>

      {lookups && panel?.type === 'item' && (
        <ItemPanel key={panel.id} supplyId={panel.id} lookups={lookups} reloadKey={undoKey}
          onClose={close} onChanged={changed} onAdjusted={adjusted} onOpenModel={openModel} onOpenItem={openItem}
          onRemoved={(item) => show('ok', `${item.name} removed from your inventory.`)} />
      )}
      {lookups && panel?.type === 'add' && (
        <AddPanel key={panel.scan?.result?.barcode ?? 'add'} lookups={lookups} settings={settings}
          scanned={panel.scan} onClose={close} onOpen={openItem}
          onAdded={(supply, problems) => {
            changed()
            if (problems.length) show('low', `${supply.name} added, but ${problems.join('; ')}.`)
            openItem(supply.supply_id)
          }}
          onWished={(wish, problems) => {
            changed()
            show(problems.length ? 'low' : 'ok',
              `${wish.name} added to your wishlist${problems.length ? `, but ${problems.join('; ')}` : ''}.`)
            close()
          }} />
      )}
      {lookups && panel?.type === 'model' && (
        <ModelPanel key={panel.id ?? 'new-model'} modelId={panel.id} lookups={lookups} settings={settings}
          onClose={close} onChanged={changed} onCreated={openModel} onOpenSupply={openItem} />
      )}
      {lookups && panel?.type === 'settings' && (
        <SettingsPanel lookups={lookups} settings={settings} onClose={close}
          onSettings={setSettings} onListsChanged={loadLookups} />
      )}

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

// Scan in the nav bar: the phone's camera (or a photo), read in the browser, then looked up.
function ScanButtonNav({ onBarcode, onUnreadable, onError }) {
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
      <button type="button" className="icon-btn scan-nav" onClick={() => input.current.click()} disabled={busy}
        aria-label="Scan a barcode" title="Scan a barcode">
        {busy ? <span className="spinner" aria-hidden="true" /> : <ScanIcon />}
      </button>
    </>
  )
}
