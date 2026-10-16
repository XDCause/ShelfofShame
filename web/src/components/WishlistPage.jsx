import { useEffect, useState } from 'react'
import { api, imageUrl, money } from '../api.js'
import { useApp } from '../core/app-context.js'
import { BoxIcon, DiceIcon, PlaneIcon, ShoeIcon } from './icons.jsx'
import WishlistView from './WishlistView.jsx'

// The Wishlist page: everything you want to buy, a section per shop (api/app/wanted.py). Your default
// shop (Hobbyrama) comes first, with the supplies wishlist itself (ticks, "Add to inventory") and the
// kits you want; then Good Games (board games), Blue Sky Athletics (Way of Wade shoes), and so on.
const KIND_ICON = { model: PlaneIcon, game: DiceIcon, gear: ShoeIcon }

export default function WishlistPage(props) {
  const { refreshKey, openThing } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => { api.wanted().then(setData).catch(() => setData(null)) }, [refreshKey])
  const [home, ...others] = data?.shops ?? []
  const count = (s) => s.items.length + (s === home ? data.supplies : 0)

  return (
    <div className="wishlist-page">
      {data && data.shops.length > 1 && (
        <nav className="chip-row scroll shop-jump" aria-label="Shops">
          {data.shops.map((s) => (
            <a key={s.shop} className="chip-filter" href={`#shop-${slug(s.shop)}`}>{s.shop} <span className="chip-count">{count(s)}</span></a>
          ))}
        </nav>
      )}
      <ShopHeading shop={home?.shop ?? props.settings?.default_shop ?? 'Your shop'} note="Supplies and kits" />
      <WishlistView {...props} />
      {home?.items.length > 0 && <WantedGrid items={home.items} openThing={openThing} title="Kits you want" />}
      {others.map((s) => (
        <section key={s.shop} className="shop-section">
          <ShopHeading shop={s.shop} total={s.total} note={`${s.items.length} item${s.items.length === 1 ? '' : 's'}`} />
          <WantedGrid items={s.items} openThing={openThing} />
        </section>
      ))}
    </div>
  )
}

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-')

function ShopHeading({ shop, note, total }) {
  return (
    <h2 className="shop-heading" id={`shop-${slug(shop)}`}>
      <BoxIcon size={20} aria-hidden="true" /> {shop}
      <span className="muted small">{note}{total > 0 && ` · about ${money(total)}`}</span>
    </h2>
  )
}

function WantedGrid({ items, openThing, title }) {
  return (
    <>
      {title && <h3 className="section-title">{title}</h3>}
      <ul className="wanted-grid">
        {items.map((i) => {
          const Icon = KIND_ICON[i.kind] ?? BoxIcon
          const photo = i.photo_url ?? (i.product_info_id ? imageUrl(i) : null)
          return (
            <li key={`${i.kind}-${i.id}`} className="wanted-card card">
              <button type="button" className="wanted-open" onClick={() => openThing(i.kind, i.id)}>
                {photo ? <img src={photo} alt="" loading="lazy" /> : <span className="photo-missing"><Icon size={32} /></span>}
                <span className="wanted-body">
                  <span className="pill">{i.label}</span>
                  <span className="item-title">{i.name}</span>
                  {i.detail && <span className="item-meta">{i.detail}</span>}
                  {i.price != null && <span className="item-meta">{money(i.price)}</span>}
                </span>
              </button>
              {i.url && <a className="small wanted-link" href={i.url} target="_blank" rel="noreferrer">View in the shop ↗</a>}
            </li>
          )
        })}
      </ul>
    </>
  )
}
