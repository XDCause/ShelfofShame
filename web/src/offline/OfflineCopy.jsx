import { useEffect, useState } from 'react'
import { shortDate } from '../api.js'
import { offlinePossible, offlineStatus, turnOfflineOff, turnOfflineOn } from './offline.js'
import { onSaveProgress, saveEverything, saveProgress } from './saveAll.js'

const at = (iso) => `${shortDate(iso)}, ${new Date(iso).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}`
const megabytes = (bytes) => `${Math.max(1, Math.round(bytes / 1048576))} MB`

// Settings > Offline copy: a copy of the app and your data on this device, for when the PC at home can't be reached.
export default function OfflineCopy() {
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState(null)
  const [progress, setProgress] = useState(saveProgress)
  const load = () => offlineStatus().then(setStatus).catch((e) => setMessage({ type: 'error', text: e.message }))
  useEffect(() => {
    load()
    return onSaveProgress(setProgress)
  }, [])

  const run = async (what, work, done) => {
    setBusy(what)
    setMessage(null)
    try {
      const result = await work()
      if (done) setMessage({ type: 'ok', text: done(result) })
    } catch (e) {
      setMessage({ type: 'error', text: /certificate/i.test(e.message)
        ? "This device doesn't trust the app's certificate yet, and a browser only keeps an offline copy for a site it " +
          'trusts. Install it from http://<this PC>:8080/ca.crt (README > Signing in and HTTPS), then try again.'
        : e.message })
    } finally {
      setBusy('')
      load()
    }
  }
  const save = () => run('save', saveEverything, (r) => r && `Saved: ${r.pages} pages and everything they show.`)
  const flip = (e) => e.target.checked
    ? run('on', async () => { await turnOfflineOn(); return saveEverything() },
      (r) => r && `On, and saved: ${r.pages} pages. Everything you open from now on is kept up to date too.`)
    : run('off', turnOfflineOff, () => 'Off: the copy on this device is gone.')

  if (!offlinePossible()) {
    return <p className="hint">This browser can't keep an offline copy here: it needs the app's https:// address, with
      the app's certificate trusted on this device.</p>
  }
  if (!status) return <p className="muted small">Loading...</p>
  return (
    <div className="offline-copy">
      <label className="tick-row">
        <input type="checkbox" checked={busy === 'on' || (status.on && busy !== 'off')} disabled={Boolean(busy || progress)}
          onChange={flip} />
        Keep a copy on this device
      </label>
      <p className="hint">For when the PC at home can't be reached (off, asleep, restarting for an update): this device
        shows the copy instead, read-only. Changes wait until the app is back.</p>
      {(status.on || busy === 'on') && (
        <>
          <p className="small">
            Everything saved: <strong>{status.savedAt ? at(status.savedAt) : 'not yet'}</strong>
            {status.bytes != null && <> · {megabytes(status.bytes)} on this device</>}
          </p>
          <div className="button-row">
            <button type="button" className="secondary" onClick={save} disabled={Boolean(busy || progress)}>
              {progress ? 'Saving...' : 'Save everything now'}</button>
          </div>
          {progress && (
            <div className="offline-progress" role="status">
              <progress value={progress.done} max={progress.total || 1} aria-label="Saving for offline" />
              <span className="small muted">{progress.total ? `${progress.done + 1} of ${progress.total}: ${progress.label}` : progress.label}</span>
            </div>
          )}
          <p className="hint">Pages you open are kept up to date as you go. Before a trip, press Save everything now.
            {!status.kept && ' The browser may clear the copy if this device runs low on space; on an iPhone, add the app to the Home Screen (Share > Add to Home Screen), sign in there and turn this on there.'}</p>
        </>
      )}
      {message && <p className={`alert ${message.type} small`} role={message.type === 'error' ? 'alert' : 'status'}>{message.text}</p>}
    </div>
  )
}
