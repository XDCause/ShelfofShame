import { useEffect, useMemo, useState } from 'react'
import { api, imageUrl, money } from '../api.js'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const NO_FILTERS = { attention: false, condition: '', category: '', brand: '', location: '' }
const STATUS_ORDER = { Out: 0, Low: 1, OK: 2 }
const CONDITION_ORDER = ['Sealed', 'Opened', 'Half used', 'Nearly empty', 'Empty', 'Dried out']

const SORTS = {
  ref: { label: 'Newest first', by: (r) => r.supply_id, dir: -1 },
  name: { label: 'Name', by: (r) => r.name },
  category: { label: 'Category', by: (r) => r.category },
  brand: { label: 'Brand', by: (r) => r.brand ?? '' },
  condition: { label: 'Condition (most used first)', by: (r) => -CONDITION_ORDER.indexOf(r.condition ?? '') },
  status: { label: 'Needs attention first', by: (r) => STATUS_ORDER[r.stock_status] },
  value: { label: 'Value', by: (r) => Number(r.total_value ?? 0), dir: -1 },
  purchased: { label: 'Last purchased', by: (r) => r.purchase_date ?? '', dir: -1 },
}

// Group the list into drop-downs by one of the same things the chips filter on.
// `order` puts the groups in a sensible order (alphabetical when there isn't one).
const GROUPS = {
  category: { label: 'By category', of: (r) => r.category ?? 'No category' },
  condition: { label: 'By condition', of: (r) => r.condition ?? 'No condition', order: CONDITION_ORDER },
  attention: { label: 'Needs attention / OK', of: (r) => (r.stock_status === 'OK' ? 'All good' : 'Needs attention'), order: ['Needs attention', 'All good'] },
  brand: { label: 'By brand', of: (r) => r.brand ?? 'No brand' },
  location: { label: 'By location', of: (r) => r.location ?? 'No location' },
  none: { label: 'No groups' },
}

// Which grouping you picked and which groups you closed are remembered on this device.
// Closed ones are stored (not open ones) so a new category shows up open.
const STORE = 'hobby-inventory.inventoryGroups'
function loadView() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE)) ?? {}
    return { groupBy: GROUPS[saved.groupBy] ? saved.groupBy : 'category', closed: saved.closed ?? {} }
  } catch {
    return { groupBy: 'category', closed: {} }
  }
}
function saveView(view) {
  try { localStorage.setItem(STORE, JSON.stringify(view)) } catch { /* private window: just don't remember */ }
}

function groupRows(rows, groupBy) {
  const { of, order = [] } = GROUPS[groupBy]
  const groups = new Map()
  for (const r of rows) {
    const key = of(r)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(r)
  }
  const rank = (k) => (order.includes(k) ? order.indexOf(k) : order.length)
  return [...groups].sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
}

// Count how many rows have each value of `key`, e.g. {Paint: 9, Thinner: 2}.
const countBy = (rows, key) => rows.reduce((m, r) => (r[key] ? { ...m, [r[key]]: (m[r[key]] ?? 0) + 1 } : m), {})
const valueOf = (rows) => rows.reduce((s, r) => s + Number(r.total_value ?? 0), 0)

