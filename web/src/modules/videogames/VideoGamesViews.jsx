import { useEffect, useMemo, useState } from 'react'
import { api, shortDate, timeAgo } from '../../api.js'
import { GamepadIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import {
  CompletionBar, GamePicture, playtime, rarity, SteamSetup, SyncBar, useSteamAccount, useSteamSummary,
} from './steam.jsx'

// The dashboard: the account and sync, profile completion against your goal, headline tiles,
// what to finish next, what you've just unlocked, your rarest achievements, your latest 100%s.
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
          <GoalCard summary={s} />
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

// "About 2 years 8 months" from a number of days.
function roughly(days) {
  if (days < 14) return `about ${days} day${days === 1 ? '' : 's'}`
  if (days < 60) return `about ${Math.round(days / 7)} weeks`
  const months = Math.round(days / 30.4)
  if (months < 24) return `about ${months} months`
  const years = Math.floor(months / 12)
  const rest = months % 12
  return `about ${years} years${rest ? ` ${rest} month${rest === 1 ? '' : 's'}` : ''}`
}

// Profile completion: the average completion of the games you've started (what SteamHunters calls
// "avg completion", and what the goal tracks), the total underneath, the goal marked on the bar,
// the quickest route there and how long at your recent pace.
function GoalCard({ summary: s }) {
  const { changed } = useApp()
  const g = s.goal
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(g.goal_percent))
  const [error, setError] = useState('')
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.setVideoGameGoal(Number(value))
      setEditing(false)
      changed()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <section className="card goal-card" aria-label="Profile completion">
      <div className="goal-head">
        <span>
          <span className="goal-label">Profile completion</span>
          <strong className="goal-percent">{g.percent}%</strong>
          <span className="muted small">average completion of the {s.perfect + s.started} games you've started</span>
        </span>
        {editing ? (
          <form className="goal-edit" onSubmit={save}>
            <label className="small">Goal <input type="number" min="1" max="100" value={value}
              onChange={(e) => setValue(e.target.value)} aria-label="Goal (%)" />%</label>
            <button type="submit" className="primary small">Save</button>
            <button type="button" className="plain small" onClick={() => setEditing(false)}>Cancel</button>
          </form>
        ) : (
          <button type="button" className="plain small" onClick={() => { setValue(String(g.goal_percent)); setEditing(true) }}>
            Goal {g.goal_percent}% · change
          </button>
        )}
      </div>
      <div className="goal-bar" role="img" aria-label={`${g.percent}% average, goal ${g.goal_percent}%`}>
        <span className="goal-fill" style={{ width: `${Math.min(100, g.percent)}%` }} />
        <span className="goal-marker" style={{ left: `${g.goal_percent}%` }}><span>Goal {g.goal_percent}%</span></span>
      </div>
      <p className="goal-detail">
        {g.reached ? <strong className="ok-text">Goal reached! 🎉</strong> : (
          <><strong>{g.points_to_go} points</strong> to go
            {g.plan && <> · quickest route: 100% your {g.plan.games} nearest-to-done game{g.plan.games === 1 ? '' : 's'}
              {' '}({g.plan.achievements.toLocaleString()} achievements)</>}</>
        )}
      </p>
      <p className="muted small">
        Total: {g.achievements.toLocaleString()} of {g.achievements_total.toLocaleString()} achievements in those games
        ({g.total_percent}%). The average counts every game the same; the total weighs big games more.
      </p>
      {!g.reached && g.plan && (
        <p className="muted small">
          {g.days_at_pace
            ? `At your pace (${s.unlocked_last_30_days} in the last 30 days), ${roughly(g.days_at_pace)} to go.`
            : 'No unlocks in the last 30 days, so no estimate yet.'}
        </p>
      )}
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

function GameRow({ game: g, detail }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('videogame', { id: g.app_id })}>
        <GamePicture game={g} className="game-capsule" />
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
      <GamePicture game={g} className="perfect-picture" />
      <span className="perfect-badge">100%</span>
      <span className="perfect-name">{g.name}</span>
      <span className="muted small">{shortDate(g.completed_at)}{g.perfect_rate != null && ` · ${Number(g.perfect_rate)}% of players`}</span>
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
  rare: ['Rarest to 100%', (a, b) => Number(a.perfect_rate ?? 1e9) - Number(b.perfect_rate ?? 1e9)],
  quick: ['Quickest to 100% (median)', (a, b) => (a.sh_median_minutes || 1e9) - (b.sh_median_minutes || 1e9)],
  name: ['Name', (a, b) => a.name.localeCompare(b.name)],
}

