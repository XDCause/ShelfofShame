import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, today as todayIso } from '../../api.js'
import Landscape from '../../components/Landscape.jsx'
import { useApp } from '../../core/app-context.js'
import { EVENTS, HARDEST, THEMES, eventOpen, stops } from './events.js'
import { DIFF_TONE, clockText } from './sudokuParts.js'

// Sudoku > Events: each event's winding path (a stop opens when the one before is solved; board themes to earn along
// the way) and the Hardest 100 (play them in any order; number 100 is the hardest).
export function EventsView() {
  const { refreshKey } = useApp()
  const [sets, setSets] = useState(null)
  useEffect(() => {
    Promise.all([...EVENTS.map((e) => e.key), 'hardest'].map((k) => api.sudokuSet(k).then((g) => [k, g]).catch(() => [k, {}])))
      .then((pairs) => setSets(Object.fromEntries(pairs)))
  }, [refreshKey])
  if (!sets) return <p className="muted loading">Loading...</p>
  const day = todayIso()
  return (
    <section className="page sudoku">
      {EVENTS.map((e) => <Path key={e.key} event={e} games={sets[e.key]} open={eventOpen(e, day)} />)}
      <Hardest games={sets.hardest} />
    </section>
  )
}

const THEME_NAME = Object.fromEntries(THEMES.map((t) => [t.key, t.name]))

