import { Link, NavLink, useLocation } from 'react-router'
import { useApp } from './app-context.js'
import { BoltIcon, BoxIcon, CalendarIcon, CartIcon, GearIcon, GridIcon, HomeIcon, JournalIcon, LogoMark, TargetIcon, WrenchIcon } from '../components/icons.jsx'
import { MODULES, moduleFor } from '../modules/index.js'

// A spanner after a hobby's name: it's a placeholder, still to be built (manifest underConstruction).
export function UnderConstruction() {
  return <span className="under-construction" title="Under construction"><WrenchIcon size={14} />
    <span className="visually-hidden"> (under construction)</span></span>
}

// The core: pages for every hobby. Supplies and the wishlist are shared (paints, glue, tape...
// for any hobby), so they sit here rather than inside a hobby. `title` is the page heading when
// it differs from the menu label.
const CORE_PAGES = [
  { path: '/', label: 'Home', Icon: HomeIcon },
  { path: '/goals', label: 'Goals', Icon: TargetIcon },
  { path: '/journal', label: 'Journal', Icon: JournalIcon },
  { path: '/calendar', label: 'Calendar', Icon: CalendarIcon },
  { path: '/supplies', label: 'Supplies', title: 'Hobby supplies', Icon: BoxIcon },
  { path: '/wishlist', label: 'Wishlist', Icon: CartIcon },
]
const SUPPLY_PAGES = CORE_PAGES.slice(4)
const HOBBIES_PAGE = { path: '/hobbies', label: 'Hobbies', Icon: GridIcon }

const under = (pathname, path) => pathname === path || pathname.startsWith(`${path}/`)
export const corePageFor = (pathname) =>
  [...CORE_PAGES, HOBBIES_PAGE].find((p) => (p.path === '/' ? pathname === '/' : under(pathname, p.path)))

const pageLink = (module, page) => `/${module.id}/${page.path}`

// The card at the foot of the sidebar: a different nudge each day.
const NUDGES = [
  ['Make time for it.', 'Ten minutes off the clock still counts.'],
  ['Thin your paints.', 'Two thin coats beat one thick one.'],
  ['Progress, not perfection.', 'One step at a time.'],
  ['Clear the shelf.', 'Finish one before you open another.'],
  ['Write it down.', 'Future you will want to know.'],
  ['Call a games night.', 'The box is no fun on the shelf.'],
  ['Stretch first.', 'Your knees will thank you on Tuesday.'],
]
const nudge = () => NUDGES[Math.floor(Date.now() / 86400000) % NUDGES.length]

// Wide screens: a sidebar like the Mac's (Notes, Mail): the core pages, then one entry per hobby.
// A hobby's own pages (Kits, Colours...) are tabs at the top of its page (SectionTabs).
// Between 701 and 1000 px it shrinks to icons only (CSS).
export function Sidebar() {
  const { openPanel } = useApp()
  return (
    <aside className="sidebar">
      <Link to="/" className="brand" aria-label="Off the Clock: Home"><LogoMark size={30} className="brand-mark" /><span className="brand-name">Off the Clock</span></Link>
      <nav aria-label="Sections">
        {CORE_PAGES.map((p) => (
          <NavLink key={p.path} to={p.path} end={p.path === '/'} className="side-link" title={p.label}>
            <p.Icon size={20} /><span>{p.label}</span>
          </NavLink>
        ))}
        <p className="side-section">Hobbies</p>
        {MODULES.map((m) => (
          <NavLink key={m.id} to={`/${m.id}`} className="side-link" title={m.what} data-hobby={m.id} style={{ '--hue': m.hue }}>
            <m.Icon size={20} /><span>{m.name}{m.underConstruction && <UnderConstruction />}</span>
          </NavLink>
        ))}
      </nav>
      <div className="nudge" aria-hidden="true">
        <BoltIcon size={18} />
        <span><strong>{nudge()[0]}</strong>{nudge()[1]}</span>
      </div>
      <button type="button" className="side-link side-settings" onClick={() => openPanel('settings')}
        title="Settings: appearance, spending, prices, backups, export, lists">
        <GearIcon size={20} /><span>Settings</span>
      </button>
    </aside>
  )
}

// Phones: five tabs (Goals is reached from its Home card). Supplies covers the wishlist too, and Hobbies covers every hobby (a page
// listing them), so the bar never overflows however many hobbies there are. Plain Links: a
// NavLink would mark itself by its own address only.
export function TabBar() {
  const { pathname } = useLocation()
  const tabs = [
    ...CORE_PAGES.filter((p) => ['/', '/journal', '/calendar'].includes(p.path)).map((p) => ({ ...p, on: p.path === '/' ? pathname === '/' : under(pathname, p.path) })),
    { ...SUPPLY_PAGES[0], on: SUPPLY_PAGES.some((p) => under(pathname, p.path)) },
    { ...HOBBIES_PAGE, on: under(pathname, HOBBIES_PAGE.path) || Boolean(moduleFor(pathname)) },
  ]
  return (
    <nav className="tabbar" aria-label="Sections">
      {tabs.map((t) => (
        <Link key={t.path} to={t.path} aria-current={t.on ? 'page' : undefined}>
          <t.Icon /><span>{t.label}</span>
        </Link>
      ))}
    </nav>
  )
}

// Tabs under the nav bar: a hobby's own pages (on every screen), and on phones Supplies | Wishlist.
export function SectionTabs() {
  const { pathname } = useLocation()
  const module = moduleFor(pathname)
  if (module) {
    if (module.pages.length < 2) return null
    return (
      <nav className="section-tabs segmented" aria-label={`${module.name} pages`}>
        {module.pages.map((p) => <NavLink key={p.path} to={pageLink(module, p)}>{p.label}</NavLink>)}
      </nav>
    )
  }
  if (!SUPPLY_PAGES.some((p) => under(pathname, p.path))) return null
  return (
    <nav className="section-tabs segmented phone-only" aria-label="Supplies pages">
      {SUPPLY_PAGES.map((p) => <NavLink key={p.path} to={p.path}>{p.label}</NavLink>)}
    </nav>
  )
}
