import { useState } from 'react'
import { Link } from 'react-router'
import { ChevronIcon } from '../components/icons.jsx'
import { BannerArt } from '../components/PageBanner.jsx'
import { useBanners } from './banners.js'
import { UnderConstruction } from './Navigation.jsx'
import { api } from '../api.js'
import { useApp } from './app-context.js'
import { useHobbies } from './useHobbies.js'

// Every hobby, with its numbers: the phone's Hobbies tab (wide screens list them in the sidebar).
export default function HobbiesPage() {
  const banners = useBanners()
  const [q, setQ] = useState('')
  const { settings, setSettings, showToast } = useApp()
  const hobbies = useHobbies()                 // favourites first, then A-Z
  const stars = settings?.favourite_hobbies ?? []
  // Star / unstar: save the whole list (the API checks it) and show what it sends back, so every list re-orders at once.
  const toggle = async (id) => {
    const next = stars.includes(id) ? stars.filter((s) => s !== id) : [...stars, id]
    try { setSettings(await api.updateSettings({ favourite_hobbies: next })) } catch (e) { showToast(`Couldn't save: ${e.message}`) }
  }
  const shown = hobbies.filter((m) => !q.trim() || `${m.name} ${m.what ?? ''}`.toLowerCase().includes(q.trim().toLowerCase()))
  return (
    <section className="page hobbies">
      {/* a search on the banner's foot, like Journal and Supplies (it narrows the cards) */}
      <div className="toolbar hobbies-find">
        <input type="search" className="search" placeholder="Find a hobby..." value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find a hobby" />
      </div>
      {shown.length === 0 && <p className="empty card">No hobby matches.</p>}
      {shown.map((m) => (
        <section key={m.id} className="card hobby-card" data-hobby={m.id} style={{ '--hue': m.hue }}>
          <Link to={`/${m.id}`} className="hobby-art" tabIndex={-1} aria-hidden="true"><BannerArt area={m} photo={banners[m.id]} strip /></Link>
          <button type="button" className={`hobby-star${stars.includes(m.id) ? ' on' : ''}`} aria-pressed={stars.includes(m.id)}
            aria-label={`${stars.includes(m.id) ? 'Unfavourite' : 'Favourite'} ${m.name}`} onClick={() => toggle(m.id)}>
            <span aria-hidden="true">{stars.includes(m.id) ? '★' : '☆'}</span>
          </button>
          <Link to={`/${m.id}`} className="hobby-head">
            <span className="stat-icon tint"><m.Icon size={24} /></span>
            <span className="grow">
              <span className="item-title">{m.name}{m.underConstruction && <UnderConstruction />}</span>
              <span className="item-meta">{m.what}</span>
            </span>
            <ChevronIcon size={18} className="chevron" />
          </Link>
          {m.home?.Tiles && <div className="home-stats"><m.home.Tiles /></div>}
        </section>
      ))}
      <p className="hint">Supplies, the wishlist, the journal and the calendar are shared by every hobby.</p>
    </section>
  )
}
