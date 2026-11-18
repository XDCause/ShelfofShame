import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { FishIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { hoursText, plural, tripName, yearChoices } from './fishFormat.js'
import { Alerts, TripRow, useFishingSpots, useFishingSummary } from './fishingParts.jsx'

// Fishing's dashboard (the trip on the water, the numbers, what is coming due, personal bests, recent trips) and the
// list of every trip with its filters.

export function Dashboard() {
  const { data: s, error } = useFishingSummary()
  const { openPanel } = useApp()
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const fresh = s.trips === 0 && !s.open_trip
  const open = s.open_trip
  const year = s.this_year
  return (
    <section className="page fsh">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="secondary" onClick={() => openPanel('fishingnewtrip', {})}>Log a past trip</button>
        <Link className="button primary" to="/fishing/live">Go fishing</Link>
      </div>
      {open && (
        <section className="card fsh-open" aria-label="A trip on the water">
          <span className="stat-icon low" aria-hidden="true"><FishIcon size={22} /></span>
          <span className="grow">
            <span className="item-title">You are on the water: {tripName(open)}</span>
            <span className="item-meta">{plural(open.catches ?? 0, 'fish', 'fish')} so far · started {shortDate(open.started_at)}</span>
          </span>
          <Link className="button primary" to="/fishing/live">Back to the water</Link>
        </section>
      )}
      {fresh && (
        <section className="card empty-start">
          <h2 className="home-card-title">Start your fishing log</h2>
          <p className="small">Tap Go fishing when you reach the water: log each fish in three taps (species, length, kept or released) with the
            time and your position, even with no signal. Or log a past trip by hand. Your spots, the best lures and what works for you follow.
            Type the size and bag rules for the fish you keep on the <Link to="/fishing/species">Species</Link> page: the app ships none.</p>
          <div className="button-row">
            <Link className="button primary" to="/fishing/live">Go fishing</Link>
            <button type="button" className="secondary" onClick={() => openPanel('fishingnewtrip', {})}>Log a past trip</button>
            <Link className="button plain" to="/fishing/spots">Add a spot</Link>
          </div>
        </section>
      )}
      {!fresh && (
        <section className="card fsh-hero">
          <div className="fsh-hero-main">
            <span className="fsh-hero-label">Fish in your log</span>
            <strong className="fsh-hero-number">{(s.catches ?? 0).toLocaleString()}</strong>
            <span className="muted small">{plural(s.trips, 'trip')} · {hoursText(s.hours)} fishing · {plural(s.species, 'species', 'species')}</span>
          </div>
          <dl className="fsh-hero-year">
            <div><dt>Trips this year</dt><dd>{year?.trips ?? 0}</dd></div>
            <div><dt>Fish this year</dt><dd>{year?.catches ?? 0}</dd></div>
          </dl>
        </section>
      )}
      <Alerts alerts={s.alerts} />
      {!fresh && (
        <div className="home-grid">
          <div className="home-stack">
            <section className="card home-card">
              <div className="section-head">
                <h2 className="home-card-title">Recent trips</h2>
                <button type="button" className="plain small" onClick={() => openPanel('fishingnewtrip', {})}>+ Past trip</button>
              </div>
              {(s.recent ?? []).length === 0 ? <p className="muted small">No trips yet.</p>
                : <ul className="list plain-list">{s.recent.map((t) => <TripRow key={t.trip_id} t={t} />)}</ul>}
              <Link className="button plain small" to="/fishing/trips">Every trip →</Link>
            </section>
          </div>
          <div className="home-stack">
            {s.personal_bests?.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Personal bests</h2>
                <ul className="list plain-list">
                  {s.personal_bests.map((p) => (
                    <li key={p.catch_id}>
                      <button type="button" className="row-button" disabled={p.trip_id == null} onClick={() => openPanel('fishingcatch', { id: p.catch_id, tripId: p.trip_id })}>
                        <span className="stat-icon low" aria-hidden="true"><TrophyIcon size={18} /></span>
                        <span className="grow">
                          <span className="item-title">{p.species}</span>
                          <span className="item-meta"><span>{shortDate(p.caught_at)}</span>{p.weight_kg != null && <span>{p.weight_kg} kg</span>}</span>
                        </span>
                        <strong className="fsh-record-value">{p.length_cm} cm</strong>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section className="card home-card">
              <h2 className="home-card-title">Before you go</h2>
              <ul className="list plain-list fsh-links">
                <li><Link className="row-button" to="/fishing/forecast">Forecast: solunar times, tides, wind and pressure for a spot</Link></li>
                <li><Link className="row-button" to="/fishing/stats">What works for you: month, tide, moon, hour and lure</Link></li>
              </ul>
            </section>
          </div>
        </div>
      )}
      {!fresh && (
        <div className="home-stats">
          <Stat to="/fishing/species" Icon={TrophyIcon} tone="teal" value={s.species ?? 0} label="Species caught" sub="and the rules you typed for them" />
          <Stat to="/fishing/spots" Icon={TargetIcon} tone="ok" value="Spots" label="Where you fish" sub="boat ramps and fishing spots too" />
        </div>
      )}
    </section>
  )
}

export function TripsView() {
  const { refreshKey, openPanel } = useApp()
  const spots = useFishingSpots()
  const [spot, setSpot] = useState('')
  const [year, setYear] = useState('')
  const [q, setQ] = useState('')
  const [rows, setRows] = useState(null)
  useEffect(() => {
    const wait = setTimeout(() => api.fishingTrips({ spot_id: spot, year, q: q.trim() }).then(setRows).catch(() => setRows([])), q ? 300 : 0)
    return () => clearTimeout(wait)
  }, [spot, year, q, refreshKey])
  const filtered = spot || year || q.trim()
  const fish = (rows ?? []).reduce((a, t) => a + (t.catches ?? 0), 0)
  const hours = (rows ?? []).reduce((a, t) => a + (t.hours ?? 0), 0)
  return (
    <section className="page fsh">
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search spot, target, species, notes..." aria-label="Search trips" className="fsh-search" />
        <select value={spot} onChange={(e) => setSpot(e.target.value)} aria-label="Spot">
          <option value="">Every spot</option>
          {(spots ?? []).map((x) => <option key={x.spot_id} value={x.spot_id}>{x.name}</option>)}
        </select>
        <select value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
          <option value="">Every year</option>
          {yearChoices(12).map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <span className="grow" />
        <Link className="button secondary" to="/fishing/live">Go fishing</Link>
        <button type="button" className="primary" onClick={() => openPanel('fishingnewtrip', {})}>+ Past trip</button>
      </div>
      {!rows ? <p className="muted loading">Loading...</p> : rows.length === 0 ? (
        filtered ? <p className="empty card">No trips match that.</p> : (
          <EmptyState Icon={FishIcon} title="No trips yet" action="Log a past trip" onAction={() => openPanel('fishingnewtrip', {})}>
            Tap Go fishing on the water, or type in a trip you have already had: where, how, what you caught. A blank trip counts too.</EmptyState>
        )
      ) : (
        <section className="card home-card">
          <p className="muted small fsh-log-note">{plural(rows.length, 'trip')}{filtered ? ' match' : ''} · {plural(fish, 'fish', 'fish')} · {hoursText(hours)}</p>
          <ul className="list plain-list">{rows.map((t) => <TripRow key={t.trip_id} t={t} />)}</ul>
        </section>
      )}
    </section>
  )
}
