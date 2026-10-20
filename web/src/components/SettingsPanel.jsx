import { useEffect, useRef, useState } from 'react'
import { api, backupUrl, exportUrl, shortDate } from '../api.js'
import Security from '../core/auth/Security.jsx'
import { readTheme, setTheme, THEMES } from '../core/theme.js'
import Drawer from './Drawer.jsx'
import Fold from './Fold.jsx'
import ListsManager from './ListsManager.jsx'
import PriceGuide from './PriceGuide.jsx'
import SiteChecks from './SiteChecks.jsx'
import Spending from './Spending.jsx'

// Settings, opened from the gear: every section is closed until you tap it.
export default function SettingsPanel({ lookups, settings, onClose, onSettings, onListsChanged }) {
  return (
    <Drawer title="Settings" onClose={onClose}>
      <div className="settings">
        <Fold title="Appearance" detail={THEMES.find(([k]) => k === readTheme())?.[1]}>
          <Appearance settings={settings} onSettings={onSettings} />
        </Fold>
        <Fold title="Security" detail="sign-in, devices"><Security /></Fold>
        <Fold title="Spending"><Spending /></Fold>
        <Fold title="Price guide" detail="your usual prices"><PriceGuide lookups={lookups} /></Fold>
        <Fold title="Default shop" detail={settings.default_shop}>
          <DefaultShop settings={settings} onSettings={onSettings} />
        </Fold>
        <Fold title="Backups"><Backups /></Fold>
        <Fold title="Export to CSV" detail="for Excel"><Exports /></Fold>
        <Fold title="Tamiya catalogue" detail="for Shop Tamiya"><Catalogue /></Fold>
        <Fold title="Lookup sites" detail="checked weekly"><SiteChecks /></Fold>
        <ListsManager lookups={lookups} onChanged={onListsChanged} />
      </div>
    </Drawer>
  )
}

// Light, dark, or whatever the device is set to (remembered on this device), and the name Home greets.
function Appearance({ settings, onSettings }) {
  const [choice, setChoice] = useState(readTheme)
  const [name, setName] = useState(settings.your_name ?? '')
  const [saved, setSaved] = useState('')
  const save = async () => {
    if (name.trim() === (settings.your_name ?? '')) return
    try {
      onSettings(await api.updateSettings({ your_name: name }))
      setSaved('Saved ✓')
    } catch (e) {
      setSaved(e.message)
    }
  }
  return (
    <>
      <div className="segmented" role="group" aria-label="Appearance">
        {THEMES.map(([key, label]) => (
          <button key={key} type="button" aria-pressed={choice === key}
            onClick={() => { setChoice(key); setTheme(key) }}>{label}</button>
        ))}
      </div>
      <p className="hint">System follows your device's light or dark setting.</p>
      <label className="field settings-name">
        <span className="field-label">Your name</span>
        <input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} onBlur={save}
          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()} placeholder="For Home's greeting" />
      </label>
      <p className="hint">Home says "Good morning, {name.trim() || 'you'}". Each page's picture is changed from its banner (Picture). {saved}</p>
    </>
  )
}

function DefaultShop({ settings, onSettings }) {
  const [shop, setShop] = useState(settings.default_shop ?? '')
  const [saved, setSaved] = useState('')
  const save = async () => {
    if (shop.trim() === (settings.default_shop ?? '')) return
    try {
      onSettings(await api.updateSettings({ default_shop: shop }))
      setSaved('Saved ✓')
    } catch (e) {
      setSaved(e.message)
    }
  }
  return (
    <>
      <label className="field">
        <span className="field-label">Shop</span>
        <input value={shop} onChange={(e) => setShop(e.target.value)} onBlur={save}
          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()} placeholder="e.g. Hobbyrama" />
      </label>
      <p className="hint">Filled in when you buy from the wishlist or add something new. {saved}</p>
    </>
  )
}

