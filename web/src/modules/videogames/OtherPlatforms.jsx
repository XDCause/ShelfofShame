import { useEffect, useState, useSyncExternalStore } from 'react'
import { Link } from 'react-router'
import { api, timeAgo } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { playtime } from './steam.jsx'

// Epic and Ubisoft games, from the user's Exophase profile (api/app/othergames.py). They use the
// Steam Games table and game panel (shaped like Steam games, ids like "ubisoft-12"); this file has
// the platform toggles for the dashboard, stats and games, and the dashboard card. (Adding an Epic
// or Ubisoft game is in Find a game.)

export const PLATFORMS = [['steam', 'Steam'], ['epic', 'Epic'], ['ubisoft', 'Ubisoft']]

// Which platforms the dashboard and stats count: null = all of them (the default). Kept while you
// move between pages; a reload goes back to all.
let counting = null
const listeners = new Set()
const setCounting = (next) => { counting = next; listeners.forEach((l) => l()) }
export function useCounting() {
  const value = useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l) }, () => counting)
  return [value, setCounting]
}

// "Counting: Steam Epic Ubisoft" toggles above the dashboard, stats and games (only platforms you have
// games on; at least one stays on; "All" turns them all back on). Steam alone matches SteamHunters' numbers.
export function PlatformToggles({ available }) {
  const [chosen, setChosen] = useCounting()
  if (!available || available.length < 2) return null
  const on = new Set(chosen ?? available)
  const all = available.every((p) => on.has(p))
  // With every platform on, a tap means "just this one"; after that, taps add or take away.
  const flip = (id) => {
    if (all) return setChosen([id])
    const next = new Set(on)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    if (next.size === 0) return
    setChosen(available.every((p) => next.has(p)) ? null : available.filter((p) => next.has(p)))
  }
  return (
    <div className="chip-row platform-toggles" role="group" aria-label="Platforms to count">
      <span className="muted small">Counting</span>
      {PLATFORMS.filter(([id]) => available.includes(id)).map(([id, label]) => (
        <button key={id} type="button" className="chip-filter" aria-pressed={on.has(id)} onClick={() => flip(id)}
          disabled={on.has(id) && on.size === 1} title={on.has(id) && on.size === 1 ? 'At least one platform stays on' : undefined}>
          {label}</button>
      ))}
      {!all && <button type="button" className="plain small" onClick={() => setChosen(null)}>All</button>}
      {chosen?.length === 1 && chosen[0] === 'steam' && <span className="muted small">· matches SteamHunters</span>}
    </div>
  )
}

// Everything about the other platforms, reloaded whenever something changes.
export function useOtherGames() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [account, setAccount] = useState(null)
  useEffect(() => {
    api.otherGames().then(setData).catch(() => setData({ games: [], platforms: [] }))
    api.otherAccount().then(setAccount).catch(() => {})
  }, [refreshKey])
  return { data, account }
}

// The dashboard card: Epic and Ubisoft at a glance - or the form to connect Exophase.
export function OtherPlatformsCard() {
  const { data, account } = useOtherGames()
  if (!data || !account) return null
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Epic and Ubisoft</h2>
      {!account.profile ? <ExophaseConnect /> : (
        <>
          {data.platforms.length === 0 ? <p className="muted small">No Epic or Ubisoft games on your Exophase profile.</p> : (
            <ul className="list plain-list">
              {data.platforms.map((p) => {
                const percent = p.total ? Math.round((100 * p.done) / p.total) : 0
                return (
                  <li key={p.platform}>
                    <Link className="row-button" to={`/videogames/games?platform=${p.platform}`}>
                      <span className={`pill ${p.platform === 'ubisoft' ? 'teal' : 'purple'}`}>{p.name}</span>
                      <span className="grow">
                        <span className="item-title">{p.games} games · {p.done.toLocaleString()} of {p.total.toLocaleString()} achievements</span>
                        <span className="item-meta">{percent}%{p.perfect > 0 && ` · ${p.perfect} at 100%`}
                          {p.playtime_minutes > 0 && ` · ${playtime(p.playtime_minutes)}`}
                          {p.to_fill_in > 0 && ` · ${p.to_fill_in} to fill in`}</span>
                        <span className="fill-bar tint" aria-hidden="true"><span style={{ width: `${percent}%` }} /></span>
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
          <p className="hint">From Exophase ({account.profile}){account.synced_at && `, read ${timeAgo(account.synced_at)}`}.
            {account.error && ` Last try: ${account.error}`} Kept apart from your Steam numbers.</p>
        </>
      )}
    </section>
  )
}

function ExophaseConnect() {
  const { changed } = useApp()
  const [profile, setProfile] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const connect = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.setOtherAccount(profile)
      changed()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={connect}>
      <p className="small muted">Add your Epic and Ubisoft games from your Exophase profile (with those platforms linked
        there). Epic achievements come in by themselves; Ubisoft's you type in.</p>
      <div className="lookup-row">
        <input value={profile} onChange={(e) => setProfile(e.target.value)} required placeholder="Exophase name or profile link"
          aria-label="Exophase name or profile link" />
        <button type="submit" className="primary" disabled={busy || !profile.trim()}>{busy ? 'Reading...' : 'Connect'}</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}
