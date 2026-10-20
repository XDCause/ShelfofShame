import { Link } from 'react-router'
import { ChevronIcon } from '../components/icons.jsx'
import { UnderConstruction } from './Navigation.jsx'
import { MODULES } from '../modules/index.js'

// Every hobby, with its numbers: the phone's Hobbies tab (wide screens list them in the sidebar).
export default function HobbiesPage() {
  return (
    <section className="page hobbies">
      {MODULES.map((m) => (
        <section key={m.id} className="card hobby-card" data-hobby={m.id}>
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
