import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useApp } from '../core/app-context.js'

// How the app itself is doing (api/app/system.py, 2026-10-21): backups and their weekly test restore, the Google
// Drive copy, the Steam sync, the website check, disk space and updates. Settings > System lists them all; Home
// shows only what needs a look (nothing when all is well).
const PILL = { ok: ['ok', 'OK'], warn: ['low', 'Look'], bad: ['out', 'Problem'], off: ['', 'Off'] }

export default function SystemStatus() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [asked, setAsked] = useState([])          // the failing websites Check now is asking again
  const [checkedAt, setCheckedAt] = useState(null)
  const poll = useRef(null)
  // Read it all; while a website re-check runs, again every 2 seconds until it's done.
  const load = (fromCheck = false) => api.system().then((d) => {
    setData(d)
    setError('')
    clearTimeout(poll.current)
    if (d.checking) poll.current = setTimeout(() => load(fromCheck), 2000)
    else if (fromCheck) { setBusy(false); setCheckedAt(new Date()) }
  }).catch((e) => { setError(e.message); setBusy(false) })
  // Load once when the section opens (load re-polls itself while a re-check runs); stop polling on close.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); return () => clearTimeout(poll.current) }, [])

  const checkNow = async () => {
    setBusy(true)
    setCheckedAt(null)
    try {
      setAsked((await api.checkSystem()).rechecking)
      load(true)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const said = busy ? (asked.length ? `Asking ${asked.join(', ')} again...` : '')
    : checkedAt ? `Checked at ${checkedAt.toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}.` : ''

  if (!data) return error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>
  return (
    <>
      <div className="button-row sys-check-now">
        <button type="button" className="secondary" onClick={checkNow} disabled={busy}>{busy ? 'Checking...' : 'Check now'}</button>
        <span className="small muted" role="status">{said}</span>
      </div>
      {error && <p className="alert error small">{error}</p>}
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
      <p className="hint">Check now reads everything again and asks any failing website once more. The full website check
        (every site) is under Lookup sites.</p>
    </>
  )
}

// Home: one line when something needs a look (a backup that's late or failed, a failed test restore...).
// (Home shows it behind the "!" by "Write today's entry": HomeAttention.)
export function useSystemAttention() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => { api.system().then(setData).catch(() => setData(null)) }, [refreshKey])
  return data?.attention?.length ? data : null
}

// data = useSystemAttention()'s answer.
export function SystemWarning({ data, onOpen }) {
  const { openPanel } = useApp()
  if (!data) return null
  return (
    <p className={`alert ${data.worst === 'bad' ? 'error' : 'low'} sys-warning`} role="status">
      {data.attention.map((c) => `${c.label}: ${c.detail}`).join(' · ')}.{' '}
      <button type="button" className="plain small" onClick={() => { onOpen?.(); openPanel('settings', { section: 'system' }) }}>Open the System panel ›</button>
    </p>
  )
}
