import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { DiveIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { clockText, diveName, field, hoursText, metres, minutesText, noFlyLeft, plural } from './scubaFormat.js'
import { Alerts, DiveRow, Numbers, useNow, useScubaSites, useScubaSummary } from './scubaParts.jsx'

// Scuba's dashboard (the dive count, the no-fly time, what is coming due, the last dives) and the logbook.

export function Dashboard() {
  const { data: s, error } = useScubaSummary()
  const { openPanel } = useApp()
  const now = useNow()
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const fly = noFlyLeft(s.no_fly_until, now)
  const last = s.last_dive
  const fresh = s.dives === 0
  const deepest = field(s.deepest, 'max_depth')
  const longest = field(s.longest, 'minutes')
  return (
    <section className="page scb">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="secondary" onClick={() => openPanel('scubaimport', {})}>Import from a dive computer</button>
        <button type="button" className="primary" onClick={() => openPanel('scubanewdive', {})}>Log a dive</button>
      </div>
      {fresh && (
        <section className="card empty-start">
          <h2 className="home-card-title">Start your logbook</h2>
          <p className="small">Log a dive by hand, or import a file from your dive computer (UDDF or Subsurface - every brand's app can export one).
            Your depth profile, air use, life list and stats follow. Already have dives in a paper log? Type how many in
            <Link to="/scuba/stats#scuba-settings"> your settings</Link> and the numbering carries on from there.</p>
          <div className="button-row">
            <button type="button" className="primary" onClick={() => openPanel('scubanewdive', {})}>Log your first dive</button>
            <button type="button" className="secondary" onClick={() => openPanel('scubaimport', {})}>Import a file</button>
            <Link className="button plain" to="/scuba/certs">Add a certification</Link>
          </div>
        </section>
      )}
      {!fresh && (
        <section className="card scb-hero">
          <div className="scb-hero-main">
            <span className="scb-hero-label">Dives in your logbook</span>
            <strong className="scb-hero-number">{s.dives.toLocaleString()}</strong>
            <span className="muted small">{hoursText(s.minutes)} underwater
              {s.dives_logged != null && s.dives_logged !== s.dives && ` · ${s.dives_logged} logged here, ${s.dives - s.dives_logged} before`}</span>
          </div>
          <dl className="scb-hero-year">
            <div><dt>This year</dt><dd>{field(s.this_year, 'dives') ?? 0}</dd></div>
            <div><dt>Deepest</dt><dd>{metres(deepest)}</dd></div>
            <div><dt>Longest</dt><dd>{minutesText(longest)}</dd></div>
          </dl>
        </section>
      )}
      {!fresh && (
        <section className={`card scb-nofly ${fly.clear ? 'clear' : 'wait'}`} aria-label="No-fly time">
          <span className={`stat-icon ${fly.clear ? 'ok' : 'low'}`} aria-hidden="true"><DiveIcon size={22} /></span>
          <span className="grow">
            <span className="item-title">{fly.clear ? 'No no-fly time running' : `No-fly time: ${fly.text} to go`}</span>
            <span className="item-meta">{fly.clear ? 'Your last dive was long enough ago. Your computer\'s own no-fly time comes first.'
              : `Until ${clockText(s.no_fly_until)}: 12 h after a single dive, 18 h after repeat dives (DAN's guideline). Your computer's time comes first.`}</span>
          </span>
        </section>
      )}
      <Alerts alerts={s.alerts} />
      {!fresh && (
        <div className="home-grid">
          <div className="home-stack">
            <section className="card home-card">
              <div className="section-head">
                <h2 className="home-card-title">Last dives</h2>
                <button type="button" className="plain small" onClick={() => openPanel('scubanewdive', {})}>+ New dive</button>
              </div>
              <ul className="list plain-list">{(s.recent ?? []).map((d) => <DiveRow key={d.dive_id} d={d} />)}</ul>
              <Link className="button plain small" to="/scuba/log">The whole logbook →</Link>
            </section>
          </div>
          <div className="home-stack">
            {last && (
              <section className="card home-card">
                <h2 className="home-card-title">Latest</h2>
                <p className="item-sub">{diveName(last)}: {last.site_name ?? 'Unnamed site'} · {shortDate(last.dived_on)}</p>
                <Numbers items={[
                  { label: 'Depth', value: metres(last.max_depth) },
                  { label: 'Time', value: minutesText(last.minutes) },
                  last.water_temp != null && { label: 'Water', value: `${last.water_temp}°C` },
                  last.sac != null && { label: 'Air use', value: `${last.sac} L/min`, sub: 'SAC' },
                ]} />
              </section>
            )}
            <section className="card home-card">
              <h2 className="home-card-title">Before you go</h2>
              <ul className="list plain-list scb-links">
                <li><Link className="row-button" to="/scuba/conditions">Conditions: swell, wind, sea temperature and tides</Link></li>
                <li><Link className="row-button" to="/scuba/plan">Plan a dive: no-deco limits, gas and nitrox maths</Link></li>
              </ul>
            </section>
          </div>
        </div>
      )}
      {!fresh && (
        <div className="home-stats">
          <Stat to="/scuba/sites" Icon={TargetIcon} tone="ok" value={s.sites ?? 0} label="Dive sites" sub="on the map, with how often you dived each" />
          <Stat to="/scuba/species" Icon={TrophyIcon} tone="teal" value={s.species ?? 0} label="Species seen" sub="your life list" />
          <Stat to="/scuba/stats" Icon={DiveIcon} tone="low" value={s.next_no ?? '—'} label="Next dive number" sub="your logbook carries on from here" />
        </div>
      )}
    </section>
  )
}

export function LogView() {
  const { refreshKey, openPanel } = useApp()
  const sites = useScubaSites()
  const [site, setSite] = useState('')
  const [year, setYear] = useState('')
  const [q, setQ] = useState('')
  const [rows, setRows] = useState(null)
  useEffect(() => {
    const wait = setTimeout(() => api.scubaDives({ site_id: site, year, q: q.trim() }).then(setRows).catch(() => setRows([])), q ? 300 : 0)
    return () => clearTimeout(wait)
  }, [site, year, q, refreshKey])
  const thisYear = new Date().getFullYear()
  const filtered = site || year || q.trim()
  const minutes = (rows ?? []).reduce((a, d) => a + (d.minutes ?? 0), 0)
  return (
    <section className="page scb">
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search site, buddy, species, notes..." aria-label="Search dives" className="scb-search" />
        <select value={site} onChange={(e) => setSite(e.target.value)} aria-label="Site">
          <option value="">Every site</option>
          {(sites ?? []).map((x) => <option key={x.site_id} value={x.site_id}>{x.name}</option>)}
        </select>
        <select value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
          <option value="">Every year</option>
          {Array.from({ length: 12 }, (_, i) => <option key={thisYear - i} value={thisYear - i}>{thisYear - i}</option>)}
        </select>
        <span className="grow" />
        <button type="button" className="secondary" onClick={() => openPanel('scubaimport', {})}>Import</button>
        <button type="button" className="primary" onClick={() => openPanel('scubanewdive', {})}>+ New dive</button>
      </div>
      {!rows ? <p className="muted loading">Loading...</p> : rows.length === 0 ? (
        filtered ? <p className="empty card">No dives match that.</p> : (
          <EmptyState Icon={DiveIcon} title="No dives yet" action="Log a dive" onAction={() => openPanel('scubanewdive', {})}>
            Type one in, or import a file from your dive computer: depth, time, air use, what you saw and the profile.</EmptyState>
        )
      ) : (
        <section className="card home-card">
          <p className="muted small scb-log-note">{plural(rows.length, 'dive')}{filtered ? ' match' : ''} · {hoursText(minutes)} underwater</p>
          <ul className="list plain-list">{rows.map((d) => <DiveRow key={d.dive_id} d={d} />)}</ul>
        </section>
      )}
    </section>
  )
}
