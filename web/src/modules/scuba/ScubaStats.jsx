import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { BarList, ColumnChart, LineChart } from '../../components/charts.jsx'
import { DiveIcon, TrophyIcon } from '../../components/icons.jsx'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { hoursText, metres, minutesText, num, oneADay, plural } from './scubaFormat.js'
import { Numbers, useScubaSettings } from './scubaParts.jsx'

// Scuba's stats (totals, records, dives by month and year, depth bands, air use, top sites, tags, water temperature -
// for every year or one) with your settings below, and the life list.

const STEPS = [0.5, 1, 2, 5, 10, 20]
const monthName = (m, opts) => new Date(`${m}-15T12:00:00`).toLocaleDateString('en-AU', opts)

export function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const settings = useScubaSettings()
  const [year, setYear] = useState('')
  const [st, setSt] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.scubaStats({ year }).then(setSt).catch((e) => setError(e.message)) }, [year, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!st) return <p className="muted loading">Loading...</p>
  const t = st.totals
  const r = st.records
  const none = t.dives === 0 && !year
  const record = (label, d, value) => d && {
    label, value, sub: `${d.site_name ?? 'unnamed site'}, ${shortDate(d.dived_on)}`, dive: d.dive_id }
  const records = [
    record('Deepest', r.deepest, metres(r.deepest?.max_depth)),
    record('Longest', r.longest, minutesText(r.longest?.minutes)),
    record('Coldest', r.coldest, r.coldest && `${num(r.coldest.water_temp)}°C`),
    record('Warmest', r.warmest, r.warmest && `${num(r.warmest.water_temp)}°C`),
    record('Best visibility', r.best_vis, r.best_vis && 'see the dive'),
  ].filter(Boolean)
  // (the label carries the year: ColumnChart keys its columns by label, and a month name repeats across two years)
  const monthRows = st.by_month.map((m) => ({ label: monthName(m.month, { month: 'short', year: '2-digit' }),
    tip: monthName(m.month, { month: 'long', year: 'numeric' }), value: m.dives }))
  const sac = oneADay(st.sac_trend.map((x) => ({ x: x.dived_on, y: x.sac, tip: `${x.sac} L/min` })))
  const temps = oneADay(st.temps.map((x) => ({ x: x.dived_on, y: Number(x.water_temp) })))
  return (
    <section className="page scb">
      <div className="toolbar">
        <div className="chip-row" role="group" aria-label="Year">
          <button type="button" className="chip-filter" aria-pressed={year === ''} onClick={() => setYear('')}>All years</button>
          {[...st.by_year].reverse().slice(0, 8).map((y) => (
            <button key={y.year} type="button" className="chip-filter" aria-pressed={year === String(y.year)} onClick={() => setYear(String(y.year))}>{y.year}</button>
          ))}
        </div>
      </div>
      {none ? (
        <EmptyState Icon={DiveIcon} title="No dives to count yet" action="Log a dive" onAction={() => openPanel('scubanewdive', {})}>
          Your totals, deepest and longest dives, air use and the sites you go to most show here.</EmptyState>
      ) : (
        <div className="home-grid">
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Totals{year && ` in ${year}`}</h2>
              <Numbers items={[
                { label: 'Dives', value: t.dives.toLocaleString(), sub: !year && t.dives !== t.dives_logged ? `${t.dives_logged} logged here` : null },
                { label: 'Underwater', value: hoursText(t.minutes) },
                t.avg_depth != null && { label: 'Average depth', value: metres(t.avg_depth) },
                t.avg_minutes != null && { label: 'Average dive', value: minutesText(t.avg_minutes) },
                { label: 'Dive days', value: t.dive_days },
                { label: 'Sites', value: t.sites },
                { label: 'Trips', value: t.trips },
                { label: 'Species seen', value: t.species },
              ]} />
            </section>
            {records.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Records</h2>
                <ul className="list plain-list">
                  {records.map((x) => (
                    <li key={x.label}>
                      <button type="button" className="row-button scb-record" onClick={() => openPanel('scubadive', { id: x.dive })}>
                        <span className="stat-icon low" aria-hidden="true"><TrophyIcon size={18} /></span>
                        <span className="grow"><span className="item-title">{x.label}</span><span className="item-meta">{x.sub}</span></span>
                        <strong className="scb-record-value">{x.value}</strong>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section className="card home-card">
              <h2 className="home-card-title">Depth</h2>
              <BarList title="Dives by depth" rows={st.depth_bands.map((b) => ({ label: `${b.band} m`, value: b.dives }))} valueLabel="dives" />
            </section>
            {st.top_sites.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Most-dived sites</h2>
                <BarList title="Dives by site" rows={st.top_sites.map((s) => ({ label: s.name, value: s.dives, site: s.site_id }))} valueLabel="dives"
                  onPick={(row) => openPanel('scubasite', { id: row.site })} />
              </section>
            )}
          </div>
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Dives by month</h2>
              <ColumnChart title="Dives a month (last 24 months)" rows={monthRows} valueLabel="dives" tickEvery={3} height={150} />
            </section>
            {st.by_year.length > 1 && (
              <section className="card home-card">
                <h2 className="home-card-title">Dives by year</h2>
                <ColumnChart title="Dives a year" rows={st.by_year.map((y) => ({ label: String(y.year), value: y.dives }))} valueLabel="dives" labelValues height={140} />
              </section>
            )}
            <section className="card home-card">
              <h2 className="home-card-title">Air use</h2>
              <p className="muted small">Surface air consumption (litres a minute at the surface): lower is calmer breathing, and it falls as you gain experience.
                Needs both pressures, the tank and the time.</p>
              <LineChart title="SAC (L/min)" rows={sac} valueLabel="L/min" height={150} stepChoices={STEPS} empty="Log the tank and both pressures on a few dives to draw this." />
            </section>
            {temps.length > 1 && (
              <section className="card home-card">
                <h2 className="home-card-title">Water temperature</h2>
                <LineChart title="Water temperature (°C)" rows={temps} valueLabel="°C" height={140} stepChoices={STEPS} />
              </section>
            )}
            {st.tags.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Kinds of dive</h2>
                <BarList title="Dives by tag" rows={st.tags.map((x) => ({ label: x.tag, value: x.dives }))} valueLabel="dives" />
              </section>
            )}
          </div>
        </div>
      )}
      <section className="card home-card" id="scuba-settings">
        <h2 className="home-card-title">Your diving settings</h2>
        {settings ? <SettingsCard key={JSON.stringify(settings)} settings={settings} /> : <p className="muted small">Loading...</p>}
      </section>
    </section>
  )
}

// ---------------------------------------------------------------- settings

const SETTING_FIELDS = [
  { name: 'dives_before', label: 'Dives before this app', type: 'number', required: true, hint: 'Your logbook numbering carries on from here.' },
  { name: 'minutes_before', label: 'Minutes underwater before', type: 'number', required: true },
  { name: 'gas_o2', label: 'Usual gas, oxygen (%)', type: 'number', min: 21, required: true },
  { name: 'tank_l', label: 'Usual tank (litres)', type: 'number', step: 0.5, required: true },
  { name: 'start_bar', label: 'Usual start pressure (bar)', type: 'number', required: true },
  { name: 'sac_l_min', label: 'Your breathing rate (SAC, L/min)', type: 'number', step: 0.5, required: true, hint: 'For planning gas.' },
  { name: 'gf_low', label: 'Gradient factor low (%)', type: 'number', required: true },
  { name: 'gf_high', label: 'Gradient factor high (%)', type: 'number', required: true, hint: 'How conservative the planner is; 40 / 85 is common.' },
  { name: 'ppo2_max', label: 'Max ppO2', type: 'number', step: 0.05, min: 1, required: true, hint: '1.4 for diving, 1.6 at the most.' },
  { name: 'medical_due', label: 'Dive medical due', type: 'date' },
  { name: 'insurance_until', label: 'Dive insurance until', type: 'date' },
  { name: 'home_lat', label: 'Home latitude', type: 'number', step: 'any', min: -90, hint: 'Where "dive sites near my home" looks.' },
  { name: 'home_lon', label: 'Home longitude', type: 'number', step: 'any', min: -180 },
]

function SettingsCard({ settings }) {
  const { changed, showToast } = useApp()
  const { form, set, payload } = useRecordForm(SETTING_FIELDS, settings)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.saveScubaSettings(payload())
      changed()
      showToast('Saved')
    } catch (err) {
      setError(err.message)
    }
    setBusy(false)
  }
  return (
    <form onSubmit={save}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <RecordFields fields={SETTING_FIELDS} form={form} set={set} />
      <div className="button-row"><button type="submit" className="primary" disabled={busy}>Save settings</button></div>
    </form>
  )
}

