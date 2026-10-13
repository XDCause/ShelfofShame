import { Link } from 'react-router'
import { api, imageUrl } from '../api.js'
import { BoxIcon, CartIcon } from '../components/icons.jsx'
import { FillBar, fillOf } from '../modules/models/fill.jsx'
import { useApp } from './app-context.js'
import Stat, { StatSkeleton } from './Stat.jsx'
import { useShared } from './useShared.js'

// Hobby supplies on Home (shared by every hobby), in two parts so Home can lay them out:
//   SuppliesTiles   Supplies (and how many need attention), To buy
//   RunningLow      the emptiest supplies, with fill bars
// Both read the same data, fetched once per change.
const load = () => Promise.all([api.listSupplies(), api.listWishlist()])
  .then(([supplies, wishlist]) => ({ supplies, wishlist }))

function useSupplies() {
  const { refreshKey } = useApp()
  return useShared(`supplies-home-${refreshKey}`, load)
}

export function SuppliesTiles() {
  const { data } = useSupplies()
  if (!data) return <><StatSkeleton /><StatSkeleton /></>
  const attention = data.supplies.filter((s) => s.stock_status !== 'OK').length
  const toBuy = data.wishlist.filter((w) => !w.got_it).length
  return (
    <>
      <Stat to="/supplies" Icon={BoxIcon} tone={attention ? 'low' : 'tint'} value={data.supplies.length}
        label="Supplies" sub={attention ? `${attention} need attention` : 'all good'} />
      <Stat to="/wishlist" Icon={CartIcon} value={toBuy} label="To buy" sub="on the wishlist" />
    </>
  )
}

export function RunningLow() {
  const { openItem } = useApp()
  const { data } = useSupplies()
  if (!data) return null
  const low = data.supplies.filter((s) => fillOf(s) < 100).sort((a, b) => fillOf(a) - fillOf(b)).slice(0, 4)
  return (
    <section className="card home-card" aria-labelledby="home-low">
      <h2 id="home-low" className="home-card-title">Running low
        <Link to="/supplies" className="small">Supplies →</Link></h2>
      {low.length === 0 ? <p className="muted small">Nothing's running low: everything is sealed or well stocked.</p> : (
        <ul className="list plain-list">
          {low.map((s) => (
            <li key={s.supply_id}>
              <button type="button" className="row-button" onClick={() => openItem(s.supply_id)}>
                {s.has_image ? <img className="thumb" src={imageUrl(s)} alt="" loading="lazy" />
                  : <span className="thumb thumb-empty" aria-hidden="true" />}
                <span className="grow">
                  <span className="low-row"><span className="item-title">{s.name}</span>
                    <span className="muted small">{s.qty_on_hand <= 0 ? 'Out' : s.condition}</span></span>
                  <FillBar percent={fillOf(s)} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