// The inventory list. Tap a row for everything about that item (opens a side panel).
// Scan: something you own opens its panel; anything else opens "Add a supply" pre-filled.
// The whole list is loaded once and filtered here, so the chip counts always describe
// everything you own, not just what's currently showing.
export default function InventoryView({ lookups, refreshKey, onOpen, onAdd, onAdjusted }) {
  const [all, setAll] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState(NO_FILTERS)
  const [sort, setSort] = useState('ref')
  const [notice, setNotice] = useState(null)
  const [photoJob, setPhotoJob] = useState(null) // {done, total, failed} while fetching photos
  const [reload, setReload] = useState(0)
  const [view, setView] = useState(loadView)
  // While searching or filtering every group with a match is open (so nothing you're looking for
  // is hidden); groups you close then are forgotten when you clear the search.
  const [closedWhileFiltering, setClosedWhileFiltering] = useState([])

  useEffect(() => {
    let current = true
    api.listSupplies()
      .then((data) => current && (setAll(data), setError('')))
      .catch((e) => current && setError(e.message))
      .finally(() => current && setLoading(false))
    return () => { current = false }
  }, [refreshKey, reload])

  const counts = useMemo(() => ({
    attention: all.filter((r) => r.stock_status !== 'OK').length,
    condition: countBy(all, 'condition'),
    category: countBy(all, 'category'),
    brand: countBy(all, 'brand'),
    location: countBy(all, 'location'),
    value: valueOf(all),
  }), [all])

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    const { by, dir = 1 } = SORTS[sort]
    return all
      .filter((r) => !q || [r.name, r.product_code, r.brand, r.category, r.notes, r.barcode]
        .some((v) => v && String(v).toLowerCase().includes(q)))
      .filter((r) => !filters.attention || r.stock_status !== 'OK')
      .filter((r) => ['condition', 'category', 'brand', 'location'].every((k) => !filters[k] || r[k] === filters[k]))
      .sort((a, b) => {
        const x = by(a), y = by(b)
        return dir * (typeof x === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true }))
      })
  }, [all, search, filters, sort])

  const filtering = search.trim() !== '' || Object.values(filters).some(Boolean)
  const shownValue = valueOf(rows)
  const toggle = (key, value) => setFilters((f) => ({ ...f, [key]: f[key] === value ? NO_FILTERS[key] : value }))
  const clearAll = () => { setSearch(''); setFilters(NO_FILTERS) }

  useEffect(() => { if (!filtering) setClosedWhileFiltering([]) }, [filtering])

  const groups = useMemo(() => (view.groupBy === 'none' ? null : groupRows(rows, view.groupBy)), [rows, view.groupBy])
  const closed = filtering ? closedWhileFiltering : (view.closed[view.groupBy] ?? [])
  const setClosed = (names) => {
    if (filtering) return setClosedWhileFiltering(names)
    const next = { ...view, closed: { ...view.closed, [view.groupBy]: names } }
    setView(next)
    saveView(next)
  }
  const setGroupOpen = (name, open) => {
    if (open !== closed.includes(name)) return // already that way (the toggle event also fires for our own changes)
    setClosed(open ? closed.filter((n) => n !== name) : [...closed, name])
  }
  const setGroupBy = (groupBy) => {
    const next = { ...view, groupBy }
    setView(next)
    saveView(next)
  }
  const allClosed = groups && groups.every(([name]) => closed.includes(name))
  const toggleAll = () => {
    const names = groups.map(([name]) => name)
    setClosed(allClosed ? closed.filter((n) => !names.includes(n)) : [...new Set([...closed, ...names])])
  }
  const missingPhotos = all.filter((r) => r.brand === 'Tamiya' && r.product_code && !r.has_image)

  const adjust = async (row, delta) => {
    try {
      const updated = await api.adjustQty(row.supply_id, delta)
      setAll((rs) => rs.map((r) => (r.supply_id === updated.supply_id ? updated : r)))
      setError('')
      onAdjusted(row, delta, updated.auto_wish_id) // "Used one: ... · Undo"
    } catch (e) {
      setError(`${row.name}: ${e.message}`)
    }
  }

  const restock = async () => {
    try {
      const r = await api.wishRestock()
      setNotice(r.added ? `Added to wishlist: ${r.names.join(', ')}.` : 'Everything that needs attention is already on your wishlist.')
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

  const conditions = CONDITION_ORDER.filter((c) => counts.condition[c])
  const categories = Object.keys(counts.category).sort()

  return (
    <section>
      <div className="toolbar">
        <input type="search" className="search" placeholder="Search name, code, brand, notes, barcode..."
          value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search" />
        <button type="button" className="primary" onClick={() => onAdd(null)}>+ Add</button>
      </div>

      {/* Totals follow the filters: "9 of 22 items · $35.55" when filtering. */}
      <p className="summary">
        {filtering
          ? <><strong>{rows.length}</strong> of {all.length} items · <strong>{money(shownValue)}</strong>{' '}
              <button type="button" className="plain" onClick={clearAll}>Clear filters</button></>
          : <><strong>{all.length}</strong> items · <strong>{money(counts.value)}</strong></>}
      </p>

      <div className="chip-rows">
        {counts.attention > 0 && (
          <div className="chip-row">
            <Chip on={filters.attention} tone="attention" onClick={() => toggle('attention', true)}
              label="Needs attention" count={counts.attention} />
            <button type="button" className="chip-btn" onClick={restock}>Add to wishlist</button>
          </div>
        )}
        {conditions.length > 1 && (
          <div className="chip-row" aria-label="Condition">
            {conditions.map((c) => (
              <Chip key={c} on={filters.condition === c} onClick={() => toggle('condition', c)} label={c} count={counts.condition[c]} />
            ))}
          </div>
        )}
        {categories.length > 1 && (
          <div className="chip-row" aria-label="Category">
            {categories.map((c) => (
              <Chip key={c} on={filters.category === c} onClick={() => toggle('category', c)} label={c} count={counts.category[c]} />
            ))}
          </div>
        )}
      </div>

      <div className="filters">
        {/* Only offered when they'd actually narrow the list (two or more values in use). */}
        {Object.keys(counts.brand).length > 1 && (
          <select value={filters.brand} onChange={(e) => setFilters((f) => ({ ...f, brand: e.target.value }))} aria-label="Brand">
            <option value="">All brands</option>
            {Object.keys(counts.brand).sort().map((b) => <option key={b} value={b}>{b} ({counts.brand[b]})</option>)}
          </select>
        )}
        {Object.keys(counts.location).length > 1 && (
          <select value={filters.location} onChange={(e) => setFilters((f) => ({ ...f, location: e.target.value }))} aria-label="Location">
            <option value="">All locations</option>
            {Object.keys(counts.location).sort().map((l) => <option key={l} value={l}>{l} ({counts.location[l]})</option>)}
          </select>
        )}
        {missingPhotos.length > 0 && !photoJob && (
          <button type="button" className="chip-btn" onClick={fetchPhotos}>
            Get {missingPhotos.length} Tamiya photo{missingPhotos.length > 1 ? 's' : ''}
          </button>
        )}
        <div className="view-controls">
          <label className="sort">
            <span className="muted small">Group</span>
            <select value={view.groupBy} onChange={(e) => setGroupBy(e.target.value)} aria-label="Group by">
              {Object.entries(GROUPS).map(([k, g]) => <option key={k} value={k}>{g.label}</option>)}
            </select>
          </label>
          <label className="sort">
            <span className="muted small">Sort</span>
            <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
              {Object.entries(SORTS).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
            </select>
          </label>
          {groups && groups.length > 1 && (
            <button type="button" className="plain small" onClick={toggleAll}>{allClosed ? 'Open all' : 'Close all'}</button>
          )}
        </div>
      </div>

      {photoJob && (
        <p className={`alert ${photoJob.failed.length ? 'low' : 'ok'} small`} role="status">
          {photoJob.done < photoJob.total
            ? `Fetching photos from tamiya.com... ${photoJob.done} of ${photoJob.total}`
            : `Done: ${photoJob.total - photoJob.failed.length} of ${photoJob.total} photos fetched.`}
          {photoJob.done === photoJob.total && <button className="plain" onClick={() => setPhotoJob(null)}>Dismiss</button>}
        </p>
      )}
      {notice && <p className="alert ok small" role="status">{notice} <button className="plain" onClick={() => setNotice(null)}>Dismiss</button></p>}
      {error && <p className="alert error" role="alert">{error}</p>}

      {groups ? (
        <div className="inv-groups">
          {groups.map(([name, items]) => {
            const attention = items.filter((r) => r.stock_status !== 'OK').length
            return (
              <details key={name} className="fold inv-group" open={!closed.includes(name)}
                onToggle={(e) => setGroupOpen(name, e.currentTarget.open)}>
                <summary>
                  <span className="fold-title">{name}</span>
                  {attention > 0 && view.groupBy !== 'attention' && <span className="badge low">{attention} need attention</span>}
                  <span className="fold-detail">{items.length} · {money(valueOf(items))}</span>
                </summary>
                <SupplyTable rows={items} showCategory={view.groupBy !== 'category'} onOpen={onOpen} adjust={adjust} />
              </details>
            )
          })}
        </div>
      ) : (
        <div className="table-wrap">
          <SupplyTable rows={rows} showHead showCategory onOpen={onOpen} adjust={adjust} />
        </div>
      )}
      {!loading && rows.length === 0 && (
        <p className="empty">{filtering ? 'Nothing matches. Try clearing the filters.' : 'No supplies yet. Scan or add your first one.'}</p>
      )}
    </section>
  )
}

// One table of supplies: the whole list, or one group. Every group's table has the same fixed
// column widths, so the columns line up down the page. Grouped by category, the Category column
// is left out (every row in a "Paint" group says Paint).
function SupplyTable({ rows, showHead = false, showCategory = false, onOpen, adjust }) {
  return (
    <table className="inventory">
      <thead className={showHead ? '' : 'quiet'}>
        <tr>
          <th className="thumb-col"><span className="visually-hidden">Photo</span></th>
          <th>Item</th>
          {showCategory && <th className="col-category hide-sm">Category</th>}
          <th className="col-condition hide-xs">Condition</th>
          <th className="col-stock num">Stock</th>
          <th className="col-value num hide-sm">Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.supply_id} className={r.stock_status === 'OK' ? 'row' : 'row attention'}
            onClick={() => onOpen(r.supply_id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpen(r.supply_id)}>
            <td className="thumb-col">
              {r.has_image
                ? <img className="thumb" src={imageUrl(r)} alt="" loading="lazy" />
                : <span className="thumb thumb-empty" aria-hidden="true" />}
            </td>
            <td className="item-cell">
              <span className="item-title">{r.name}</span>
              <span className="item-meta">
                {[r.brand, r.product_code, r.size].filter(Boolean).join(' · ')}
                {/* On phones the Condition column is hidden, so show it here instead */}
                <span className="show-xs"><Condition row={r} /></span>
              </span>
            </td>
            {showCategory && <td className="hide-sm">{r.category}</td>}
            <td className="hide-xs"><Condition row={r} /></td>
            <td className="num">
              <span className="qty" onClick={(e) => e.stopPropagation()}>
                <button aria-label={`Use one ${r.name}`} disabled={r.qty_on_hand <= 0} onClick={() => adjust(r, -1)}>−</button>
                <span>{r.qty_on_hand}</span>
                <button aria-label={`Add one ${r.name}`} onClick={() => adjust(r, 1)}>+</button>
              </span>
            </td>
            <td className="num hide-sm">{money(r.total_value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// Condition, plus a Low / Out badge only when it applies, and "On wishlist" when it is.
function Condition({ row }) {
  return (
    <span className="condition">
      {row.condition ?? <span className="muted">—</span>}
      {row.stock_status !== 'OK' && <span className={`badge ${row.stock_status.toLowerCase()}`}>{row.stock_status}</span>}
      {row.on_wishlist && <span className="tag">On wishlist</span>}
    </span>
  )
}

function Chip({ label, count, on, onClick, tone = '' }) {
  return (
    <button type="button" className={`chip-filter ${tone}`} aria-pressed={on} onClick={onClick}>
      {label} <span className="chip-count">{count}</span>
    </button>
  )
}
