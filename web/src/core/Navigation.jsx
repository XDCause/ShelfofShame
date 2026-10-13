import { NavLink, useLocation } from 'react-router'
import { BoltIcon, ClockIcon, HomeIcon, JournalIcon } from '../components/icons.jsx'
import { MODULES, moduleFor } from '../modules/index.js'

// The core's own pages, for every hobby (the calendar joins them in phase 3, docs/ROADMAP.md).
export const CORE_PAGES = [
  { path: '/', label: 'Home', Icon: HomeIcon },
  { path: '/journal', label: 'Journal', Icon: JournalIcon },
]
export const corePageFor = (pathname) =>
  CORE_PAGES.find((p) => (p.path === '/' ? pathname === '/' : pathname === p.path || pathname.startsWith(`${p.path}/`)))

const pageLink = (module, page) => `/${module.id}/${page.path}`

// The card at the foot of the sidebar: a different nudge each day.
const NUDGES = [
  ['Keep building.', 'One model at a time.'],
  ['Thin your paints.', 'Two thin coats beat one thick one.'],
  ['Progress, not perfection.', 'Ten minutes at the bench still counts.'],
  ['Clear the shelf.', 'Finish one before you open another.'],
  ['Write it down.', 'Future you will want to know what you mixed.'],
]
const nudge = () => NUDGES[Math.floor(Date.now() / 86400000) % NUDGES.length]

// Wide screens: a sidebar like the Mac's (Notes, Mail): Home and Journal, then each hobby and
// its pages. Between 701 and 1000 px it shrinks to icons only (CSS).
export function Sidebar() {
  return (
    <aside className="sidebar">
      <p className="brand"><span className="brand-mark"><ClockIcon size={20} /></span>Off the Clock</p>
      <nav aria-label="Sections">
        {CORE_PAGES.map((p) => (
          <NavLink key={p.path} to={p.path} end={p.path === '/'} className="side-link" title={p.label}>
            <p.Icon size={20} /><span>{p.label}</span>
          </NavLink>
        ))}
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
      <div className="nudge" aria-hidden="true">
        <BoltIcon size={18} />
        <span><strong>{nudge()[0]}</strong>{nudge()[1]}</span>
      </div>
    </aside>
  )
}

// Phones: a tab bar with Home, Journal and one tab per hobby (its short name). A hobby's own
// pages are a switcher at the top of the screen (ModuleTabs), so the bar never overflows.
export function TabBar() {
  return (
    <nav className="tabbar" aria-label="Sections">
      {CORE_PAGES.map((p) => (
        <NavLink key={p.path} to={p.path} end={p.path === '/'}><p.Icon /><span>{p.label}</span></NavLink>
      ))}
      {MODULES.map((m) => (
        <NavLink key={m.id} to={`/${m.id}`} title={m.name}><m.Icon /><span>{m.short}</span></NavLink>
      ))}
    </nav>
  )
}

// Phones, inside a hobby: its pages as a segmented control under the nav bar.
export function ModuleTabs() {
  const { pathname } = useLocation()
  const module = moduleFor(pathname)
  if (!module) return null
  return (
    <nav className="module-tabs segmented" aria-label={`${module.name} pages`}>
      {module.pages.map((p) => <NavLink key={p.path} to={pageLink(module, p)}>{p.label}</NavLink>)}
    </nav>
  )
}
