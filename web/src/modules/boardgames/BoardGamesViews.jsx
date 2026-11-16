import { useEffect, useState } from 'react'
import { api, shortDate, today } from '../../api.js'
import { DiceIcon, TimerIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'
import { KINDS, gameMeta } from './GamePanel.jsx'
import EmptyState from '../../core/EmptyState.jsx'
import { unplayedGames } from './statsHelpers.js'

const STATUS_TONE = { Owned: 'ok', 'To sell': 'low', Wanted: 'tint', Borrowed: 'purple', 'Played elsewhere': 'teal', Gone: '' }
const monthOf = (day) => new Date(`${day}T12:00:00`).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })

function useGames() {
  const { refreshKey } = useApp()
  return useShared(`boardgames-${refreshKey}`, () => Promise.all([api.listBoardGames(), api.boardGameSummary()])
    .then(([games, summary]) => ({ games, summary })))
}

const UNPLAYED = 'unplayed'          // the status filter's extra chip
const KIND_GROUPS = { game: 'Base games', expansion: 'Expansions', other: 'Other' }

// The collection: a few numbers, status and type chips, then the games in drop-down groups (base
// games, expansions, other), a card per game.
export function GamesView() {
  const { openPanel } = useApp()
  const { data, error } = useGames()
  const [status, setStatus] = useState('')
  const [kind, setKind] = useState('')
  const [whatOpen, setWhatOpen] = useState(false)
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const { games, summary } = data
  const statuses = [...new Set(games.map((g) => g.status))]
  const kinds = KINDS.map(([k]) => k).filter((k) => games.some((g) => g.kind === k))
  // "Unplayed": owned games never played, or not played for a year - a filter like the statuses (2026-11-16: it was a
  // fold of its own between the buttons and the filters, and the page looked like loose parts)
  const { never, stale } = unplayedGames(games, today())
  const unplayed = new Set([...never, ...stale].map((g) => g.game_id))
  const visible = games.filter((g) => (!status || (status === UNPLAYED ? unplayed.has(g.game_id) : g.status === status))
    && (!kind || g.kind === kind))
  const groups = kinds.map((k) => [k, visible.filter((g) => g.kind === k)]).filter(([, list]) => list.length)

  return (
    <section className="page">
      <div className="stat-grid card">
        <div><span>Games owned</span><strong>{summary.owned}</strong>
          {summary.played_elsewhere > 0 && <small className="muted">+ {summary.played_elsewhere} played elsewhere</small>}</div>
        <div><span>Plays this month</span><strong>{summary.plays_this_month}</strong>
          {summary.abandoned > 0 && <small className="muted">{summary.abandoned} abandoned in all</small>}</div>
        <div><span>Most played</span><strong className="ellipsis">{summary.most_played?.name ?? '—'}</strong>
          {summary.most_played && <small className="muted">{summary.most_played.plays} play{summary.most_played.plays === 1 ? '' : 's'}</small>}</div>
      </div>
      <NowPlaying live={summary.live} />
      {/* one row of actions, then the filters, then the games */}
      <div className="toolbar bgt-actions">
        <button type="button" className="primary" onClick={() => openPanel('liveplay')}>▶ Start a play</button>
        <button type="button" className="secondary" onClick={() => openPanel('play')}>Log a play</button>
        <button type="button" className="secondary" onClick={() => openPanel('boardgame', { id: null })}>+ Add game</button>
        <button type="button" className="secondary" aria-expanded={whatOpen} onClick={() => setWhatOpen(!whatOpen)}>🎲 What to play?</button>
      </div>
      {whatOpen && <WhatToPlay games={games} onClose={() => setWhatOpen(false)} />}
      <div className="chip-rows">
          {kinds.length > 1 && (
            <div className="chip-row scroll" role="group" aria-label="Type">
              {['', ...kinds].map((k) => (
                <button key={k || 'all'} type="button" className="chip-filter" aria-pressed={kind === k} onClick={() => setKind(k)}>
                  {k ? KIND_GROUPS[k] : 'All types'} <span className="chip-count">{k ? games.filter((g) => g.kind === k).length : games.length}</span>
                </button>
              ))}
            </div>
          )}
          {(statuses.length > 1 || unplayed.size > 0) && (
            <div className="chip-row scroll" role="group" aria-label="Show">
              {['', ...statuses].map((s) => (
                <button key={s || 'all'} type="button" className="chip-filter" aria-pressed={status === s} onClick={() => setStatus(s)}>
                  {s || 'All'} <span className="chip-count">{s ? games.filter((g) => g.status === s).length : games.length}</span>
                </button>
              ))}
              {unplayed.size > 0 && (
                <button type="button" className="chip-filter" aria-pressed={status === UNPLAYED} onClick={() => setStatus(UNPLAYED)}
                  title={`${never.length} never played, ${stale.length} not played in a year`}>
                  Unplayed <span className="chip-count">{unplayed.size}</span>
                </button>
              )}
            </div>
          )}
        </div>
      {visible.length === 0 ? (
        <EmptyState Icon={DiceIcon} title="No board games yet" action="+ Add a game" onAction={() => openPanel('boardgame', { id: null })}>
          Add the ones on your shelf, and the ones you'd like to own.</EmptyState>
      ) : groups.length === 0 ? <p className="empty card">Nothing here with those filters.</p> : groups.map(([k, list]) => (
        <details key={k} className="fold game-group" open>
          <summary><span className="fold-title">{KIND_GROUPS[k]}</span><span className="fold-detail">{list.length}</span></summary>
          <div className="fold-body">
        <div className="model-grid">
          {list.map((g) => (
            <button key={g.game_id} type="button" className="model-card" onClick={() => openPanel('boardgame', { id: g.game_id })}>
              <span className="model-photo cover">
                {g.photo_url ? <img src={g.photo_url} alt="" loading="lazy" />
                  : <span className="photo-missing big-icon"><DiceIcon size={44} /></span>}
                <span className={`status-badge pill ${STATUS_TONE[g.status]}`}>{g.status}</span>
              </span>
              <span className="model-body">
                <span className="model-name">{g.name}</span>
                {g.kind !== 'game' && g.base_name && <span className="model-meta game-for">{g.kind === 'expansion' ? 'Expansion' : 'Extra'} for {g.base_name}</span>}
                {g.kind === 'game' && g.add_ons > 0 && <span className="model-meta game-for">+ {g.add_ons} expansion{g.add_ons === 1 ? '' : 's'} / extra{g.add_ons === 1 ? '' : 's'}</span>}
                <span className="model-meta">{gameMeta(g)}</span>
                <span className="muted small">
                  {g.plays ? `Played ${g.plays} time${g.plays === 1 ? '' : 's'} · last ${shortDate(g.last_played)}` : 'Not played yet'}
                  {g.rating ? ` · ★ ${g.rating}` : ''}
                </span>
              </span>
            </button>
          ))}
        </div>
          </div>
        </details>
      ))}
    </section>
  )
}

