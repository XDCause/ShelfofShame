import { useEffect, useMemo, useState } from 'react'
import { api, imageUrl, money } from '../api.js'
import ScanButton from './ScanButton.jsx'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const EMPTY_FILTERS = { q: '', category: '', brand: '', status: '', location: '' }
const STATUS_ORDER = { Out: 0, Low: 1, OK: 2 }

const SORTS = {
  ref: { label: 'Newest first', by: (r) => r.supply_id, dir: -1 },
  name: { label: 'Name', by: (r) => r.name },
  category: { label: 'Category', by: (r) => r.category },
  brand: { label: 'Brand', by: (r) => r.brand ?? '' },
  status: { label: 'Status (out first)', by: (r) => STATUS_ORDER[r.stock_status] },
  qty: { label: 'Quantity', by: (r) => r.qty_on_hand, dir: -1 },
  value: { label: 'Value', by: (r) => Number(r.total_value ?? 0), dir: -1 },
  purchased: { label: 'Last purchased', by: (r) => r.purchase_date ?? '', dir: -1 },
}

// The inventory list. Tap a row for everything about that item (opens a side panel).
// Scan: something you own opens its panel; anything else opens "Add a supply" pre-filled.
export default function InventoryView({ lookups, refreshKey, onOpen, onAdd }) {
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [search, setSearch] = useState('') // what's typed; copied into filters.q after a pause
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sort, setSort] = useState('ref')
  const [notice, setNotice] = useState(null)
  const [photoJob, setPhotoJob] = useState(null) // {done, total, failed} while fetching photos
  const [reload, setReload] = useState(0)

  // Debounce: wait until typing stops for 250 ms before searching, instead of one call per key.
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search.trim() })), 250)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    let current = true // ignore late answers from an older search
    setLoading(true)
    api.listSupplies(filters)
      .then((data) => current && (setRows(data), setError('')))
      .catch((e) => current && setError(e.message))
      .finally(() => current && setLoading(false))
    return () => { current = false }
  }, [filters, refreshKey, reload])

  const sorted = useMemo(() => {
    const { by, dir = 1 } = SORTS[sort]
    return [...rows].sort((a, b) => {
      const x = by(a), y = by(b)
      return dir * (typeof x === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true }))
    })
  }, [rows, sort])

  const totals = useMemo(() => ({
    items: rows.length,
    units: rows.reduce((s, r) => s + r.qty_on_hand, 0),
    value: rows.reduce((s, r) => s + Number(r.total_value ?? 0), 0),
    out: rows.filter((r) => r.stock_status === 'Out').length,
    low: rows.filter((r) => r.stock_status === 'Low').length,
  }), [rows])

  const missingPhotos = rows.filter((r) => r.brand === 'Tamiya' && r.product_code && !r.has_image)
  const filtered = Object.values(filters).some(Boolean)
  const setFilter = (name) => (e) => setFilters((f) => ({ ...f, [name]: e.target.value }))
  const clearAll = () => { setSearch(''); setFilters(EMPTY_FILTERS) }

  const adjust = async (row, delta) => {
    try {
      const updated = await api.adjustQty(row.supply_id, delta)
      setRows((rs) => rs.map((r) => (r.supply_id === updated.supply_id ? updated : r)))
      setError('')
    } catch (e) {
      setError(`${row.name}: ${e.message}`)
    }
  }

  const onBarcode = async (barcode, photo) => {
    const result = await api.scan(barcode)
    if (result.supply_id) onOpen(result.supply_id)
    else onAdd({ result, photo })
  }

  const wishOutOfStock = async () => {
    try {
      const r = await api.wishOutOfStock()
      setNotice(r.added ? `Added to wishlist: ${r.names.join(', ')}.` : 'Everything out of stock is already on your wishlist.')
    } catch (e) {
      setError(e.message)
    }
  }

  // One at a time with a pause between, to be gentle on tamiya.com. Cached after the first time.
  const fetchPhotos = async () => {
    const todo = missingPhotos
    const failed = []
    setPhotoJob({ done: 0, total: todo.length, failed })
    for (const [i, r] of todo.entries()) {
      try { await api.lookupTamiya(r.product_code) } catch (e) { failed.push(`${r.product_code}: ${e.message}`) }
      setPhotoJob({ done: i + 1, total: todo.length, failed: [...failed] })
      if (i < todo.length - 1) await sleep(1000)
    }
    setReload((n) => n + 1)
  }

  return (
    <section>
      <div className="stats">
        <Stat label={filtered ? 'Matching' : 'Items'} value={totals.items} />
        <Stat label="Units" value={totals.units} />
        <Stat label="Value" value={money(totals.value)} />
        <Stat label="Out" value={totals.out} tone={totals.out ? 'out' : ''} />
        <Stat label="Low" value={totals.low} tone={totals.low ? 'low' : ''} />
      </div>

      <div className="toolbar">
        <input type="search" className="search" placeholder="Search name, code, brand, notes..."
          value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search" />
        <ScanButton onBarcode={onBarcode} />
        <button type="button" className="secondary" onClick={() => onAdd(null)}>+ Add</button>
      </div>

      <div className="filters">
        <Select label="Category" value={filters.category} onChange={setFilter('category')} options={lookups.categories} />
        <Select label="Brand" value={filters.brand} onChange={setFilter('brand')} options={lookups.brands} />
        <Select label="Status" value={filters.status} onChange={setFilter('status')}
          options={['OK', 'Low', 'Out'].map((name) => ({ name }))} />
        <Select label="Location" value={filters.location} onChange={setFilter('location')} options={lookups.locations} />
        <label className="sort">
          <span className="muted small">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
            {Object.entries(SORTS).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
          </select>
        </label>
        {filtered && <button type="button" className="link" onClick={clearAll}>Clear filters</button>}
      </div>

      {(totals.out > 0 || (missingPhotos.length > 0 && !photoJob)) && (
        <div className="suggestions">
          {totals.out > 0 && (
            <button type="button" className="chip-btn" onClick={wishOutOfStock}>
              Add {totals.out} out-of-stock to wishlist
            </button>
          )}
          {missingPhotos.length > 0 && !photoJob && (
            <button type="button" className="chip-btn" onClick={fetchPhotos}>
              Get {missingPhotos.length} Tamiya photo{missingPhotos.length > 1 ? 's' : ''}
            </button>
          )}
        </div>
      )}

      {photoJob && (
        <p className={`alert ${photoJob.failed.length ? 'low' : 'ok'} small`} role="status">
          {photoJob.done < photoJob.total
            ? `Fetching photos from tamiya.com... ${photoJob.done} of ${photoJob.total}`
            : `Done: ${photoJob.total - photoJob.failed.length} of ${photoJob.total} photos fetched.`}
          {photoJob.done === photoJob.total && <button className="link" onClick={() => setPhotoJob(null)}>Dismiss</button>}
        </p>
      )}
      {notice && <p className="alert ok small" role="status">{notice} <button className="link" onClick={() => setNotice(null)}>Dismiss</button></p>}
      {error && <p className="alert error" role="alert">{error}</p>}

      <div className="table-wrap">
        <table className="inventory">
          <thead>
            <tr>
              <th className="thumb-col"><span className="visually-hidden">Photo</span></th>
              <th>Item</th>
              <th className="hide-sm">Category</th>
              <th className="hide-md">Finish</th>
              <th className="num">Stock</th>
              <th className="hide-xs">Status</th>
              <th className="num hide-sm">Value</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.supply_id} className="row" onClick={() => onOpen(r.supply_id)}
                tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpen(r.supply_id)}>
                <td className="thumb-col">
                  {r.has_image
                    ? <img className="thumb" src={imageUrl(r)} alt="" loading="lazy" />
                    : <span className="thumb thumb-empty" aria-hidden="true" />}
                </td>
                <td className="item-cell">
                  <span className="item-title">{r.name}</span>
                  <span className="item-meta">
                    {[r.brand, r.product_code, r.size].filter(Boolean).join(' · ')}
                    <span className={`badge ${r.stock_status.toLowerCase()} show-xs`}>{r.stock_status}</span>
                  </span>
                </td>
                <td className="hide-sm">{r.category}</td>
                <td className="hide-md">{r.finish !== 'N/A' ? r.finish : ''}</td>
                <td className="num">
                  <span className="qty" onClick={(e) => e.stopPropagation()}>
                    <button aria-label={`Use one ${r.name}`} disabled={r.qty_on_hand <= 0} onClick={() => adjust(r, -1)}>−</button>
                    <span>{r.qty_on_hand}</span>
                    <button aria-label={`Add one ${r.name}`} onClick={() => adjust(r, 1)}>+</button>
                  </span>
                </td>
                <td className="hide-xs"><span className={`badge ${r.stock_status.toLowerCase()}`}>{r.stock_status}</span></td>
                <td className="num hide-sm">{money(r.total_value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p className="empty">{filtered ? 'Nothing matches. Try clearing the filters.' : 'No supplies yet. Scan or add your first one.'}</p>
        )}
      </div>
    </section>
  )
}

function Stat({ label, value, tone = '' }) {
  return (
    <div className={`stat ${tone}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function Select({ label, value, onChange, options }) {
  return (
    <select value={value} onChange={onChange} aria-label={label}>
      <option value="">All {label === 'Status' ? 'statuses' : `${label.toLowerCase()}s`.replace('ys', 'ies')}</option>
      {options.map((o) => <option key={o.name} value={o.name}>{o.name}</option>)}
    </select>
  )
}
