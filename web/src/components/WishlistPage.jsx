import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, imageUrl, money } from '../api.js'
import { useApp } from '../core/app-context.js'
import { MODULES } from '../modules/index.js'
import { BoxIcon, DiceIcon, PlaneIcon, ShoeIcon, SproutIcon } from './icons.jsx'
import { ExtraTags, WishHistory, extraOf, hobbyName } from './wishExtras.jsx'
import WishlistView from './WishlistView.jsx'

// The Wishlist page: everything you want to buy (api/app/wanted.py), like Supplies: a hobby row and Options (2026-10-21).
// Group by shop (your default shop first, with the supplies wishlist itself - ticks, "Add to inventory" - then Good Games,
// Blue Sky...) or by hobby. Every card can be ticked when you buy it (a kit In stash, a game Owned, gear New; Undo);
// Details holds what it's for, a target price, saving up and its prices (wishExtras.jsx).
const KIND_ICON = { model: PlaneIcon, game: DiceIcon, gear: ShoeIcon, garden: SproutIcon }
const ORDER = Object.fromEntries(MODULES.map((m, i) => [m.id, i]))
const store = (key, fallback) => ({
  read: () => { try { return localStorage.getItem(key) ?? fallback } catch { return fallback } },
  save: (v) => { try { localStorage.setItem(key, v) } catch { /* not important */ } },
})
const HOBBY = store('offtheclock.wishHobby', '')
const GROUP = store('offtheclock.wishGroup', 'shop')

