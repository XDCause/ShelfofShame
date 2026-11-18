import { useEffect, useRef, useState } from 'react'
import { api, backupUrl, exportUrl, shortDate } from '../api.js'
import Security from '../core/auth/Security.jsx'
import CalendarFeed from './CalendarFeed.jsx'
import { LOOKS, readLook, setLook } from '../core/look.js'
import { readTheme, setTheme, THEMES } from '../core/theme.js'
import OfflineCopy from '../offline/OfflineCopy.jsx'
import Drawer from './Drawer.jsx'
import Fold from './Fold.jsx'
import { LookupList } from './ListsManager.jsx'
import { BookIcon, CalendarIcon, CartIcon, CoinsIcon, DatabaseIcon, DownloadIcon, GlobeIcon, KeyIcon, ListIcon,
  PaletteIcon, PersonIcon, PhoneIcon, PulseIcon, SearchIcon, TagIcon } from './icons.jsx'
import PriceGuide from './PriceGuide.jsx'
import SiteChecks from './SiteChecks.jsx'
import SystemStatus from './SystemStatus.jsx'
import Spending from './Spending.jsx'

// Settings, opened from the gear (regrouped 2026-11-16): six groups, each a card of rows with an icon, and a box to
// find a setting by name or by what it's for. Every row is closed until you tap it (and loads nothing until then);
// section opens one row (Home's "Open the System panel" -> 'system').
export default function SettingsPanel({ lookups, settings, onClose, onSettings, onListsChanged, section }) {
  const [query, setQuery] = useState('')
  const status = useStatus()
  const groups = settingsGroups({ lookups, settings, onSettings, onListsChanged, status })
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  const matches = (text) => words.every((w) => text.toLowerCase().includes(w))
  const shown = groups.map((g) => ({
    ...g, rows: words.length && !matches(g.title) ? g.rows.filter((r) => matches(`${r.title} ${r.words}`)) : g.rows,
  })).filter((g) => g.rows.length)
  const only = words.length > 0 && shown.length === 1 && shown[0].rows.length === 1
  return (
    <Drawer title="Settings" onClose={onClose}>
      <div className="settings">
        <label className="set-find">
          <SearchIcon size={18} />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a setting"
            aria-label="Find a setting" />
        </label>
        {shown.map((g) => (
          <section key={g.key} className="set-group" style={{ '--set-hue': g.hue }} aria-labelledby={`set-${g.key}`}>
            <h3 className="set-group-title" id={`set-${g.key}`}>{g.title}</h3>
            <p className="set-group-note">{g.note}</p>
            <div className="set-rows">
              {g.rows.map((r) => (
                <Fold key={`${r.key}${only ? '-only' : ''}`} title={r.title} detail={r.detail}
                  className={`set-row ${r.className ?? ''}`} lead={<span className="set-icon">{r.icon}</span>}
                  open={section === r.key || only}>
                  {r.body}
                </Fold>
              ))}
            </div>
          </section>
        ))}
        {!shown.length && <p className="muted set-none">No setting matches "{query.trim()}".</p>}
      </div>
    </Drawer>
  )
}

const LISTS = [
  { kind: 'brands', title: 'Brands', placeholder: 'New brand' },
  { kind: 'categories', title: 'Categories', placeholder: 'New category' },
  { kind: 'locations', title: 'Storage locations', placeholder: 'New location' },
]

