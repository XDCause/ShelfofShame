import { Fragment, useEffect, useMemo, useState } from 'react'
import { api, imageUrl, money } from '../api.js'
import ScanButton from './ScanButton.jsx'
import StockHistory from './StockHistory.jsx'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const EMPTY_FILTERS = { q: '', category: '', brand: '', status: '', location: '' }

const COLUMNS = [
  { key: 'item_ref', label: 'Ref' },
  { key: 'brand', label: 'Brand' },
  { key: 'product_code', label: 'Code' },
  { key: 'name', label: 'Name' },
  { key: 'category', label: 'Category' },
  { key: 'paint_type', label: 'Type' },
  { key: 'finish', label: 'Finish' },
  { key: 'size', label: 'Size' },
  { key: 'qty_on_hand', label: 'Qty', numeric: true },
  { key: 'stock_status', label: 'Status' },
  { key: 'unit_price', label: 'Price', numeric: true },
  { key: 'total_value', label: 'Value', numeric: true },
  { key: 'location', label: 'Location' },
]

// onAddScanned / onWishScanned({result, photo}) hand a scanned item that you don't own yet to
// the supply form or the wishlist.
export default function InventoryView({ lookups, onEdit, onAdd, onAddScanned, onWishScanned }) {
  const [scanHit, setScanHit] = useState(null) // {result, photo, supply} after a scan
  const [notice, setNotice] = useState(null) // {type, text}
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [search, setSearch] = useState('') // what's typed; copied into filters.q after a pause
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sort, setSort] = useState({ key: 'item_ref', dir: 1 })
  const [expanded, setExpanded] = useState(null)
  const [reload, setReload] = useState(0) // bump to re-run the search
  const [photoJob, setPhotoJob] = useState(null) // {done, total, failed: []} while fetching photos

  // Debounce: wait until typing stops for 250 ms before searching, instead of one call per key.
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search.trim() })), 250)
    return () => clearTimeout(t)
  }, [search])

  // Ask the API for matching supplies whenever the filters change.
  useEffect(() => {
    let current = true // ignore late answers from an older search
    setLoading(true)
    api
      .listSupplies(filters)
      .then((data) => current && (setRows(data), setError('')))
      .catch((e) => current && setError(e.message))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [filters, reload])

  // Tamiya items we could fetch a photo for. Other brands need a different source (later).
  const missingPhotos = rows.filter((r) => r.brand === 'Tamiya' && r.product_code && !r.has_image)

  // One item at a time with a pause between, to be gentle on tamiya.com. Each result is
  // cached by the API, so this only ever needs doing once per item.
  const fetchPhotos = async () => {
    const todo = missingPhotos
    const failed = []
    setPhotoJob({ done: 0, total: todo.length, failed })
    for (const [i, r] of todo.entries()) {
      try {
        await api.lookupTamiya(r.product_code)
      } catch (e) {
        failed.push(`${r.product_code}: ${e.message}`)
      }
      setPhotoJob({ done: i + 1, total: todo.length, failed: [...failed] })
      if (i < todo.length - 1) await sleep(1000)
    }
    setReload((n) => n + 1)
  }

  const sorted = useMemo(() => {
    const { key, dir } = sort
    const numeric = COLUMNS.find((c) => c.key === key)?.numeric
    return [...rows].sort((a, b) => {
      const x = a[key], y = b[key]
      if (x == null || x === '') return 1 // blanks always last
      if (y == null || y === '') return -1
      return dir * (numeric ? Number(x) - Number(y) : String(x).localeCompare(String(y), undefined, { numeric: true }))
    })
  }, [rows, sort])

  const totals = useMemo(
    () => ({
      items: rows.length,
      units: rows.reduce((s, r) => s + r.qty_on_hand, 0),
      value: rows.reduce((s, r) => s + Number(r.total_value ?? 0), 0),
      out: rows.filter((r) => r.stock_status === 'Out').length,
      low: rows.filter((r) => r.stock_status === 'Low').length,
    }),
    [rows],
  )

  const setFilter = (name) => (e) => setFilters((f) => ({ ...f, [name]: e.target.value }))
  const clearAll = () => {
    setSearch('')
    setFilters(EMPTY_FILTERS)
  }
  const toggleSort = (key) => setSort((s) => ({ key, dir: s.key === key ? -s.dir : 1 }))

  const adjust = async (row, delta) => {
    try {
      const updated = await api.adjustQty(row.supply_id, delta)
      setRows((rs) => rs.map((r) => (r.supply_id === updated.supply_id ? updated : r)))
      setScanHit((h) => (h?.supply?.supply_id === updated.supply_id ? { ...h, supply: updated } : h))
      setError('')
    } catch (e) {
      setError(`${row.name}: ${e.message}`)
    }
  }

  // Scan: if you own it, show it with -1/+1; if not, offer to add it somewhere.
  const onBarcode = async (barcode, photo) => {
    setNotice(null)
    const result = await api.scan(barcode)
    const supply = result.supply_id ? await api.getSupply(result.supply_id) : null
    setScanHit({ result, photo, supply })
  }

  const wishOutOfStock = async () => {
    try {
      const r = await api.wishOutOfStock()
      setNotice(r.added
        ? { type: 'ok', text: `Added to wishlist: ${r.names.join(', ')}.` }
        : { type: 'ok', text: 'Everything out of stock is already on your wishlist.' })
    } catch (e) {
      setNotice({ type: 'error', text: e.message })
    }
  }

  const filtered = Object.values(filters).some(Boolean)

  return (
    <section>
      <div className="stats">
        <Stat label={filtered ? 'Matching items' : 'Items'} value={totals.items} />
        <Stat label="Units on hand" value={totals.units} />
        <Stat label="Value" value={money(totals.value)} />
        <Stat label="Out of stock" value={totals.out} tone={totals.out ? 'out' : ''} />
        <Stat label="Low" value={totals.low} tone={totals.low ? 'low' : ''} />
      </div>

      <div className="toolbar">
        <input
          type="search"
          className="search"
          placeholder="Search name, code, brand, category, project, notes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search"
        />
        <Select label="Category" value={filters.category} onChange={setFilter('category')} options={lookups.categories} />
        <Select label="Brand" value={filters.brand} onChange={setFilter('brand')} options={lookups.brands} />
        <Select label="Status" value={filters.status} onChange={setFilter('status')}
          options={['OK', 'Low', 'Out'].map((name) => ({ name }))} />
        <Select label="Location" value={filters.location} onChange={setFilter('location')} options={lookups.locations} />
        {filtered && <button className="link" onClick={clearAll}>Clear</button>}
        <span className="spacer" />
        {missingPhotos.length > 0 && !photoJob && (
          <button onClick={fetchPhotos} className="secondary">
            Get {missingPhotos.length} Tamiya photo{missingPhotos.length > 1 ? 's' : ''}
          </button>
        )}
        {totals.out > 0 && (
          <button onClick={wishOutOfStock} className="secondary">
            Add {totals.out} out-of-stock to wishlist
          </button>
        )}
        <ScanButton onBarcode={onBarcode} className="secondary" />
        <button className="primary" onClick={onAdd}>+ Add supply</button>
      </div>

      {notice && <p className={`alert ${notice.type}`} role="status">{notice.text}</p>}

      {scanHit && (
        <ScanHit
          hit={scanHit}
          onAdjust={(delta) => adjust(scanHit.supply, delta)}
          onEdit={() => onEdit(scanHit.supply.supply_id)}
          onAddToInventory={() => onAddScanned({ result: scanHit.result, photo: scanHit.photo })}
          onAddToWishlist={() => onWishScanned({ result: scanHit.result, photo: scanHit.photo })}
          onClose={() => setScanHit(null)}
        />
      )}

      {photoJob && (
        <div className={`alert ${photoJob.failed.length ? 'low' : 'ok'}`} role="status">
          {photoJob.done < photoJob.total
            ? `Fetching photos from tamiya.com... ${photoJob.done} of ${photoJob.total}`
            : `Done: ${photoJob.total - photoJob.failed.length} of ${photoJob.total} photos fetched.`}
          {photoJob.failed.length > 0 && (
            <ul className="small">{photoJob.failed.map((f) => <li key={f}>{f}</li>)}</ul>
          )}
          {photoJob.done === photoJob.total && (
            <button className="link" onClick={() => setPhotoJob(null)}>Dismiss</button>
          )}
        </div>
      )}

      {error && <p className="alert error">{error}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="thumb-col"><span className="visually-hidden">Photo</span></th>
              {COLUMNS.map((c) => (
                <th key={c.key} className={c.numeric ? 'num' : ''}>
                  <button className="sort" onClick={() => toggleSort(c.key)}>
                    {c.label}
                    <span aria-hidden="true">{sort.key === c.key ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}</span>
                  </button>
                </th>
              ))}
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <Fragment key={r.supply_id}>
                <tr
                  className={expanded === r.supply_id ? 'row open' : 'row'}
                  onClick={() => setExpanded(expanded === r.supply_id ? null : r.supply_id)}
                >
                  <td className="thumb-col">
                    {r.has_image ? (
                      <img className="thumb" src={imageUrl(r)} alt="" loading="lazy" />
                    ) : (
                      <span className="thumb thumb-empty" aria-hidden="true" />
                    )}
                  </td>
                  <td className="mono">{r.item_ref}</td>
                  <td>{r.brand}</td>
                  <td className="mono">{r.product_code}</td>
                  <td className="name">{r.name}</td>
                  <td>{r.category}</td>
                  <td>{r.paint_type}</td>
                  <td>{r.finish}</td>
                  <td>{r.size}</td>
                  <td className="num">
                    <span className="qty" onClick={(e) => e.stopPropagation()}>
                      <button aria-label={`Use one ${r.name}`} title="Use one" disabled={r.qty_on_hand <= 0}
                        onClick={() => adjust(r, -1)}>−</button>
                      <span>{r.qty_on_hand}</span>
                      <button aria-label={`Add one ${r.name}`} title="Add one" onClick={() => adjust(r, 1)}>+</button>
                    </span>
                  </td>
                  <td><span className={`badge ${r.stock_status.toLowerCase()}`}>{r.stock_status}</span></td>
                  <td className="num">{money(r.unit_price)}</td>
                  <td className="num">{money(r.total_value)}</td>
                  <td>{r.location}</td>
                  <td>
                    <button className="link" onClick={(e) => (e.stopPropagation(), onEdit(r.supply_id))}>Edit</button>
                  </td>
                </tr>
                {expanded === r.supply_id && (
                  <tr className="details">
                    <td colSpan={COLUMNS.length + 2}>
                      <div className="details-inner">
                      {r.has_image && (
                        <img className="detail-photo" src={imageUrl(r)} alt={r.name} />
                      )}
                      <div>
                      {r.product_description && <p className="detail-desc">{r.product_description}</p>}
                      <dl>
                        <Detail label="Condition" value={r.condition} />
                        <Detail label="Reorder at" value={r.reorder_at} />
                        <Detail label="Purchased" value={r.purchase_date} />
                        <Detail label="From" value={r.purchased_from} />
                        <Detail label="Used for" value={r.used_for} />
                        <Detail label="Notes" value={r.notes} />
                        <Detail label="Last updated" value={new Date(r.updated_at).toLocaleString('en-AU')} />
                      </dl>
                      {r.source_url && (
                        <a className="small" href={r.source_url} target="_blank" rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}>View on tamiya.com ↗</a>
                      )}
                      <StockHistory supplyId={r.supply_id} version={r.qty_on_hand} />
                      </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p className="empty">{filtered ? 'Nothing matches. Try clearing the filters.' : 'No supplies yet.'}</p>
        )}
      </div>
    </section>
  )
}

