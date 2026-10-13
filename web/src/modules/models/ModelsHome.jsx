import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, duration, imageUrl, shortDate } from '../../api.js'
import { ChevronIcon, PlaneIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'

// Shelf of Shame on the Home page: the numbers worth a glance (each one opens its page), the
// kits being built, and the latest stock changes.
export default function ModelsHome() {
  const { refreshKey, openModel, lookups } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.listSupplies(), api.listWishlist(), api.listModels(), api.stashSummary(), api.recentHistory(5)])
      .then(([supplies, wishlist, models, summary, history]) => setData({ supplies, wishlist, models, summary, history }))
      .catch((e) => setError(e.message))
  }, [refreshKey])

  if (error) return <p className="alert error">Shelf of Shame: {error}</p>
  if (!data) return <section className="card home-card" aria-busy="true"><p className="muted">Loading...</p></section>

  const attention = data.supplies.filter((s) => s.stock_status !== 'OK').length
  const toBuy = data.wishlist.filter((w) => !w.got_it).length
  const building = data.models.filter((m) => m.status === 'In progress')
  const steps = (m) => lookups?.stages?.[m.hobby] ?? []

  return (
    <section className="card home-card" aria-labelledby="home-models">
      <h2 id="home-models" className="home-card-title"><PlaneIcon size={20} /> Shelf of Shame
        <span className="muted small">Model kits</span></h2>

      <div className="home-stats">
        <Stat to="/models/inventory" label="Needs attention" value={attention} tone={attention ? 'low' : ''}
          sub={`of ${data.supplies.length} supplies`} />
        <Stat to="/models/wishlist" label="To buy" value={toBuy} sub="on the wishlist" />
        <Stat to="/models/kits" label="Shelf of shame" value={data.summary.shelf_of_shame.kits}
          sub="kits not finished" />
        <Stat to="/models/kits" label="Time building" value={duration(data.summary.total_minutes) || '0 min'} sub="all time" />
      </div>

      {building.length > 0 && (
        <>
          <h3 className="section-title">Building now</h3>
          <ul className="list">
            {building.map((m) => (
              <li key={m.model_id}>
                <button type="button" className="row-button" onClick={() => openModel(m.model_id)}>
                  {m.has_image ? <img className="thumb" src={imageUrl(m)} alt="" loading="lazy" />
                    : <span className="thumb thumb-empty" aria-hidden="true" />}
                  <span className="grow">
                    <span className="item-title">{m.name}</span>
                    <span className="item-meta">
                      {m.stage ? `${m.stage}, step ${steps(m).indexOf(m.stage) + 1} of ${steps(m).length}` : 'Not started a step yet'}
                      {m.running_since && <span className="badge out">● Timing</span>}
                    </span>
                  </span>
                  <ChevronIcon size={16} className="chevron" />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {data.history.length > 0 && (
        <>
          <h3 className="section-title">Latest stock changes</h3>
          <ul className="list compact">
            {data.history.map((h) => (
              <li key={h.movement_id}>
                <span className={h.change < 0 ? 'change minus' : 'change plus'}>{h.change > 0 ? `+${h.change}` : h.change}</span>
                <span className="grow">{h.item_name}<span className="muted small"> · {h.reason}</span></span>
                <span className="muted small">{shortDate(h.created_at)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function Stat({ to, label, value, sub, tone = '' }) {
  return (
    <Link to={to} className={`home-stat ${tone}`}>
      <span className="home-stat-label">{label}</span>
      <strong>{value}</strong>
      <span className="muted small">{sub}</span>
    </Link>
  )
}
