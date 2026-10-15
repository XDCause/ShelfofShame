import { useEffect, useRef, useState } from 'react'
import { api, money } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { GamePicture } from './steam.jsx'
import { AchievementList, Compared } from './VideoGamePanel.jsx'

// Scouting a game you may not own: type some words, pick a game from Steam's store search, and see
// what its 100% takes - achievements and how rare they are, SteamHunters' times and 100% rate
// (api/app/vgfind.py). Nothing is saved; a game you've played but don't track yet can be added.
export default function FindGamePanel({ onClose }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)
  const latest = useRef('')
  useEffect(() => {
    const words = q.trim()
    latest.current = words
    if (words.length < 2) { setResults(null); setError(''); return undefined }
    const wait = setTimeout(async () => {
      setBusy(true)
      try {
        const found = await api.findSteamGames(words)
        if (latest.current === words) { setResults(found); setError('') }
      } catch (err) {
        if (latest.current === words) setError(err.message)
      } finally {
        if (latest.current === words) setBusy(false)
      }
    }, 400)
    return () => clearTimeout(wait)
  }, [q])

  if (picked) return <Scouted appId={picked} onBack={() => setPicked(null)} onClose={onClose} />
  return (
    <Drawer title="Find a game" onClose={onClose} wide>
      <section className="panel-section">
        <label className="field">Search Steam
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} autoFocus placeholder="e.g. hollow knight" />
        </label>
        {busy && <p className="muted small">Looking...</p>}
        {error && <p className="alert error small">{error}</p>}
        {results && !busy && results.length === 0 && <p className="muted small">Nothing on Steam by that name. Try fewer words.</p>}
        {results?.length > 0 && (
          <ul className="list plain-list shop-results find-games">
            {results.map((r) => (
              <li key={r.app_id}>
                <button type="button" className="row-button" onClick={() => setPicked(r.app_id)}>
                  {r.picture ? <img className="find-thumb" src={r.picture} alt="" loading="lazy" referrerPolicy="no-referrer" />
                    : <span className="find-thumb thumb-empty" />}
                  <span className="grow">
                    <span className="item-title">{r.name}{r.yours && <span className="pill ok">In your games</span>}</span>
                    <span className="item-meta">{r.price == null ? 'Free or not for sale' : money(r.price)}</span>
                  </span>
                  <span className="muted" aria-hidden="true">›</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="hint">Steam's store search. Pick a game to see its achievements and what a 100% takes - no need to own it.</p>
      </section>
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
      openPanel('videogame', { id: added.app_id })
      onClose()
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
      {game?.yours ? <button type="button" className="primary" onClick={() => { openPanel('videogame', { id: game.yours.id }); onClose() }}>Open yours</button>
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
