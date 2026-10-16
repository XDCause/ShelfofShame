import { useEffect, useState } from 'react'
import { api, shortDate, timeAgo } from '../api.js'
import { useApp } from '../core/app-context.js'

// Settings > Lookup sites: the weekly check of the websites the app reads (api/app/sitecheck.py).
// Each site: OK / Not working (since when, and why) / Not checked yet; "Check now" runs them all.
export default function SiteChecks() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => api.siteChecks().then(setData).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])
  useEffect(() => {          // while a check runs, look again every 2 s
    if (!data?.running) return undefined
    const t = setTimeout(load, 2000)
    return () => clearTimeout(t)
  }, [data])

  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted">Loading...</p>
  return (
    <div className="site-checks">
      <p className="muted small">
        Once a week the app does one real look-up on each site it reads, to notice when a site changes and a
        look-up stops working. {data.last_run && `Last checked ${timeAgo(data.last_run)}.`}
      </p>
      <ul className="list plain-list">
        {data.sites.map((s) => (
          <li key={s.site} className="site-check">
            <span className={`pill ${s.ok == null ? '' : s.ok ? 'ok' : 'out'}`}>{s.ok == null ? 'Not checked' : s.ok ? 'OK' : 'Not working'}</span>
            <span className="grow">
              <span className="item-title">{s.site}</span>
              <span className="item-meta">{s.used_for}</span>
              {s.detail && <span className={`item-meta${s.ok ? '' : ' site-check-error'}`}>
                {s.ok ? s.detail : `${s.detail}${s.failing_since ? ` (since ${shortDate(s.failing_since.slice(0, 10))})` : ''}`}</span>}
            </span>
          </li>
        ))}
      </ul>
      <button type="button" className="secondary small" disabled={data.running}
        onClick={() => api.runSiteChecks().then(() => setData({ ...data, running: true })).catch((e) => setError(e.message))}>
        {data.running ? 'Checking...' : 'Check now'}
      </button>
    </div>
  )
}

// Home: a quiet warning when a site the app reads has stopped working (nothing when all is well).
export function SiteCheckWarning() {
  const { refreshKey, openPanel } = useApp()
  const [failing, setFailing] = useState([])
  useEffect(() => {
    api.siteChecks().then((d) => setFailing(d.sites.filter((s) => s.ok === false))).catch(() => setFailing([]))
  }, [refreshKey])
  if (failing.length === 0) return null
  return (
    <p className="alert low site-check-warning">
      {failing.map((s) => s.site).join(', ')} {failing.length === 1 ? 'has' : 'have'} changed: look-ups there may not
      work. <button type="button" className="plain small" onClick={() => openPanel('settings')}>See Settings › Lookup sites</button>
    </p>
  )
}
