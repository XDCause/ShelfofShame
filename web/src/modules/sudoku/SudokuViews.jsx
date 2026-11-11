import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, shortDate, timeAgo } from '../../api.js'
import { BarList, LineChart } from '../../components/charts.jsx'
import { SudokuIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { UnlockCalendar } from '../videogames/StatsView.jsx'
import { DIFFICULTIES, TECHNIQUE, TECHNIQUES } from './engine.js'
import { DIFF_TONE, PAPER_LINKS, clockText, dailyDifficulty, readLocal, uploadLocal, useSudokuSummary } from './sudokuParts.js'

// Sudoku's pages besides Play: Today (the daily puzzle, the game in progress, a new game, streaks), Learn (every
// technique the hints use, and a puzzle to practise each), Stats.

const plural = (n, one, many = `${one}s`) => `${n.toLocaleString()} ${n === 1 ? one : many}`

export function TodayView() {
  const { data: s, error } = useSudokuSummary()
  const { changed, showToast } = useApp()
  const [local, setLocal] = useState(readLocal)
  useEffect(() => {                       // a game played offline: saved now the PC answers
    if (!local || !s) return
    uploadLocal().then((g) => { if (g) { setLocal(null); showToast('Saved the game you played offline'); changed() } }).catch(() => {})
  }, [s])   // eslint-disable-line react-hooks/exhaustive-deps
  if (error && !local) return <p className="alert error">{error}</p>
  if (!s) return local ? <LocalCard /> : <p className="muted loading">Loading...</p>
  const daily = s.daily
  const dailyDiff = daily?.difficulty ?? dailyDifficulty(s.today)
  return (
    <section className="page sudoku">
      <div className="home-grid">
        <div className="home-stack">
          <section className={`card home-card sdk-daily${daily?.status === 'solved' ? ' done' : ''}`}>
            <span className="sdk-daily-date">{new Date(`${s.today}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
            <h2 className="home-card-title">Daily puzzle</h2>
            <p><span className={`pill ${DIFF_TONE[dailyDiff]}`}>{dailyDiff}</span>{' '}
              {daily?.status === 'solved' ? <strong>Solved in {clockText(daily.seconds)} ✓</strong>
                : daily ? <span className="muted small">{daily.filled} of 81 filled · {clockText(daily.seconds)}</span>
                  : <span className="muted small">Easy on Mondays, building to Expert at the weekend.</span>}</p>
            <div className="button-row">
              {daily?.status === 'solved' ? <Link className="button secondary" to={`/sudoku/play?game=${daily.game_id}`}>See it</Link>
                : <Link className="button primary" to={daily ? `/sudoku/play?game=${daily.game_id}` : '/sudoku/play?daily=1'}>{daily ? 'Carry on' : 'Play today\'s puzzle'}</Link>}
            </div>
            <p className="muted small">Daily streak: {plural(s.daily_streak.current, 'day')}{s.daily_streak.longest > s.daily_streak.current && ` · best ${s.daily_streak.longest}`}</p>
            <PastDailies today={s.today} />
          </section>
          <section className={`card home-card sdk-weekly${s.weekly?.status === 'solved' ? ' done' : ''}`}>
            <span className="sdk-daily-date">Week of {new Date(`${s.week_of}T12:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'long' })}</span>
            <h2 className="home-card-title">The weekly</h2>
            <p className="small">One seriously hard 9 × 9 a week, from the app's refined hardest list - well beyond the hints'
              techniques, so give it a few sittings. A new one every Monday.</p>
            <p>{s.weekly?.status === 'solved' ? <strong>Solved in {clockText(s.weekly.seconds)} ✓</strong>
              : s.weekly ? <span className="muted small">{s.weekly.filled} of {s.weekly.size * s.weekly.size} filled · {clockText(s.weekly.seconds)}</span> : null}</p>
            <Link className={`button ${s.weekly?.status === 'solved' ? 'secondary' : 'primary'}`} to={s.weekly ? `/sudoku/play?game=${s.weekly.game_id}` : '/sudoku/play?weekly=1'}>
              {s.weekly?.status === 'solved' ? 'See it' : s.weekly ? 'Carry on' : "Start this week's"}</Link>
          </section>
          {local && <LocalCard />}
          {s.playing && s.playing.game_id !== daily?.game_id && (
            <section className="card home-card">
              <h2 className="home-card-title">Carry on</h2>
              <p><span className={`pill ${DIFF_TONE[s.playing.difficulty]}`}>{s.playing.difficulty}</span>{' '}
                <span className="muted small">{s.playing.filled} of 81 filled · {clockText(s.playing.seconds)} · {timeAgo(s.playing.updated_at)}</span></p>
              <Link className="button primary" to={`/sudoku/play?game=${s.playing.game_id}`}>Carry on</Link>
              {s.playing_count > 1 && <p className="muted small">{s.playing_count - 1} more on the go (Stats → Games).</p>}
            </section>
          )}
        </div>
        <div className="home-stack">
          <RatingCard rating={s.rating} />
          <section className="card home-card">
            <h2 className="home-card-title">New game</h2>
            <div className="sdk-pick compact">
              {DIFFICULTIES.map((d) => <Link key={d} className={`sdk-pick-btn ${DIFF_TONE[d]}`} to={`/sudoku/play?new=${d}`}><strong>{d}</strong></Link>)}
            </div>
            <div className="button-row">
              <Link className="button plain small" to="/sudoku/play">16 × 16 giants</Link>
              <Link className="button plain small" to="/sudoku/play?enter=1">Type in a puzzle from a book</Link>
              <Link className="button plain small" to="/sudoku/learn">Practise a technique</Link>
            </div>
          </section>
          <div className="home-stats">
            <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="ok" value={s.solved_this_week} label="Solved this week" sub={`${plural(s.solved, 'puzzle')} in all`} />
            <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="teal" value={plural(s.streak.current, 'day')} label="Streak"
              sub={s.streak.longest ? `longest ${plural(s.streak.longest, 'day')}` : 'solve one a day to start one'} />
            <Stat to="/sudoku/awards" Icon={SudokuIcon} tone="purple" value={`${s.awards.earned}/${s.awards.of}`} label="Achievements"
              sub={s.awards.latest[0] ? `latest: ${s.awards.latest[0].name}` : 'solve a puzzle to earn the first'} />
          </div>
          <section className="card home-card">
            <h2 className="home-card-title">Events and the Hardest 100</h2>
            <p className="small">The Grand Tour: {s.sets['grand-tour']?.furthest ?? 0} of 30 stops · The Hardest 100: {s.sets.hardest?.solved ?? 0} solved</p>
            <Link className="button secondary small" to="/sudoku/events">Open the paths</Link>
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Today's paper</h2>
            <p className="small">Doing a newspaper's sudoku? Type it in (or paste it) for hints, its grade, your time and rating - and say which paper.
              The app doesn't fetch papers' puzzles: they're licensed, often paywalled, and not ours to copy.</p>
            <div className="button-row">
              <Link className="button secondary small" to="/sudoku/play?enter=1">Type in today's</Link>
              {PAPER_LINKS.map(([name, url]) => <a key={url} className="button plain small" href={url} target="_blank" rel="noreferrer">{name} ↗</a>)}
            </div>
          </section>
          {s.recent.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Lately</h2>
              <ul className="list plain-list">{s.recent.map((g) => <GameRow key={g.game_id} game={g} />)}</ul>
            </section>
          )}
        </div>
      </div>
    </section>
  )
}