// What a scan found. Owned: photo, stock and -1/+1 for the workbench. Not owned: add it somewhere.
function ScanHit({ hit, onAdjust, onEdit, onAddToInventory, onAddToWishlist, onClose }) {
  const { result, supply } = hit
  const photo = supply?.has_image ? supply : result.has_image ? result : null
  const name = supply?.name ?? result.suggested?.name ?? result.title

  return (
    <div className="card scan-hit" role="status">
      {photo ? <img src={imageUrl(photo)} alt="" /> : <div className="photo-missing">No photo</div>}
      <div className="scan-hit-body">
        <p className="muted small mono">Barcode {result.barcode}</p>
        {supply ? (
          <>
            <h3>{supply.item_ref} · {supply.name}</h3>
            <p className="muted">{[supply.brand, supply.product_code, supply.category].filter(Boolean).join(' · ')}</p>
            <div className="scan-qty">
              <button aria-label="Use one" onClick={() => onAdjust(-1)} disabled={supply.qty_on_hand <= 0}>−1</button>
              <span><strong>{supply.qty_on_hand}</strong> on hand</span>
              <button aria-label="Add one" onClick={() => onAdjust(1)}>+1</button>
              <span className={`badge ${supply.stock_status.toLowerCase()}`}>{supply.stock_status}</span>
            </div>
            <div className="photo-actions">
              <button className="link" onClick={onEdit}>Edit</button>
              <button className="link" onClick={onClose}>Close</button>
            </div>
          </>
        ) : (
          <>
            <h3>{name ?? 'Not recognised'}</h3>
            <p className="muted">
              {result.match === 'unknown'
                ? "This barcode isn't known yet. Add the item and the barcode will be remembered."
                : 'Not in your inventory.'}
            </p>
            <div className="photo-actions">
              <button className="primary" onClick={onAddToInventory}>Add to inventory</button>
              <button className="secondary" onClick={onAddToWishlist}>Add to wishlist</button>
              <button className="link" onClick={onClose}>Close</button>
            </div>
          </>
        )}
      </div>
    </div>
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
      <option value="">All {label.toLowerCase()}</option>
      {options.map((o) => (
        <option key={o.name} value={o.name}>{o.name}</option>
      ))}
    </select>
  )
}

function Detail({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value === null || value === undefined || value === '' ? '—' : value}</dd>
    </div>
  )
}