// The six groups. words: what else you might search for to find a row.
function settingsGroups({ lookups, settings, onSettings, onListsChanged, status }) {
  const look = LOOKS.find(([k]) => k === readLook())?.[1]
  const theme = THEMES.find(([k]) => k === readTheme())?.[1].toLowerCase()
  return [
    { key: 'device', title: 'This device', hue: '#3f7f5a', note: 'Remembered on this phone or computer only.', rows: [
      { key: 'look', title: 'Look and theme', detail: `${look}, ${theme}`, icon: <PaletteIcon />,
        words: 'appearance light dark system botanical journal colour color', body: <LookAndTheme /> },
      { key: 'offline', title: 'Offline copy', detail: 'for when the PC is off', icon: <PhoneIcon />,
        words: 'travel away read-only save phone', body: <OfflineCopy /> },
    ] },
    { key: 'you', title: 'You', hue: '#7a52b3', note: 'Your name, how you sign in, your calendar.', rows: [
      { key: 'name', title: 'Name and banners', detail: settings.your_name || 'not set', icon: <PersonIcon />,
        words: 'greeting home picture photo banner appearance',
        body: <NameAndBanners settings={settings} onSettings={onSettings} /> },
      { key: 'security', title: 'Security', detail: 'sign-in, devices', icon: <KeyIcon />,
        words: 'password passkey authenticator totp sign out devices sessions', body: <Security /> },
      { key: 'feed', title: 'Calendar feed', detail: "for your phone's calendar", icon: <CalendarIcon />,
        words: 'ics subscribe google apple outlook', body: <CalendarFeed /> },
    ] },
    { key: 'shopping', title: 'Shopping', hue: '#b0611f', note: 'Where you buy, what things cost, what you spent.', rows: [
      { key: 'shop', title: 'Default shop', detail: settings.default_shop || 'none', icon: <CartIcon />,
        words: 'store wishlist buy', body: <DefaultShop settings={settings} onSettings={onSettings} /> },
      { key: 'prices', title: 'Price guide', detail: 'your usual prices', icon: <TagIcon />,
        words: 'cost price', body: <PriceGuide lookups={lookups} /> },
      { key: 'spending', title: 'Spending', detail: 'what went where', icon: <CoinsIcon />,
        words: 'money spent cost total', body: <Spending /> },
      { key: 'catalogue', title: 'Tamiya catalogue', detail: 'for Shop Tamiya', icon: <BookIcon />,
        words: 'catalog products new releases refresh', body: <Catalogue /> },
    ] },
    { key: 'lists', title: 'Lists', hue: '#24806a', note: 'The choices offered when you add or edit a supply.', rows:
      LISTS.map((l) => ({ key: l.kind, title: l.title, detail: lookups[l.kind].length, icon: <ListIcon />,
        className: 'lookup', words: 'choices manage add remove',
        body: <LookupList {...l} items={lookups[l.kind]} onChanged={onListsChanged} /> })) },
    { key: 'data', title: 'Your data', hue: '#2d68ad', note: 'Kept safe every night; yours to take away any time.', rows: [
      { key: 'backups', title: 'Backups', detail: status.backup, icon: <DatabaseIcon />,
        words: 'restore google drive download', body: <Backups /> },
      { key: 'exports', title: 'Export to CSV', detail: 'for Excel', icon: <DownloadIcon />,
        words: 'excel spreadsheet download csv', body: <Exports /> },
    ] },
    { key: 'app', title: 'Behind the scenes', hue: '#5f6874', note: 'How the app and its outside sources are doing.', rows: [
      { key: 'system', title: 'System', detail: status.system, icon: <PulseIcon />,
        words: 'health syncs disk updates steam drive status', body: <SystemStatus /> },
      { key: 'sites', title: 'Lookup sites', detail: 'checked weekly', icon: <GlobeIcon />,
        words: 'websites check shops', body: <SiteChecks /> },
    ] },
  ]
}

// What the System and Backups rows say while closed: how things are, at a glance.
function useStatus() {
  const [system, setSystem] = useState(null)
  const [backup, setBackup] = useState(null)
  useEffect(() => {
    api.system().then((d) => setSystem(d.attention?.length
      ? <span className={`pill ${d.worst === 'bad' ? 'out' : 'low'}`}>{d.attention.length} to look at</span>
      : 'all OK')).catch(() => {})
    api.backups().then((d) => setBackup(!d.available ? null : d.backups?.[0] ? `last ${shortDate(d.backups[0].created_at)}`
      : 'none yet')).catch(() => {})
  }, [])
  return { system: system ?? 'syncs, disk, updates', backup: backup ?? 'every night' }
}

