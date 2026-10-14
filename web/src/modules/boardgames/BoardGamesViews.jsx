import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { DiceIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'
import { gameMeta } from './GamePanel.jsx'
import EmptyState from '../../core/EmptyState.jsx'

const STATUS_TONE = { Owned: 'ok', Wanted: 'tint', Borrowed: 'purple', Gone: '' }
const monthOf = (day) => new Date(`${day}T12:00:00`).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })

function useGames() {
  const { refreshKey } = useApp()
  return useShared(`boardgames-${refreshKey}`, () => Promise.all([api.listBoardGames(), api.boardGameSummary()])
    .then(([games, summary]) => ({ games, summary })))
}

// The collection: a few numbers, status chips, then a card per game.
export function GamesView() {
  const { openPanel } = useApp()
  const { data, error } = useGames()
  const [status, setStatus] = useState('')
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const { games, summary } = data
  const statuses = [...new Set(games.map((g) => g.status))]
  const visible = games.filter((g) => !status || g.status === status)

  return (
    <section className="page">
      <div className="stat-grid card">
        <div><span>Games owned</span><strong>{summary.owned}</strong></div>
        <div><span>Plays this month</span><strong>{summary.plays_this_month}</strong></div>
        <div><span>Most played</span><strong className="ellipsis">{summary.most_played?.name ?? '—'}</strong>
          {summary.most_played && <small className="muted">{summary.most_played.plays} plays</small>}</div>
      </div>
      <div className="toolbar">
        <div className="chip-row scroll" role="group" aria-label="Show">
          {statuses.length > 1 && ['', ...statuses].map((s) => (
            <button key={s || 'all'} type="button" className="chip-filter" aria-pressed={status === s} onClick={() => setStatus(s)}>
              {s || 'All'} <span className="chip-count">{s ? games.filter((g) => g.status === s).length : games.length}</span>
            </button>
          ))}
        </div>
        <button type="button" className="secondary" onClick={() => openPanel('play')}>Log a play</button>
        <button type="button" className="primary" onClick={() => openPanel('boardgame', { id: null })}>+ Add game</button>
      </div>
      {visible.length === 0 ? (
        <EmptyState Icon={DiceIcon} title="No board games yet" action="+ Add a game" onAction={() => openPanel('boardgame', { id: null })}>
          Add the ones on your shelf, and the ones you'd like to own.</EmptyState>
      ) : (
        <div className="model-grid">
          {visible.map((g) => (
            <button key={g.game_id} type="button" className="model-card" onClick={() => openPanel('boardgame', { id: g.game_id })}>
              <span className="model-photo cover">
                {g.photo_url ? <img src={g.photo_url} alt="" loading="lazy" />
                  : <span className="photo-missing big-icon"><DiceIcon size={44} /></span>}
                <span className={`status-badge pill ${STATUS_TONE[g.status]}`}>{g.status}</span>
              </span>
              <span className="model-body">
                <span className="model-name">{g.name}</span>
                <span className="model-meta">{gameMeta(g)}</span>
                <span className="muted small">
                  {g.plays ? `Played ${g.plays} time${g.plays === 1 ? '' : 's'} · last ${shortDate(g.last_played)}` : 'Not played yet'}
                  {g.rating ? ` · ★ ${g.rating}` : ''}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

// Every play, newest first, a heading per month.
export function PlaysView() {
  const { refreshKey, openPanel } = useApp()
  const [plays, setPlays] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.listPlays().then(setPlays).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!plays) return <p className="muted loading">Loading...</p>
  const months = []
  for (const p of plays) {
    if (months.at(-1)?.name !== monthOf(p.played_on)) months.push({ name: monthOf(p.played_on), plays: [] })
    months.at(-1).plays.push(p)
  }
  return (
    <section className="page">
      <div className="toolbar">
        <p className="summary grow"><strong>{plays.length}</strong> play{plays.length === 1 ? '' : 's'} logged</p>
        <button type="button" className="primary" onClick={() => openPanel('play')}>+ Log a play</button>
      </div>
      {plays.length === 0 && (
        <EmptyState Icon={DiceIcon} title="No plays yet" action="+ Log a play" onAction={() => openPanel('play')}>
          Log one after your next games night: who played, who won, how long it took.</EmptyState>
      )}
      {months.map((m) => (
        <div key={m.name}>
          <h3 className="section-title">{m.name}</h3>
          <ul className="list">
            {m.plays.map((p) => (
              <li key={p.play_id}>
                <button type="button" className="row-button" onClick={() => openPanel('boardgame', { id: p.game_id })}>
                  <span className="thumb thumb-icon purple"><DiceIcon size={20} /></span>
                  <span className="grow">
                    <span className="item-title">{p.game_name}</span>
                    <span className="item-meta">{[shortDate(p.played_on), p.players, p.minutes && `${p.minutes} min`].filter(Boolean).join(' · ')}</span>
                  </span>
                  {p.winner && <span className="pill ok"><TrophyIcon size={14} /> {p.winner}</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}

// Home: two tiles (just the summary - not every game).
export function BoardGamesTiles() {
  const { refreshKey } = useApp()
  const { data: summary } = useShared(`boardgames-summary-${refreshKey}`, api.boardGameSummary)
  if (!summary) return <><StatSkeleton /><StatSkeleton /></>
  return (
    <>
      <Stat to="/boardgames/games" Icon={DiceIcon} tone="purple" value={summary.owned} label="Board games"
        sub={summary.wanted ? `${summary.wanted} wanted` : 'on the shelf'} />
      <Stat to="/boardgames/plays" Icon={TrophyIcon} tone="teal" value={summary.plays_this_month} label="Plays"
        sub="this month" />
    </>
  )
}
