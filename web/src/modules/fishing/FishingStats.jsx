import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { BarList, ColumnChart, LineChart } from '../../components/charts.jsx'
import { FishIcon } from '../../components/icons.jsx'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { MONTHS, MOON_PHASES, cm, dateOf, heatLevel, hoursText, monthLabel, num, oneADay, plural } from './fishFormat.js'
import { Numbers, useFishingSettings, useFishingSpecies } from './fishingParts.jsx'

// Fishing's stats: what works for YOU. Your own catches by month, species, season, time of day, moon phase, tide stage,
// lure and spot, the length of one species over time - for every year or one - with your settings below. (Solunar
// tables are an old angling theory: this is where your own log shows whether the moon or the tide matters to you.)

const STEPS = [1, 2, 5, 10, 20]
const hourName = (h) => `${h % 12 === 0 ? 12 : h % 12}${h < 12 ? 'am' : 'pm'}`

// A heat grid: one row a species, one column a month; a darker cell is more fish. rows: [{species, months: [12]}]
export function SeasonGrid({ rows }) {
  const max = Math.max(0, ...rows.flatMap((r) => r.months))
  return (
    <div className="fsh-grid-wrap">
      <table className="fsh-grid">
        <caption className="visually-hidden">Fish by species and month</caption>
        <thead><tr><th scope="col">Species</th>{MONTHS.map((m) => <th key={m} scope="col">{m}</th>)}</tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.species}>
              <th scope="row">{r.species}</th>
              {r.months.map((n, i) => <td key={MONTHS[i]} className={`fsh-heat-${heatLevel(n, max)}`} title={`${r.species}, ${MONTHS[i]}: ${n}`}>{n || ''}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const settings = useFishingSettings()
  const species = useFishingSpecies()
  const [year, setYear] = useState('')
  const [fish, setFish] = useState('')                 // species_id for the length trend
  const [st, setSt] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.fishingStats({ year, species_id: fish }).then(setSt).catch((e) => setError(e.message)) }, [year, fish, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!st) return <p className="muted loading">Loading...</p>
  const t = st.totals
  const none = t.trips === 0 && !year
  const years = [...new Set(st.by_month.map((m) => m.month.slice(0, 4)))].reverse()
  const monthRows = st.by_month.map((m) => ({ label: monthLabel(m.month), tip: monthLabel(m.month, { month: 'long', year: 'numeric' }), value: m.catches }))
  const hourRows = st.by_hour.map((n, h) => ({ label: hourName(h), value: n }))
  const moonRows = MOON_PHASES.map((p) => st.by_moon.find((x) => x.phase === p) ?? { phase: p, catches: 0, trips: 0 })
  const moonKnown = moonRows.some((m) => m.trips > 0)
  const tideRows = st.by_tide.map((x) => ({ label: x.stage[0].toUpperCase() + x.stage.slice(1), value: x.catches }))
  const tideKnown = tideRows.some((x) => x.value > 0)
  const trend = oneADay(st.length_trend.map((x) => ({ x: dateOf(x.caught_at), y: x.length_cm, tip: `${x.species} ${cm(x.length_cm)}` })))
  const caughtSpecies = (species ?? []).filter((s) => s.caught > 0)
  return (
    <section className="page fsh">
      <div className="toolbar">
        <div className="chip-row" role="group" aria-label="Year">
          <button type="button" className="chip-filter" aria-pressed={year === ''} onClick={() => setYear('')}>All years</button>
          {years.slice(0, 6).map((y) => (
            <button key={y} type="button" className="chip-filter" aria-pressed={year === y} onClick={() => setYear(y)}>{y}</button>
          ))}
        </div>
      </div>
      {none ? (
        <EmptyState Icon={FishIcon} title="Nothing to count yet" action="Log a past trip" onAction={() => openPanel('fishingnewtrip', {})}>
          Your catches by month, tide, moon, time of day and lure show here once you have a few trips.</EmptyState>
      ) : (
        <div className="home-grid">
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Totals{year && ` in ${year}`}</h2>
              <Numbers items={[
                { label: 'Trips', value: t.trips },
                { label: 'Fish', value: t.catches },
                { label: 'Kept', value: t.kept },
                { label: 'Released', value: t.released },
                { label: 'Time fishing', value: hoursText(t.hours) },
                { label: 'Blank trips', value: t.blanks },
                t.hours > 0 && { label: 'Fish an hour', value: num(t.catches / t.hours, 2) },
              ]} />
            </section>
            {st.by_species.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Species</h2>
                <BarList title="Fish by species" rows={st.by_species.map((s) => ({ label: s.species, value: s.catches,
                  text: `${s.catches}${s.best_cm != null ? ` · best ${num(s.best_cm)} cm` : ''}` }))} valueLabel="fish" />
              </section>
            )}
            {st.seasons.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">When each species bites</h2>
                <p className="muted small">Your catches by month: a darker cell is more fish.</p>
                <SeasonGrid rows={st.seasons} />
              </section>
            )}
            {st.top_lures.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Best lures and baits</h2>
                <BarList title="Fish by lure" rows={st.top_lures.map((l) => ({ label: l.name, value: l.catches, lure: l.lure_id }))} valueLabel="fish"
                  onPick={(row) => openPanel('fishinglure', { id: row.lure })} />
              </section>
            )}
            {st.top_spots.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Best spots</h2>
                <p className="muted small">Ranked by fish an hour on finished trips.</p>
                <BarList title="Spots by fish an hour" rows={st.top_spots.map((s) => ({ label: s.name, value: s.fish_per_hour ?? 0, spot: s.spot_id,
                  text: `${s.fish_per_hour != null ? num(s.fish_per_hour, 2) : '—'} an hour · ${plural(s.catches, 'fish', 'fish')}` }))} valueLabel="fish an hour"
                  onPick={(row) => openPanel('fishingspot', { id: row.spot })} />
              </section>
            )}
          </div>
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Fish by month</h2>
              <ColumnChart title="Fish a month (last 24 months)" rows={monthRows} valueLabel="fish" tickEvery={3} height={150} />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Time of day</h2>
              <ColumnChart title="Fish by the hour of the day" rows={hourRows} valueLabel="fish" tickEvery={3} height={130} />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Moon phase</h2>
              {moonKnown ? (
                <>
                  <p className="muted small">Fish by the moon at the start of the trip. Solunar tables are an old angling theory: compare the bars to how many trips you made in each phase before you believe it.</p>
                  <BarList title="Fish by moon phase" rows={moonRows.map((m) => ({ label: m.phase, value: m.catches, text: `${m.catches} fish · ${plural(m.trips, 'trip')}` }))} valueLabel="fish" />
                </>
              ) : <p className="muted small">Trips at a spot with a position save the moon phase, so this fills in as you fish.</p>}
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Tide</h2>
              {tideKnown ? (
                <BarList title="Fish by tide stage" rows={tideRows} valueLabel="fish" />
              ) : <p className="muted small">Salt and estuary trips at a spot with a position save the tide, so this fills in as you fish.</p>}
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Length over time</h2>
              <label className="field">Species
                <select value={fish} onChange={(e) => setFish(e.target.value)}>
                  <option value="">Pick a species...</option>
                  {caughtSpecies.map((s) => <option key={s.species_id} value={s.species_id}>{s.name}</option>)}
                </select></label>
              {fish === '' ? <p className="muted small">Pick a species to see whether your fish are getting bigger.</p>
                : <LineChart title="Length (cm)" rows={trend} valueLabel="cm" height={150} stepChoices={STEPS} empty="Measure a few of that species to draw this." />}
            </section>
          </div>
        </div>
      )}
      <section className="card home-card" id="fishing-settings">
        <h2 className="home-card-title">Your fishing settings</h2>
        {settings ? <SettingsCard key={JSON.stringify(settings)} settings={settings} /> : <p className="muted small">Loading...</p>}
      </section>
    </section>
  )
}

// ---------------------------------------------------------------- settings

const SETTING_FIELDS = [
  { name: 'sip_until', label: 'Stocked Impoundment Permit until', type: 'date', hint: 'For stocked dams (Somerset, Wivenhoe, North Pine...). A reminder shows 60 days before.' },
  { name: 'boat_rego_until', label: 'Boat registration until', type: 'date' },
  { name: 'home_lat', label: 'Home latitude', type: 'number', step: 'any', min: -90, hint: 'Where "boat ramps near my home" looks.' },
  { name: 'home_lon', label: 'Home longitude', type: 'number', step: 'any', min: -180 },
  { name: 'rules_url', label: 'Official rules page', type: 'url', wide: true, hint: 'Every rules screen links here. Blank goes back to the Queensland page.' },
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
      await api.saveFishingSettings(payload())
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
      {settings.updated_at && <p className="muted small">Last saved {shortDate(settings.updated_at)}.</p>}
      <div className="button-row"><button type="submit" className="primary" disabled={busy}>Save settings</button></div>
    </form>
  )
}
