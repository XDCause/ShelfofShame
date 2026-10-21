import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, money, shortDate } from '../../api.js'
import { ColumnChart } from '../../components/charts.jsx'
import { CrosshairIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { startShooting } from './ShootingLive.jsx'
import { KIND_TONE, LicenceCard, angle, dist, plural, useShootingSummary, useShootingThings } from './shootingParts.jsx'

// Precision shooting's pages: the dashboard, every session, rifles, ammunition, and the DOPE card.
const monthName = (ym) => new Date(`${ym}-15T12:00:00`).toLocaleDateString('en-AU', { month: 'short' })


export function Dashboard() {
  const { data: s, error } = useShootingSummary()
  const app = useApp()
  const { openPanel } = app
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const y = s.this_year
  const months = s.months.map((m) => ({ label: monthName(m.month), value: m.rounds, tip: `${plural(m.sessions, 'session')}` }))
  const sizes = s.months.filter((m) => m.avg_moa != null).map((m) => ({ label: monthName(m.month), value: m.avg_moa, tip: `${m.avg_moa} MOA average` }))
  const scores = s.matches.filter((m) => m.score != null).map((m) => ({ label: shortDate(m.shot_on), value: m.score,
    tip: `${m.match_name ?? m.range_name ?? 'Match'}${m.finish ? ` · ${m.finish}` : ''}` }))
  const alerts = [
    ...s.clean_due.map((r) => ({ key: `c${r.rifle_id}`, text: `${r.name} is due for a clean (${r.since_clean} rounds)`, open: () => openPanel('rifle', { id: r.rifle_id }) })),
    ...s.low_ammo.map((a) => ({ key: `a${a.ammo_id}`, text: `${a.name}: ${a.rounds_left} rounds left`, open: () => openPanel('ammo', { id: a.ammo_id }) })),
    ...s.pta.map((r) => ({ key: `p${r.rifle_id}`, text: `${r.name}: Permit to Acquire ${r.pta_approved ? 'approved - not bought yet' : `waiting since ${shortDate(r.pta_applied)}`}`,
      open: () => openPanel('rifle', { id: r.rifle_id }) })),
  ]
  return (
    <section className="page shooting">
      {!s.all_time.sessions && (
        <section className="card empty-start">
          <h2 className="home-card-title">Get set up</h2>
          <p className="small">Add your rifle (and its scope), your ammo and your range - then log each session at the range, with its groups.</p>
          <div className="button-row">
            <button type="button" className="primary" onClick={() => openPanel('rifle', {})}>+ Add a rifle</button>
            <button type="button" className="secondary" onClick={() => openPanel('ammo', {})}>+ Add ammo</button>
            <button type="button" className="secondary" onClick={() => openPanel('shootsession', {})}>+ Log a session</button>
          </div>
        </section>
      )}
      <div className="toolbar"><span className="grow" />
        <button type="button" className="primary" onClick={() => startShooting(app).catch((e) => app.showToast(e.message))}>Start shooting</button>
      </div>
      <div className="home-stats">
        <Stat to="/shooting/sessions" Icon={CrosshairIcon} tone="out" value={y.sessions} label={`Sessions in ${s.year}`} sub={`${plural(s.all_time.sessions, 'session')} in all`} />
        <Stat to="/shooting/sessions" Icon={TargetIcon} tone="tint" value={y.rounds.toLocaleString()} label="Rounds this year" sub={`${s.all_time.rounds.toLocaleString()} in all`} />
        <Stat to="/shooting/sessions" Icon={TrophyIcon} tone={s.club_needed != null && y.club_days >= s.club_needed ? 'ok' : 'low'}
          value={s.club_needed != null ? `${y.club_days}/${s.club_needed}` : y.club_days} label="Club shoots this year"
          sub={y.matches ? plural(y.matches, 'match', 'matches') : 'no matches yet'} />
        <Stat to="/shooting/ammo" Icon={TargetIcon} tone="purple" value={money(s.spent)} label="Ammo shot this year" sub="at what you paid a round" />
      </div>
      {alerts.length > 0 && (
        <section className="card home-card">
          <h2 className="home-card-title">Needs doing</h2>
          <ul className="list plain-list">{alerts.map((a) => (
            <li key={a.key}><button type="button" className="row-button" onClick={a.open}><span className="grow">{a.text}</span></button></li>))}</ul>
        </section>
      )}
      <div className="home-grid">
        <div className="home-stack">
          <section className="card home-card">
            <div className="section-head">
              <h2 className="home-card-title">Latest sessions</h2>
              <button type="button" className="plain small" onClick={() => openPanel('shootsession', {})}>+ Log a session</button>
            </div>
            {s.recent.length === 0 ? <p className="muted small">None yet.</p>
              : <ul className="list plain-list">{s.recent.map((x) => <SessionRow key={x.session_id} s={x} />)}</ul>}
            <Link className="button plain small" to="/shooting/sessions">All sessions →</Link>
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Best groups</h2>
            {s.bests.length === 0 ? <p className="muted small">Log groups (3 shots or more) to see your best at each distance.</p> : (
              <ul className="list plain-list">{s.bests.map((g) => (
                <li key={`${g.distance}${g.unit}`}>
                  <button type="button" className="row-button" onClick={() => openPanel('shootsession', { id: g.session_id })}>
                    <span className="stat-icon ok"><TargetIcon size={18} /></span>
                    <span className="grow"><span className="item-title">{dist(g)}: {angle(g.moa, 'MOA')}</span>
                      <span className="item-meta">{g.size_mm} mm · {g.shots ?? '?'} shots · {shortDate(g.shot_on)}</span></span>
                  </button>
                </li>))}</ul>
            )}
          </section>
          <LicenceCard summary={s} />
        </div>
        <div className="home-stack">
          <section className="card home-card">
            <h2 className="home-card-title">Rounds per month</h2>
            <ColumnChart title="Rounds per month" rows={months} valueLabel="rounds" />
          </section>
          {sizes.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Average group (MOA)</h2>
              <ColumnChart title="Average group size per month" rows={sizes} valueLabel="MOA" labelValues />
              <p className="muted small">Groups of 3 shots or more. Smaller is better.</p>
            </section>
          )}
          {s.hit_rates.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Hit rate by distance ({s.year})</h2>
              <ColumnChart title="Hit rate by distance" rows={s.hit_rates.map((r) => ({ label: r.label, value: r.rate, tip: `${r.hits} of ${r.shots} hit` }))}
                valueLabel="% hit" labelValues />
            </section>
          )}
          {scores.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Match scores</h2>
              <ColumnChart title="Match scores" rows={scores} valueLabel="points" labelValues />
            </section>
          )}
          {s.rifles.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Rifles</h2>
              <ul className="list plain-list">{s.rifles.map((r) => <RifleRow key={r.rifle_id} r={r} />)}</ul>
            </section>
          )}
        </div>
      </div>
    </section>
  )
}

