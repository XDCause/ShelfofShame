import { useEffect, useMemo, useState } from 'react'
import { api, shortDate, timeAgo } from '../../api.js'
import { ColumnChart } from '../../components/charts.jsx'
import { BellCurveIcon, ClockIcon, GamepadIcon, PuzzleIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { Change, StatSkeleton } from '../../core/Stat.jsx'
import { OtherPlatformsCard, PLATFORMS, PlatformToggles, useCounting, useOtherGames } from './OtherPlatforms.jsx'
import {
  CompletionBar, GamePicture, HandTicked, playtime, rarity, SteamSetup, SyncBar, SyncButton, useSteamAccount, useSteamSummary,
} from './steam.jsx'

// The dashboard: the account and sync, profile completion against your goal, headline tiles,
// what to finish next, what you've just unlocked, your rarest achievements, your latest 100%s -
// Steam, Epic and Ubisoft together, unless some are toggled off.
export function Dashboard() {
  const { account, setAccount, error } = useSteamAccount()
  const [counting] = useCounting()
  const { data: s } = useSteamSummary(counting)
  if (error) return <p className="alert error">{error}</p>
  if (!account) return <p className="muted loading">Loading...</p>
  if (!account.steam_id) return <section className="page"><SteamSetup account={account} setAccount={setAccount} /></section>

  return (
    <section className="page videogames">
      <SyncBar account={account} setAccount={setAccount} />
      <PlatformToggles available={s?.available} />
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
              label="Played" sub={`${s.games} games · ${playtime(s.played.this_week)} this week`} />
          </div>
          <PlaytimeCard platforms={counting} />

          <div className="home-grid">
            <div className="home-stack">
              <section className="card home-card">
                <h2 className="home-card-title">Closest to 100%</h2>
                {s.closest.length === 0 ? <p className="muted small">Nothing part-done. Pick a game and start hunting!</p> : (
                  <ul className="list plain-list">{s.closest.map((g) => <GameRow key={g.app_id} game={g} detail={`${g.left_to_get} to go`} />)}</ul>
                )}
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
              <OtherPlatformsCard />
            </div>
            <div className="home-stack">
              <section className="card home-card">
                <h2 className="home-card-title">Recently unlocked<StreakPill streak={s.streak} /></h2>
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
          </div>
        </>
      )}
    </section>
  )
}

