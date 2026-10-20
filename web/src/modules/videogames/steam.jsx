import { useEffect, useState } from 'react'
import { api, duration, timeAgo } from '../../api.js'
import { GamepadIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// Shared bits of the Video games hobby: the Steam account and sync, rarity, completion bars.

// How rare an achievement is: the share of all players who have it.
export const rarity = (percent) => {
  if (percent == null) return null
  const p = Number(percent)
  return { text: `${p < 1 ? p.toFixed(1) : Math.round(p)}%`, tone: p <= 5 ? 'low' : p <= 20 ? 'purple' : 'tint',
    label: p <= 5 ? 'Ultra rare' : p <= 20 ? 'Rare' : null }
}

// An asterisk after a game's progress when you ticked its achievements yourself (a Ubisoft game, or an Epic one
// added by hand using its Steam version's list) - the platform doesn't sync them.
export const HandTicked = ({ game }) => (game?.by_hand ? (
  <span className="hand-ticked" title={`Ticked off by you - ${game.platform === 'ubisoft' ? 'Ubisoft' : 'Epic'} doesn't sync these${
    game.counted === false ? '; not counted in your totals' : ''}`}>*</span>) : null)

// Playtime as hours and minutes: "45 min", "3 h 5 min", "1,204 h 12 min".
export const playtime = (minutes) => {
  const m = Math.max(0, Math.round(minutes ?? 0))
  if (m < 60) return duration(m)
  return `${Math.floor(m / 60).toLocaleString()} h${m % 60 ? ` ${m % 60} min` : ''}`
}

// A game's picture from Steam; if Steam has none (or it won't load), a gamepad in its place.
export function GamePicture({ game, className }) {
  const [failed, setFailed] = useState(false)
  if (!game.header_url || failed) {
    return <span className={`${className} game-picture-missing`} aria-hidden="true"><GamepadIcon size={22} /></span>
  }
  return <img className={className} src={game.header_url} alt="" loading="lazy" referrerPolicy="no-referrer"
    onError={() => setFailed(true)} />
}

// A game's completion as a bar (green once it's 100%).
export function CompletionBar({ game }) {
  if (!game.achievements_total) return null
  const percent = Number(game.percent ?? 0)
  return (
    <span className={percent === 100 ? 'fill-bar ok' : 'fill-bar tint'} aria-hidden="true">
      <span style={{ width: `${percent}%` }} />
    </span>
  )
}

// The tracked Steam account and the sync running now; while a sync runs, it checks every two
// seconds and tells every page when it's finished (so they reload).
export function useSteamAccount() {
  const { refreshKey, changed } = useApp()
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.steamAccount().then(setAccount).catch((e) => setError(e.message)) }, [refreshKey])
  const running = account?.sync?.running
  useEffect(() => {
    if (!running) return undefined
    const t = setInterval(() => {
      api.steamAccount().then((a) => {
        setAccount(a)
        if (!a.sync.running) changed()
      }).catch(() => {})
    }, 2000)
    return () => clearInterval(t)
  }, [running, changed])
  return { account, setAccount, error }
}

// The dashboard / Home numbers: every platform, or only `platforms` (a list) when given.
export function useSteamSummary(platforms = null) {
  const { refreshKey } = useApp()
  return useShared(`videogames-summary-${platforms ?? 'all'}-${refreshKey}`, () => api.videoGameSummary(platforms))
}

// "Synced 5 min ago · Sync now", or the sync's progress, or what went wrong.
export function SyncBar({ account, setAccount }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const sync = account.sync
  const start = async (full) => {
    setBusy(true)
    setError('')
    try {
      setAccount({ ...account, sync: (await api.syncSteam(full)).sync })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="sync-bar card">
      <span className="grow">
        <strong>{account.persona_name ?? account.profile}</strong>
        {sync.running ? (
          <span className="item-meta">
            {sync.message}{sync.total > 0 && ` (${sync.done} of ${sync.total})`}
            {sync.total > 0 && <span className="fill-bar tint"><span style={{ width: `${(100 * sync.done) / sync.total}%` }} /></span>}
          </span>
        ) : (
          <span className="item-meta">{account.last_sync_at ? `Synced ${timeAgo(account.last_sync_at)}` : 'Not synced yet'}
            {' · syncs by itself once a day'}</span>
        )}
      </span>
      {!sync.running && (
        <span className="button-row">
          <button type="button" className="primary" onClick={() => start(false)} disabled={busy}>Sync now</button>
          <button type="button" className="plain small" onClick={() => start(true)} disabled={busy}
            title="Read every game again, not just the ones played since the last sync">Full sync</button>
        </span>
      )}
      {(error || sync.error || account.last_error) && !sync.running && (
        <p className="alert error small sync-error">{error || sync.error || account.last_error}</p>
      )}
    </div>
  )
}

// A small "Sync now" for the Games page's toolbar: while a sync runs it shows how far it's got, and
// the list reloads by itself when it finishes (useSteamAccount calls changed()).
export function SyncButton() {
  const { showToast } = useApp()
  const { account, setAccount } = useSteamAccount()
  const [busy, setBusy] = useState(false)
  if (!account?.steam_id) return null
  const sync = account.sync
  const start = async () => {
    setBusy(true)
    try {
      setAccount({ ...account, sync: (await api.syncSteam(false)).sync })
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <button type="button" className="secondary" onClick={start} disabled={busy || sync.running}
      title={account.last_sync_at ? `Synced ${timeAgo(account.last_sync_at)}` : 'Not synced yet'}>
      {sync.running ? `Syncing${sync.total > 0 ? ` ${sync.done} of ${sync.total}` : ''}...` : 'Sync now'}
    </button>
  )
}

// First time: which Steam profile to follow.
export function SteamSetup({ account, setAccount }) {
  const [profile, setProfile] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!account.has_key) {
    return (
      <div className="card empty">
        <p><strong>No Steam API key yet.</strong></p>
        <p className="muted">Add <code>STEAM_API_KEY=...</code> to the <code>.env</code> file in the project folder
          (get one free at steamcommunity.com/dev/apikey), then rebuild the app.</p>
      </div>
    )
  }
  const connect = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setAccount(await api.setSteamProfile(profile))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="card steam-setup" onSubmit={connect}>
      <h2 className="home-card-title">Connect your Steam profile</h2>
      <p className="muted small">Your profile name (the part after /id/ in its address), its 17-digit id, or the whole
        address. Your profile's <strong>Game details</strong> must be Public.</p>
      <div className="lookup-row">
        <input value={profile} onChange={(e) => setProfile(e.target.value)} placeholder="e.g. SomeGamer"
          aria-label="Steam profile" required />
        <button type="submit" className="primary" disabled={busy || !profile.trim()}>{busy ? 'Connecting...' : 'Connect'}</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}
