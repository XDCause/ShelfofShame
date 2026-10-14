import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { CompletionBar, GamePicture, playtime, rarity } from './steam.jsx'

// One game: its picture, completion, every achievement (unlocked first; locked ones greyed, hidden
// ones' descriptions kept secret), links to Steam, journal pages about it, and Hide.
export default function VideoGamePanel({ id, onClose }) {
  const { changed } = useApp()
  const [game, setGame] = useState(null)
  const [error, setError] = useState('')
  const [account, setAccount] = useState(null)
  const [show, setShow] = useState('all')
  useEffect(() => {
    api.getVideoGame(id).then(setGame).catch((e) => setError(e.message))
    api.steamAccount().then(setAccount).catch(() => {})
  }, [id])

  if (!game) return <Drawer title="Game" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const hide = async () => {
    setGame(await api.hideVideoGame(id, !game.hidden))
    changed()
  }
  const list = game.achievements.filter((a) => show === 'all' || (show === 'got' ? a.achieved : !a.achieved))
  const footer = (
    <>
      <a className="button secondary" href={`https://store.steampowered.com/app/${id}`} target="_blank" rel="noreferrer">Store page ↗</a>
      {account?.steam_id && game.achievements_total > 0 && (
        <a className="button plain" href={`https://steamcommunity.com/profiles/${account.steam_id}/stats/${id}/achievements`}
          target="_blank" rel="noreferrer">Your achievements on Steam ↗</a>
      )}
      <span className="spacer" />
      <button type="button" className="plain" onClick={hide}>{game.hidden ? 'Show on dashboard' : 'Hide'}</button>
    </>
  )

  return (
    <Drawer title={game.name} onClose={onClose} footer={footer} wide>
      <GamePicture game={game} className="game-header" />
      <section className="panel-section">
        <div className="section-head">
          <strong>{game.achievements_total ? `${game.achievements_done} of ${game.achievements_total} achievements · ${game.percent}%`
            : game.has_achievements === false ? 'This game has no achievements' : 'Not read from Steam yet'}</strong>
          {game.completed_at && <span className="pill ok">100% · {shortDate(game.completed_at)}</span>}
        </div>
        <CompletionBar game={game} />
        <p className="muted small">{playtime(game.playtime_minutes)} played{game.last_played && ` · last played ${shortDate(game.last_played)}`}</p>
      </section>

      {game.achievements.length > 0 && (
        <section className="panel-section">
          <div className="segmented" role="group" aria-label="Show achievements">
            {[['all', 'All'], ['got', 'Unlocked'], ['left', 'Still to get']].map(([k, label]) => (
              <button key={k} type="button" aria-pressed={show === k} onClick={() => setShow(k)}>{label}</button>
            ))}
          </div>
          <ul className="list achievements">
            {list.map((a) => {
              const r = rarity(a.global_percent)
              const secret = a.hidden && !a.achieved
              return (
                <li key={a.api_name} className={a.achieved ? 'achievement got' : 'achievement'}>
                  {(a.achieved ? a.icon : a.icon_gray ?? a.icon)
                    ? <img className="achievement-icon" src={a.achieved ? a.icon : a.icon_gray ?? a.icon} alt="" loading="lazy" referrerPolicy="no-referrer" />
                    : <span className="achievement-icon thumb-empty" />}
                  <span className="grow">
                    <span className="item-title">{a.name}</span>
                    <span className="item-meta">{secret ? 'Hidden achievement' : a.description ?? ''}</span>
                    {a.achieved && a.unlocked_at && <span className="item-meta">Unlocked {shortDate(a.unlocked_at)}</span>}
                  </span>
                  {r && <span className={`pill ${r.tone}`} title={r.label ? `${r.label}: ${r.text} of players have it` : `${r.text} of players have it`}>{r.text}</span>}
                </li>
              )
            })}
          </ul>
        </section>
      )}
      <JournalMentions kind="videogame" id={game.app_id} name={game.name} onLeave={onClose} />
    </Drawer>
  )
}
