import { NavLink, useLocation } from 'react-router'
import { HomeIcon } from '../components/icons.jsx'
import { MODULES, moduleFor } from '../modules/index.js'

const pageLink = (module, page) => `/${module.id}/${page.path}`

// Wide screens: a sidebar like the Mac's (Notes, Mail): Home, then each hobby and its pages.
// Between 701 and 1000 px it shrinks to icons only (CSS).
export function Sidebar() {
  return (
    <aside className="sidebar">
      <p className="brand">Off the Clock</p>
      <nav aria-label="Sections">
        <NavLink to="/" end className="side-link" title="Home"><HomeIcon size={20} /><span>Home</span></NavLink>
        <p className="side-section">Hobbies</p>
        {MODULES.map((m) => (
          <div key={m.id} className="side-module">
            <p className="side-module-name" title={m.what}><m.Icon size={18} /><span>{m.name}</span></p>
            {m.pages.map((p) => (
              <NavLink key={p.path} to={pageLink(m, p)} className="side-link sub" title={p.label}>
                <p.Icon size={20} /><span>{p.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  )
}

// Phones: a tab bar with Home and the pages of the hobby you're in (the first one from Home).
export function TabBar() {
  const { pathname } = useLocation()
  const module = moduleFor(pathname) ?? MODULES[0]
  return (
    <nav className="tabbar" aria-label="Pages">
      <NavLink to="/" end><HomeIcon /><span>Home</span></NavLink>
      {module.pages.map((p) => (
        <NavLink key={p.path} to={pageLink(module, p)}><p.Icon /><span>{p.label}</span></NavLink>
      ))}
    </nav>
  )
}
