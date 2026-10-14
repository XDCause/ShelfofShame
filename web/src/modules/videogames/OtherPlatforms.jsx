import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate, timeAgo } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { GamepadIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { playtime } from './steam.jsx'

// Epic and Ubisoft games, from the user's Exophase profile (api/app/othergames.py). Kept apart from
// Steam: profile completion, the goal, streaks and the 7-day changes stay Steam-only. Ubisoft's
// achievements aren't visible to Exophase (it only sees Ubisoft's challenges), so they're typed in.

export const PLATFORMS = [['steam', 'Steam'], ['epic', 'Epic'], ['ubisoft', 'Ubisoft']]
const NAME = Object.fromEntries(PLATFORMS)

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

// Steam | Epic | Ubisoft above the Games page (only the platforms you have games on).
export function PlatformSwitch({ platform, setPlatform, platforms }) {
  const have = new Set(['steam', ...platforms.map((p) => p.platform)])
  if (have.size < 2) return null
  return (
    <div className="segmented platform-switch" role="group" aria-label="Platform">
      {PLATFORMS.filter(([id]) => have.has(id)).map(([id, label]) => (
        <button key={id} type="button" aria-pressed={platform === id} onClick={() => setPlatform(id)}>{label}</button>
      ))}
    </div>
  )
}

function OtherPicture({ game }) {
  const [failed, setFailed] = useState(false)
  if (!game.picture_url || failed) return <span className="other-pic game-picture-missing" aria-hidden="true"><GamepadIcon size={18} /></span>
  return <img className="other-pic" src={game.picture_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
}

function Progress({ game: g }) {
  if (g.total == null) {
    return <span className="item-meta">{g.platform === 'ubisoft' ? 'Add your achievements' : 'No achievements'}</span>
  }
  const percent = Number(g.percent ?? 0)
  return (
    <>
      <span className="item-meta">{g.done} of {g.total} · {percent}%{g.completed_at && ' · 100%'}</span>
      <span className={percent === 100 ? 'fill-bar ok' : 'fill-bar tint'} aria-hidden="true"><span style={{ width: `${percent}%` }} /></span>
    </>
  )
}

// One platform's games: search, the list (tap one to open it), and for Ubisoft "+ Add a game".
export function OtherGamesView({ platform, data, switcher }) {
  const { openPanel } = useApp()
  const [q, setQ] = useState('')
  const [showHidden, setShowHidden] = useState(false)
  const [adding, setAdding] = useState(false)
  const games = useMemo(() => (data?.games ?? [])
    .filter((g) => g.platform === platform && g.hidden === showHidden)
    .filter((g) => !q.trim() || g.name.toLowerCase().includes(q.trim().toLowerCase())), [data, platform, q, showHidden])
  const summary = data?.platforms.find((p) => p.platform === platform)
  return (
    <section className="page">
      {switcher}
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={`Search your ${NAME[platform]} games...`} aria-label={`Search your ${NAME[platform]} games`} />
        <button type="button" className="chip-filter" aria-pressed={showHidden} onClick={() => setShowHidden(!showHidden)}>Hidden</button>
        {platform === 'ubisoft' && <button type="button" className="secondary" onClick={() => setAdding(!adding)}>+ Add a Ubisoft game</button>}
      </div>
      {summary && (
        <p className="muted small">
          {summary.games} games · {summary.done.toLocaleString()} of {summary.total.toLocaleString()} achievements
          {summary.perfect > 0 && ` · ${summary.perfect} at 100%`}{summary.playtime_minutes > 0 && ` · ${playtime(summary.playtime_minutes)} played`}
          {platform === 'ubisoft' && ' · Ubisoft achievements are typed in: Exophase only sees Ubisoft\'s challenges.'}
        </p>
      )}
      {adding && <AddUbisoftGame onDone={() => setAdding(false)} />}
      {!data ? <p className="muted loading">Loading...</p> : games.length === 0 ? <p className="empty card">No games here.</p> : (
        <ul className="list other-games">
          {games.map((g) => (
            <li key={g.game_id}>
              <button type="button" className="row-button" onClick={() => openPanel('othergame', { id: g.game_id })}>
                <OtherPicture game={g} />
                <span className="grow">
                  <span className="item-title">{g.name}</span>
                  <Progress game={g} />
                </span>
                <span className="muted small other-hours">
                  {g.playtime_minutes ? playtime(g.playtime_minutes) : ''}
                  {g.last_played && <><br />{shortDate(g.last_played)}</>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function AddUbisoftGame({ onDone }) {
  const { changed, showToast } = useApp()
  const [f, setF] = useState({ name: '', done: '', total: '', hours: '' })
  const [error, setError] = useState('')
  const num = (v) => (v === '' ? null : Number(v))
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const game = await api.addOtherGame({ name: f.name, done: num(f.done), total: num(f.total), hours: num(f.hours) })
      changed()
      showToast(`Added ${game.name}`)
      onDone()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="card other-form" onSubmit={save}>
      <p className="small muted">For a Ubisoft game Exophase doesn't list. Its numbers are in Ubisoft Connect: the game's Achievements page.</p>
      <div className="other-fields">
        <label>Game<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required autoFocus /></label>
        <label>Achievements you have<input type="number" min="0" value={f.done} onChange={(e) => setF({ ...f, done: e.target.value })} /></label>
        <label>Achievements in the game<input type="number" min="0" value={f.total} onChange={(e) => setF({ ...f, total: e.target.value })} /></label>
        <label>Hours played<input type="number" min="0" step="0.5" value={f.hours} onChange={(e) => setF({ ...f, hours: e.target.value })} /></label>
      </div>
      <div className="button-row">
        <button type="submit" className="primary">Add</button>
        <button type="button" className="plain" onClick={onDone}>Cancel</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}

// One Epic or Ubisoft game: its numbers (Ubisoft's typed in here), its Exophase page, Hide.
export function OtherGamePanel({ id, onClose }) {
  const { changed } = useApp()
  const [game, setGame] = useState(null)
  const [f, setF] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    api.otherGames().then((d) => {
      const g = d.games.find((x) => x.game_id === id)
      setGame(g ?? false)
      if (g) setF({ done: g.my_done ?? '', total: g.my_total ?? '', hours: g.my_minutes != null ? String(g.my_minutes / 60) : '' })
    }).catch((e) => setError(e.message))
  }, [id])
  if (game === null) return <Drawer title="Game" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  if (game === false) return <Drawer title="Game" onClose={onClose}><p className="muted">This game isn't there any more.</p></Drawer>

  const num = (v) => (v === '' ? null : Number(v))
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      setGame(await api.updateOtherGame(id, { done: num(f.done), total: num(f.total), hours: num(f.hours) }))
      setMessage('Saved ✓')
      changed()
    } catch (err) {
      setError(err.message)
    }
  }
  const hide = async () => {
    setGame(await api.updateOtherGame(id, { hidden: !game.hidden }))
    changed()
  }
  const remove = async () => {
    await api.deleteOtherGame(id)
    changed()
    onClose()
  }
  const ubisoft = game.platform === 'ubisoft'
  const footer = (
    <>
      {game.page_url && <a className="button secondary" href={game.page_url} target="_blank" rel="noreferrer">Exophase ↗</a>}
      <span className="spacer" />
      {game.source_id
        ? <button type="button" className="plain" onClick={hide}>{game.hidden ? 'Show again' : 'Hide'}</button>
        : <button type="button" className="plain destructive" onClick={remove}>Remove</button>}
    </>
  )
  return (
    <Drawer title={game.name} onClose={onClose} footer={footer}>
      <section className="panel-section other-head">
        <OtherPicture game={game} />
        <span>
          <span className={`pill ${ubisoft ? 'teal' : 'purple'}`}>{NAME[game.platform]}</span>
          <Progress game={game} />
          {game.playtime_minutes ? <span className="item-meta">{playtime(game.playtime_minutes)} played</span> : null}
        </span>
      </section>
      {ubisoft ? (
        <form className="panel-section" onSubmit={save}>
          <h4 className="section-title">Your achievements</h4>
          <p className="small muted">Exophase can't see Ubisoft's achievements, only its challenges, so type them in from
            Ubisoft Connect (the game's Achievements page).</p>
          <div className="other-fields">
            <label>Achievements you have<input type="number" min="0" value={f.done} onChange={(e) => { setF({ ...f, done: e.target.value }); setMessage('') }} /></label>
            <label>Achievements in the game<input type="number" min="0" value={f.total} onChange={(e) => { setF({ ...f, total: e.target.value }); setMessage('') }} /></label>
            <label>Hours played<input type="number" min="0" step="0.5" value={f.hours} placeholder={game.exo_minutes ? playtime(game.exo_minutes) : ''}
              onChange={(e) => { setF({ ...f, hours: e.target.value }); setMessage('') }} /></label>
          </div>
          <div className="button-row">
            <button type="submit" className="primary">Save</button>
            {message && <span className="muted small">{message}</span>}
          </div>
          {error && <p className="alert error small">{error}</p>}
          {game.challenges_total > 0 && (
            <p className="hint">Ubisoft challenges (from Exophase): {game.challenges_done} of {game.challenges_total}.</p>
          )}
        </form>
      ) : (
        <p className="panel-section small muted">Achievements from your Exophase profile, read with every sync.</p>
      )}
    </Drawer>
  )
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