// Every play, newest first, a heading per month.
export function PlaysView() {
  const { refreshKey, openPanel } = useApp()
  const [plays, setPlays] = useState(null)
  const [tag, setTag] = useState('')               // show only plays with this tag
  const [tags, setTags] = useState([])
  const [error, setError] = useState('')
  useEffect(() => { api.listPlays(200, tag).then(setPlays).catch((e) => setError(e.message)) }, [refreshKey, tag])
  useEffect(() => { api.boardGameTags().then(setTags).catch(() => {}) }, [refreshKey])
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
        <button type="button" className="primary" onClick={() => openPanel('liveplay')}>▶ Start a play</button>
        <button type="button" className="secondary" onClick={() => openPanel('play')}>+ Log a play</button>
      </div>
      {tags.length > 0 && (
        <div className="chip-row bgx-tag-filter" role="group" aria-label="Filter by tag">
          <button type="button" className="chip-filter" aria-pressed={!tag} onClick={() => setTag('')}>All plays</button>
          {tags.map((t) => <button key={t.tag} type="button" className="chip-filter" aria-pressed={tag === t.tag} onClick={() => setTag(t.tag)}>{t.tag} · {t.plays}</button>)}
        </div>
      )}
      {plays.length === 0 && !tag && (
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
                    <span className="item-meta">{[shortDate(p.played_on), p.game_status === 'Played elsewhere' && 'played elsewhere',
                      p.seats.some((s) => s.score != null) ? p.seats.map((s) => `${s.name} ${s.score != null ? Number(s.score) : ''}`.trim()).join(', ') : p.players,
                      p.location, p.minutes && `${p.minutes} min`, p.fun && '★'.repeat(p.fun), ...(p.tags ?? [])].filter(Boolean).join(' · ')}</span>
                  </span>
                  {p.photos.length > 0 && <span className="pill">📷 {p.photos.length}</span>}
                  {!p.finished ? <span className="pill low">Abandoned</span>
                    : p.scoring === 'coop' && p.coop_won === false ? <span className="pill low">The game won</span>
                      : p.winner && <span className="pill ok"><TrophyIcon size={14} /> {p.winner}</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}


// Plays going on now (started with "Start a play"): back to the table in one tap.
function NowPlaying({ live }) {
  const { openPanel } = useApp()
  if (!live?.length) return null
  return (
    <div className="bgt-now">
      {live.map((l) => (
        <button key={l.live_id} type="button" className="card bgt-now-card" onClick={() => openPanel('liveplay', { id: l.live_id })}>
          <span className="stat-icon teal"><TimerIcon size={22} /></span>
          <span className="grow">
            <span className="bgt-now-label">Playing now</span>
            <span className="item-title">{l.game_name}</span>
            <span className="muted small">since {new Date(l.started_at).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}</span>
          </span>
          <span className="pill teal">Open</span>
        </button>
      ))}
    </div>
  )
}

const TIMES = [['', 'Any length'], ['30', 'Up to 30 min'], ['60', 'Up to an hour'], ['90', 'Up to 90 min'], ['120', 'Up to 2 hours']]
const WEIGHTS = [['', 'Any weight'], ['light', 'Light'], ['medium', 'Medium'], ['heavy', 'Heavy']]
const weightFits = (w, want) => !want || w == null || (want === 'light' ? w < 2.2 : want === 'medium' ? w >= 2 && w < 3.4 : w >= 3.2)

// "What should we play?": your games that take this many players in the time you have (and the weight you're in the
// mood for), the ones you haven't played for longest first - or let the app pick.
function WhatToPlay({ games, onClose }) {
  const { openPanel } = useApp()
  const [players, setPlayers] = useState('4')
  const [time, setTime] = useState('')
  const [weight, setWeight] = useState('')
  const [picked, setPicked] = useState(null)
  const [all, setAll] = useState(false)
  const n = Number(players) || 0
  const fits = games.filter((g) => g.kind === 'game' && ['Owned', 'To sell', 'Borrowed'].includes(g.status)
    && (!n || ((g.min_players ?? 1) <= n && (g.max_players ?? 99) >= n))
    && (!time || !g.play_minutes || g.play_minutes <= Number(time))
    && weightFits(g.weight == null ? null : Number(g.weight), weight))
    .sort((a, b) => (a.last_played ?? '').localeCompare(b.last_played ?? '') || (b.rating ?? 0) - (a.rating ?? 0))
  const shown = picked ? [picked] : all ? fits : fits.slice(0, 6)
  return (
    <section className="card bgt-what" aria-label="What should we play?">
      <div className="section-head">
        <h3 className="section-title">What should we play?</h3>
        <button type="button" className="icon-btn small" aria-label="Close" onClick={() => onClose()}>✕</button>
      </div>
      <div className="bgt-what-filters">
        <label className="field"><span className="field-label">Players</span>
          <input type="number" min="1" max="20" inputMode="numeric" value={players} onChange={(e) => { setPlayers(e.target.value); setPicked(null) }} /></label>
        <label className="field"><span className="field-label">Time</span>
          <select value={time} onChange={(e) => { setTime(e.target.value); setPicked(null) }}>{TIMES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="field"><span className="field-label">Weight</span>
          <select value={weight} onChange={(e) => { setWeight(e.target.value); setPicked(null) }}>{WEIGHTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {fits.length === 0 ? <p className="muted small">Nothing on your shelf fits that. Try more time or another weight.</p> : (
        <>
          <ul className="list compact">
            {shown.map((g) => (
              <li key={g.game_id} className="bgt-what-row">
                <span className="grow">
                  <span className="item-title">{g.name}</span>
                  <span className="item-meta">{[gameMeta(g), g.last_played ? `last played ${shortDate(g.last_played)}` : 'never played'].filter(Boolean).join(' · ')}</span>
                </span>
                <button type="button" className="primary small" onClick={() => openPanel('liveplay', { gameId: g.game_id })}>▶ Play</button>
              </li>
            ))}
          </ul>
          <div className="button-row">
            <button type="button" className="secondary" onClick={() => setPicked(fits[Math.floor(Math.random() * fits.length)])}>
              {picked ? 'Pick again' : 'Pick one for us'}</button>
            {(picked || (!all && fits.length > 6)) && (
              <button type="button" className="plain" onClick={() => { setPicked(null); setAll(true) }}>Show them all ({fits.length})</button>
            )}
          </div>
        </>
      )}
    </section>
  )
}
