import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, today as todayIso } from '../../api.js'
import Landscape from '../../components/Landscape.jsx'
import { useApp } from '../../core/app-context.js'
import { EVENTS, HARDEST, THEMES, eventOpen, stops } from './events.js'
import { clockText } from './sudokuParts.js'

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

// The path (user, 2026-11-11, with a screenshot of the kind of thing: "the events still look off"): the event's scene
// fills the card and stays put while the road scrolls over it - starting at the bottom and winding up, big round stops
// (done, next, locked; a gift where a theme is earned), the event's name and time left on top, and a Play button for
// the next stop pinned at the bottom. It opens scrolled to where you're up to.
const STEP = 118, TOP = 150, BOTTOM = 130
const LANES = [50, 80, 50, 20]                        // across the card, %: centre, right, centre, left...
function Path({ event, games, open }) {
  const scroller = useRef(null)
  const all = stops(event)
  const solved = all.filter((s) => games[s.stop]?.status === 'solved').length
  const day = todayIso()
  const next = all.find((s) => games[s.stop]?.status !== 'solved')
  const nextOpen = next && open && !(event.opens && event.opens(next.stop) > day)
  const height = TOP + BOTTOM + (all.length - 1) * STEP
  const pos = (i) => ({ x: LANES[i % LANES.length], y: height - BOTTOM - i * STEP })
  // the road: a smooth S between each pair of stops
  const road = all.map((_, i) => {
    const p = pos(i)
    if (!i) return `M ${p.x} ${p.y}`
    const q = pos(i - 1)
    return `C ${q.x} ${q.y - STEP * 0.55} ${p.x} ${p.y + STEP * 0.55} ${p.x} ${p.y}`
  }).join(' ')
  const walked = all.slice(0, Math.min(all.length, solved + 1)).map((_, i) => {
    const p = pos(i)
    if (!i) return `M ${p.x} ${p.y}`
    const q = pos(i - 1)
    return `C ${q.x} ${q.y - STEP * 0.55} ${p.x} ${p.y + STEP * 0.55} ${p.x} ${p.y}`
  }).join(' ')
  const at = Math.min(all.length - 1, solved)
  useEffect(() => {                                   // start where you're up to
    const el = scroller.current
    if (el) el.scrollTop = Math.max(0, pos(at).y - el.clientHeight * 0.62)
  }, [at, height])                                    // eslint-disable-line react-hooks/exhaustive-deps
  const art = event.art ?? {}
  const ends = event.to && open ? Math.ceil((new Date(`${event.to}T23:59:59`) - new Date(`${day}T12:00:00`)) / 86400000) : null
  const nextReward = all.find((s) => s.reward && games[s.stop]?.status !== 'solved')
  return (
    <section className="sdk-event sdk-trail" style={{ '--event-hue': art.hue ?? 'var(--tint)' }} aria-label={event.name}>
      <div className="sdk-trail-bg" aria-hidden="true">
        <Landscape scene={art.scene} seed={art.seed} time={art.time} extras={art.extras} hue={art.hue} />
      </div>
      <div className="sdk-trail-scroll" ref={scroller}>
        <div className="sdk-trail-map" style={{ height }}>
          <svg className="sdk-trail-road" viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" aria-hidden="true">
            <path className="edge" d={road} vectorEffect="non-scaling-stroke" />
            <path className="road" d={road} vectorEffect="non-scaling-stroke" />
            {solved > 0 && <path className="walked" d={walked} vectorEffect="non-scaling-stroke" />}
          </svg>
          {all.map((s, i) => {
            const g = games[s.stop]
            const done = g?.status === 'solved'
            const notYet = event.opens && event.opens(s.stop) > day
            const current = open && s.stop === next?.stop && !notYet
            const playable = done || g || current
            const p = pos(i)
            const label = `${s.name}: ${s.difficulty}${s.size === 16 ? ' 16 × 16' : ''}${done ? `, solved in ${clockText(g.seconds)}` : current ? ', next' : g ? ', started' : notYet ? ', opens on its day' : ', locked'}${s.reward ? `, earns the ${THEME_NAME[s.reward]} theme` : ''}`
            const face = done ? '✓' : s.reward ? '🎁' : notYet ? '🔒' : s.stop
            const cls = `sdk-trail-stop${done ? ' done' : ''}${current ? ' current' : ''}${!playable ? ' locked' : ''}${s.reward ? ' gift' : ''}`
            const inner = (
              <>
                <span className="sdk-trail-dot">{face}</span>
                <span className="sdk-trail-name">{s.reward && !done ? `${s.stop} · ${THEME_NAME[s.reward]}` : s.name}</span>
              </>
            )
            const style = { left: `${p.x}%`, top: p.y }
            return playable ? (
              <Link key={s.stop} className={cls} style={style} aria-label={label}
                to={g ? `/sudoku/play?game=${g.game_id}` : `/sudoku/play?set=${event.key}&stop=${s.stop}`}>{inner}</Link>
            ) : <span key={s.stop} className={cls} style={style} aria-label={label} role="img">{inner}</span>
          })}
        </div>
      </div>
      <header className="sdk-trail-head">
        <h2>{event.name}</h2>
        <p className="sdk-trail-sub">{solved} of {event.length} stops{ends != null && ` · ends in ${ends} day${ends === 1 ? '' : 's'}`}
          {nextReward && ` · next gift: ${THEME_NAME[nextReward.reward]}`}</p>
        <span className="sdk-trail-progress" role="img" aria-label={`${solved} of ${event.length} stops`}><span style={{ width: `${(100 * solved) / event.length}%` }} /></span>
      </header>
      <div className="sdk-trail-play">
        {!open ? <span className="sdk-trail-button off">{solved ? 'This event has closed - your stops stay' : `Opens ${new Date(`${event.from}T12:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'long' })}`}</span>
          : !next ? <span className="sdk-trail-button off">Finished! 🎉</span>
            : nextOpen ? (
              <Link className="sdk-trail-button" to={games[next.stop] ? `/sudoku/play?game=${games[next.stop].game_id}` : `/sudoku/play?set=${event.key}&stop=${next.stop}`}>
                <strong>{games[next.stop] ? 'Carry on' : 'Play'}</strong><span>{next.name} · {next.difficulty}{next.size === 16 ? ' · 16 × 16' : ''}</span></Link>
            ) : <span className="sdk-trail-button off">Next door opens {next.name}</span>}
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