// The path: stops on a winding line, done / next / locked; a reward flag where a theme is earned.
function Path({ event, games, open }) {
  const all = stops(event)
  const solved = all.filter((s) => games[s.stop]?.status === 'solved').length
  const next = all.find((s) => games[s.stop]?.status !== 'solved')
  const W = 100, STEP = 84
  const pos = (i) => ({ x: 50 + 26 * Math.sin(i * 0.9), y: 48 + i * STEP })
  const pts = all.map((_, i) => { const p = pos(i); return `${(p.x * W) / 100},${p.y}` })
  const walked = all.filter((s) => games[s.stop]?.status === 'solved').length   // (stops open in order: the trail so far)
  const nextReward = all.find((s) => s.reward && games[s.stop]?.status !== 'solved')
  const art = event.art ?? {}
  return (
    <section className="card sdk-event" style={{ '--event-hue': art.hue ?? 'var(--tint)' }}>
      <header className="sdk-event-hero">
        <Landscape scene={art.scene} seed={art.seed} time={art.time} extras={art.extras} hue={art.hue} strip />
        <div className="sdk-event-title">
          <h2>{event.name}</h2>
          <p>{event.blurb}</p>
          <span className="sdk-event-progress" role="img" aria-label={`${solved} of ${event.length} stops`}>
            <span style={{ width: `${(100 * solved) / event.length}%` }} /></span>
          <p className="sdk-event-meta">{solved} of {event.length} stops
            {nextReward && ` · next reward: ${THEME_NAME[nextReward.reward]} at ${nextReward.name}`}</p>
        </div>
      </header>
      {!open && <p className="alert small sdk-event-note">{solved ? 'This event has closed - your stops stay.' : `Opens ${new Date(`${event.from}T12:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'long' })}.`}</p>}
      <div className="sdk-path" style={{ height: 56 + all.length * STEP }}>
        <svg className="sdk-path-line" viewBox={`0 0 ${W} ${56 + all.length * STEP}`} preserveAspectRatio="none" aria-hidden="true">
          <polyline className="trail" points={pts.join(' ')} vectorEffect="non-scaling-stroke" />
          {walked > 0 && <polyline className="walked" points={pts.slice(0, walked + (walked < all.length ? 1 : 0)).join(' ')} vectorEffect="non-scaling-stroke" />}
        </svg>
        {all.map((s, i) => {
          const g = games[s.stop]
          const done = g?.status === 'solved'
          const notYet = event.opens && event.opens(s.stop) > todayIso()        // an Advent door: opens on its day
          const current = open && s.stop === next?.stop && !notYet
          const playable = done || g || current
          const p = pos(i)
          const label = `${s.name}: ${s.difficulty}${s.size === 16 ? ' 16 × 16' : ''}${done ? `, solved in ${clockText(g.seconds)}` : current ? ', next' : g ? ', started' : notYet ? ', opens on its day' : ', locked'}`
          const node = (
            <>
              <span className="sdk-stop-dot">{done ? '✓' : notYet ? '🔒' : s.stop}</span>
              <span className="sdk-stop-text">
                <strong>{s.name}</strong>
                <span className={`pill ${DIFF_TONE[s.difficulty]}`}>{s.difficulty}{s.size === 16 ? ' · 16×16' : ''}</span>
                {s.reward && <span className={`sdk-stop-reward${done ? ' got' : ''}`}>{done ? '🏆' : '🎁'} {THEME_NAME[s.reward]}</span>}
              </span>
            </>
          )
          const cls = `sdk-stop${done ? ' done' : ''}${current ? ' current' : ''}${!playable ? ' locked' : ''}${p.x > 50 ? ' right' : ''}`
          return playable ? (
            <Link key={s.stop} className={cls} style={{ left: `${p.x}%`, top: p.y }} aria-label={label}
              to={g ? `/sudoku/play?game=${g.game_id}` : `/sudoku/play?set=${event.key}&stop=${s.stop}`}>{node}</Link>
          ) : (
            <span key={s.stop} className={cls} style={{ left: `${p.x}%`, top: p.y }} aria-label={label} role="img">{node}</span>
          )
        })}
      </div>
    </section>
  )
}

function Hardest({ games }) {
  const { refreshKey } = useApp()
  const [credit, setCredit] = useState(undefined)
  useEffect(() => { api.sudokuLibrary('hardest', 1, 1).then((l) => setCredit(l.credit)).catch(() => setCredit(null)) }, [refreshKey])
  const solved = Object.values(games).filter((g) => g.status === 'solved').length
  const next = HARDEST.findIndex((_, i) => games[i + 1]?.status !== 'solved') + 1
  return (
    <section className="card home-card">
      <div className="section-head">
        <h2 className="home-card-title">The Hardest 100</h2>
        <span className="muted small">{solved} of 100</span>
      </div>
      {credit ? (
        <p className="small">The hardest sudokus known - each rated 11 or more on the experts' scale (the famous 2012 "world's hardest"
          is around 10-11). Nothing here can be solved by the usual techniques, or by one chain of "if this, then that": they need
          guesses inside guesses. Easiest first; number 100 is the brute. The hints show the next digit when logic runs out.
          <span className="muted"> {credit}</span></p>
      ) : (
        <p className="small">The app's own hardest: puzzles none of its techniques can finish, ranked by the longest chain of
          "if this, then that" they need (19 to 28 steps). Very hard - but not the world's hardest, which this PC's library
          adds when it's loaded. Easiest first; play them in any order.</p>
      )}
      {next > 0 && <Link className="button primary" to={games[next] ? `/sudoku/play?game=${games[next].game_id}` : `/sudoku/play?set=hardest&stop=${next}`}>
        {games[next] ? `Carry on with number ${next}` : `Play number ${next}`}</Link>}
      <ol className="sdk-hardest" aria-label="The Hardest 100">
        {HARDEST.map((_, i) => {
          const g = games[i + 1]
          return (
            <li key={i}>
              <Link className={`sdk-hardest-cell${g?.status === 'solved' ? ' done' : g ? ' started' : ''}`} to={g ? `/sudoku/play?game=${g.game_id}` : `/sudoku/play?set=hardest&stop=${i + 1}`}
                aria-label={`Number ${i + 1}${g?.status === 'solved' ? `, solved in ${clockText(g.seconds)}` : g ? ', started' : ''}`}>{i + 1}</Link>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
