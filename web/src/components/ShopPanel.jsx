import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Drawer from './Drawer.jsx'
import OwnedBadge from './OwnedBadge.jsx'

const SUGGESTIONS = ['panel line', 'XF-1', 'masking tape', 'thinner', 'primer', 'cement']

// Shop Tamiya: search Tamiya's catalogue (imported with app/tamiya_catalog.py) and add things to
// the wishlist in one tap. Photos in the results load from Tamiya's site; adding one fetches its
// full details and photo into your database.
export default function ShopPanel({ onClose, onAdded }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [info, setInfo] = useState(null)
  const [busy, setBusy] = useState('') // product_code being added
  const [error, setError] = useState('')

  useEffect(() => { api.catalogInfo().then(setInfo).catch(() => {}) }, [])

  // Search as you type, after a short pause.
  useEffect(() => {
    if (!q.trim()) { setResults(null); return }
    let current = true
    const t = setTimeout(() => {
      api.searchCatalog(q.trim())
        .then((r) => current && (setResults(r), setError('')))
        .catch((e) => current && setError(e.message))
    }, 250)
    return () => { current = false; clearTimeout(t) }
  }, [q])

  const add = async (p) => {
    setBusy(p.product_code)
    setError('')
    try {
      await api.addCatalogToWishlist(p.product_code) // may fetch from tamiya.com the first time
      setResults((rs) => rs.map((r) => (r.product_code === p.product_code ? { ...r, on_wishlist: true } : r)))
      onAdded(p)
    } catch (e) {
      setError(`${p.name}: ${e.message}`)
    } finally {
      setBusy('')
    }
  }

  const empty = info && info.products === 0

  return (
    <Drawer title="Shop Tamiya" onClose={onClose} wide>
      <div className="shop-search">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} autoFocus
          placeholder="Search Tamiya: panel line black, XF-76, masking tape..." aria-label="Search Tamiya" />
        {!q && !empty && (
          <div className="chip-row">
            {SUGGESTIONS.map((s) => <button key={s} type="button" className="chip-filter" onClick={() => setQ(s)}>{s}</button>)}
          </div>
        )}
      </div>

      {empty && (
        <p className="alert low small">
          The Tamiya catalogue hasn't been imported yet. In the project folder run:{' '}
          <code>docker exec hobby-inventory-api python -m app.tamiya_catalog</code>
        </p>
      )}
      {error && <p className="alert error small" role="alert">{error}</p>}

      {results && results.length === 0 && <p className="empty">Nothing matches "{q}".</p>}
      {results && results.length > 0 && (
        <ul className="shop-results">
          {results.map((p) => (
            <li key={p.product_code}>
              <span className="shop-photo">
                {p.thumb_url ? <img src={p.thumb_url} alt="" loading="lazy" referrerPolicy="no-referrer" /> : null}
              </span>
              <span className="shop-text">
                <span className="item-title">{p.name}</span>
                <span className="item-meta">
                  {p.product_code} · {p.genre}
                  <OwnedBadge wish={p} />
                  {p.on_wishlist && <span className="tag ok">On wishlist ✓</span>}
                </span>
              </span>
              <span className="shop-actions">
                {p.on_wishlist ? null : (
                  <button type="button" className="secondary" onClick={() => add(p)} disabled={busy !== ''}>
                    {busy === p.product_code ? 'Adding...' : '+ Wishlist'}
                  </button>
                )}
                {p.source_url && (
                  <a className="small" href={p.source_url} target="_blank" rel="noreferrer">tamiya.com ↗</a>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {info?.products > 0 && (
        <p className="hint shop-footnote">
          {info.products} Tamiya products · catalogue imported{' '}
          {new Date(info.imported_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}
        </p>
      )}
    </Drawer>
  )
}
