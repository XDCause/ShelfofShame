import { Link } from 'react-router'
import { api, duration, imageUrl } from '../../api.js'
import { BoxIcon, CartIcon, ChevronIcon, PlaneIcon, TimerIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'
import { FillBar, fillOf } from './fill.jsx'

// Shelf of Shame on the Home page, in two parts so Home can lay them out:
//   ModelsStats   four tiles: needs attention, to buy, unfinished kits, time (each opens its page)
//   ModelsCards   "Building now" (kits in progress) and "Running low" (fill bars)
// Both read the same data, fetched once per change.
const load = () => Promise.all([api.listSupplies(), api.listWishlist(), api.listModels(), api.stashSummary()])
  .then(([supplies, wishlist, models, summary]) => ({ supplies, wishlist, models, summary }))

function useShelf() {
  const { refreshKey } = useApp()
  return useShared(`models-home-${refreshKey}`, load)
}

export function ModelsStats() {
  const { data, error } = useShelf()
  if (error) return <p className="alert error">Shelf of Shame: {error}</p>
  if (!data) return <div className="home-stats" aria-busy="true" />
  const attention = data.supplies.filter((s) => s.stock_status !== 'OK').length
  const toBuy = data.wishlist.filter((w) => !w.got_it).length
  return (
    <div className="home-stats">
      <Stat to="/models/inventory" Icon={BoxIcon} tone={attention ? 'low' : 'tint'} value={data.supplies.length}
        label="Supplies" sub={attention ? `${attention} need attention` : 'all good'} />
      <Stat to="/models/wishlist" Icon={CartIcon} tone="tint" value={toBuy} label="To buy" sub="on the wishlist" />
      <Stat to="/models/kits" Icon={PlaneIcon} tone="purple" value={data.summary.shelf_of_shame.kits}
        label="Shelf of shame" sub="kits not finished" />
      <Stat to="/models/kits" Icon={TimerIcon} tone="ok" value={duration(data.summary.total_minutes)}
        label="Time building" sub="all time" />
    </div>
  )
}

function Stat({ to, Icon, tone, value, label, sub }) {
  return (
    <Link to={to} className="home-stat">
      <span className={`stat-icon ${tone}`}><Icon size={22} /></span>
      <span className="stat-text">
        <strong>{value}</strong>
        <span className="home-stat-label">{label}</span>
        <span className="muted small">{sub}</span>
      </span>
    </Link>
  )
}

export function ModelsCards() {
  const { openModel, openItem, lookups } = useApp()
  const { data } = useShelf()
  if (!data) return null
  const building = data.models.filter((m) => m.status === 'In progress')
  const steps = (m) => lookups?.stages?.[m.hobby] ?? []
  const low = data.supplies.filter((s) => fillOf(s) < 100).sort((a, b) => fillOf(a) - fillOf(b)).slice(0, 4)

  return (
    <div className="home-grid">
      <section className="card home-card" aria-labelledby="home-building">
        <h2 id="home-building" className="home-card-title">Building now
          <Link to="/models/kits" className="small">All kits →</Link></h2>
        {building.length === 0 ? <p className="muted small">Nothing on the bench. Start a kit from the stash?</p> : (
          <ul className="list plain-list">
            {building.map((m) => (
              <li key={m.model_id}>
                <button type="button" className="row-button" onClick={() => openModel(m.model_id)}>
                  {m.has_image ? <img className="thumb" src={imageUrl(m)} alt="" loading="lazy" />
                    : <span className="thumb thumb-empty" aria-hidden="true" />}
                  <span className="grow">
                    <span className="item-title">{m.name}</span>
                    <span className="item-meta">
                      {m.stage ? `${m.stage} · step ${steps(m).indexOf(m.stage) + 1} of ${steps(m).length}` : 'No build step ticked yet'}
                      {m.running_since && <span className="badge out">● Timing</span>}
                    </span>
                    {steps(m).length > 0 && (
                      <span className="step-bar" aria-hidden="true">
                        {steps(m).map((s, i) => <span key={s} className={i <= steps(m).indexOf(m.stage) ? 'on' : ''} />)}
                      </span>
                    )}
                  </span>
                  <ChevronIcon size={16} className="chevron" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card home-card" aria-labelledby="home-low">
        <h2 id="home-low" className="home-card-title">Running low
          <Link to="/models/inventory" className="small">Inventory →</Link></h2>
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
    </div>
  )
}
