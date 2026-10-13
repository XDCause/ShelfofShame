import { useEffect, useMemo, useState } from 'react'
import { api, shortDate, timeAgo } from '../../api.js'
import { GamepadIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { CompletionBar, playtime, rarity, SteamSetup, SyncBar, useSteamAccount, useSteamSummary } from './steam.jsx'

// The dashboard: the account and sync, headline tiles, what to finish next, what you've just
// unlocked, your rarest achievements, your latest 100%s.
export function Dashboard() {
  const { account, setAccount, error } = useSteamAccount()
  const { data: s } = useSteamSummary()
  if (error) return <p className="alert error">{error}</p>
  if (!account) return <p className="muted loading">Loading...</p>
  if (!account.steam_id) return <section className="page"><SteamSetup account={account} setAccount={setAccount} /></section>

  return (
    <section className="page videogames">
      <SyncBar account={account} setAccount={setAccount} />
      {!s ? <p className="muted loading">Loading...</p> : s.games === 0 ? (
        <p className="empty card">{account.sync.running ? 'Reading your games from Steam...' : 'No games yet. Sync now to read them from Steam.'}</p>
      ) : (
        <>
          <div className="home-stats">
            <Stat to="/videogames/games?show=perfect" Icon={TrophyIcon} tone="ok" value={s.perfect} label="Games at 100%"
              sub={`of ${s.with_achievements} games`} />
            <Stat to="/videogames/games?show=started" Icon={GamepadIcon} tone="tint" value={s.started} label="In progress"
              sub={s.average_percent != null ? `${s.average_percent}% average` : 'started, not finished'} />
            <Stat to="/videogames/games" Icon={TrophyIcon} tone="purple" value={s.achievements.toLocaleString()}
              label="Achievements" sub={`${s.unlocked_this_month} this month`} />
            <Stat to="/videogames/games" Icon={GamepadIcon} tone="teal" value={playtime(s.playtime_minutes)}
              label="Played" sub={`${s.games} games`} />
          </div>

          <div className="home-grid">
            <section className="card home-card">
              <h2 className="home-card-title">Closest to 100%</h2>
              {s.closest.length === 0 ? <p className="muted small">Nothing part-done. Pick a game and start hunting!</p> : (
                <ul className="list plain-list">{s.closest.map((g) => <GameRow key={g.app_id} game={g} detail={`${g.left_to_get} to go`} />)}</ul>
              )}
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Recently unlocked</h2>
              <AchievementList items={s.recent} when />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Rarest you have</h2>
              <AchievementList items={s.rarest} />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Latest 100%</h2>
              {s.recent_perfect.length === 0 ? <p className="muted small">Your first 100% will show here.</p> : (
                <div className="perfect-grid">
                  {s.recent_perfect.map((g) => <PerfectCard key={g.app_id} game={g} />)}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </section>
  )
}

function GameRow({ game: g, detail }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('videogame', { id: g.app_id })}>
        <img className="game-capsule" src={g.header_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
        <span className="grow">
          <span className="item-title">{g.name}</span>
          <span className="item-meta">{g.achievements_done} of {g.achievements_total} · {g.percent}%{detail && ` · ${detail}`}</span>
          <CompletionBar game={g} />
        </span>
      </button>
    </li>
  )
}

function AchievementList({ items, when = false }) {
  const { openPanel } = useApp()
  if (!items.length) return <p className="muted small">Nothing yet.</p>
  return (
    <ul className="list plain-list">
      {items.map((a) => {
        const r = rarity(a.global_percent)
        return (
          <li key={`${a.app_id}-${a.api_name}`}>
            <button type="button" className="row-button" onClick={() => openPanel('videogame', { id: a.app_id })}>
              {a.icon ? <img className="achievement-icon" src={a.icon} alt="" loading="lazy" referrerPolicy="no-referrer" />
                : <span className="achievement-icon thumb-empty" />}
              <span className="grow">
                <span className="item-title">{a.name}</span>
                <span className="item-meta">{a.game}{when && a.unlocked_at && ` · ${timeAgo(a.unlocked_at)}`}</span>
              </span>
              {r && <span className={`pill ${r.tone}`}>{r.text}</span>}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function PerfectCard({ game: g }) {
  const { openPanel } = useApp()
  return (
    <button type="button" className="perfect-card" onClick={() => openPanel('videogame', { id: g.app_id })}>
      <img src={g.header_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
      <span className="perfect-badge">100%</span>
      <span className="perfect-name">{g.name}</span>
      <span className="muted small">{shortDate(g.completed_at)}</span>
    </button>
  )
}

const SHOWS = [['all', 'All'], ['perfect', '100%'], ['started', 'In progress'], ['untouched', 'Not started'],
  ['no_achievements', 'No achievements'], ['hidden', 'Hidden']]
const SORTS = {
  played: ['Recently played', (a, b) => (b.last_played ?? '').localeCompare(a.last_played ?? '')],
  percent: ['Completion', (a, b) => Number(b.percent ?? -1) - Number(a.percent ?? -1) || a.left_to_get - b.left_to_get],
  left: ['Fewest to go', (a, b) => (a.left_to_get || 1e9) - (b.left_to_get || 1e9)],
  time: ['Most played', (a, b) => b.playtime_minutes - a.playtime_minutes],
  name: ['Name', (a, b) => a.name.localeCompare(b.name)],
}

// Every game: which to show, a search, a sort, and a row each with its completion.
export function GamesView() {
  const { refreshKey, openPanel } = useApp()
  const [show, setShow] = useState(() => new URLSearchParams(window.location.search).get('show') ?? 'all')
  const [sort, setSort] = useState('played')
  const [q, setQ] = useState('')
  const [games, setGames] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.listVideoGames(show).then(setGames).catch((e) => setError(e.message)) }, [show, refreshKey])
  const visible = useMemo(() => (games ?? [])
    .filter((g) => !q.trim() || g.name.toLowerCase().includes(q.trim().toLowerCase()))
    .sort(SORTS[sort][1]), [games, q, sort])

  if (error) return <p className="alert error">{error}</p>
  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search your games..." aria-label="Search your games" />
        <label className="sort view-controls">
          <span className="muted small">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort games">
            {Object.entries(SORTS).map(([id, [label]]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </label>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Show">
        {SHOWS.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={show === id} onClick={() => setShow(id)}>{label}</button>
        ))}
      </div>
      {!games ? <p className="muted loading">Loading...</p> : visible.length === 0 ? <p className="empty card">No games here.</p> : (
        <ul className="list game-list">
          {visible.map((g) => (
            <li key={g.app_id}>
              <button type="button" className="row-button" onClick={() => openPanel('videogame', { id: g.app_id })}>
                <img className="game-capsule" src={g.header_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
                <span className="grow">
                  <span className="item-title">{g.name}</span>
                  <span className="item-meta">
                    {g.achievements_total ? `${g.achievements_done} of ${g.achievements_total} · ${g.percent}%`
                      : g.has_achievements === false ? 'No achievements' : 'Not read yet'}
                    {g.playtime_minutes > 0 && ` · ${playtime(g.playtime_minutes)}`}
                  </span>
                  <CompletionBar game={g} />
                </span>
                {g.completed_at && <span className="pill ok">100%</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// Home: two tiles.
export function VideoGamesTiles() {
  const { data: s } = useSteamSummary()
  if (!s) return <><StatSkeleton /><StatSkeleton /></>
  return (
    <>
      <Stat to="/videogames/dashboard" Icon={TrophyIcon} tone="ok" value={s.perfect} label="Games at 100%"
        sub={s.closest[0] ? `next: ${s.closest[0].name}` : 'Steam'} />
      <Stat to="/videogames/dashboard" Icon={GamepadIcon} tone="purple" value={s.achievements.toLocaleString()}
        label="Achievements" sub={`${s.unlocked_this_month} this month`} />
    </>
  )
}
