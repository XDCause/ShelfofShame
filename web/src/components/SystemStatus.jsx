import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useApp } from '../core/app-context.js'

// How the app itself is doing (api/app/system.py, 2026-10-21): backups and their weekly test restore, the Google
// Drive copy, the Steam sync, the website check, disk space and updates. Settings > System lists them all; Home
// shows only what needs a look (nothing when all is well).
const PILL = { ok: ['ok', 'OK'], warn: ['low', 'Look'], bad: ['out', 'Problem'], off: ['', 'Off'] }

export default function SystemStatus() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.system().then(setData).catch((e) => setError(e.message)) }, [])
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted">Loading...</p>
  return (
    <ul className="list plain-list sys-checks">
      {data.checks.map((c) => (
        <li key={c.key} className="sys-check">
          <span className={`pill ${PILL[c.state][0]}`}>{PILL[c.state][1]}</span>
          <span className="grow">
            <span className="item-title">{c.label}</span>
            <span className="item-meta">{c.detail}</span>
            {c.fix && <span className="item-meta sys-fix">{c.fix}</span>}
          </span>
        </li>
      ))}
    </ul>
  )
}

// Home: one line when something needs a look (a backup that's late or failed, a failed test restore...).
export function SystemWarning() {
  const { refreshKey, openPanel } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => { api.system().then(setData).catch(() => setData(null)) }, [refreshKey])
  if (!data?.attention?.length) return null
  return (
    <p className={`alert ${data.worst === 'bad' ? 'error' : 'low'} sys-warning`} role="status">
      {data.attention.map((c) => `${c.label}: ${c.detail}`).join(' · ')}.{' '}
      <button type="button" className="plain small" onClick={() => openPanel('settings')}>Open the System panel ›</button>
    </p>
  )
}