// Playtime over time: today, this week, this month; each day of the last 30; the most played lately.
function PlaytimeCard({ platforms }) {
  const { refreshKey, openPanel } = useApp()
  const [p, setP] = useState(null)
  const key = platforms?.join(',') ?? ''
  useEffect(() => { api.videoGamePlaytime(30, key ? key.split(',') : null).then(setP).catch(() => setP(null)) }, [key, refreshKey])
  if (!p) return null
  const t = p.totals
  const young = t.since && (Date.now() - new Date(`${t.since}T12:00:00`)) / 864e5 < 30
  const rows = p.days.map((d) => ({ label: new Date(`${d.day}T12:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
    value: d.minutes, tip: `${new Date(`${d.day}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })}: ${playtime(d.minutes)}` }))
  return (
    <section className="card home-card vg-playtime">
      <h2 className="home-card-title">Playtime</h2>
      <dl className="vg-played">
        <div><dt>Today</dt><dd>{playtime(t.today)}</dd></div>
        <div><dt>This week</dt><dd>{playtime(t.this_week)}</dd></div>
        <div><dt>Last 7 days</dt><dd>{playtime(t.last_7_days)}</dd></div>
        <div><dt>This month</dt><dd>{playtime(t.this_month)}</dd></div>
      </dl>
      <ColumnChart title="Minutes played each day, the last 30 days" rows={rows} valueLabel="minutes" tickEvery={5} height={150} />
      {p.games.length > 0 && (
        <ul className="list plain-list vg-played-games">{p.games.map((g) => (
          <li key={`${g.platform}${g.app_id}`}><button type="button" className="row-button" onClick={() => openPanel('videogame', { id: g.app_id })}>
            <span className="grow item-title">{g.name}</span><span className="muted small">{playtime(g.minutes)}</span></button></li>))}</ul>
      )}
      <p className="hint">{young ? `Counting since ${shortDate(t.since)}: Steam and Epic only give each game's total, so each sync saves it and the difference is what you played. `
        : 'Each sync saves every game\'s total; the difference from day to day is what you played. '}Games you add by hand count when you change their time.</p>
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
          <span className="item-meta">{g.achievements_done} of {g.achievements_total} · {g.percent}%<HandTicked game={g} />{detail && ` · ${detail}`}</span>
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
      <span className="perfect-badge">100%{g.by_hand && '*'}</span>
      <span className="perfect-name">{g.name}</span>
      <span className="muted small">{shortDate(g.completed_at)}{g.perfect_rate != null && ` · ${Number(g.perfect_rate)}% of players`}</span>
    </button>
  )
}

const SHOWS = [['all', 'All'], ['perfect', '100%'], ['started', 'In progress'], ['untouched', 'Not started'],
  ['no_achievements', 'No achievements'], ['hidden', 'Hidden']]
// Each sort: its label, the value compared (null = no number: always last) and which way it starts
// (1 = smallest first, -1 = biggest first). Clicking the same heading again flips the way.
const num = (v) => (v == null || v === '' ? null : Number(v))
const SORTS = {
  played: ['Recently played', (g) => g.last_played || null, -1],
  percent: ['Completion', (g) => num(g.percent), -1],
  left: ['Fewest to go', (g) => g.left_to_get || null, 1],
  time: ['Most played', (g) => g.playtime_minutes ?? 0, -1],
  rare: ['Rarest to 100%', (g) => num(g.perfect_rate), 1],
  quick: ['Quickest to 100% (median)', (g) => g.sh_median_minutes || null, 1],
  name: ['Name', (g) => g.name.toLowerCase(), 1],
}
function sorter(sort, flipped) {
  const [, value, way] = SORTS[sort]
  const dir = flipped ? -way : way
  const cmp = (x, y) => (typeof x === 'string' ? x.localeCompare(y) : x - y)
  return (a, b) => {
    const x = value(a)
    const y = value(b)
    if (x == null || y == null) return x == null ? (y == null ? 0 : 1) : -1
    return dir * cmp(x, y) || a.name.localeCompare(b.name)
  }
}

// Every game: which to show, a search, a sort, and a row each with its completion. Adding a game
// (Steam, Epic or Ubisoft) is in Find a game (FindGamePanel.jsx).
// The Games page: Steam, Epic or Ubisoft (the switch shows when you have more than Steam), all in
// the same table with the same filters and sorts. ?platform=epic opens on that platform.
export function GamesPage() {
  const { data } = useOtherGames()
  const [counting, setCounting] = useCounting()
  // ?platform=epic (the dashboard's Epic / Ubisoft card) opens on just that platform.
  useEffect(() => {
    const only = new URLSearchParams(window.location.search).get('platform')
    if (only) setCounting([only])
  }, [setCounting])
  const available = ['steam', ...PLATFORMS.map(([id]) => id).filter((id) => data?.platforms.some((p) => p.platform === id))]
  const chosen = (counting ?? available).filter((p) => available.includes(p))
  return <GamesView chosen={chosen.length ? chosen : available} other={data} switcher={<PlatformToggles available={available} />} />
}

// The show-chips for Epic / Ubisoft games (Steam's are worked out by the API).
// (A Ubisoft game you own on Steam is counted as the Steam game: it shows only under Hidden.)
const shown = (g) => !g.hidden && !g.on_steam
const OTHER_SHOWS = {
  all: shown,
  perfect: (g) => shown(g) && g.completed_at,
  started: (g) => shown(g) && g.achievements_done > 0 && !g.completed_at,
  untouched: (g) => shown(g) && g.achievements_total > 0 && !g.achievements_done,
  no_achievements: (g) => shown(g) && !g.achievements_total,
  hidden: (g) => g.hidden || g.on_steam,
}

// The games of the chosen platforms (Steam's from the API, filtered there; Epic / Ubisoft's filtered
// here), in one table; each row says its platform when more than one is shown.
function GamesView({ chosen, other, switcher }) {
  const { refreshKey, openPanel } = useApp()
  const [show, setShow] = useState(() => new URLSearchParams(window.location.search).get('show') ?? 'all')
  const [sort, setSortKey] = useState('played')
  const [flipped, setFlipped] = useState(false)
  // A new sort starts its usual way; the same one again (a heading clicked twice) flips it.
  const setSort = (key) => {
    setFlipped((f) => (key === sort ? !f : false))
    setSortKey(key)
  }
  const [q, setQ] = useState('')
  // Hide games already at 100% (remembered on this device): sorting by progress then starts with the ones to do.
  const [hideDone, setHideDone] = useState(() => { try { return localStorage.getItem('videogames.hideDone') === '1' } catch { return false } })
  const toggleHideDone = () => setHideDone((v) => {
    try { localStorage.setItem('videogames.hideDone', v ? '0' : '1') } catch { /* a private window: just not remembered */ }
    return !v
  })
  const [steamGames, setSteamGames] = useState(null)
  const [error, setError] = useState('')
  const withSteam = chosen.includes('steam')
  useEffect(() => {
    if (withSteam) api.listVideoGames(show).then(setSteamGames).catch((e) => setError(e.message))
  }, [show, refreshKey, withSteam])
  const chosenKey = chosen.join(',')
  // Rebuilt only when the games or the choice change (not on every keystroke in the search box).
  const games = useMemo(() => ((withSteam && !steamGames) || !other ? null : [
    ...(withSteam ? steamGames.map((g) => ({ ...g, platform: 'steam' })) : []),
    ...other.games.filter((g) => chosenKey.split(',').includes(g.platform) && OTHER_SHOWS[show](g)),
  ]), [withSteam, steamGames, other, chosenKey, show])
  const several = chosen.length > 1
  const hiding = hideDone && show !== 'perfect'
  const visible = useMemo(() => (games ?? [])
    .filter((g) => !hiding || !(g.completed_at || Number(g.percent) >= 100))
    .filter((g) => !q.trim() || g.name.toLowerCase().includes(q.trim().toLowerCase()))
    .sort(sorter(sort, flipped)), [games, q, sort, flipped, hiding])

  if (error) return <p className="alert error">{error}</p>
  return (
    <section className="page">
      {switcher}
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
        <button type="button" className="secondary" onClick={() => openPanel('findgame')}>Find a game</button>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Show">
        {SHOWS.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={show === id} onClick={() => setShow(id)}>{label}</button>
        ))}
        <button type="button" className="chip-filter games-hide-done" aria-pressed={hideDone} onClick={toggleHideDone}
          disabled={show === 'perfect'} title="Leave out games you've already 100%'d">Hide 100%</button>
      </div>
      <GameHead sort={sort} flipped={flipped} setSort={setSort} />
      </div>
      {!games ? <p className="muted loading">Loading...</p> : visible.length === 0 ? <p className="empty card">No games here.</p> : (
        <GameTable games={visible} showPlatform={several} onOpen={(g) => openPanel('videogame', { id: g.app_id })} />
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
      {/* three short lines each (the number, what it is, one detail) so the card lines up with the others; the
          dashboard has the rest (the next game to finish, points to go) */}
      <Stat to="/videogames/dashboard" Icon={TrophyIcon} tone="ok" value={s.perfect} label="Games at 100%"
        sub={s.week?.perfect ? `${s.week.perfect > 0 ? '+' : ''}${s.week.perfect} this week` : 'all platforms'} />
      <Stat to="/videogames/dashboard" Icon={GamepadIcon} tone="purple" value={`${s.goal.percent}%`}
        label="Profile complete" sub={s.goal.reached ? `goal ${s.goal.goal_percent}% reached` : `goal ${s.goal.goal_percent}%`} />
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
function GameHead({ sort, flipped, setSort }) {
  const heads = [['name', 'Game'], ['percent', 'Progress'], ['time', COLUMNS.time], ['quick', COLUMNS.median], ['rare', COLUMNS.rate]]
  return (
    <div className="game-table">
      <p className="game-key small muted" aria-hidden="true">
        {Object.values(COLUMNS).map(({ Icon, what }) => <span key={what}><Icon size={14} /> {what}</span>)}
      </p>
      <div className="game-head" role="group" aria-label="Sort by">
        <span />
        {heads.map(([key, head]) => (
          <button key={key} type="button" className="game-head-cell" aria-pressed={sort === key}
            onClick={() => setSort(key)} title={sort === key ? 'Click again to reverse'
              : `Sort by ${typeof head === 'string' ? head.toLowerCase() : head.what.toLowerCase()}`}>
            {typeof head === 'string' ? head : <><head.Icon size={15} aria-hidden="true" /> {head.label}</>}
            {sort === key && <span aria-hidden="true">{flipped ? ' ▴' : ' ▾'}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

// The games as table rows on a PC (the pinned headings say what each column is, so the rows show
// just the numbers) and as cards on a phone (where each number keeps its icon).
const PLATFORM_NAME = Object.fromEntries(PLATFORMS)

function GameTable({ games, onOpen, showPlatform = false }) {
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
                  {showPlatform && <span className={`pill platform-${g.platform}`}>{PLATFORM_NAME[g.platform]}</span>}
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
                      <span className="muted"> · {Number(g.percent)}%</span><HandTicked game={g} /></span>
                    <CompletionBar game={g} />
                  </>
                ) : <span className="muted small">{g.has_achievements === false ? 'No achievements'
                  : g.platform !== 'steam' && !g.source_id && !g.steam_app_id ? 'No achievements' : 'Not read yet'}</span>}
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
function StreakPill({ streak }) {
  if (!streak?.current) return null
  const what = `${streak.current} day${streak.current === 1 ? '' : 's'} in a row with an unlock${
    streak.unlocked_today ? '' : ' - unlock one today to keep it going'}. Longest: ${streak.longest} days.`
  return <span className="pill low streak-pill" title={what} aria-label={what}>🔥 {streak.current}-day streak</span>
}