function SessionRow({ s }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('shootsession', { id: s.session_id })}>
        {s.photo_url ? <img className="thumb" src={s.photo_url} alt="" loading="lazy" /> : <span className="stat-icon out"><CrosshairIcon size={18} /></span>}
        <span className="grow">
          <span className="item-title">{shortDate(s.shot_on)} · {s.match_name || s.range_name || 'Range session'}</span>
          <span className="item-meta">{[s.rifle_name, s.ammo_name, plural(s.rounds, 'round'), s.best_moa != null && `best ${s.best_moa} MOA`,
            s.score != null && `${s.score}${s.x_count ? `-${s.x_count}X` : ''}`, s.hits != null && `${s.hits}/${s.hit_shots} hits`].filter(Boolean).join(' · ')}</span>
        </span>
        <span className={`pill ${KIND_TONE[s.kind] ?? ''}`}>{s.kind}</span>
      </button>
    </li>
  )
}

function RifleRow({ r }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('rifle', { id: r.rifle_id })}>
        {r.photo_url ? <img className="thumb" src={r.photo_url} alt="" loading="lazy" /> : <span className="stat-icon tint"><CrosshairIcon size={18} /></span>}
        <span className="grow">
          <span className="item-title">{r.name}</span>
          <span className="item-meta">{[r.calibre, `${r.round_count.toLocaleString()} rounds`, r.scope_unit].filter(Boolean).join(' · ')}</span>
        </span>
        {r.clean_due && <span className="pill low">Clean due</span>}
        {r.status !== 'In use' && <span className="pill">{r.status}</span>}
      </button>
    </li>
  )
}