// Light, dark, or whatever the device is set to, and the look (both remembered on this device).
export function LookAndTheme() {      // (exported for its tests)
  const [choice, setChoice] = useState(readTheme)
  const [look, setLookChoice] = useState(readLook)
  return (
    <>
      <p className="set-label" id="set-look-label">Look</p>
      <div className="segmented settings-look" role="group" aria-labelledby="set-look-label">
        {LOOKS.map(([key, label]) => (
          <button key={key} type="button" aria-pressed={look === key}
            onClick={() => { setLookChoice(key); setLook(key) }}>{label}</button>
        ))}
      </div>
      <p className="hint">Botanical: the pine sidebar and landscape banners. Journal: a hobby notebook, paper and ink, with
        its tabs along the top.</p>
      <p className="set-label" id="set-theme-label">Theme</p>
      <div className="segmented" role="group" aria-labelledby="set-theme-label">
        {THEMES.map(([key, label]) => (
          <button key={key} type="button" aria-pressed={choice === key}
            onClick={() => { setChoice(key); setTheme(key) }}>{label}</button>
        ))}
      </div>
      <p className="hint">System follows your device's light or dark setting.</p>
    </>
  )
}

// The name Home greets, and the Picture button on banners.
export function NameAndBanners({ settings, onSettings }) {      // (exported for its tests)
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
      <label className="field settings-name">
        <span className="field-label">Your name</span>
        <input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} onBlur={save}
          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()} placeholder="For Home's greeting" />
      </label>
      <p className="hint">Home says "Good morning, {name.trim() || 'you'}". {saved}</p>
      <BannerPictures settings={settings} onSettings={onSettings} />
    </>
  )
}

// The Picture button on every page's banner: off unless you want to change a picture (pictures you chose show either way).
function BannerPictures({ settings, onSettings }) {
  const [error, setError] = useState('')
  const [on, setOn] = useState(settings.banner_pictures === 'on')   // ticks at once; back again if it couldn't save
  const flip = async () => {
    const want = !on
    setOn(want)
    try {
      onSettings(await api.updateSettings({ banner_pictures: want ? 'on' : 'off' }))
      setError('')
    } catch (e) {
      setOn(!want)
      setError(e.message)
    }
  }
  return (
    <>
      <label className="tick-row">
        <input type="checkbox" checked={on} onChange={flip} /> Picture button on banners
      </label>
      <p className="hint">Turn on to put a photo of your own behind a page's banner (or move it, or go back to the drawing);
        turn off again when you're done. {error}</p>
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

export function Backups() {      // (exported for its tests)
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
        {' '}Every night at 8 pm; the newest {data.keep} are kept.
      </p>
      <div className="button-row">
        <button type="button" className="primary" onClick={backUp} disabled={busy}>{busy ? 'Backing up...' : 'Back up now'}</button>
        {latest && <a className="button secondary" href={backupUrl(latest.name)} download>Download latest</a>}
      </div>
      {message && <p className={`alert ${message.type} small`}>{message.text}</p>}
      <p className="hint">Each backup is checked, and also goes to Google Drive, encrypted - Behind the scenes › System shows how that's going.</p>
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
  ['model-paints', 'Model paint lists'], ['builds', 'Build sessions (time)'], ['paint-recipes', 'Paint recipes'], ['history', 'Stock history'],
  ['video-games', 'Video games'], ['video-game-achievements', 'Video game achievements'], ['video-game-playtime', 'Video game playtime (per day)'],
  ['golf-rounds', 'Golf rounds'], ['golf-holes', 'Golf scores hole by hole'],
  ['scuba-dives', 'Scuba dives'], ['scuba-sightings', 'Scuba sightings (life list)'],
  ['fishing-trips', 'Fishing trips'], ['fishing-catches', 'Fishing catches'],
  ['language-cards', 'Language cards'], ['language-study', 'Language study log'],
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
