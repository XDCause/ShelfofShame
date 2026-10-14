import { useEffect, useMemo, useState } from 'react'
import { api, shortDate, timeAgo } from '../../api.js'
import { BellCurveIcon, ClockIcon, GamepadIcon, PuzzleIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { Change, StatSkeleton } from '../../core/Stat.jsx'
import {
  CompletionBar, GamePicture, playtime, rarity, SteamSetup, SyncBar, SyncButton, useSteamAccount, useSteamSummary,
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
              sub={`of ${s.with_achievements} games`} change={<Change value={s.week.perfect} />} />
            <Stat to="/videogames/games?show=started" Icon={GamepadIcon} tone="tint" value={s.started} label="In progress"
              sub={s.average_percent != null ? `${s.average_percent}% average` : 'started, not finished'}
              change={<Change value={s.week.in_progress} />} />
            <Stat to="/videogames/games" Icon={TrophyIcon} tone="purple" value={s.achievements.toLocaleString()}
              label="Achievements" sub={`${s.unlocked_this_month} this month`} change={<Change value={s.week.achievements} />} />
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
              <h2 className="home-card-title">Recently unlocked<StreakPill streak={s.streak} /></h2>
              <AchievementList items={s.recent} when />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Quick wins</h2>
              <p className="muted small chart-sub">Started games with the least time left to 100% (from SteamHunters' median)</p>
              {s.quick_wins.length === 0 ? <p className="muted small">Nothing yet - Sync now reads how long others took.</p> : (
                <ul className="list plain-list">
                  {s.quick_wins.map((g) => (
                    <GameRow key={g.app_id} game={g} detail={`about ${playtime(g.minutes_left)} left${
                      g.perfect_rate != null ? ` · ${Number(g.perfect_rate)}% of players 100% it` : ''}`} />
                  ))}
                </ul>
              )}
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
          <strong className="goal-percent">{g.percent}%<Change value={s.week.percent} unit="%" /></strong>
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
        ({g.total_percent}%<Change value={s.week.total_percent} unit="%" />). The average counts every game the same; the
        total weighs big games more. The small +/− numbers are the change in the last 7 days.
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

export function AchievementList({ items, when = false }) {
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

export function PerfectCard({ game: g }) {
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
      {/* Pinned under the top bar while the list scrolls: search, sort, filters and the headings. */}
      <div className="games-pinned">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search your games..." aria-label="Search your games" />
        <label className="sort view-controls">
          <span className="muted small">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort games">
            {Object.entries(SORTS).map(([id, [label]]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </label>
        <SyncButton />
        <button type="button" className="secondary" onClick={() => setAdding(!adding)}>+ Add a game</button>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Show">
        {SHOWS.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={show === id} onClick={() => setShow(id)}>{label}</button>
        ))}
      </div>
      <GameHead sort={sort} setSort={setSort} />
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
      {!games ? <p className="muted loading">Loading...</p> : visible.length === 0 ? <p className="empty card">No games here.</p> : (
        <GameTable games={visible} onOpen={(g) => openPanel('videogame', { id: g.app_id })} />
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
        sub={s.closest[0] ? `next: ${s.closest[0].name}` : 'Steam'} change={s.week && <Change value={s.week.perfect} />} />
      <Stat to="/videogames/dashboard" Icon={GamepadIcon} tone="purple" value={`${s.goal.percent}%`}
        change={s.week && <Change value={s.week.percent} unit="%" />}
        label="Profile completion" sub={s.goal.reached ? `goal ${s.goal.goal_percent}% reached` : `goal ${s.goal.goal_percent}% · ${s.goal.points_to_go} points to go`} />
    </>
  )
}

// What each number is: an icon, a name and what it means (headers, tooltips, the key).
const COLUMNS = {
  time: { Icon: ClockIcon, label: 'Your time', what: 'Your playtime' },
  median: { Icon: BellCurveIcon, label: 'Median', what: 'Median time to 100% (SteamHunters players)' },
  rate: { Icon: TrophyIcon, label: '100% rate', what: "Players who started it and 100%'d it (SteamHunters)" },
}

function Stat1({ kind, value }) {
  const { Icon, what } = COLUMNS[kind]
  return (
    <span className={value == null ? 'game-stat none' : 'game-stat'} title={what}>
      <Icon size={16} aria-hidden="true" /><span>{value ?? '—'}</span>
      <span className="visually-hidden">{what}</span>
    </span>
  )
}

// The column headings (pinned with the search and filters; click one to sort by it). On a phone
// there are no columns, so they become a small key to the icons on each card.
function GameHead({ sort, setSort }) {
  const heads = [['name', 'Game'], ['percent', 'Progress'], ['time', COLUMNS.time], ['quick', COLUMNS.median], ['rare', COLUMNS.rate]]
  return (
    <div className="game-table">
      <p className="game-key small muted" aria-hidden="true">
        {Object.values(COLUMNS).map(({ Icon, what }) => <span key={what}><Icon size={14} /> {what}</span>)}
      </p>
      <div className="game-head" role="row">
        <span />
        {heads.map(([key, head]) => (
          <button key={key} type="button" className="game-head-cell" aria-pressed={sort === key}
            onClick={() => setSort(key)} title={`Sort by ${typeof head === 'string' ? head.toLowerCase() : head.what.toLowerCase()}`}>
            {typeof head === 'string' ? head : <><head.Icon size={15} aria-hidden="true" /> {head.label}</>}
            {sort === key && <span aria-hidden="true"> ▾</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

// The games as table rows on a PC (the pinned headings say what each column is, so the rows show
// just the numbers) and as cards on a phone (where each number keeps its icon).
function GameTable({ games, onOpen }) {
  return (
    <div className="game-table">
      <ul className="game-rows">
        {games.map((g) => (
          <li key={g.app_id}>
            <button type="button" className="game-row" onClick={() => onOpen(g)}>
              <GamePicture game={g} className="game-capsule" />
              <span className="game-name">
                <span className="item-title">{g.name}</span>
                <span className="game-tags">
                  {g.completed_at && <span className="pill ok"><TrophyIcon size={12} /> 100%</span>}
                  {g.dlc_count > 0 && <DlcBadge game={g} />}
                  {g.extra && <span className="pill" title="Added by hand">Added</span>}
                  {g.last_played && <span className="muted small">Played {shortDate(g.last_played)}</span>}
                </span>
              </span>
              <span className="game-progress">
                {g.achievements_total ? (
                  <>
                    <span className="game-progress-text"><strong>{g.achievements_done}</strong> / {g.achievements_total}
                      <span className="muted"> · {Number(g.percent)}%</span></span>
                    <CompletionBar game={g} />
                  </>
                ) : <span className="muted small">{g.has_achievements === false ? 'No achievements' : 'Not read yet'}</span>}
              </span>
              <span className="game-stats">
                <Stat1 kind="time" value={g.playtime_minutes > 0 ? playtime(g.playtime_minutes) : null} />
                <Stat1 kind="median" value={g.sh_median_minutes > 0 ? playtime(g.sh_median_minutes) : null} />
                <Stat1 kind="rate" value={g.perfect_rate != null ? `${Number(g.perfect_rate)}%` : null} />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

// "DLC" beside a game's name when a DLC adds achievements (they count towards 100%); the tooltip says
// how many DLCs, how many achievements they add and how many of those you have.
function DlcBadge({ game: g }) {
  const what = `${g.dlc_count} DLC${g.dlc_count === 1 ? '' : 's'} with achievements: ${g.dlc_done} of ${g.dlc_achievements}`
  return <span className="pill purple dlc-badge" title={what} aria-label={what}><PuzzleIcon size={12} /> DLC</span>
}

// "🔥 5-day streak" beside a heading: days in a row with an unlock (still alive until today ends).
export function StreakPill({ streak }) {
  if (!streak?.current) return null
  const what = `${streak.current} day${streak.current === 1 ? '' : 's'} in a row with an unlock${
    streak.unlocked_today ? '' : ' - unlock one today to keep it going'}. Longest: ${streak.longest} days.`
  return <span className="pill low streak-pill" title={what} aria-label={what}>🔥 {streak.current}-day streak</span>
}