export function SessionsView() {
  const app = useApp()
  const { refreshKey, openPanel } = app
  const things = useShootingThings()
  const [year, setYear] = useState('')
  const [rifle, setRifle] = useState('')
  const [kind, setKind] = useState('')
  const [q, setQ] = useState('')
  const [rows, setRows] = useState(null)
  useEffect(() => {
    const t = setTimeout(() => api.shootingSessions({ year, rifle_id: rifle, kind, q }).then(setRows).catch(() => setRows([])), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [year, rifle, kind, q, refreshKey])
  const thisYear = new Date().getFullYear()
  return (
    <section className="page shooting">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search sessions..." aria-label="Search sessions" />
        <select value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
          <option value="">Every year</option>
          {[0, 1, 2, 3, 4].map((i) => <option key={i} value={thisYear - i}>{thisYear - i}</option>)}
        </select>
        <select value={rifle} onChange={(e) => setRifle(e.target.value)} aria-label="Rifle">
          <option value="">Every rifle</option>
          {things.rifles.map((r) => <option key={r.rifle_id} value={r.rifle_id}>{r.name}</option>)}
        </select>
        <button type="button" className="primary" onClick={() => startShooting(app).catch((e) => app.showToast(e.message))}>Start shooting</button>
        <button type="button" className="secondary" onClick={() => openPanel('shootsession', {})}>+ Log a session</button>
      </div>
      <div className="chip-row" role="group" aria-label="Kind">
        {['', 'Practice', 'Match', 'Zeroing', 'Ammo test'].map((k) => (
          <button key={k} type="button" className="chip-filter" aria-pressed={kind === k} onClick={() => setKind(k)}>{k || 'All'}</button>
        ))}
      </div>
      {!rows ? <p className="muted loading">Loading...</p> : rows.length === 0 ? (
        q || year || rifle || kind ? <p className="empty card">No sessions match that.</p> : (
          <EmptyState Icon={CrosshairIcon} title="No sessions yet" action="+ Log a session" onAction={() => openPanel('shootsession', {})}>
            Each day at the range: rifle, ammo, conditions, and every group you shot.</EmptyState>
        )
      ) : <section className="card"><ul className="list plain-list">{rows.map((x) => <SessionRow key={x.session_id} s={x} />)}</ul></section>}
    </section>
  )
}

export function RiflesView() {
  const { openPanel } = useApp()
  const things = useShootingThings()
  return (
    <section className="page shooting">
      <div className="toolbar"><span className="grow" /><button type="button" className="primary" onClick={() => openPanel('rifle', {})}>+ Add a rifle</button></div>
      {things.rifles.length === 0 ? (
        <EmptyState Icon={CrosshairIcon} title="No rifles yet" action="+ Add a rifle" onAction={() => openPanel('rifle', {})}>
          Each rifle and its scope (MOA or MIL turrets), its zero, and a round count with cleaning reminders. No serial numbers are kept.
        </EmptyState>
      ) : <section className="card"><ul className="list plain-list">{things.rifles.map((r) => <RifleRow key={r.rifle_id} r={r} />)}</ul></section>}
    </section>
  )
}

export function AmmoView() {
  const { openPanel } = useApp()
  const things = useShootingThings()
  return (
    <section className="page shooting">
      <div className="toolbar"><span className="grow" /><button type="button" className="primary" onClick={() => openPanel('ammo', {})}>+ Add ammo</button></div>
      {things.ammo.length === 0 ? (
        <EmptyState Icon={TargetIcon} title="No ammo yet" action="+ Add ammo" onAction={() => openPanel('ammo', {})}>
          Factory ammunition: the bullet, BC, box velocity and lot - and what's left, as sessions use it up.
        </EmptyState>
      ) : (
        <section className="card">
          <ul className="list plain-list">{things.ammo.map((a) => (
            <li key={a.ammo_id}>
              <button type="button" className="row-button" onClick={() => openPanel('ammo', { id: a.ammo_id })}>
                {a.photo_url ? <img className="thumb" src={a.photo_url} alt="" loading="lazy" /> : <span className="stat-icon purple"><TargetIcon size={18} /></span>}
                <span className="grow">
                  <span className="item-title">{a.name}</span>
                  <span className="item-meta">{[a.calibre, a.bullet_gr && `${a.bullet_gr} gr`, `${a.rounds_left.toLocaleString()} left`,
                    a.per_round != null && `${money(a.per_round)} a round`, a.lot && `lot ${a.lot}`].filter(Boolean).join(' · ')}</span>
                </span>
                {a.low && <span className="pill low">Low</span>}
                {a.status !== 'Have' && <span className="pill">{a.status}</span>}
              </button>
            </li>))}</ul>
        </section>
      )}
    </section>
  )
}

// The DOPE card: a rifle (and ammo) - elevation and wind per distance, confirmed by your groups or entered by you,
// with estimates between confirmed distances. Prints on one page.
export function DopeView() {
  const { refreshKey } = useApp()
  const things = useShootingThings()
  const [params, setParams] = useSearchParams()
  const rifleId = params.get('rifle') || String(things.rifles.find((r) => r.status === 'In use')?.rifle_id ?? '')
  const ammoId = params.get('ammo') || ''
  const [card, setCard] = useState(null)
  const [row, setRow] = useState({ distance: '', elevation: '', wind10: '' })
  const [error, setError] = useState('')
  useEffect(() => {
    if (rifleId) api.dope(rifleId, ammoId || null).then(setCard).catch((e) => setError(e.message))
  }, [rifleId, ammoId, refreshKey])
  const pick = (k) => (e) => setParams({ rifle: rifleId, ammo: ammoId, [k]: e.target.value })
  const add = async (e) => {
    e.preventDefault()
    setError('')
    try {
      setCard(await api.addDope({ rifle_id: Number(rifleId), ammo_id: ammoId ? Number(ammoId) : null, distance: Number(row.distance),
        elevation: Number(row.elevation), wind10: row.wind10 === '' ? null : Number(row.wind10) }))
      setRow({ distance: '', elevation: '', wind10: '' })
    } catch (err) {
      setError(err.message)
    }
  }
  if (!things.rifles.length) return <section className="page shooting"><p className="empty card">Add a rifle first.</p></section>
  const unit = card?.unit ?? 'MOA'
  const click = card?.rifle.click
  return (
    <section className="page shooting">
      <div className="toolbar shoot-noprint">
        <select value={rifleId} onChange={pick('rifle')} aria-label="Rifle">
          {things.rifles.map((r) => <option key={r.rifle_id} value={r.rifle_id}>{r.name}</option>)}
        </select>
        <select value={ammoId} onChange={pick('ammo')} aria-label="Ammo">
          <option value="">Any ammo</option>
          {things.ammo.map((a) => <option key={a.ammo_id} value={a.ammo_id}>{a.name}</option>)}
        </select>
        <button type="button" className="secondary" onClick={() => window.print()}>Print</button>
      </div>
      <section className="card shoot-dope">
        <h2 className="home-card-title">DOPE · {card?.rifle.name}{ammoId && ` · ${things.ammo.find((a) => String(a.ammo_id) === ammoId)?.name ?? ''}`}</h2>
        <p className="muted small">Elevation from your zero{card?.rifle.zero_m ? ` (${card.rifle.zero_m} m)` : ''}, in {unit}{click ? `, ${click} a click` : ''}.
          Wind is for a 10 km/h full-value wind.</p>
        {!card ? <p className="muted">Loading...</p> : card.rows.length === 0 ? (
          <p className="small">Nothing yet. Tick "This confirms my elevation" on a group, or add what your ballistic app says below.</p>
        ) : (
          <table className="shoot-table">
            <thead><tr><th>Distance</th><th>Elevation</th><th>Clicks</th><th>Wind /10 km/h</th><th>From</th></tr></thead>
            <tbody>{card.rows.map((r) => (
              <tr key={r.m} className={r.source === 'estimate' ? 'shoot-estimate' : ''}>
                <td>{r.unit === 'yd' ? `${r.distance} yd` : `${r.m} m`}</td>
                <td>{r.elevation != null ? `${r.elevation} ${unit}` : '—'}</td>
                <td>{r.elevation != null && click ? Math.round(r.elevation / click) : '—'}</td>
                <td>{r.wind10 != null ? `${r.wind10} ${unit}` : '—'}</td>
                <td>{r.source === 'confirmed' ? `Confirmed ${shortDate(r.on)}` : r.source === 'entered' ? (
                  <>Entered <button type="button" className="plain small destructive shoot-noprint" onClick={async () => {
                    await api.deleteDope(r.dope_id); setCard(await api.dope(rifleId, ammoId || null)) }}>Remove</button></>) : 'Estimate'}</td>
              </tr>))}</tbody>
          </table>
        )}
      </section>
      <form className="card shoot-noprint shoot-dope-add" onSubmit={add} aria-label="Add a DOPE row">
        <h2 className="home-card-title">Add a distance</h2>
        <div className="shoot-form-grid">
          <label className="field">Distance (m)<input type="number" min="1" required value={row.distance} onChange={(e) => setRow({ ...row, distance: e.target.value })} /></label>
          <label className="field">Elevation ({unit})<input type="number" step="0.01" required value={row.elevation} onChange={(e) => setRow({ ...row, elevation: e.target.value })} /></label>
          <label className="field">Wind per 10 km/h ({unit})<input type="number" step="0.01" value={row.wind10} onChange={(e) => setRow({ ...row, wind10: e.target.value })} /></label>
        </div>
        {error && <p className="alert error small">{error}</p>}
        <button type="submit" className="primary small">Add</button>
      </form>
    </section>
  )
}
