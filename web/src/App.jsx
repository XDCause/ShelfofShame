import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import InventoryView from './components/InventoryView.jsx'
import SupplyForm from './components/SupplyForm.jsx'
import ListsManager from './components/ListsManager.jsx'
import WishlistView from './components/WishlistView.jsx'

// Three areas:
//   Inventory  - view and search (the primary function)
//   Wishlist   - things to buy; tick them off in the shop, then move them into inventory
//   Add & Edit - the supply form, plus managing the brand/category/location lists
export default function App() {
  const [tab, setTab] = useState('inventory')
  const [editingId, setEditingId] = useState(null) // null = adding a new supply
  const [lookups, setLookups] = useState(null)
  const [error, setError] = useState('')
  // A scanned item handed from the Inventory page to the supply form or the wishlist.
  const [scanForSupply, setScanForSupply] = useState(null)
  const [scanForWish, setScanForWish] = useState(null)

  // Dropdown contents. Reloaded after anything that could change them or their usage counts.
  const loadLookups = useCallback(() => {
    api.lookups().then(setLookups).catch((e) => setError(`Can't reach the API: ${e.message}`))
  }, [])
  useEffect(loadLookups, [loadLookups])

  const go = (next) => {
    setScanForSupply(null)
    setScanForWish(null)
    setTab(next)
  }
  const startEdit = (id) => {
    setEditingId(id)
    go('edit')
  }
  const startAdd = (scan = null) => {
    setEditingId(null)
    go('edit')
    setScanForSupply(scan)
  }
  const wishScanned = (scan) => {
    go('wishlist')
    setScanForWish(scan)
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Shelf of Shame</h1>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'inventory'} onClick={() => go('inventory')}>
            Inventory
          </button>
          <button role="tab" aria-selected={tab === 'wishlist'} onClick={() => go('wishlist')}>
            Wishlist
          </button>
          <button role="tab" aria-selected={tab === 'edit'} onClick={() => startAdd()}>
            Add &amp; Edit
          </button>
        </nav>
      </header>

      {error && <p className="alert error">{error}</p>}

      <main>
        {!lookups ? (
          !error && <p className="muted">Loading...</p>
        ) : tab === 'inventory' ? (
          <InventoryView lookups={lookups} onEdit={startEdit} onAdd={() => startAdd()}
            onAddScanned={startAdd} onWishScanned={wishScanned} />
        ) : tab === 'wishlist' ? (
          <WishlistView key={scanForWish?.result?.barcode ?? 'wishlist'} lookups={lookups}
            onChanged={loadLookups} initialScan={scanForWish} />
        ) : (
          <div className="edit-layout">
            <SupplyForm
              key={scanForSupply?.result?.barcode ?? 'supply-form'}
              scanned={scanForSupply}
              supplyId={editingId}
              lookups={lookups}
              onSaved={(supply) => {
                setEditingId(supply.supply_id)
                loadLookups()
              }}
              onNew={() => {
                setScanForSupply(null)
                setEditingId(null)
              }}
              onDeleted={() => {
                loadLookups()
                setEditingId(null)
                setTab('inventory')
              }}
              onBack={() => setTab('inventory')}
            />
            <ListsManager lookups={lookups} onChanged={loadLookups} />
          </div>
        )}
      </main>
    </div>
  )
}
