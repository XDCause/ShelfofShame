import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, money, shortDate, vinylExportUrl } from '../../api.js'
import { BarList, ColumnChart, LineChart } from '../../components/charts.jsx'
import { VinylIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { RecordCover } from './vinylParts.jsx'
import { changeText, lastCleaned, loanTime, stylusText } from './vinylMoreHelpers.js'

// Vinyl care, value history, the listening year and the insurance print view
// (api/app/vinyl_care.py, vinyl_more.py).

const plural = (n, one, many = `${one}s`) => `${n.toLocaleString()} ${n === 1 ? one : many}`
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// On a record: who has it, and when it was last cleaned.
export function CareSection({ record: r, onUpdate, onRecord }) {
  const [who, setWho] = useState('')
  const [since, setSince] = useState('')
  const [error, setError] = useState('')
  const run = async (fn) => {
    setError('')
    try { await fn() } catch (e) { setError(e.message) }
  }
  const cleaned = lastCleaned(r.care)
  return (
    <section className="panel-section vnm-care">
      <h3 className="section-title">Loans and care</h3>
      {r.loaned_to ? (
        <p className="vnm-loaned">
          <strong>Loaned to {r.loaned_to}</strong> <span className="muted small">since {shortDate(r.loaned_on)}</span>{' '}
          <button type="button" className="secondary small" onClick={() => run(() => onUpdate({ loaned_to: null }))}>Got it back</button>
        </p>
      ) : (
        <form className="button-row" onSubmit={(e) => { e.preventDefault(); run(async () => { await onUpdate({ loaned_to: who, loaned_on: since || null }); setWho(''); setSince('') }) }}>
          <label className="small">Loan it to <input value={who} onChange={(e) => setWho(e.target.value)} placeholder="a name" required maxLength={120} /></label>
          <label className="small">Since <input type="date" value={since} onChange={(e) => setSince(e.target.value)} /></label>
          <button type="submit" className="secondary small">Loan it</button>
        </form>
      )}
      <p className="small">{cleaned ? `Last cleaned ${shortDate(cleaned)}` : 'Not cleaned yet'}{' '}
        <button type="button" className="secondary small" onClick={() => run(async () => onRecord(await api.cleanVinylRecord(r.record_id)))}>Cleaned it today</button></p>
      {r.care?.length > 0 && (
        <ul className="vnm-care-list">
          {r.care.map((c) => (
            <li key={c.care_id}>
              <span className="grow small">Cleaned {shortDate(c.done_on)}{c.note && ` · ${c.note}`}</span>
              <button type="button" className="icon-btn" aria-label={`Remove the cleaning on ${shortDate(c.done_on)}`}
                onClick={() => run(async () => { await api.deleteVinylCare(c.care_id); onRecord(await api.vinylRecord(r.record_id)) })}>✕</button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

// The stylus: hours played since it was fitted, against when to replace it.
export function StylusCard({ stylus, onChanged }) {
  const [limit, setLimit] = useState(String(stylus.limit_hours))
  const [error, setError] = useState('')
  const run = async (fn) => {
    setError('')
    try { await fn(); onChanged() } catch (e) { setError(e.message) }
  }
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Stylus</h2>
      <p className={stylus.due ? 'vinyl-warn' : stylus.soon ? 'vnm-soon' : undefined}><strong>{stylusText(stylus)}</strong></p>
      <span className={`fill-bar ${stylus.due ? 'out' : stylus.soon ? 'low' : 'ok'}`} role="progressbar" aria-label="Stylus wear"
        aria-valuenow={stylus.percent} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${stylus.percent}%` }} /></span>
      <p className="muted small">Worked out from your plays: {plural(stylus.plays, 'play')}{stylus.since ? ` since ${shortDate(stylus.since)}` : ' so far'}, timed from each
        side's tracks (a usual side when the tracklist has no times). CDs don't count.</p>
      <form className="button-row" onSubmit={(e) => { e.preventDefault(); run(() => api.setVinylStylus(Number(limit))) }}>
        <label className="small">Replace at (hours) <input type="number" min="1" max="5000" step="1" value={limit} onChange={(e) => setLimit(e.target.value)} /></label>
        <button type="submit" className="secondary small">Save</button>
        <button type="button" className="secondary small" onClick={() => run(() => api.vinylStylusFitted())}>I fitted a new stylus</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

// A line on the dashboard when the stylus is nearly due or due.
export function StylusReminder({ stylus }) {
  if (!stylus || !(stylus.due || stylus.soon)) return null
  return (
    <Link className={`card vnm-reminder${stylus.due ? ' due' : ''}`} to="/vinyl/care">
      <strong>{stylus.due ? 'Time to replace the stylus' : 'The stylus is nearly worn'}</strong>
      <span className="muted small"> {stylusText(stylus)}</span>
    </Link>
  )
}

// Care page: the stylus and what's out on loan.
export function CareView() {
  const { refreshKey, openPanel } = useApp()
  const [stylus, setStylus] = useState(null)
  const [loans, setLoans] = useState(null)
  const [error, setError] = useState('')
  const [n, setN] = useState(0)
  useEffect(() => {
    api.vinylStylus().then(setStylus).catch((e) => setError(e.message))
    api.vinylLoans().then(setLoans).catch((e) => setError(e.message))
  }, [refreshKey, n])
  if (error) return <p className="alert error">{error}</p>
  if (!stylus || !loans) return <p className="muted loading">Loading...</p>
  return (
    <section className="page vinyl">
      <div className="home-grid">
        <StylusCard key={stylus.limit_hours} stylus={stylus} onChanged={() => setN(n + 1)} />
        <section className="card home-card">
          <h2 className="home-card-title">Loaned out</h2>
          {loans.length === 0 ? <p className="muted small">Nothing is out on loan. Open a record and loan it to someone to see it here.</p> : (
            <ul className="list plain-list">
              {loans.map((l) => (
                <li key={l.record_id}>
                  <button type="button" className="row-button" onClick={() => openPanel('record', { id: l.record_id })}>
                    <RecordCover record={l} className="vinyl-cover small" />
                    <span className="grow"><span className="item-title">{l.title}</span>
                      <span className="item-meta">{l.artist} · with {l.loaned_to} for {loanTime(l.days)}</span></span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  )
}

// The collection's value week by week, what moved, and what it cost.
export function ValueHistoryCard() {
  const { refreshKey, openPanel } = useApp()
  const [h, setH] = useState(null)
  useEffect(() => { api.vinylValueHistory().then(setH).catch(() => setH({ series: [], changes: [], movers: [], paid: 0, now: 0 })) }, [refreshKey])
  if (!h) return <section className="card home-card wide-card"><h2 className="home-card-title">What it's worth</h2><p className="muted loading">Loading...</p></section>
  return (
    <section className="card home-card wide-card">
      <h2 className="home-card-title">What it's worth</h2>
      {h.series.length > 1 ? (
        <>
          <p><strong className="vinyl-value">{money(h.now)}</strong>{h.paid > 0 && <span className="muted small"> · {money(h.paid)} paid</span>}</p>
          <LineChart title="Collection value" rows={h.series.map((w) => ({ x: w.week, y: w.value, tip: `Week of ${shortDate(w.week)}` }))} valueLabel="AUD" />
          {h.changes.length > 0 && <ul className="vnm-changes">{h.changes.map((c) => <li key={c.days} className={c.change < 0 ? 'vinyl-warn' : 'ok-text'}>{changeText(c)}</li>)}</ul>}
        </>
      ) : <p className="muted small">The value is read from Discogs every week; the line starts after the second week.</p>}
      {h.movers.length > 0 && (
        <>
          <h3 className="section-title">Biggest movers (3 months)</h3>
          <ul className="list plain-list">
            {h.movers.map((m) => (
              <li key={m.record_id}>
                <button type="button" className="row-button" onClick={() => openPanel('record', { id: m.record_id })}>
                  <span className="grow"><span className="item-title">{m.title}</span><span className="item-meta">{m.artist} · {money(m.was)} → {money(m.value)}</span></span>
                  <span className={m.moved < 0 ? 'vinyl-warn' : 'ok-text'}>{m.moved < 0 ? '−' : '+'}{money(Math.abs(m.moved))}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

// Your listening year: plays by month, most played, new arrivals.
export function ListeningYearView() {
  const { refreshKey, openPanel } = useApp()
  const [year, setYear] = useState(null)
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.vinylReview(year).then(setR).catch((e) => setError(e.message)) }, [year, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!r) return <p className="muted loading">Loading...</p>
  const months = r.by_month.map((m, i) => ({ label: MONTHS[i], value: m.plays, tip: `${MONTHS[i]} ${r.year}` }))
  return (
    <section className="page stats vinyl">
      <div className="toolbar">
        <label className="small">Year <select value={r.year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Year">
          {r.years.map((y) => <option key={y} value={y}>{y}</option>)}</select></label>
      </div>
      {r.plays === 0 && r.new_arrivals.length === 0 ? (
        <EmptyState Icon={VinylIcon} title={`Nothing played in ${r.year}`}>Log a play (Played it) and your listening year fills in.</EmptyState>
      ) : (
        <>
          <div className="home-stats">
            <Stat to="/vinyl/plays" Icon={VinylIcon} tone="tint" value={r.plays} label={`Plays in ${r.year}`} sub={`${plural(r.records_played, 'record')} · ${plural(r.days, 'day')}`} />
            <Stat to="/vinyl/plays" Icon={VinylIcon} tone="teal" value={`${r.hours} h`} label="Listening time" sub="from each side's length" />
            <Stat to="/vinyl/crate?sort=added" Icon={VinylIcon} tone="ok" value={r.new_arrivals.length} label="New arrivals"
              sub={r.new_unplayed ? `${r.new_unplayed} not played yet` : 'all played'} />
            <Stat to="/vinyl/connect" Icon={VinylIcon} tone="purple" value={r.scrobbled.toLocaleString()} label="Tracks scrobbled" sub="to Last.fm from your plays" />
          </div>
          <div className="home-grid">
            <section className="card home-card wide-card">
              <h2 className="home-card-title">Plays each month</h2>
              <ColumnChart title="Month" rows={months} valueLabel="plays" labelValues />
              {r.busiest_day && <p className="muted small">You play most on {r.busiest_day.day}s ({plural(r.busiest_day.plays, 'play')}).</p>}
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Most played records</h2>
              {r.top_records.length === 0 ? <p className="muted small">No plays yet.</p> : (
                <ul className="list plain-list">
                  {r.top_records.map((x) => (
                    <li key={x.record_id}>
                      <button type="button" className="row-button" onClick={() => openPanel('record', { id: x.record_id })}>
                        <span className="grow"><span className="item-title">{x.title}</span><span className="item-meta">{x.artist}</span></span>
                        <span className="muted small">{plural(x.plays, 'play')}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Most played artists</h2>
              {r.top_artists.length === 0 ? <p className="muted small">No plays yet.</p>
                : <BarList title="Artist" valueLabel="Plays" rows={r.top_artists.map((a) => ({ label: a.label, value: a.plays, text: plural(a.plays, 'play') }))} />}
            </section>
            {r.new_arrivals.length > 0 && (
              <section className="card home-card wide-card">
                <h2 className="home-card-title">New in the collection</h2>
                <div className="vnm-arrivals">
                  {r.new_arrivals.slice(0, 24).map((x) => (
                    <button key={x.record_id} type="button" className="vnm-arrival" onClick={() => openPanel('record', { id: x.record_id })}>
                      <RecordCover record={x} className="vinyl-cover" />
                      <span className="item-title">{x.title}</span>
                      <span className="item-meta">{x.plays ? plural(x.plays, 'play') : 'not played yet'}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </div>
        </>
      )}
    </section>
  )
}

// The insurance list: every record you own with its value, grades and what you paid, and a cover picture; for printing.
export function InsuranceView() {
  const { refreshKey } = useApp()
  const [records, setRecords] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.vinylRecords({ status: 'Owned', sort: 'artist' }).then((d) => setRecords(d.records)).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!records) return <p className="muted loading">Loading...</p>
  const value = records.reduce((n, r) => n + (r.value ?? 0), 0)
  const paid = records.reduce((n, r) => n + (r.price_paid ?? 0), 0)
  return (
    <section className="page vinyl vnm-insure">
      <div className="toolbar vnm-noprint">
        <button type="button" className="primary" onClick={() => window.print()}>Print this list</button>
        <a className="button secondary" href={vinylExportUrl} download>Download as a spreadsheet (CSV)</a>
      </div>
      <h2 className="home-card-title">Record collection for insurance</h2>
      <p className="small">{plural(records.length, 'record')} · worth {money(value)} (Discogs' prices) · {money(paid)} paid</p>
      {records.length === 0 ? <p className="muted small">No records yet.</p> : (
        <table className="vnm-insure-table">
          <thead><tr><th scope="col">Cover</th><th scope="col">Record</th><th scope="col">Grades</th>
            <th scope="col" className="num">Paid</th><th scope="col" className="num">Worth</th></tr></thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.record_id}>
                <td><RecordCover record={r} className="vnm-insure-cover" /></td>
                <td><strong>{r.title}</strong><br /><span className="muted small">{[r.artist, r.label, r.catno, r.year].filter(Boolean).join(' · ')}</span></td>
                <td className="small">{[r.media_condition && `Record ${r.media_condition}`, r.sleeve_condition && `Sleeve ${r.sleeve_condition}`].filter(Boolean).join(', ') || '—'}</td>
                <td className="num">{r.price_paid != null ? money(r.price_paid) : '—'}</td>
                <td className="num">{r.value != null ? money(r.value) : '—'}</td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr><th scope="row" colSpan={3}>Total</th><td className="num">{money(paid)}</td><td className="num">{money(value)}</td></tr></tfoot>
        </table>
      )}
    </section>
  )
}