// The last three weeks of daily puzzles: solved, started or missed - a missed one can still be played.
function PastDailies({ today }) {
  const { refreshKey } = useApp()
  const [games, setGames] = useState(null)
  const [open, setOpen] = useState(null)              // the day whose details show underneath
  useEffect(() => { api.sudokuDailies(21).then(setGames).catch(() => setGames([])) }, [refreshKey])
  if (!games) return null
  const byDay = Object.fromEntries(games.map((g) => [g.daily_on, g]))
  const days = Array.from({ length: 21 }, (_, i) => {
    const d = new Date(`${today}T12:00:00`)
    d.setDate(d.getDate() - 20 + i)
    return d.toLocaleDateString('en-CA')
  })
  const stateOf = (day) => { const g = byDay[day]; return g?.status === 'solved' ? 'done' : g ? 'started' : day === today ? 'today' : 'missed' }
  return (
    <>
      <div className="sdk-past" role="group" aria-label="The last three weeks of daily puzzles">
        {days.map((day) => {
          const g = byDay[day]
          const state = stateOf(day)
          const text = new Date(`${day}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
          return (
            <button key={day} type="button" className={`sdk-past-day ${state}`} aria-pressed={open === day} aria-controls="sdk-past-detail"
              onClick={() => setOpen(open === day ? null : day)}
              aria-label={`${text}: ${(g?.difficulty ?? dailyDifficulty(day))}, ${state === 'done' ? `solved in ${clockText(g.seconds)}` : state === 'started' ? 'started' : state === 'today' ? "today's" : 'not played'}`}>
              {Number(day.slice(8))}</button>
          )
        })}
      </div>
      {open && <PastDay day={open} game={byDay[open]} state={stateOf(open)} />}
    </>
  )
}

// A daily puzzle's details, under the three weeks: its day, difficulty, how it went, and a way in.
function PastDay({ day, game: g, state }) {
  const difficulty = g?.difficulty ?? dailyDifficulty(day)
  const when = new Date(`${day}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })
  return (
    <div className="sdk-past-detail" id="sdk-past-detail" aria-live="polite">
      <p className="sdk-past-head"><strong>{when}</strong> <span className={`pill ${DIFF_TONE[difficulty]}`}>{difficulty}</span></p>
      <p className="muted small">{state === 'done' ? `Solved in ${clockText(g.seconds)}${g.hints ? ` · ${plural(g.hints, 'hint')}` : ''}${g.mistakes ? ` · ${plural(g.mistakes, 'mistake')}` : ''}${!g.hints && !g.mistakes ? ' · clean' : ''}`
        : state === 'started' ? `Started: ${g.filled} of 81 filled · ${clockText(g.seconds)} so far`
          : state === 'today' ? "Today's puzzle - not started yet." : 'Not played - you can still do it (it counts towards your daily streak).'}</p>
      <Link className={`button small ${state === 'done' ? 'secondary' : 'primary'}`} to={g ? `/sudoku/play?game=${g.game_id}` : `/sudoku/play?daily=1&day=${day}`}>
        {state === 'done' ? 'See it' : state === 'started' ? 'Carry on' : 'Play it'}</Link>
    </div>
  )
}

// Your rating and rank (api/app/sudoku.py rating()): every finished game moves it.
function RatingCard({ rating: r }) {
  if (!r) return null
  const span = r.rank.next ? r.rank.next.at - r.rank.from : 1
  return (
    <section className="card home-card sdk-rating">
      <div className="section-head">
        <h2 className="home-card-title">Rating</h2>
        <span className="pill tint">{r.rank.name}</span>
      </div>
      <p><strong className="sdk-done-time">{r.now}</strong>
        {r.last && <span className={`small ${r.last.change >= 0 ? 'ok-text' : 'sdk-down'}`}> {r.last.change >= 0 ? '+' : '−'}{Math.abs(r.last.change)} last game</span>}
        <span className="muted small"> · peak {r.peak}</span></p>
      {r.rank.next && (
        <>
          <span className="fill-bar tint" role="img" aria-label={`${r.now - r.rank.from} of ${span} to ${r.rank.next.name}`}>
            <span style={{ width: `${Math.max(0, Math.min(100, (100 * (r.now - r.rank.from)) / span))}%` }} /></span>
          <p className="muted small">{r.rank.next.at - r.now} to {r.rank.next.name}. Faster, cleaner solves of harder puzzles earn the most.</p>
        </>
      )}
      {!r.games && <p className="muted small">Finish a puzzle to get your first rating (everyone starts at 1000).</p>}
    </section>
  )
}

function LocalCard() {
  const g = readLocal()
  if (!g) return null
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Played on this device</h2>
      <p className="muted small">A {g.data.difficulty} game made while the PC couldn't be reached. It's saved to the app as soon as the PC answers.</p>
      <Link className="button primary" to="/sudoku/play?game=local">{g.solved ? 'See it' : 'Carry on'}</Link>
    </section>
  )
}

function GameRow({ game: g }) {
  const navigate = useNavigate()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => navigate(`/sudoku/play?game=${g.game_id}`)}>
        <span className={`pill ${DIFF_TONE[g.difficulty]}`}>{g.difficulty}</span>
        {g.size === 16 && <span className="pill tint">16×16</span>}
        <span className="grow">
          <span className="item-title">{g.daily_on ? `Daily · ${shortDate(g.daily_on)}` : g.practice ? `Practice: ${TECHNIQUE[g.practice]?.name ?? g.practice}` : g.source === 'typed' ? 'Typed in' : 'New game'}</span>
          <span className="item-meta">{g.status === 'solved' ? `Solved ${timeAgo(g.finished_at)}` : g.status === 'gave_up' ? 'Gave up' : `${g.filled} of 81 filled`}
            {g.hints ? ` · ${plural(g.hints, 'hint')}` : ''}{g.status === 'solved' && !g.hints && !g.mistakes ? ' · clean' : ''}</span>
        </span>
        <span className="sdk-row-time">{clockText(g.seconds)}</span>
      </button>
    </li>
  )
}

