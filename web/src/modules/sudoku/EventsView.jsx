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
const TOP = 150, BOTTOM = 130
// Each event's own way up the card (user, 2026-11-11: "some design variation in the layout of the stops"):
//   snake       centre, right, centre, left... joined by smooth S-bends (The Grand Tour)
//   switchback  a mountain path: straight legs zig-zagging across, a turn every few stops (the Patagonia Trail)
//   garland     a gentle swing from side to side, like tinsel (the Advent calendar)
const LAYOUTS = {
  snake: { step: 118, x: (i) => [50, 80, 50, 20][i % 4], curve: 'S' },
  switchback: { step: 96, x: (i) => [18, 40, 62, 84, 62, 40][i % 6], curve: 'L' },
  garland: { step: 104, x: (i) => 50 + 30 * Math.sin(i * 0.75), curve: 'S' },
}
function roadThrough(points, curve, step) {
  return points.map((p, i) => {
    if (!i) return `M ${p.x} ${p.y}`
    const q = points[i - 1]
    return curve === 'L' ? `L ${p.x} ${p.y}` : `C ${q.x} ${q.y - step * 0.55} ${p.x} ${p.y + step * 0.55} ${p.x} ${p.y}`
  }).join(' ')
}
function Path({ event, games, open }) {
  const layout = LAYOUTS[event.layout] ?? LAYOUTS.snake
  const STEP = layout.step
  const [photo, setPhoto] = useState(null)
  useEffect(() => { api.sudokuEventPhoto(event.key).then(setPhoto).catch(() => setPhoto(null)) }, [event.key])
  const scroller = useRef(null)
  const all = stops(event)
  const solved = all.filter((s) => games[s.stop]?.status === 'solved').length
  const day = todayIso()
  const next = all.find((s) => games[s.stop]?.status !== 'solved')
  const nextOpen = next && open && !(event.opens && event.opens(next.stop) > day)
  const height = TOP + BOTTOM + (all.length - 1) * STEP
  const pos = (i) => ({ x: layout.x(i), y: height - BOTTOM - i * STEP })
  const points = all.map((_, i) => pos(i))
  const road = roadThrough(points, layout.curve, STEP)
  const walked = roadThrough(points.slice(0, Math.min(all.length, solved + 1)), layout.curve, STEP)
  const at = Math.min(all.length - 1, solved)
  useEffect(() => {                                   // start where you're up to
    const el = scroller.current
    if (el) el.scrollTop = Math.max(0, pos(at).y - el.clientHeight * 0.62)
  }, [at, height])                                    // eslint-disable-line react-hooks/exhaustive-deps
  const art = event.art ?? {}
  const ends = event.to && open ? Math.ceil((new Date(`${event.to}T23:59:59`) - new Date(`${day}T12:00:00`)) / 86400000) : null
  const nextReward = all.find((s) => s.reward && games[s.stop]?.status !== 'solved')
  return (
    <section className={`sdk-event sdk-trail sdk-trail-${event.layout ?? 'snake'}`} style={{ '--event-hue': art.hue ?? 'var(--tint)' }} aria-label={event.name}>
      <div className="sdk-trail-bg" aria-hidden="true">
        {photo ? <img src={photo.url} alt="" /> : <Landscape scene={art.scene} seed={art.seed} time={art.time} extras={art.extras} hue={art.hue} />}
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
            const last = s.stop === all.length
            const milestone = !last && s.stop % 5 === 0
            const face = done ? '✓' : s.reward ? '🎁' : last ? '🏁' : notYet ? '🔒' : s.stop
            const cls = `sdk-trail-stop${done ? ' done' : ''}${current ? ' current' : ''}${!playable ? ' locked' : ''}${s.reward ? ' gift' : ''}${milestone ? ' milestone' : ''}${last ? ' finish' : ''}`
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
      {photo && (
        <p className="sdk-trail-credit">Photo: {photo.page ? <a href={photo.page} target="_blank" rel="noreferrer">{photo.author ?? 'Wikimedia Commons'}</a> : photo.author}
          {photo.licence && `, ${photo.licence}`} · Wikimedia Commons</p>
      )}
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

// The Hardest 100 counts down (user, 2026-11-11): start at 100; winning a number unlocks the one below; number 1 is the
// hardest of them all.
export const hardestOpen = (games, n) => n === 100 || Boolean(games[n]) || games[n + 1]?.status === 'solved'
function Hardest({ games }) {
  const { refreshKey } = useApp()
  const [credit, setCredit] = useState(undefined)
  useEffect(() => { api.sudokuLibrary('hardest', 1, 1).then((l) => setCredit(l.credit)).catch(() => setCredit(null)) }, [refreshKey])
  const solved = Object.values(games).filter((g) => g.status === 'solved').length
  let next = 0
  for (let n = 100; n >= 1; n--) if (games[n]?.status !== 'solved') { next = n; break }
  return (
    <section className="card home-card">
      <div className="section-head">
        <h2 className="home-card-title">The Hardest 100</h2>
        <span className="muted small">{solved} of 100</span>
      </div>
      {credit ? (
        <p className="small">The hardest sudokus known - each rated 11 or more on the experts' scale (the famous 2012 "world's hardest"
          is around 10-11). Nothing here can be solved by the usual techniques, or by one chain of "if this, then that": they need
          guesses inside guesses. Start at 100 and count down - winning one unlocks the next; number 1 is the brute. The hints
          show the next digit when logic runs out.
          <span className="muted"> {credit}</span></p>
      ) : (
        <p className="small">The app's own hardest: puzzles none of its techniques can finish, ranked by the longest chain of
          "if this, then that" they need (19 to 28 steps). Very hard - but not the world's hardest, which this PC's library
          adds when it's loaded. Start at 100 and count down; number 1 is the hardest.</p>
      )}
      {next > 0 && <Link className="button primary" to={games[next] ? `/sudoku/play?game=${games[next].game_id}` : `/sudoku/play?set=hardest&stop=${next}`}>
        {games[next] ? `Carry on with number ${next}` : `Play number ${next}`}</Link>}
      <ol className="sdk-hardest" aria-label="The Hardest 100, counting down">
        {HARDEST.map((_, i) => {
          const n = 100 - i
          const g = games[n]
          const openNow = hardestOpen(games, n)
          const label = `Number ${n}${g?.status === 'solved' ? `, solved in ${clockText(g.seconds)}` : g ? ', started' : openNow ? ', next' : ', locked'}`
          return (
            <li key={n}>
              {openNow ? (
                <Link className={`sdk-hardest-cell${g?.status === 'solved' ? ' done' : g ? ' started' : ' next'}`} aria-label={label}
                  to={g ? `/sudoku/play?game=${g.game_id}` : `/sudoku/play?set=hardest&stop=${n}`}>{n}</Link>
              ) : <span className="sdk-hardest-cell locked" role="img" aria-label={label}>🔒</span>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