export default function WishlistPage(props) {
  const { refreshKey, openThing, openPanel, changed, showToast } = useApp()
  const [data, setData] = useState(null)
  const [extras, setExtras] = useState({})
  const [hobby, setHobbyState] = useState(HOBBY.read)
  const [group, setGroupState] = useState(GROUP.read)
  const [view, setView] = useState('list')            // list | history
  const [gotten, setGotten] = useState({})            // just ticked: "kind:id" -> true (with Undo)
  const ticked = useRef({})                           // (the same, for the timer that lets the list catch up)
  const menu = useRef(null)
  useEffect(() => { api.wanted().then(setData).catch(() => setData(null)) }, [refreshKey])
  useEffect(() => { api.wantedExtras().then(setExtras).catch(() => setExtras({})) }, [refreshKey])
  useEffect(() => {
    const away = (e) => { if (menu.current?.open && !menu.current.contains(e.target)) menu.current.open = false }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [])
  const setHobby = (h) => { setHobbyState(h); HOBBY.save(h) }
  const closeMenu = () => { if (menu.current) menu.current.open = false }
  const setGroup = (g) => { setGroupState(g); GROUP.save(g); closeMenu() }

  const items = useMemo(() => (data?.shops ?? []).flatMap((s) => s.items.map((i) => ({ ...i, shop: s.shop, hobby: extraOf(extras, i.kind, i.id)?.hobby }))), [data, extras])
  const hobbies = useMemo(() => {
    const set = new Set(items.map((i) => i.hobby).filter(Boolean))
    if (data?.supplies) set.add('models')
    return [...set].sort((a, b) => (ORDER[a] ?? 99) - (ORDER[b] ?? 99))
  }, [items, data])
  const shown = items.filter((i) => !hobby || i.hobby === hobby)
  const showSupplies = !hobby || hobby === 'models'

  // Bought it: yours now; Undo for a few seconds (then the list catches up).
  const tick = async (i) => {
    const key = `${i.kind}:${i.id}`
    try {
      await api.gotWanted(i.kind, i.id)
      ticked.current[key] = true
      setGotten((g) => ({ ...g, [key]: true }))
      showToast(`${i.name}: bought ✓`)
      setTimeout(() => { if (ticked.current[key]) changed() }, 6000)
    } catch (e) { showToast(e.message) }
  }
  const untick = async (i) => {
    const key = `${i.kind}:${i.id}`
    try {
      await api.ungotWanted(i.kind, i.id)
      delete ticked.current[key]
      setGotten((g) => { const n = { ...g }; delete n[key]; return n })
    } catch (e) { showToast(e.message) }
  }
  const grid = (list, title) => list.length > 0 && (
    <WantedGrid items={list} title={title} extras={extras} gotten={gotten} openThing={openThing} openPanel={openPanel} onTick={tick} onUntick={untick} />
  )

  // sections: by shop (the default shop first, with the supplies wishlist) or by hobby (Models with the supplies)
  const home = data?.shops?.[0]?.shop
  const shops = [...new Set(shown.map((i) => i.shop))].filter((s) => s !== home)
  const byHobby = [...new Set([...(showSupplies && data?.supplies ? ['models'] : []), ...shown.map((i) => i.hobby ?? 'other')])]
    .sort((a, b) => (ORDER[a] ?? 99) - (ORDER[b] ?? 99))

  return (
    <div className="wishlist-page">
      <div className="inv-bar">
        {hobbies.length > 1 ? (
          <div className="chip-row scroll inv-hobbies" role="group" aria-label="Hobby">
            <button type="button" className="chip-filter" aria-pressed={!hobby} onClick={() => setHobby('')}>All hobbies</button>
            {hobbies.map((h) => (
              <button key={h} type="button" className="chip-filter" aria-pressed={hobby === h} onClick={() => setHobby(h)}>
                {hobbyName(h)} <span className="chip-count">{items.filter((i) => i.hobby === h).length + (h === 'models' ? data?.supplies ?? 0 : 0)}</span>
              </button>
            ))}
          </div>
        ) : <span className="grow" />}
        <details className="inv-menu" ref={menu}>
          <summary className="secondary">Options ▾</summary>
          <div className="inv-menu-body">
            <label>Group
              <select value={group} onChange={(e) => setGroup(e.target.value)} aria-label="Group the wishlist">
                <option value="shop">By shop</option>
                <option value="hobby">By hobby</option>
              </select>
            </label>
            <button type="button" className="plain" onClick={() => { setView(view === 'history' ? 'list' : 'history'); closeMenu() }}>
              {view === 'history' ? 'Back to the wishlist' : 'What I bought (history)'}</button>
            <button type="button" className="plain" onClick={() => { openPanel('wantedlink'); closeMenu() }}>Add from a shop link…</button>
            <Link to="/wishlist/gift">🎁 Gift list to share</Link>
          </div>
        </details>
      </div>

      {view === 'history' ? <WishHistory /> : group === 'hobby' ? (
        byHobby.map((h) => (
          <section key={h} className="shop-section">
            <h2 className="shop-heading">{hobbyName(h)}</h2>
            {h === 'models' && showSupplies && <WishlistView {...props} extras={extras} />}
            {grid(shown.filter((i) => (i.hobby ?? 'other') === h), h === 'models' ? 'Kits' : null)}
          </section>
        ))
      ) : (
        <>
          {(showSupplies || shown.some((i) => i.shop === home)) && (
            <section className="shop-section first">
              <ShopHeading shop={home ?? props.settings?.default_shop ?? 'Your shop'} note={showSupplies ? 'Supplies and kits' : null} />
              {showSupplies && <WishlistView {...props} extras={extras} />}
              {grid(shown.filter((i) => i.shop === home), 'Kits')}
            </section>
          )}
          {shops.map((s) => {
            const list = shown.filter((i) => i.shop === s)
            const total = list.reduce((t, i) => t + Number(i.price ?? 0), 0)
            return (
              <section key={s} className="shop-section">
                <ShopHeading shop={s} total={total} note={`${list.length} item${list.length === 1 ? '' : 's'}`} />
                {grid(list)}
              </section>
            )
          })}
        </>
      )}
    </div>
  )
}

function ShopHeading({ shop, note, total }) {
  return (
    <h2 className="shop-heading">
      <BoxIcon size={20} aria-hidden="true" /> {shop}
      {(note || total > 0) && <span className="muted small">{note}{total > 0 && ` · about ${money(total)}`}</span>}
    </h2>
  )
}

function WantedGrid({ items, title, extras, gotten, openThing, openPanel, onTick, onUntick }) {
  return (
    <>
      {title && <h3 className="section-title wish-sub">{title}</h3>}
      <ul className="wanted-grid">
        {items.map((i) => {
          const Icon = KIND_ICON[i.kind] ?? BoxIcon
          const photo = i.photo_url ?? (i.product_info_id ? imageUrl(i) : null)
          const done = gotten[`${i.kind}:${i.id}`]
          return (
            <li key={`${i.kind}-${i.id}`} className={done ? 'wanted-card card got' : 'wanted-card card'}>
              {/* the photo isn't a button: the tick sits on it (two buttons on top of each other trip up screen readers) */}
              <span className="wanted-photo">
                {photo ? <img src={photo} alt="" loading="lazy" /> : <span className="photo-missing"><Icon size={32} /></span>}
                <button type="button" className="wanted-tick" aria-pressed={Boolean(done)} aria-label={done ? `Bought ${i.name} - undo` : `Bought ${i.name}`}
                  onClick={() => (done ? onUntick(i) : onTick(i))}>{done ? '✓' : ''}</button>
              </span>
              <button type="button" className="wanted-open" onClick={() => openThing(i.kind, i.id)}>
                <span className="wanted-body">
                  <span className="pill">{i.label}</span>
                  <span className="item-title">{i.name}</span>
                  {i.detail && <span className="item-meta">{i.detail}</span>}
                  {i.price != null && <span className="item-meta">{money(i.price)}</span>}
                </span>
              </button>
              <span className="wanted-extra"><ExtraTags x={extraOf(extras, i.kind, i.id)} /></span>
              <span className="wanted-links">
                <button type="button" className="plain small" onClick={() => openPanel('wanted', { kind: i.kind, wantedRef: i.id, name: i.name })}>Details</button>
                {i.url && <a className="small" href={i.url} target="_blank" rel="noreferrer">Shop ↗</a>}
              </span>
            </li>
          )
        })}
      </ul>
    </>
  )
}
