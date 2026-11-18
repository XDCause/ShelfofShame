import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { FishIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { catchLine, dueText, fateName, plural, stars, tripName } from './fishFormat.js'

// Bits shared by fishing's pages and panels: the summary (Home's tiles and the dashboard), the spots / species / lures
// for pickers, a trip's row in a list, a grid of numbers, the things coming due. Kept small: Home loads this file up
// front (HomeTiles.jsx). The plain formatters are in fishFormat.js.

export function useFishingSummary() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.fishingSummary().then(setData).catch((e) => setError(e.message)) }, [refreshKey])
  return { data, error }
}

// Spots, species and lures for the pickers and the lists; null until loaded, [] when the call fails.
export function useFishingSpots() {
  const { refreshKey } = useApp()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.fishingSpots().then(setRows).catch(() => setRows([])) }, [refreshKey])
  return rows
}
export function useFishingSpecies() {
  const { refreshKey } = useApp()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.fishingSpecies().then(setRows).catch(() => setRows([])) }, [refreshKey])
  return rows
}
export function useFishingLures(retired = '') {
  const { refreshKey } = useApp()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.fishingLures({ retired }).then(setRows).catch(() => setRows([])) }, [refreshKey, retired])
  return rows
}

// The settings (home position, permit and boat rego dates, the official rules link), refreshed with the app.
export function useFishingSettings() {
  const { refreshKey } = useApp()
  const [settings, setSettings] = useState(null)
  useEffect(() => { api.fishingSettings().then(setSettings).catch(() => setSettings({})) }, [refreshKey])
  return settings
}

// A trip in a list: where, when, how it was fished, what came of it.
export function TripRow({ t, before }) {
  const { openPanel } = useApp()
  const best = t.best?.species ? `${t.best.species}${t.best.length_cm != null ? ` ${t.best.length_cm} cm` : ''}` : null
  return (
    <li>
      <button type="button" className="row-button fsh-trip-row" onClick={() => { before?.(); openPanel('fishingtrip', { id: t.trip_id }) }}>
        <span className="stat-icon teal" aria-hidden="true"><FishIcon size={18} /></span>
        <span className="grow">
          <span className="item-title">{tripName(t)}{!t.ended_at && <span className="pill low fsh-open-pill">on the water</span>}</span>
          <span className="item-meta">
            <span>{shortDate(t.started_at)}</span>
            {t.platform && <span>{t.platform}</span>}
            {t.target && t.spot_name && <span>after {t.target}</span>}
            {best && <span>best: {best}</span>}
            {t.rating != null && <span className="fsh-stars" role="img" aria-label={`${t.rating} stars`}>{stars(t.rating)}</span>}
          </span>
        </span>
        <span className="fsh-trip-figures">
          <strong>{t.catches ? plural(t.catches, 'fish', 'fish') : 'Blank'}</strong>
          <span className="muted small">{t.kept ? `${t.kept} kept` : t.hours != null ? `${t.hours} h` : ''}</span>
        </span>
      </button>
    </li>
  )
}

// A catch in a list: the fish, its fate, the lure, the time; warnings show under it.
export function CatchRow({ c, onOpen }) {
  const lure = c.lure_name ?? c.bait
  return (
    <li>
      <button type="button" className="row-button fsh-catch-row" onClick={() => onOpen(c)}>
        <span className="stat-icon ok" aria-hidden="true"><FishIcon size={18} /></span>
        <span className="grow">
          <span className="item-title">{catchLine(c)}</span>
          <span className="item-meta">
            <span>{fateName(c.fate)}</span>
            {c.weight_kg != null && <span>{c.weight_kg} kg</span>}
            {lure && <span>{lure}</span>}
            {c.caught_at && <span>{new Date(c.caught_at).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit', hour12: true })}</span>}
            {c.photos?.length > 0 && <span>{plural(c.photos.length, 'photo')}</span>}
          </span>
        </span>
      </button>
      {c.warnings?.length > 0 && (
        <ul className="fsh-warnings" aria-label="Rule warnings">
          {c.warnings.map((w) => <li key={w}><span className="pill low">check</span> <span>{w}</span></li>)}
        </ul>
      )}
    </li>
  )
}

// A row of labelled numbers: [{label, value, sub?}] (falsy ones left out).
export function Numbers({ items }) {
  return (
    <dl className="fsh-numbers">
      {items.filter(Boolean).map((x) => (
        <div key={x.label}><dt>{x.label}</dt><dd>{x.value}{x.sub && <span className="muted small"> {x.sub}</span>}</dd></div>
      ))}
    </dl>
  )
}

// The permit / boat rego / rules reminders: [{kind, text, due}]
export function Alerts({ alerts }) {
  if (!alerts?.length) return null
  const day = new Date().toLocaleDateString('en-CA')
  return (
    <ul className="fsh-alerts" aria-label="Things coming due">
      {alerts.map((a, i) => (
        <li key={`${a.kind}-${i}`} className={`fsh-alert ${a.due && a.due < day ? 'overdue' : ''}`}>
          <span className="pill low">{a.kind === 'sip' ? 'permit' : a.kind === 'boat_rego' ? 'boat rego' : a.kind}</span> <span>{a.text}</span>
          {a.due && <span className="muted small">{dueText(a.due)}</span>}
        </li>
      ))}
    </ul>
  )
}
