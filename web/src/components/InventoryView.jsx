import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, imageUrl } from '../api.js'
import { useApp } from '../core/app-context.js'
import { MODULES } from '../modules/index.js'
import { FAMILIES, colourKey, familyOf, swatchFromImage } from './supplyExtras.jsx'
import { BulkBar, HobbySection, OwnedTable, SupplyTable, hobbyName } from './inventoryParts.jsx'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const NO_FILTERS = { attention: false, condition: '', category: '', brand: '', location: '', colour: '' }
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
  colour: { label: 'Colour', by: (r) => colourKey(r.swatch) },
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
// The hobby picked at the top (remembered on this device): '' = every hobby, 'models' = the model supplies.
const HOBBY_STORE = 'hobby-inventory.suppliesHobby'
const loadHobby = () => { try { return localStorage.getItem(HOBBY_STORE) ?? '' } catch { return '' } }
const FOLD_STORE = 'hobby-inventory.foldedHobbies'                  // the hobby sections you folded away (All hobbies)
const loadFolded = () => { try { return JSON.parse(localStorage.getItem(FOLD_STORE)) ?? [] } catch { return [] } }
const HOBBY_ORDER = Object.fromEntries(MODULES.map((m, i) => [m.id, i]))

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
// Every hobby's kit (user, 2026-10-21): pick a hobby first (Models = the paints, weathering... below; Volleyball and
// Hiking their gear, Gardening its supplies and seeds, Shooting rifles and ammo), then one of its kinds.
export default function InventoryView({ refreshKey, onOpen, onAdd, onAdjusted }) {
  const { openThing, openPanel } = useApp()
  const [hobby, setHobbyState] = useState(loadHobby)
  const [owned, setOwned] = useState([])
  const [folded, setFolded] = useState(loadFolded)
  const menu = useRef(null)
  const closeMenu = () => { if (menu.current) menu.current.open = false }
  useEffect(() => {                                              // Options closes when you tap elsewhere
    const away = (e) => { if (menu.current?.open && !menu.current.contains(e.target)) menu.current.open = false }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [])
  const fold = (h, open) => {
    if (open !== folded.includes(h)) return                     // already that way (toggle fires for our own changes too)
    const next = open ? folded.filter((x) => x !== h) : [...folded, h]
    setFolded(next)
    try { localStorage.setItem(FOLD_STORE, JSON.stringify(next)) } catch { /* not important */ }
  }
  const setHobby = (h) => { setHobbyState(h); setFilters(NO_FILTERS); try { localStorage.setItem(HOBBY_STORE, h) } catch { /* not important */ } }
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
  useEffect(() => { api.owned().then(setOwned).catch(() => setOwned([])) }, [refreshKey])
  const hobbies = useMemo(() => ['models', ...[...new Set(owned.map((o) => o.hobby))].sort((a, b) => (HOBBY_ORDER[a] ?? 99) - (HOBBY_ORDER[b] ?? 99))], [owned])
  const showSupplies = hobby === '' || hobby === 'models' || !hobbies.includes(hobby)
  const others = useMemo(() => {
    const q = search.trim().toLowerCase()
    return owned.filter((o) => (hobby === '' || o.hobby === hobby)
      && (!q || [o.name, o.detail, o.kind, o.status].some((v) => v && String(v).toLowerCase().includes(q))))
  }, [owned, hobby, search])
  const openOwned = (o) => (o.open === 'rifle' || o.open === 'ammo' ? openPanel(o.open, { id: o.id }) : openThing(o.open, o.id))

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
      .filter((r) => !filters.colour || familyOf(r.swatch) === filters.colour)
      .sort((a, b) => {
        const x = by(a), y = by(b)
        return dir * (typeof x === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true }))
      })
  }, [all, search, filters, sort])

  const filtering = search.trim() !== '' || Object.values(filters).some(Boolean)
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
  const hiddenFilters = ['category', 'condition', 'brand', 'location', 'colour'].filter((k) => filters[k]).length
  const families = FAMILIES.filter((f) => all.some((r) => familyOf(r.swatch) === f))
  const noColour = all.filter((r) => r.has_image && !r.swatch)
  // Fill in colours from the bottle photos (one at a time; you can change any of them in its panel).
  const fillColours = async () => {
    let done = 0
    for (const r of noColour) {
      try { await api.updateSupply(r.supply_id, { swatch: await swatchFromImage(imageUrl(r)) }); done += 1 } catch { /* skip that one */ }
    }
    setNotice(`Colours filled in from ${done} photo${done === 1 ? '' : 's'} - check any that look wrong in their panel.`)
    setReload((n) => n + 1)
  }
  // Select several: tick rows, then move / change category / set aside / wishlist / remove them all at once.
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState([])
  const pickRow = (id) => setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]))
  const stopSelecting = () => { setSelecting(false); setSelected([]) }    // (shown on Options when it hides some)
  const categories = Object.keys(counts.category).sort()

  const sections = hobby === '' && hobbies.length > 1          // every hobby: each a section you can fold away
  return (
    <section className="inv-page">
      <div className="toolbar">
        <input type="search" className="search" placeholder="Search name, code, brand, notes, barcode..."
          value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search" />
        <button type="button" className="primary" onClick={() => onAdd(null)}>+ Add</button>
      </div>

      {/* What's always in view: search, the hobbies and Options (user, 2026-10-21: "too many options and buttons" - a
          short list is quicker to scroll than to filter). Each category is already a heading below; the category
          filter and the rest wait under Options, and "need attention" on a hobby's heading shows just those. */}
      <div className="inv-bar">
        {hobbies.length > 1 ? (
          <div className="chip-row scroll inv-hobbies" role="group" aria-label="Hobby">
            <button type="button" className="chip-filter" aria-pressed={hobby === ''} onClick={() => setHobby('')}>All hobbies</button>
            {hobbies.map((h) => (
              <button key={h} type="button" className="chip-filter" aria-pressed={hobby === h} onClick={() => setHobby(h)}>
                {hobbyName(h)} <span className="chip-count">{h === 'models' ? all.length : owned.filter((o) => o.hobby === h).length}</span>
              </button>
            ))}
          </div>
        ) : <span className="grow" />}
        {showSupplies && (
          <details className="inv-menu" ref={menu}>
            <summary className="secondary">Options{hiddenFilters ? ` · ${hiddenFilters} on` : ''} ▾</summary>
            <div className="inv-menu-body">
              <label>Group
                <select value={view.groupBy} onChange={(e) => setGroupBy(e.target.value)} aria-label="Group by">
                  {Object.entries(GROUPS).map(([k, g]) => <option key={k} value={k}>{g.label}</option>)}
                </select>
              </label>
              <label>Sort
                <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
                  {Object.entries(SORTS).map(([k, x]) => <option key={k} value={k}>{x.label}</option>)}
                </select>
              </label>
              {/* Only offered when they'd actually narrow the list (two or more values in use). */}
              {categories.length > 1 && (
                <label>Category
                  <select value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))} aria-label="Category">
                    <option value="">Every category</option>
                    {categories.map((c) => <option key={c} value={c}>{c} ({counts.category[c]})</option>)}
                  </select>
                </label>
              )}
              {families.length > 1 && (
                <label>Colour
                  <select value={filters.colour} onChange={(e) => setFilters((f) => ({ ...f, colour: e.target.value }))} aria-label="Colour">
                    <option value="">Any colour</option>
                    {families.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
              )}
              {conditions.length > 1 && (
                <label>Condition
                  <select value={filters.condition} onChange={(e) => setFilters((f) => ({ ...f, condition: e.target.value }))} aria-label="Condition">
                    <option value="">Any condition</option>
                    {conditions.map((c) => <option key={c} value={c}>{c} ({counts.condition[c]})</option>)}
                  </select>
                </label>
              )}
              {Object.keys(counts.brand).length > 1 && (
                <label>Brand
                  <select value={filters.brand} onChange={(e) => setFilters((f) => ({ ...f, brand: e.target.value }))} aria-label="Brand">
                    <option value="">All brands</option>
                    {Object.keys(counts.brand).sort().map((b) => <option key={b} value={b}>{b} ({counts.brand[b]})</option>)}
                  </select>
                </label>
              )}
              {Object.keys(counts.location).length > 1 && (
                <label>Location
                  <select value={filters.location} onChange={(e) => setFilters((f) => ({ ...f, location: e.target.value }))} aria-label="Location">
                    <option value="">All locations</option>
                    {Object.keys(counts.location).sort().map((l) => <option key={l} value={l}>{l} ({counts.location[l]})</option>)}
                  </select>
                </label>
              )}
              {groups && groups.length > 1 && (
                <button type="button" className="plain" onClick={() => { toggleAll(); closeMenu() }}>{allClosed ? 'Open all groups' : 'Close all groups'}</button>
              )}
              {counts.attention > 0 && (
                <button type="button" className="plain" onClick={() => { restock(); closeMenu() }}>Add what needs attention to the wishlist</button>
              )}
              {missingPhotos.length > 0 && !photoJob && (
                <button type="button" className="plain" onClick={() => { fetchPhotos(); closeMenu() }}>
                  Get {missingPhotos.length} Tamiya photo{missingPhotos.length > 1 ? 's' : ''}
                </button>
              )}
              {noColour.length > 0 && (
                <button type="button" className="plain" onClick={() => { fillColours(); closeMenu() }}>Fill in {noColour.length} colour{noColour.length === 1 ? '' : 's'} from photos</button>
              )}
              <button type="button" className="plain" onClick={() => { setSelecting(true); closeMenu() }}>Select several…</button>
              <p className="inv-menu-head">Tools</p>
              <nav className="inv-tools" aria-label="Supplies tools">
                <Link to="/supplies/shop">🛒 Shopping mode</Link>
                <Link to="/supplies/stocktake">✅ Stocktake</Link>
                <Link to="/supplies/places">🗄️ Places and labels</Link>
                <Link to="/supplies/report">🧾 Value report</Link>
              </nav>
            </div>
          </details>
        )}
      </div>
      {filtering && <button type="button" className="plain small inv-clear" onClick={clearAll}>Clear filters</button>}


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
      {selecting && <BulkBar selected={selected} onDone={() => { stopSelecting(); setReload((n) => n + 1) }} onCancel={stopSelecting}
        onAll={() => setSelected(rows.map((r) => r.supply_id))} />}

      {showSupplies && <HobbySection fold={sections} id="models" count={rows.length} attention={counts.attention}
        attentionOn={filters.attention} onAttention={() => toggle('attention', true)}
        open={!folded.includes('models') || filtering} onToggle={fold}>
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
                  <span className="fold-detail">{items.length}</span>
                </summary>
                <SupplyTable rows={items} showCategory={view.groupBy !== 'category'} onOpen={selecting ? pickRow : onOpen} adjust={adjust}
                  selected={selecting ? selected : null} />
              </details>
            )
          })}
        </div>
      ) : (
        <div className="table-wrap">
          <SupplyTable rows={rows} showHead showCategory onOpen={selecting ? pickRow : onOpen} adjust={adjust} selected={selecting ? selected : null} />
        </div>
      )}
      {!loading && rows.length === 0 && (
        <p className="empty">{filtering ? 'Nothing matches. Try clearing the filters.' : 'No supplies yet. Scan or add your first one.'}</p>
      )}
      </HobbySection>}
      {(hobby === '' ? hobbies.filter((h) => h !== 'models') : showSupplies ? [] : [hobby]).map((h) => {
        const mine = others.filter((o) => o.hobby === h)
        if (hobby === '' && !mine.length) return null
        return (
          <HobbySection key={h} fold={sections} id={h} count={mine.length} attention={mine.filter((o) => o.attention).length}
            open={!folded.includes(h) || filtering} onToggle={fold}>
            {mine.length === 0 ? <p className="empty">Nothing matches.</p> : (
              <div className="inv-groups">
                {groupRows(mine.map((o) => ({ ...o, category: o.kind })), 'category').map(([name, items]) => (
                  <details key={name} className="fold inv-group" open>
                    <summary>
                      <span className="fold-title">{name}</span>
                      {items.some((o) => o.attention) && <span className="badge low">{items.filter((o) => o.attention).length} need attention</span>}
                      <span className="fold-detail">{items.length}</span>
                    </summary>
                    <OwnedTable rows={items} onOpen={openOwned} />
                  </details>
                ))}
              </div>
            )}
          </HobbySection>
        )
      })}
    </section>
  )
}