// Every game: which to show, a search, a sort, and a row each with its completion. "+ Add a game"
// tracks one Steam's owned-games list leaves out (a free game like Counter-Strike 2, or one you no
// longer own) by its store link or app id.
export function GamesView() {
  const { refreshKey, openPanel, changed, showToast } = useApp()
  const [adding, setAdding] = useState(false)
  const [link, setLink] = useState('')
  const [addError, setAddError] = useState('')
  const [busy, setBusy] = useState(false)
  const addGame = async (e) => {
    e.preventDefault()
    setAddError('')
    // The same check the API makes: a plain app id, or a link with /app/<id> or /stats/<id> in it.
    if (!/^\s*\d+\s*$|\/(app|stats)\/\d+/.test(link)) {
      setAddError("Paste the game's Steam store link (store.steampowered.com/app/...) or its app id.")
      return
    }
    setBusy(true)
    try {
      const game = await api.addExtraVideoGame(link)
      setAdding(false)
      setLink('')
      changed()
      showToast(`Added ${game.name}: ${game.achievements_done} of ${game.achievements_total} achievements`)
    } catch (err) {
      setAddError(err.message)
    } finally {
      setBusy(false)
    }
  }
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
        <button type="button" className="secondary" onClick={() => setAdding(!adding)}>+ Add a game</button>
      </div>
      {adding && (
        <form className="card add-game" onSubmit={addGame}>
          <p className="small muted">For a game with achievements that isn't in your Steam library list, like a free
            game (Counter-Strike 2) or one you no longer own. Paste its Steam store link or app id.</p>
          <div className="lookup-row">
            <input value={link} onChange={(e) => setLink(e.target.value)} required autoFocus
              placeholder="https://store.steampowered.com/app/730/..." aria-label="Steam store link or app id" />
            <button type="submit" className="primary" disabled={busy || !link.trim()}>{busy ? 'Adding...' : 'Add'}</button>
            <button type="button" className="plain" onClick={() => setAdding(false)}>Cancel</button>
          </div>
          {addError && <p className="alert error small">{addError}</p>}
        </form>
      )}
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
                <GamePicture game={g} className="game-capsule" />
                <span className="grow">
                  <span className="item-title">{g.name}</span>
                  <span className="item-meta">
                    {g.achievements_total ? `${g.achievements_done} of ${g.achievements_total} · ${g.percent}%`
                      : g.has_achievements === false ? 'No achievements' : 'Not read yet'}
                    {g.playtime_minutes > 0 && ` · ${playtime(g.playtime_minutes)}`}
                    {g.sh_median_minutes > 0 && ` · median 100% ${playtime(g.sh_median_minutes)}`}
                    {g.perfect_rate != null && ` · ${Number(g.perfect_rate)}% 100%'d`}
                  </span>
                  <CompletionBar game={g} />
                </span>
                {g.extra && <span className="pill" title="Added by hand">Added</span>}
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
      <Stat to="/videogames/dashboard" Icon={GamepadIcon} tone="purple" value={`${s.goal.percent}%`}
        label="Profile completion" sub={s.goal.reached ? `goal ${s.goal.goal_percent}% reached` : `goal ${s.goal.goal_percent}% · ${s.goal.points_to_go} points to go`} />
    </>
  )
}
