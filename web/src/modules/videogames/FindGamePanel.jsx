import { useEffect, useRef, useState } from 'react'
import { api, money } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { GamePicture } from './steam.jsx'
import { AchievementList, Compared } from './VideoGamePanel.jsx'

// Find a game, on Steam, Ubisoft or Epic.
// Steam: scout any game, owned or not - type some words, pick one from Steam's store search, and see
// what its 100% takes (achievements and how rare they are, SteamHunters' times and 100% rate;
// api/app/vgfind.py). Nothing is saved; a game you've played but don't track yet can be added.
// Ubisoft / Epic: Exophase's list of the platform's games (only games with achievements or
// challenges are on it); pick one, or add any game by hand - a game without achievements (Fortnite)
// is tracked by its hours.
const WHERE = [['steam', 'Steam'], ['ubisoft', 'Ubisoft'], ['epic', 'Epic Games']]
const PLATFORM = Object.fromEntries(WHERE)

export default function FindGamePanel({ onClose }) {
  const [platform, setPlatform] = useState('steam')
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)      // Steam: the app id being scouted
  const [adding, setAdding] = useState(null)      // Ubisoft / Epic: {name, exo_id?, picture?}
  const { openPanel } = useApp()
  const latest = useRef('')
  useEffect(() => {
    const words = q.trim()
    const ask = `${platform}:${words}`
    latest.current = ask
    setResults(null)
    if (words.length < 2) { setError(''); setBusy(false); return undefined }
    const wait = setTimeout(async () => {
      setBusy(true)
      try {
        const found = await (platform === 'steam' ? api.findSteamGames(words) : api.findOtherGames(platform, words))
        if (latest.current === ask) { setResults(found); setError('') }
      } catch (err) {
        if (latest.current === ask) setError(err.message)
      } finally {
        if (latest.current === ask) setBusy(false)
      }
    }, 400)
    return () => clearTimeout(wait)
  }, [q, platform])

  if (picked) return <Scouted appId={picked} onBack={() => setPicked(null)} onClose={onClose} />
  if (adding) return <AddOtherGame platform={platform} game={adding} onBack={() => setAdding(null)} onClose={onClose} />
  const steam = platform === 'steam'
  const open = (r) => {
    if (steam) return setPicked(r.app_id)
    if (r.yours) { onClose(); return openPanel('videogame', { id: r.yours.id }) }
    return setAdding(r)
  }
  return (
    <Drawer title="Find a game" onClose={onClose} wide>
      <section className="panel-section">
        <div className="segmented find-where" role="group" aria-label="Where to search">
          {WHERE.map(([id, label]) => (
            <button key={id} type="button" aria-pressed={platform === id} onClick={() => setPlatform(id)}>{label}</button>
          ))}
        </div>
        <label className="field">Search {PLATFORM[platform]}
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} autoFocus
            placeholder={steam ? 'e.g. hollow knight' : platform === 'epic' ? 'e.g. fortnite' : 'e.g. rainbow six'} />
        </label>
        {busy && <p className="muted small">Looking...</p>}
        {error && <p className="alert error small">{error}</p>}
        {results && !busy && results.length === 0 && (
          <p className="muted small">{steam ? 'Nothing on Steam by that name. Try fewer words.' : `Exophase doesn't list a ${PLATFORM[platform]} game by that name.`}</p>
        )}
        {results?.length > 0 && (
          <ul className="list plain-list shop-results find-games">
            {results.map((r) => (
              <li key={r.app_id ?? r.exo_id}>
                <button type="button" className="row-button" onClick={() => open(r)}>
                  {r.picture ? <img className={steam ? 'find-thumb' : 'find-thumb contain'} src={r.picture} alt="" loading="lazy" referrerPolicy="no-referrer" />
                    : <span className="find-thumb thumb-empty" />}
                  <span className="grow">
                    <span className="item-title">{r.name}{r.yours && <span className="pill ok">In your games</span>}</span>
                    <span className="item-meta">{steam ? (r.price == null ? 'Free or not for sale' : money(r.price))
                      : r.awards ? `${r.awards} ${platform === 'ubisoft' ? 'challenges' : 'achievements'}` : ''}</span>
                  </span>
                  <span className="muted" aria-hidden="true">{steam || r.yours ? '›' : '+'}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {!steam && q.trim().length >= 2 && !busy && (
          <button type="button" className="secondary find-by-hand" onClick={() => setAdding({ name: q.trim() })}>
            + Add “{q.trim()}” to your {PLATFORM[platform]} games by hand</button>
        )}
        <p className="hint">{steam ? "Steam's store search. Pick a game to see its achievements and what a 100% takes - no need to own it."
          : `Exophase's list of ${PLATFORM[platform]} games - it only has games with ${platform === 'ubisoft' ? 'challenges' : 'achievements'}. `
            + 'Not there (like Fortnite)? Add it by hand and track your hours.'}</p>
      </section>
    </Drawer>
  )
}

// Adding an Ubisoft or Epic game: hours played (and for Ubisoft, the achievement numbers if you like -
// its list comes from its Steam version when there is one).
function AddOtherGame({ platform, game, onBack, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const [f, setF] = useState({ name: game.name, hours: '', done: '', total: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const num = (v) => (v === '' ? null : Number(v))
  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const added = await api.addOtherGame({ platform, name: f.name, exo_id: game.exo_id ?? null, hours: num(f.hours),
        done: num(f.done), total: num(f.total) })
      changed()
      showToast(`Added ${added.name} to your ${PLATFORM[platform]} games`)
      onClose()                                     // first: closing after opening would close the new panel too
      openPanel('videogame', { id: added.app_id })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <Drawer title={`Add a ${PLATFORM[platform]} game`} onClose={onClose} wide
      footer={<button type="button" className="secondary" onClick={onBack}>‹ Back to results</button>}>
      <form className="panel-section" onSubmit={save}>
        {game.picture && <img className="find-picked" src={game.picture} alt="" referrerPolicy="no-referrer" />}
        <div className="other-fields">
          <label>Game<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required readOnly={!!game.exo_id} /></label>
          <label>Hours played<input type="number" min="0" step="0.5" value={f.hours} autoFocus
            onChange={(e) => setF({ ...f, hours: e.target.value })} /></label>
          {platform === 'ubisoft' && (
            <>
              <label>Achievements you have<input type="number" min="0" value={f.done} onChange={(e) => setF({ ...f, done: e.target.value })} /></label>
              <label>Achievements in the game<input type="number" min="0" value={f.total} onChange={(e) => setF({ ...f, total: e.target.value })} /></label>
            </>
          )}
        </div>
        <p className="hint">{platform === 'ubisoft'
          ? "If it's on Steam too, its achievement list comes from there and you tick them off; otherwise type the numbers (or leave them, and track just the hours)."
          : "Tracked by hours played. Epic games with achievements come in by themselves from your Exophase profile."}</p>
        <button type="submit" className="primary" disabled={busy || !f.name.trim()}>{busy ? 'Adding...' : 'Add game'}</button>
        {error && <p className="alert error small">{error}</p>}
      </form>
    </Drawer>
  )
}

// One game: its picture, what the 100% takes, other players' numbers and every achievement.
function Scouted({ appId, onBack, onClose }) {
  const { openPanel, changed, showToast } = useApp()
  const [game, setGame] = useState(null)
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  useEffect(() => { api.scoutVideoGame(appId).then(setGame).catch((e) => setError(e.message)) }, [appId])
  const track = async () => {
    setAdding(true)
    setError('')
    try {
      const added = await api.addExtraVideoGame(String(appId))
      changed()
      showToast(`Added ${added.name}: ${added.achievements_done} of ${added.achievements_total} achievements`)
      onClose()
      openPanel('videogame', { id: added.app_id })
    } catch (err) {
      setError(err.message)
    } finally {
      setAdding(false)
    }
  }
  const footer = (
    <>
      <button type="button" className="secondary" onClick={onBack}>‹ Back to results</button>
      <a className="button plain" href={`https://store.steampowered.com/app/${appId}`} target="_blank" rel="noreferrer">Store page ↗</a>
      <span className="spacer" />
      {game?.yours ? <button type="button" className="primary" onClick={() => { onClose(); openPanel('videogame', { id: game.yours.id }) }}>Open yours</button>
        : game?.achievements_total > 0 && (
          <button type="button" className="plain" disabled={adding} onClick={track}
            title="For a game you've unlocked achievements in that isn't in your Steam library list">{adding ? 'Adding...' : "I've played it - track it"}</button>
        )}
    </>
  )
  return (
    <Drawer title={game?.name ?? 'Game'} onClose={onClose} footer={footer} wide>
      {error && <p className="alert error">{error}</p>}
      {!game ? !error && <p className="muted">Reading Steam and SteamHunters...</p> : (
        <>
          <GamePicture game={game} className="game-header" />
          <section className="panel-section">
            <div className="section-head">
              <strong>{game.achievements_total ? `${game.achievements_total} achievements` : 'No Steam achievements'}</strong>
              {game.yours && <span className="pill ok">In your games</span>}
              {game.sh_has_dlc && <span className="pill purple" title="SteamHunters: the game has paid DLC; some achievements may need it">Paid DLC</span>}
            </div>
            {game.achievements_total > 0 && (
              <p className="small muted">
                {game.ultra_rare > 0 ? `${game.ultra_rare} ultra rare (5% of players or fewer)` : 'None ultra rare'}
                {game.rarest_percent != null && ` · rarest held by ${game.rarest_percent}% of players`}
                {game.unobtainable_count > 0 && ` · ${game.unobtainable_count} can't be earned any more (not counted)`}
              </p>
            )}
            {game.notes.map((n) => <p key={n} className="muted small">{n}</p>)}
          </section>
          <Compared game={game} hint="Median, fastest and 100% rate: SteamHunters' players." />
          {game.achievements.length > 0 && (
            <section className="panel-section scout-list">
              <h4 className="section-title">Achievements, most players first</h4>
              <AchievementList items={game.achievements} />
            </section>
          )}
        </>
      )}
    </Drawer>
  )
}
