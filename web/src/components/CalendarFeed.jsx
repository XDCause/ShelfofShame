import { useEffect, useState } from 'react'
import { api } from '../api.js'

// Settings > Calendar feed (api/app/calendar_feed.py): your events and trips in your phone's calendar app. The address
// carries its own secret key (a calendar app can't sign in): turn it on, copy it, subscribe on the phone. "New address"
// stops the old one working (if it was ever shared by mistake); Off stops the feed.
export default function CalendarFeed() {
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  useEffect(() => { api.calendarFeed().then(setState).catch((e) => setError(e.message)) }, [])
  const run = async (fn) => {
    setError('')
    setCopied(false)
    try { setState(await fn()) } catch (e) { setError(e.message) }
  }
  if (!state) return error ? <p className="alert error small">{error}</p> : <p className="muted small">Loading...</p>
  const url = state.path && `${window.location.origin}${state.path}`
  const copy = () => navigator.clipboard?.writeText(url).then(() => setCopied(true)).catch(() => setError("Couldn't copy - select the address instead."))
  return (
    <div className="cal-feed">
      <p className="muted small">Your calendar's events (a month back to a year ahead) and your trips, in your phone's own calendar app. It
        checks for changes by itself every so often.</p>
      {!state.on ? (
        <button type="button" className="primary" onClick={() => run(api.calendarFeedOn)}>Turn on the calendar feed</button>
      ) : (
        <>
          <label className="field wide"><span className="field-label">Your private address</span>
            <input readOnly value={url} onFocus={(e) => e.target.select()} aria-label="Calendar feed address" /></label>
          <div className="button-row">
            <button type="button" className="secondary" onClick={copy}>{copied ? 'Copied ✓' : 'Copy'}</button>
            <a className="button secondary" href={url.replace(/^https?:/, 'webcal:')}>Subscribe on this device</a>
            <button type="button" className="plain" onClick={() => run(api.calendarFeedOn)}>New address</button>
            <button type="button" className="plain destructive" onClick={() => run(async () => { await api.calendarFeedOff(); return { on: false, path: null } })}>Turn off</button>
          </div>
          <ul className="muted small cal-feed-how">
            <li>iPhone: Settings › Calendar › Calendar Accounts › Add Account › Other › Add Subscribed Calendar, and paste it.</li>
            <li>Android: an app such as ICSx⁵ subscribes to it for the phone's calendar.</li>
            <li>It works where the app does - at home or over Tailscale. Google Calendar's own servers can't reach it, so subscribe on the
              phone itself, not in Google Calendar on the web.</li>
            <li>Anyone with this address can read your calendar: keep it to your own devices. New address cuts off the old one.</li>
          </ul>
        </>
      )}
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}
