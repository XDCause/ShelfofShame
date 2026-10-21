import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { ColumnChart } from '../../components/charts.jsx'
import Fold from '../../components/Fold.jsx'
import { BootIcon, MountainIcon, TimerIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { Stars } from '../reading/readingParts.jsx'
import { GpxImport, hikeMeta, hikeTime, km, metres, pace, useHikingSummary } from './hikingParts.jsx'
import { plural } from './HomeTiles.jsx'

// The Hiking hobby's pages: a dashboard (this year, km per month, personal bests, latest hikes)
// and every hike (search, year, import more).

const monthName = (ym, long = false) => new Date(`${ym}-15T12:00:00`)
  .toLocaleDateString('en-AU', long ? { month: 'long', year: 'numeric' } : { month: 'short' })


export function Dashboard() {
  const { data: s, error } = useHikingSummary()
  const { openPanel } = useApp()
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  if (!s.all_time.hikes) {
    return (
      <section className="page hiking">
        <section className="card empty-start">
          <h2 className="home-card-title">Bring in your hikes</h2>
          <GpxImport />
          <div className="button-row">
            <button type="button" className="plain" onClick={() => openPanel('hike', {})}>Or log a hike by hand</button>
          </div>
        </section>
      </section>
    )
  }
  const y = s.this_year
  const months = s.months.map((m) => ({ label: monthName(m.month), value: Math.round(m.km * 10) / 10,
    tip: `${monthName(m.month, true)} · ${plural(m.hikes, 'hike')}` }))
  const b = s.bests
  return (
    <section className="page hiking">
      <div className="home-stats">
        <Stat to="/hiking/hikes" Icon={BootIcon} tone="ok" value={y.hikes} label={`Hikes in ${s.year}`} sub={`${plural(s.all_time.hikes, 'hike')} in all`} />
        <Stat to="/hiking/hikes" Icon={BootIcon} tone="tint" value={`${y.km.toFixed(1)} km`} label="Distance this year"
          sub={`${s.all_time.km.toFixed(0)} km in all`} />
        <Stat to="/hiking/hikes" Icon={MountainIcon} tone="teal" value={metres(y.ascent_m)} label="Climbed this year"
          sub={`${metres(s.all_time.ascent_m)} in all`} />
        <Stat to="/hiking/hikes" Icon={TimerIcon} tone="purple" value={hikeTime(y.seconds)} label="On the trail this year"
          sub={s.all_time.trails ? plural(s.all_time.trails, 'different trail') : `${(s.all_time.km / s.all_time.hikes).toFixed(1)} km a hike on average`} />
      </div>
      <div className="home-grid">
        <div className="home-stack">
          <section className="card home-card">
            <div className="section-head">
              <h2 className="home-card-title">Latest hikes</h2>
              <button type="button" className="plain small" onClick={() => openPanel('hike', {})}>+ Log a hike</button>
            </div>
            <ul className="list plain-list">{s.recent.map((h) => <HikeRow key={h.hike_id} hike={h} />)}</ul>
            <Link className="button plain small" to="/hiking/hikes">All hikes →</Link>
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Import from AllTrails</h2>
            <GpxImport compact />
          </section>
        </div>
        <div className="home-stack">
          <section className="card home-card">
            <h2 className="home-card-title">Distance per month</h2>
            <ColumnChart title="Distance per month" rows={months} valueLabel="km" />
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Personal bests</h2>
            <ul className="list plain-list hike-bests">
              <Best Icon={BootIcon} label="Longest" hike={b.longest} value={b.longest && km(b.longest.distance_m)} />
              <Best Icon={MountainIcon} label="Most climbing" hike={b.climb} value={b.climb && metres(b.climb.ascent_m)} />
              <Best Icon={TrophyIcon} label="Highest point" hike={b.highest} value={b.highest && metres(b.highest.max_ele_m)} />
              <Best Icon={TimerIcon} label="Fastest pace (3 km+)" hike={b.fastest}
                value={b.fastest && pace(b.fastest.moving_s, b.fastest.distance_m)} />
            </ul>
          </section>
        </div>
      </div>
    </section>
  )
}

function Best({ Icon, label, hike, value }) {
  const { openPanel } = useApp()
  if (!hike) return null
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('hike', { id: hike.hike_id })}>
        <span className="stat-icon ok"><Icon size={18} /></span>
        <span className="grow">
          <span className="item-title">{label}: {value}</span>
          <span className="item-meta">{hike.name} · {shortDate(hike.hiked_on)}</span>
        </span>
      </button>
    </li>
  )
}

function HikeRow({ hike: h }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('hike', { id: h.hike_id })}>
        {h.photo_url ? <img className="hike-thumb" src={h.photo_url} alt="" loading="lazy" />
          : <span className="hike-thumb"><MountainIcon size={20} /></span>}
        <span className="grow">
          <span className="item-title">{h.name}</span>
          <span className="item-meta">{[shortDate(h.hiked_on), hikeMeta(h)].filter(Boolean).join(' · ')}</span>
        </span>
        {h.rating && <Stars value={h.rating} size="small" />}
      </button>
    </li>
  )
}

// Every hike, newest first: search names, trails, places, people and notes; one year at a time.
export function HikesView() {
  const { refreshKey, openPanel } = useApp()
  const [q, setQ] = useState('')
  const [year, setYear] = useState('')
  const [hikes, setHikes] = useState(null)
  const [years, setYears] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    const t = setTimeout(() => api.hikes({ q, year }).then((list) => {
      setHikes(list)
      if (!q && !year) setYears([...new Set(list.map((h) => h.hiked_on.slice(0, 4)))])
    }).catch((e) => setError(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [q, year, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  const total = hikes?.reduce((a, h) => a + (h.distance_m ?? 0), 0) ?? 0
  return (
    <section className="page hiking">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search hikes, trails, places, people..." aria-label="Search your hikes" />
        {years.length > 1 && (
          <select value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
            <option value="">Every year</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        )}
        <button type="button" className="primary" onClick={() => openPanel('hike', {})}>+ Log a hike</button>
      </div>
      {!hikes ? <p className="muted loading">Loading...</p> : hikes.length === 0 ? (
        q || year ? <p className="empty card">No hikes match that.</p> : (
          <EmptyState Icon={BootIcon} title="No hikes yet" action="+ Log a hike" onAction={() => openPanel('hike', {})}>
            Import your recordings from AllTrails below (GPX files), or log a hike by hand.</EmptyState>
        )
      ) : (
        <>
          <p className="muted small">{plural(hikes.length, 'hike')} · {km(total)}</p>
          <ul className="list plain-list card hike-list">{hikes.map((h) => <HikeRow key={h.hike_id} hike={h} />)}</ul>
        </>
      )}
      <Fold title="Import from AllTrails" open={hikes?.length === 0 && !q && !year}><GpxImport /></Fold>
    </section>
  )
}