// ---------------------------------------------------------------- the life list

export function SpeciesView() {
  const { refreshKey, openPanel } = useApp()
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')
  useEffect(() => { api.scubaSpecies().then(setRows).catch(() => setRows([])) }, [refreshKey])
  if (!rows) return <p className="muted loading">Loading...</p>
  const shown = rows.filter((s) => !q.trim() || s.species.toLowerCase().includes(q.trim().toLowerCase()))
  return (
    <section className="page scb">
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your life list..." aria-label="Search species" className="scb-search" />
        <span className="grow" />
        <p className="muted small scb-log-note">{plural(rows.length, 'species', 'species')} seen</p>
      </div>
      {rows.length === 0 ? (
        <EmptyState Icon={TrophyIcon} title="Your life list is empty">
          Open a dive and note what you saw (turtles, rays, sharks, the small stuff): every species you have seen shows here, with the first time and how often.</EmptyState>
      ) : shown.length === 0 ? <p className="empty card">Nothing by that name.</p> : (
        <section className="card home-card">
          <ul className="list plain-list">
            {shown.map((s) => (
              <li key={s.species}>
                <button type="button" className="row-button" onClick={() => openPanel('scubadive', { id: s.first_dive_id })}>
                  <span className="stat-icon teal" aria-hidden="true"><DiveIcon size={18} /></span>
                  <span className="grow">
                    <span className="item-title">{s.species}</span>
                    <span className="item-meta"><span>first seen {shortDate(s.first_on)}</span>{s.last_on !== s.first_on && <span>last {shortDate(s.last_on)}</span>}</span>
                  </span>
                  <span className="scb-dive-figures">
                    <strong>{plural(s.dives, 'dive')}</strong>
                    {s.total > 0 && <span className="muted small">{s.total.toLocaleString()} seen</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}
