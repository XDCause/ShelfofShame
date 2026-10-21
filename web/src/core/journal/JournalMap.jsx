import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import { weatherText } from './JournalExtras.jsx'
import { pageFace } from './moods.js'

const TravelMap = lazy(() => import('../../modules/travel/TravelMap.jsx'))   // (Leaflet: only loaded for the map)

// Journal > Map: every page with a place (Apple Journal's map). A dot opens its page. A page gets a place from
// "+ Place" on the page (or "+ Weather", which places it at home).
export default function JournalMap() {
  const { refreshKey } = useApp()
  const navigate = useNavigate()
  const [pages, setPages] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.journalPlaces().then(setPages).catch((e) => setError(e.message)) }, [refreshKey])
  const places = useMemo(() => (pages ?? []).map((p) => ({ ...p, name: `${p.title || 'Untitled'} · ${shortDate(p.entry_date)}`, shown: 'Planned' })),
    [pages])
  const open = useCallback((p) => navigate(`/journal/${p.page_id}`), [navigate])

  if (error) return <p className="alert error">{error}</p>
  if (!pages) return <p className="muted loading">Loading...</p>
  return (
    <section className="page">
      {pages.length === 0 ? (
        <p className="empty card">No pages have a place yet. Open a page and tap "+ Place" (or "+ Weather", which uses home).</p>
      ) : (
        <>
          <Suspense fallback={<p className="muted loading">Opening the map...</p>}>
            <TravelMap places={places} onPlace={open} label="Map of journal pages"
              legend={<span><i className="travel-key-planned" /> A page (tap to open it)</span>} />
          </Suspense>
          <ul className="list jx-map-list">
            {pages.map((p) => (
              <li key={p.page_id}>
                <Link to={`/journal/${p.page_id}`}>{pageFace(p)} {p.title || 'Untitled'}</Link>
                <span className="muted small"> {shortDate(p.entry_date)} · 📍 {p.place_name}{p.weather ? ` · ${weatherText(p.weather)}` : ''}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
