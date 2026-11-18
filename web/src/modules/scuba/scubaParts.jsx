import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { DiveIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { diveName, gasName, metres, minutesText, stars, timeText } from './scubaFormat.js'

// Bits shared by scuba's pages and panels: the summary (Home's tiles and the dashboard), the settings, the sites and
// trips for pickers, a dive's row in a list, a grid of numbers. Kept small: Home loads this file up front
// (HomeTiles.jsx). The plain formatters are in scubaFormat.js.

export function useScubaSummary() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.scubaSummary().then(setData).catch((e) => setError(e.message)) }, [refreshKey])
  return { data, error }
}

// The time now, again every half minute (the no-fly countdown).
export function useNow(every = 30000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), every)
    return () => clearInterval(t)
  }, [every])
  return now
}

// The settings (gas, tank, breathing rate, gradient factors, medical and insurance dates), refreshed with the app.
export function useScubaSettings() {
  const { refreshKey } = useApp()
  const [settings, setSettings] = useState(null)
  useEffect(() => { api.scubaSettings().then(setSettings).catch(() => setSettings({})) }, [refreshKey])
  return settings
}

// Sites (most dived first) for the pickers and the list; null until loaded.
export function useScubaSites() {
  const { refreshKey } = useApp()
  const [sites, setSites] = useState(null)
  useEffect(() => { api.scubaSites().then(setSites).catch(() => setSites([])) }, [refreshKey])
  return sites
}

export function useScubaTrips() {
  const { refreshKey } = useApp()
  const [trips, setTrips] = useState(null)
  useEffect(() => { api.scubaTrips().then(setTrips).catch(() => setTrips([])) }, [refreshKey])
  return trips
}

// A dive in a list: number, site, date, depth and time, the gas when it isn't air, the rating.
// `before`: called first when the row sits in a panel (the panel closes before the next opens).
export function DiveRow({ d, before }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button scb-dive-row" onClick={() => { before?.(); openPanel('scubadive', { id: d.dive_id }) }}>
        <span className="stat-icon teal" aria-hidden="true"><DiveIcon size={18} /></span>
        <span className="grow">
          <span className="item-title">{d.site_name ?? 'Unnamed site'}</span>
          <span className="item-meta">
            <span>{shortDate(d.dived_on)}{d.time_in ? ` ${timeText(d.time_in)}` : ''}</span>
            <span>{diveName(d)}</span>
            {d.gas_o2 != null && d.gas_o2 !== 21 && <span>{gasName(d.gas_o2)}</span>}
            {d.water_temp != null && <span>{d.water_temp}°C</span>}
            {d.has_profile && <span>profile</span>}
            {d.rating != null && <span className="scb-stars" role="img" aria-label={`${d.rating} stars`}>{stars(d.rating)}</span>}
          </span>
        </span>
        <span className="scb-dive-figures">
          <strong>{metres(d.max_depth)}</strong>
          <span className="muted small">{minutesText(d.minutes)}</span>
        </span>
      </button>
    </li>
  )
}

// A row of labelled numbers: [{label, value, sub?}] (nulls left out).
export function Numbers({ items }) {
  return (
    <dl className="scb-numbers">
      {items.filter(Boolean).map((x) => (
        <div key={x.label}><dt>{x.label}</dt><dd>{x.value}{x.sub && <span className="muted small"> {x.sub}</span>}</dd></div>
      ))}
    </dl>
  )
}

// "No-fly until..." and "Medical due..." alerts as a list: [{kind, text, due}]
export function Alerts({ alerts }) {
  if (!alerts?.length) return null
  return (
    <ul className="scb-alerts" aria-label="Things coming due">
      {alerts.map((a, i) => (
        <li key={`${a.kind}-${i}`} className={`scb-alert ${a.due && a.due < new Date().toLocaleDateString('en-CA') ? 'overdue' : ''}`}>
          <span className="pill low">{a.kind}</span> <span>{a.text}</span>
        </li>
      ))}
    </ul>
  )
}
