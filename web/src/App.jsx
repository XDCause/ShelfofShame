import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
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
export default function App() {
  const [tab, setTab] = useState('inventory')
  const [panel, setPanel] = useState(null) // {type: 'item', id} | {type: 'add', scan} | {type: 'lists'}
  const [lookups, setLookups] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null) // {type, text} shown under the header
  const [refreshKey, setRefreshKey] = useState(0) // bump to reload the inventory list

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
          <InventoryView lookups={lookups} refreshKey={refreshKey}
            onOpen={(id) => setPanel({ type: 'item', id })}
            onAdd={(scan) => setPanel({ type: 'add', scan })} />
        ) : tab === 'wishlist' ? (
          <WishlistView lookups={lookups} onChanged={changed} />
        ) : (
          <ModelsView refreshKey={refreshKey} onOpen={(id) => setPanel({ type: 'model', id })} />
        )}
      </main>

      {lookups && panel?.type === 'item' && (
        <ItemPanel key={panel.id} supplyId={panel.id} lookups={lookups} onClose={close} onChanged={changed} />
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
    </div>
  )
}