function Backups() {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const load = () => api.backups().then(setData).catch((e) => setMessage({ type: 'error', text: e.message }))
  useEffect(() => { load() }, [])

  const backUp = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const made = await api.backUpNow()
      setMessage({ type: 'ok', text: `Backed up: ${made.name} (${Math.round(made.size / 1024)} KB).` })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  if (!data) return message ? <p className="alert error small">{message.text}</p> : <p className="muted small">Loading...</p>
  if (!data.available) return <p className="hint">The backups folder isn't connected to the app. Use backup.ps1 on the PC.</p>
  const [latest] = data.backups
  return (
    <>
      <p className="small">
        {latest ? <>Last backup: <strong>{shortDate(latest.created_at)}</strong>, {new Date(latest.created_at)
          .toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}</> : 'No backups yet.'}
        {' '}Every night at 2 am; the newest {data.keep} are kept.
      </p>
      <div className="button-row">
        <button type="button" className="primary" onClick={backUp} disabled={busy}>{busy ? 'Backing up...' : 'Back up now'}</button>
        {latest && <a className="button secondary" href={backupUrl(latest.name)} download>Download latest</a>}
      </div>
      {message && <p className={`alert ${message.type} small`}>{message.text}</p>}
      <p className="hint">Download one now and then and keep it off this PC (a USB stick, OneDrive), in case the PC dies.</p>
      {data.backups.length > 1 && (
        <Fold title="All backups" detail={data.backups.length} className="inner">
          <ul className="list compact">
            {data.backups.map((b) => (
              <li key={b.name}>
                <span className="grow">{shortDate(b.created_at)} {new Date(b.created_at)
                  .toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}</span>
                <span className="muted small">{Math.round(b.size / 1024)} KB</span>
                <a href={backupUrl(b.name)} download>Download</a>
              </li>
            ))}
          </ul>
        </Fold>
      )}
    </>
  )
}

const EXPORTS = [
  ['inventory', 'Inventory'], ['wishlist', 'Wishlist'], ['models', 'Models'],
  ['model-paints', 'Model paint lists'], ['history', 'Stock history'],
]

function Exports() {
  return (
    <>
      <ul className="list">
        {EXPORTS.map(([kind, label]) => (
          <li key={kind}><span className="grow">{label}</span><a href={exportUrl(kind)} download>Download CSV</a></li>
        ))}
      </ul>
      <p className="hint">Opens in Excel. Exports are copies: changing them doesn't change the app.</p>
    </>
  )
}

function Catalogue() {
  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const poll = useRef(null)
  const load = () => api.catalogInfo().then((i) => {
    setInfo(i)
    clearTimeout(poll.current)
    if (i.refresh.running) poll.current = setTimeout(load, 2000) // follow the refresh as it goes
  }).catch((e) => setError(e.message))
  // Load once when the section opens (load re-polls itself while a refresh runs); stop polling on close.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); return () => clearTimeout(poll.current) }, [])

  const refresh = async () => {
    setError('')
    try {
      await api.refreshCatalog()
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (!info) return <p className="muted small">{error || 'Loading...'}</p>
  const { refresh: r } = info
  return (
    <>
      <p className="small">
        <strong>{info.products}</strong> Tamiya products
        {info.imported_at && <>, last updated {shortDate(info.imported_at)}</>}.
      </p>
      <div className="button-row">
        <button type="button" className="secondary" onClick={refresh} disabled={r.running}>
          {r.running ? 'Refreshing...' : 'Refresh from tamiya.com'}
        </button>
        {r.running && <span className="small muted">{r.message}</span>}
      </div>
      {!r.running && r.message && !r.error && <p className="hint">{r.message}.</p>}
      {(r.error || error) && <p className="alert error small">{r.error || error}</p>}
      <p className="hint">Reads Tamiya's product lists for new releases: about 50 pages, 2 seconds apart (3 minutes). You can close this meanwhile.</p>
    </>
  )
}