// Every technique, easiest first: what it is, how often you've met it, and a puzzle made to need it.
export function LearnView() {
  const { refreshKey } = useApp()
  const [st, setSt] = useState(null)
  useEffect(() => { api.sudokuStats().then(setSt).catch(() => setSt(null)) }, [refreshKey])
  useEffect(() => {
    const id = window.location.hash.slice(1)
    if (id) document.getElementById(`tech-${id}`)?.scrollIntoView({ block: 'center' })
  }, [])
  return (
    <section className="page sudoku">
      <section className="card home-card">
        <h2 className="home-card-title">How the hints teach</h2>
        <p className="small">A hint first names the technique and where to look. Ask again and it shows the cells and explains why;
          once more and it does it for you. A wrong digit always comes first. Notes matter from Medium up: <strong>Fill notes</strong> puts
          every possible digit in each cell, and many techniques work by crossing notes out.</p>
      </section>
      {DIFFICULTIES.slice(0, 4).map((d, i) => (
        <section key={d} className="sdk-learn-level">
          <h2 className="sdk-learn-head"><span className={`pill ${DIFF_TONE[d]}`}>{d}</span></h2>
          <div className="sdk-learn-grid">
            {TECHNIQUES.filter((t) => t.level === i + 1).map((t) => (
              <article key={t.key} id={`tech-${t.key}`} className={`card sdk-tech${window.location.hash === `#${t.key}` ? ' focus' : ''}`}>
                <h3>{t.name}</h3>
                <p className="small">{t.about}</p>
                {st && (st.hints_by_technique[t.key] || st.techniques_needed[t.key]) ? (
                  <p className="muted small">{[st.techniques_needed[t.key] && `needed in ${plural(st.techniques_needed[t.key], 'puzzle')} you solved`,
                    st.hints_by_technique[t.key] && `${plural(st.hints_by_technique[t.key], 'hint')}`].filter(Boolean).join(' · ')}</p>
                ) : null}
                {t.level > 1 && <Link className="button secondary small" to={`/sudoku/play?practice=${t.key}`}>Practise it</Link>}
              </article>
            ))}
          </div>
        </section>
      ))}
      <section className="card home-card">
        <h2 className="home-card-title"><span className={`pill ${DIFF_TONE.Extreme}`}>Extreme</span></h2>
        <p className="small">Puzzles none of these techniques can finish. They need chains (following "if this, then that" through
          the notes), uniqueness tricks or plain patience. The hint shows the next digit when it runs out of logic.</p>
      </section>
    </section>
  )
}

export function StatsView() {
  const { refreshKey } = useApp()
  const [st, setSt] = useState(null)
  const [games, setGames] = useState(null)
  const [diff, setDiff] = useState('Medium')
  const [error, setError] = useState('')
  useEffect(() => {
    api.sudokuStats().then((x) => {
      setSt(x)
      const most = [...x.per_difficulty].sort((a, b) => b.solved - a.solved)[0]
      if (most?.solved) setDiff(most.difficulty)
    }).catch((e) => setError(e.message))
    api.sudokuGames().then(setGames).catch(() => setGames([]))
  }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!st) return <p className="muted loading">Loading...</p>
  const t = st.totals
  if (!t.solved && !games?.length) {
    return <section className="page sudoku"><EmptyState Icon={SudokuIcon} title="Nothing played yet">Solve a puzzle and your times show up here.</EmptyState></section>
  }
  const times = st.solves.filter((x) => x.difficulty === diff && x.size === 9).map((x) => ({ x: x.day, y: Math.round(x.seconds / 6) / 10, tip: clockText(x.seconds) }))
  const techRows = (obj) => Object.entries(obj).filter(([k]) => TECHNIQUE[k]).sort((a, b) => b[1] - a[1])
    .map(([k, n]) => ({ label: TECHNIQUE[k].name, value: n, text: String(n) }))
  return (
    <section className="page sudoku stats">
      <div className="home-stats">
        <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="ok" value={t.solved} label="Solved" sub={`${t.dailies} daily · ${t.gave_up} given up`} />
        <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="teal" value={plural(st.streak.current, 'day')} label="Streak" sub={`longest ${plural(st.streak.longest, 'day')}`} />
        <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="purple" value={t.clean} label="Clean solves" sub="no hints, no mistakes" />
        <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="tint" value={clockText(t.seconds)} label="Time solving" sub={`${plural(t.hints, 'hint')} asked`} />
      </div>
      <div className="home-grid">
        <section className="card home-card wide-card">
          <h2 className="home-card-title">By difficulty (9 × 9)</h2>
          <div className="sdk-table-wrap">
            <table className="sdk-table">
              <thead><tr><th scope="col">Difficulty</th><th scope="col">Solved</th><th scope="col">Best</th><th scope="col">Average</th><th scope="col">Last 10</th><th scope="col">Clean</th></tr></thead>
              <tbody>
                {st.per_difficulty.map((p) => (
                  <tr key={p.difficulty}>
                    <th scope="row"><span className={`pill ${DIFF_TONE[p.difficulty]}`}>{p.difficulty}</span></th>
                    <td>{p.solved}</td><td>{clockText(p.best)}</td><td>{clockText(p.average)}</td>
                    <td>{p.recent != null && p.average != null ? <>{clockText(p.recent)} {p.recent < p.average ? <span className="ok-text" title="faster than your average">↓</span> : null}</> : '—'}</td>
                    <td>{p.clean}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        {t.giants > 0 && (
          <section className="card home-card wide-card">
            <h2 className="home-card-title">16 × 16</h2>
            <div className="sdk-table-wrap">
              <table className="sdk-table">
                <thead><tr><th scope="col">Difficulty</th><th scope="col">Solved</th><th scope="col">Best</th><th scope="col">Average</th><th scope="col">Clean</th></tr></thead>
                <tbody>
                  {st.giant.map((p) => (
                    <tr key={p.difficulty}><th scope="row"><span className={`pill ${DIFF_TONE[p.difficulty]}`}>{p.difficulty}</span></th>
                      <td>{p.solved}</td><td>{clockText(p.best)}</td><td>{clockText(p.average)}</td><td>{p.clean}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Rating</h2>
          {st.rating.length > 1 ? <LineChart title="Your rating" rows={st.rating.map((x) => ({ x: x.day, y: x.rating }))} valueLabel="rating" />
            : <p className="muted small">Finish two puzzles to see your rating's line.</p>}
          <p className="muted small">Ranks: Novice · Apprentice 900 · Solver 1050 · Adept 1200 · Expert 1400 · Master 1600 · Grandmaster 1800 · Legend 2000.
            Each finished game is a match against the puzzle: its difficulty against your rating, and your time against the par
            (Easy 6 min, Medium 10, Hard 18, Expert 30, Extreme 50; three times that for a 16 × 16), less a bit for each mistake and more
            for each hint. Giving up counts as a loss. Practice lessons don't count.</p>
        </section>
        <MistakeMap byCell={st.mistakes_by_cell} byDigit={st.mistakes_by_digit} />
        <UnlockCalendar title="Days you solved one" one="puzzle" many="puzzles" today={st.today} days={st.by_day} streak={st.streak} />
        <section className="card home-card wide-card">
          <div className="section-head">
            <h2 className="home-card-title">Your times</h2>
            <select value={diff} onChange={(e) => setDiff(e.target.value)} aria-label="Difficulty">{DIFFICULTIES.map((d) => <option key={d}>{d}</option>)}</select>
          </div>
          {times.length > 1 ? <LineChart title={`${diff} solve times`} rows={times} valueLabel="minutes" />
            : <p className="muted small">Solve two {diff} puzzles to see the line (minutes per solve).</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Techniques your puzzles needed</h2>
          {techRows(st.techniques_needed).length ? <BarList title="Technique" valueLabel="Puzzles" rows={techRows(st.techniques_needed)} />
            : <p className="muted small">Shows once you've solved some.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Hints you asked for</h2>
          {techRows(st.hints_by_technique).length ? <BarList title="Technique" valueLabel="Hints" rows={techRows(st.hints_by_technique)} />
            : <p className="muted small">No hints yet - nice.</p>}
        </section>
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Games</h2>
          {!games ? <p className="muted small loading">Loading...</p> : <ul className="list plain-list">{games.slice(0, 60).map((g) => <GameRow key={g.game_id} game={g} />)}</ul>}
        </section>
      </div>
    </section>
  )
}

// Where your wrong digits go (classic 9 x 9s): a heat map of the board, and the digits you slip on most.
function MistakeMap({ byCell, byDigit }) {
  const total = byCell.reduce((a, b) => a + b, 0)
  const most = Math.max(1, ...byCell)
  const digits = Object.entries(byDigit).sort((a, b) => b[1] - a[1])
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Where mistakes happen</h2>
      {!total ? <p className="muted small">No wrong digits yet - or none since replays began. They'll show here, cell by cell.</p> : (
        <>
          <div className="sdk-heat" role="img" aria-label={`${total} wrong digits across the board; most in one cell: ${most}`}>
            {byCell.map((n, i) => (
              <span key={i} className={`sdk-heat-cell${(i % 9) % 3 === 2 && i % 9 < 8 ? ' edge-r' : ''}${Math.floor(i / 9) % 3 === 2 && i < 72 ? ' edge-b' : ''}`}
                style={{ '--heat': n / most }} title={`r${Math.floor(i / 9) + 1}c${(i % 9) + 1}: ${n}`}>{n || ''}</span>
            ))}
          </div>
          <p className="muted small">{total} wrong digit{total === 1 ? '' : 's'} in all. You slip most on {digits.slice(0, 3).map(([d, n]) => `${d}s (${n})`).join(', ')}.</p>
        </>
      )}
    </section>
  )
}
