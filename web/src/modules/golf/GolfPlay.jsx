import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { isOffline } from '../../offline/state.js'
import HoleMap from './HoleMap.jsx'
import { BLANK, KIND_NAMES, PUTT_PICKS, changeHole, enqueue, entered, failure, greenDistances, metresBetween, roundTotals,
  scoreKind, scoreOf, shotDistances, stableford, suggestClub, teeAndPin, toParText } from './golfMath.js'

// Golf > Play: the live round, on the phone while you play (/golf/play?round=12). One hole at a time - swipe, Prev /
// Next or the strip of holes - with:
//   the green    GPS distances to its front, middle and back (from the tee when you're over 2 km away; no green
//                mapped: the hole's metres), the hole drawn (HoleMap: tap it to measure a layup)
//   the score    steppers for strokes (from par) and putts, fairway, penalties, bunker shots, first putt, pick up;
//                running totals (holes, against par, Stableford points) and the strokes you get on the hole
//   your shots   "Mark my ball" where it lies, with the club (suggested from your carries) and the lie (Arccos-style):
//                each shot's distance as you go
// Courses have patchy signal, so nothing waits for the server: the round (maps and all) is kept on this phone, each
// change goes into a waiting list (localStorage golf-queue-<id>) that's sent in order - at once, every 20 s and when
// the phone says it's back online. The API's PUTs are safe to resend. Without ?round: the rounds in progress to carry
// on, or start one (the 'golfnewround' panel). The screen stays on while the page is open (where the browser allows).

const GPS_KEY = 'offtheclock.golf.gps'               // 'on' once you've pressed Use my location (on this device)
const CLUBS_KEY = 'offtheclock.golf.clubs'           // the bag, for marking shots without signal
const TEE_CLUBS_KEY = 'offtheclock.golf.teeClubs'    // {"<course>:<hole>": club_id}: what you hit off each tee last time
const roundKey = (id) => `golf-round-${id}`
const queueKey = (id) => `golf-queue-${id}`
const FAR = 2000                                     // metres from the green: not on the course
const FAIRWAY_PICKS = [['left', 'Left'], ['hit', 'Hit'], ['right', 'Right'], ['short', 'Short']]
const LIE_PICKS = [['fairway', 'Fairway'], ['rough', 'Rough'], ['sand', 'Sand'], ['recovery', 'Recovery']]

// localStorage, which can be missing or full (a private window): never let it stop play
const load = (k) => { try { return JSON.parse(localStorage.getItem(k)) } catch { return null } }
const keep = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* full or blocked: play goes on */ } }
const drop = (k) => { try { localStorage.removeItem(k) } catch { /* blocked */ } }

let counter = 0
const itemNo = () => `${Date.now()}-${++counter}`

const scoresFrom = (r) => Object.fromEntries(r.holes.map((h) => [h.hole_no, scoreOf(h)]))
const shotsFrom = (r) => {
  const out = {}
  for (const s of r.shots ?? []) (out[s.hole_no] ??= []).push({ seq: s.seq, lat: s.lat, lon: s.lon, club_id: s.club_id, club: s.club, lie: s.lie })
  return out
}

export function PlayView() {
  const [params] = useSearchParams()
  const id = Number(params.get('round')) || null
  return id ? <LiveRound key={id} id={id} /> : <PickRound />
}

// ---------------------------------------------------------------- no round: carry one on, or start one

function keptRounds() {
  const out = []
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (!k?.startsWith('golf-round-')) continue
      const r = load(k)?.round
      if (r?.status === 'playing') out.push({ round_id: r.round_id, course_name: r.course_name, tee_name: r.tee_name, played_on: r.played_on })
    }
  } catch { /* blocked */ }
  return out
}

function PickRound() {
  const app = useApp()
  const [rounds, setRounds] = useState(null)
  const [note, setNote] = useState('')
  useEffect(() => {
    let gone = false
    api.golfRounds().then((all) => {
      if (gone) return
      setRounds(all.filter((r) => r.status === 'playing'))
      setNote('')
    }).catch(() => {
      if (gone) return
      setRounds(keptRounds())
      setNote("The PC can't be reached: these are the rounds kept on this phone.")
    })
    return () => { gone = true }
  }, [app.refreshKey])

  return (
    <section className="page gplay">
      <section className="card gplay-pick">
        <h2>Play a round</h2>
        <p className="muted">The live round: distances to the front, middle and back of the green, your score as you go, and your
          shots marked where the ball lies. It keeps working without signal.</p>
        <button type="button" className="primary gplay-big" onClick={() => app.openPanel('golfnewround', {})}>Start a round</button>
      </section>
      <section className="card gplay-pick">
        <h2>Rounds in progress</h2>
        {note && <p className="muted small">{note}</p>}
        {rounds == null ? <p className="muted">Loading…</p> : rounds.length === 0 ? <p className="muted">None right now.</p> : (
          <ul className="list gplay-pick-list">
            {rounds.map((r) => (
              <li key={r.round_id}>
                <Link className="gplay-pick-link" to={`/golf/play?round=${r.round_id}`}>
                  <strong>{r.course_name}</strong>
                  <span className="muted small">{[r.tee_name, r.played_on, r.entered != null ? `${r.entered} of ${r.of} holes` : null].filter(Boolean).join(' · ')}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  )
}

// ---------------------------------------------------------------- the round

// Keep the phone's screen on while the round is open (where the browser lets a page ask; boardgames/LivePlay.jsx too).
function useScreenOn() {
  useEffect(() => {
    let lock = null
    let gone = false
    const ask = async () => {
      try { if (document.visibilityState === 'visible' && navigator.wakeLock) lock = await navigator.wakeLock.request('screen') } catch { /* not allowed: fine */ }
      if (gone) lock?.release().catch(() => {})
    }
    ask()
    document.addEventListener('visibilitychange', ask)
    return () => { gone = true; document.removeEventListener('visibilitychange', ask); lock?.release().catch(() => {}) }
  }, [])
}

// The phone's position while location is on: {fix: {lat, lon, acc}, error}.
function usePosition(on, onBlocked) {
  const [fix, setFix] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!on || !navigator.geolocation) return undefined
    const watch = navigator.geolocation.watchPosition(
      (p) => { setFix({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy }); setError('') },
      (e) => {
        if (e.code === 1) { onBlocked(); setError("Location is blocked for this site: allow it in the browser's settings, then try again.") }
        else setError(e.code === 3 ? 'Still looking for a GPS fix…' : "The phone can't find where it is yet.")
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 })
    return () => navigator.geolocation.clearWatch(watch)
  }, [on, onBlocked])
  return { fix: on ? fix : null, error }
}

function sendItem(id, q) {
  if (q.kind === 'hole') return api.saveGolfHole(id, q.hole, q.data)
  if (q.kind === 'shot') return api.saveGolfShot(id, q.hole, q.seq, q.data)
  return api.deleteGolfShot(id, q.hole, q.seq)
}

function LiveRound({ id }) {
  const app = useApp()
  const { showToast } = app
  const navigate = useNavigate()
  useScreenOn()
  const [round, setRound] = useState(null)
  const [scores, setScores] = useState({})
  const [shots, setShots] = useState({})
  const [idx, setIdx] = useState(0)
  const [error, setError] = useState('')
  const [clubs, setClubs] = useState(() => load(CLUBS_KEY) ?? [])
  const [queue, setQueue] = useState(() => load(queueKey(id)) ?? [])
  const [stalled, setStalled] = useState(false)
  const [finishing, setFinishing] = useState(false)     // the "Finish round?" question is showing
  const [busy, setBusy] = useState(false)
  const [gpsOn, setGpsOn] = useState(() => { try { return localStorage.getItem(GPS_KEY) === 'on' } catch { return false } })
  const [pick, setPick] = useState({ key: '', club: null, lie: null })   // a club / lie picked for the next mark
  const qRef = useRef(queue)
  const running = useRef(null)
  const timer = useRef(null)

  const blocked = useCallback(() => { setGpsOn(false); drop(GPS_KEY) }, [])
  const { fix, error: gpsError } = usePosition(gpsOn, blocked)

  const setQ = useCallback((next) => {
    qRef.current = next
    setQueue(next)
    keep(queueKey(id), next)
  }, [id])

  // Send what's waiting, in order, one at a time (one run at a time: a second call waits for the first).
  const flush = useCallback(() => {
    if (running.current) return running.current
    running.current = (async () => {
      while (qRef.current.length) {
        const item = qRef.current[0]
        try {
          const r = await sendItem(id, item)
          if (r?.holes) setRound(r)
          setQ(qRef.current.filter((q) => q.n !== item.n))
        } catch (e) {
          if (failure(e) === 'retry') { setStalled(true); return }
          setQ(qRef.current.filter((q) => q.n !== item.n))
          if (!(item.kind === 'unshot' && e.status === 404)) showToast(`Hole ${item.hole} wasn't saved: ${e.message}`)
        }
      }
      setStalled(false)
    })().finally(() => { running.current = null })
    return running.current
  }, [id, setQ, showToast])

  // The round: the server's, or the one kept on this phone (with changes still waiting, this phone's scores win).
  useEffect(() => {
    let gone = false
    const kept = load(roundKey(id))
    const adopt = (r, sc, sh, at) => {
      setRound(r)
      setScores(sc)
      setShots(sh)
      const next = r.holes.findIndex((h) => !entered(sc[h.hole_no]))
      setIdx(at ?? (next >= 0 ? next : 0))
    }
    api.golfRound(id).then((r) => {
      if (gone) return
      if (kept?.round && (isOffline() || qRef.current.length)) adopt({ ...r, holes: r.holes.length ? r.holes : kept.round.holes }, kept.scores, kept.shots, kept.hole)
      else adopt(r, scoresFrom(r), shotsFrom(r), kept?.hole)
      if (qRef.current.length) flush()
    }).catch((e) => {
      if (gone) return
      if (kept?.round) { adopt(kept.round, kept.scores, kept.shots, kept.hole); setStalled(qRef.current.length > 0) }
      else setError(e.status === 404 ? 'There is no such round.' : `The round couldn't be loaded: ${e.message}`)
    })
    api.golfClubs().then((c) => { if (!gone) { setClubs(c); keep(CLUBS_KEY, c) } }).catch(() => { /* the kept bag */ })
    return () => { gone = true }
  }, [id, flush])

  // Kept on this phone as it changes (the maps too), so it reopens without signal.
  useEffect(() => {
    if (round) keep(roundKey(id), { round, scores, shots, hole: idx })
  }, [id, round, scores, shots, idx])

  // Try again every 20 s and when the phone's back online; on leaving, one last go (what's left waits for next time).
  useEffect(() => {
    const again = () => { if (qRef.current.length) flush() }
    const t = setInterval(again, 20000)
    window.addEventListener('online', again)
    return () => { clearInterval(t); window.removeEventListener('online', again); clearTimeout(timer.current); again() }
  }, [flush])

  const soon = () => { clearTimeout(timer.current); timer.current = setTimeout(flush, 600) }

  if (error) {
    return (
      <section className="page gplay">
        <section className="card gplay-pick">
          <h2>Play a round</h2>
          <p role="alert">{error}</p>
          <Link className="button secondary" to="/golf/play">Rounds in progress</Link>
        </section>
      </section>
    )
  }
  if (!round) return <section className="page gplay"><p className="muted">Loading the round…</p></section>
  if (!round.holes.length) {
    return (
      <section className="page gplay">
        <section className="card gplay-pick">
          <h2>{round.course_name}</h2>
          <p>This course has no holes set up yet: add its pars and stroke indexes under Courses first.</p>
          <Link className="button secondary" to="/golf/courses">Courses</Link>
        </section>
      </section>
    )
  }

  const holes = round.holes
  const at = Math.min(idx, holes.length - 1)
  const hole = holes[at]
  const no = hole.hole_no
  const score = scores[no] ?? BLANK
  const holeShots = shots[no] ?? []
  const totals = roundTotals(holes, scores)
  const go = (i) => setIdx(Math.max(0, Math.min(holes.length - 1, i)))

  const change = (c) => {
    const next = changeHole(score, hole.par, c)
    setScores((s) => ({ ...s, [no]: next }))
    setQ(enqueue(qRef.current, { n: itemNo(), kind: 'hole', hole: no, data: next }))
    soon()
  }

  // where you are, and the green from there
  const me = fix ? [fix.lat, fix.lon] : null
  const { tee, pin } = teeAndPin(hole.map)
  const far = me && (pin || tee) ? metresBetween(me, pin ?? tee) > FAR : false
  const from = me && !far ? me : tee
  const green = hole.map?.green?.length >= 3 ? greenDistances(from, hole.map.green) : null
  const toMiddle = me && !far && pin ? metresBetween(me, pin) : null

  // marking shots
  const pickKey = `${no}:${holeShots.length}`
  const first = holeShots.length === 0
  const remembered = load(TEE_CLUBS_KEY)?.[`${round.course_id}:${no}`]
  const bag = clubs.filter((c) => c.in_bag !== false)
  const suggested = (first && bag.find((c) => c.club_id === remembered)) || suggestClub(bag, toMiddle ?? (first ? hole.metres : null))
  const clubId = pick.key === pickKey && pick.club !== undefined ? pick.club : suggested?.club_id ?? null
  const lie = first ? 'tee' : pick.key === pickKey && pick.lie ? pick.lie : 'fairway'
  const choose = (k, v) => setPick((p) => ({ ...(p.key === pickKey ? p : { club: clubId, lie }), key: pickKey, [k]: v }))
  const mark = () => {
    if (!fix || holeShots.length >= 20) return
    const seq = holeShots.length + 1
    const club = bag.find((c) => c.club_id === clubId)
    const data = { lie, lat: fix.lat, lon: fix.lon, club_id: clubId, accuracy_m: fix.acc != null ? Math.round(fix.acc) : null }
    setShots((s) => ({ ...s, [no]: [...(s[no] ?? []), { seq, lat: fix.lat, lon: fix.lon, club_id: clubId, club: club?.name ?? null, lie }] }))
    setQ(enqueue(qRef.current, { n: itemNo(), kind: 'shot', hole: no, seq, data }))
    if (seq === 1 && clubId) keep(TEE_CLUBS_KEY, { ...(load(TEE_CLUBS_KEY) ?? {}), [`${round.course_id}:${no}`]: clubId })
    navigator.vibrate?.(25)
    flush()
  }
  const unmark = () => {
    if (!holeShots.length) return
    const seq = holeShots.length
    setShots((s) => ({ ...s, [no]: (s[no] ?? []).slice(0, -1) }))
    setQ(enqueue(qRef.current, { n: itemNo(), kind: 'unshot', hole: no, seq }))
    flush()
  }
  const measured = shotDistances(holeShots)
  const lastShot = measured.at(-1)
  const sinceLast = lastShot && me && !far ? Math.round(metresBetween([lastShot.lat, lastShot.lon], me)) : null

  const missing = holes.filter((h) => !entered(scores[h.hole_no])).map((h) => h.hole_no)
  const finish = async () => {
    setBusy(true)
    clearTimeout(timer.current)
    await flush()
    await flush()
    if (qRef.current.length) {
      setBusy(false)
      setFinishing(false)
      showToast("Your scores are still waiting for signal: finish once they've gone.")
      return
    }
    try {
      await api.updateGolfRound(id, { status: 'done' })
      drop(roundKey(id))
      drop(queueKey(id))
      app.changed()
      navigate('/golf/rounds')
      app.openPanel('golfround', { id })
    } catch (e) {
      setBusy(false)
      showToast(e.message)
    }
  }

  const kind = scoreKind(score.strokes, hole.par, score.picked_up)
  const points = entered(score) ? stableford(score.strokes, hole.par, hole.received ?? 0) : null

  return (
    <section className="page gplay">
      <header className="gplay-top">
        <div className="gplay-where">
          <strong>{round.course_name}</strong>
          <span className="muted small">{[round.tee_name, round.daily_handicap != null ? `daily handicap ${round.daily_handicap}` : null].filter(Boolean).join(' · ')}</span>
        </div>
        <dl className="gplay-totals">
          <div><dt>Holes</dt><dd>{totals.played}/{totals.of}</dd></div>
          <div><dt>To par</dt><dd>{toParText(totals.toPar)}</dd></div>
          <div><dt>Strokes</dt><dd>{totals.strokes || '–'}</dd></div>
          <div><dt>Points</dt><dd>{totals.points}</dd></div>
        </dl>
        {round.status === 'done' && <p className="gplay-note">This round is finished: changes here still save.</p>}
        {queue.length > 0 && stalled && (
          <p className="gplay-waiting" role="status">
            {queue.length} {queue.length === 1 ? 'change' : 'changes'} waiting for signal
            <button type="button" className="plain small" onClick={flush}>Try now</button>
          </p>
        )}
      </header>

      <HoleStrip holes={holes} scores={scores} at={at} onPick={go} />

      <SwipeArea onPrev={() => go(at - 1)} onNext={() => go(at + 1)}>
        <div className="gplay-hole-head">
          <button type="button" className="secondary gplay-nav" onClick={() => go(at - 1)} disabled={at === 0} aria-label="Previous hole">‹</button>
          <div className="gplay-hole-title">
            <h2>Hole {no}</h2>
            <span className="muted">
              Par {hole.par}{hole.stroke_index ? ` · index ${hole.stroke_index}` : ''}{hole.metres ? ` · ${hole.metres} m` : ''}
            </span>
            <Received n={hole.received ?? 0} />
          </div>
          <button type="button" className="secondary gplay-nav" onClick={() => go(at + 1)} disabled={at === holes.length - 1} aria-label="Next hole">›</button>
        </div>

        <section className="card gplay-green" aria-label="Distances to the green">
          {green ? (
            <div className="gplay-gmb">
              <div><span>Front</span><strong>{Math.round(green.front)}</strong></div>
              <div className="gplay-gmb-mid"><span>Middle</span><strong>{Math.round(green.middle)}</strong></div>
              <div><span>Back</span><strong>{Math.round(green.back)}</strong></div>
            </div>
          ) : (
            <div className="gplay-gmb gplay-gmb-plain">
              <div className="gplay-gmb-mid"><span>{hole.metres ? 'From the tee' : 'Par'}</span><strong>{hole.metres ? `${hole.metres}` : hole.par}</strong></div>
            </div>
          )}
          <p className="gplay-gps muted small">
            {green && (me && !far ? `Metres from you${fix.acc != null ? ` · GPS ± ${Math.round(fix.acc)} m` : ''}`
              : far ? `Metres from the tee: you're more than 2 km from the course` : 'Metres from the tee')}
            {!green && (hole.map ? "This hole's green isn't mapped: its length from your tees." : "This hole isn't mapped: its length from your tees.")}
            {fix?.acc > 30 && !far && ' (a weak fix: the numbers may be out)'}
          </p>
          {gpsError && <p className="gplay-gps-error" role="status">{gpsError}</p>}
          {!gpsOn && (
            <button type="button" className="primary gplay-big" onClick={() => { setGpsOn(true); try { localStorage.setItem(GPS_KEY, 'on') } catch { /* blocked */ } }}>
              Use my location
            </button>
          )}
          {gpsOn && !fix && !gpsError && <p className="muted small" role="status">Finding where you are…</p>}
        </section>

        {hole.map && (
          <HoleMap key={no} map={hole.map} holeNo={no} par={hole.par} me={me && !far ? me : null} shots={measured} className="gplay-hole-map" />
        )}

        <section className="card gplay-score" aria-label={`Hole ${no} score`}>
          <div className="gplay-steppers">
            <Stepper label="Strokes" value={score.picked_up ? 'P/U' : score.strokes ?? '–'} big
              onDown={() => change({ strokes: -1 })} onUp={() => change({ strokes: 1 })} />
            <Stepper label="Putts" value={score.putts ?? '–'} big onDown={() => change({ putts: -1 })} onUp={() => change({ putts: 1 })} />
          </div>
          <p className="gplay-verdict" aria-live="polite">
            {kind ? <span className={`gplay-kind gplay-kind-${kind}`}>{score.picked_up ? 'Picked up' : KIND_NAMES[kind]}</span> : <span className="muted">No score yet</span>}
            {points != null && <span> · {points} {points === 1 ? 'point' : 'points'}</span>}
          </p>
          {hole.par >= 4 && (
            <div className="gplay-row">
              <span className="gplay-row-label" id={`gplay-fw-${no}`}>Fairway</span>
              <div className="segmented gplay-seg" role="group" aria-labelledby={`gplay-fw-${no}`}>
                {FAIRWAY_PICKS.map(([v, label]) => (
                  <button key={v} type="button" aria-pressed={score.fairway === v} onClick={() => change({ fairway: v })}>{label}</button>
                ))}
              </div>
            </div>
          )}
          <div className="gplay-steppers gplay-small-steppers">
            <Stepper label="Penalties" value={score.penalties} onDown={() => change({ penalties: -1 })} onUp={() => change({ penalties: 1 })} />
            <Stepper label="Bunker shots" value={score.sand} onDown={() => change({ sand: -1 })} onUp={() => change({ sand: 1 })} />
          </div>
          {score.putts !== 0 && (
            <div className="gplay-row">
              <span className="gplay-row-label" id={`gplay-fp-${no}`}>First putt</span>
              <div className="gplay-chips" role="group" aria-labelledby={`gplay-fp-${no}`}>
                {PUTT_PICKS.map(([label, m]) => (
                  <button key={m} type="button" className="gplay-chip" aria-pressed={score.first_putt_m === m} onClick={() => change({ first_putt_m: m })}>{label}</button>
                ))}
              </div>
            </div>
          )}
          <div className="gplay-row gplay-row-end">
            <button type="button" className="secondary" aria-pressed={score.picked_up} onClick={() => change({ picked_up: !score.picked_up })}>
              {score.picked_up ? 'Picked up' : 'Pick up'}
            </button>
            {entered(score) && <button type="button" className="plain" onClick={() => change({ clear: true })}>Clear hole</button>}
          </div>
        </section>

        <section className="card gplay-shots" aria-label="Your shots on this hole">
          <h3>Your shots</h3>
          {measured.length > 0 ? (
            <ol className="gplay-shot-list">
              {measured.map((s) => (
                <li key={s.seq}>
                  <span>{s.club ?? 'Club not noted'} <span className="muted small">({s.lie})</span></span>
                  <strong>{s.metres != null ? `${s.metres} m` : sinceLast != null ? `${sinceLast} m so far` : '–'}</strong>
                </li>
              ))}
            </ol>
          ) : <p className="muted small">Mark where the ball lies before each shot: the distances and your clubs' carries add up from them.</p>}
          {bag.length > 0 ? (
            <div className="gplay-clubs" role="group" aria-label="Club for this shot">
              {bag.map((c) => (
                <button key={c.club_id} type="button" className="gplay-chip" aria-pressed={clubId === c.club_id}
                  onClick={() => choose('club', clubId === c.club_id ? null : c.club_id)}>
                  {c.name}{c.carry_m ? <span className="gplay-carry"> {c.carry_m}</span> : null}
                </button>
              ))}
            </div>
          ) : <p className="muted small">No clubs in your bag yet: <Link to="/golf/bag">set up your bag</Link> to note a club with each shot.</p>}
          {!first && (
            <div className="segmented gplay-seg" role="group" aria-label="Lie">
              {LIE_PICKS.map(([v, label]) => (
                <button key={v} type="button" aria-pressed={lie === v} onClick={() => choose('lie', v)}>{label}</button>
              ))}
            </div>
          )}
          <div className="gplay-row gplay-row-end">
            <button type="button" className="primary gplay-big" onClick={mark} disabled={!fix || far || holeShots.length >= 20}>
              Mark my ball{first ? ' (tee)' : ''}
            </button>
            <button type="button" className="secondary" onClick={unmark} disabled={!holeShots.length}>Undo mark</button>
          </div>
          {(!fix || far) && <p className="muted small">{!gpsOn ? 'Marking needs your location.' : far ? 'Marking works on the course.' : 'Waiting for a GPS fix.'}</p>}
        </section>
      </SwipeArea>

      <section className="card gplay-finish">
        {finishing ? (
          <>
            <p role="alert">{missing.length ? `${missing.length === 1 ? 'Hole' : 'Holes'} ${missing.join(', ')} ${missing.length === 1 ? 'has' : 'have'} no score. Finish anyway?`
              : 'Finish the round?'}</p>
            <div className="gplay-row gplay-row-end">
              <button type="button" className="primary" onClick={finish} disabled={busy}>Finish round</button>
              <button type="button" className="secondary" onClick={() => setFinishing(false)} disabled={busy}>Keep playing</button>
            </div>
          </>
        ) : (
          <button type="button" className="secondary gplay-big" onClick={() => setFinishing(true)}>Finish round</button>
        )}
      </section>
    </section>
  )
}

// The strokes you get on the hole, as dots like a scorecard (a plus handicap gives one back).
function Received({ n }) {
  if (!n) return null
  const text = n < 0 ? 'you give a stroke back here' : `${n} ${n === 1 ? 'stroke' : 'strokes'} received`
  return (
    <span className="gplay-received">
      <span aria-hidden="true">{n < 0 ? '−●' : '●'.repeat(n)}</span>
      <span className="gplay-received-text">{text}</span>
    </span>
  )
}

function Stepper({ label, value, onDown, onUp, big = false }) {
  return (
    <div className={big ? 'gplay-stepper gplay-stepper-big' : 'gplay-stepper'}>
      <span className="gplay-stepper-label">{label}</span>
      <div className="gplay-stepper-row">
        <button type="button" className="gplay-step" onClick={onDown} aria-label={`${label}: one fewer`}>−</button>
        <output className="gplay-stepper-value" aria-live="polite" aria-label={label}>{value}</output>
        <button type="button" className="gplay-step" onClick={onUp} aria-label={`${label}: one more`}>+</button>
      </div>
    </div>
  )
}

// Every hole as a button with its score's colour (and the score written on it: never colour alone).
function HoleStrip({ holes, scores, at, onPick }) {
  const current = useRef(null)
  useEffect(() => { current.current?.scrollIntoView?.({ block: 'nearest', inline: 'center', behavior: 'smooth' }) }, [at])
  return (
    <nav className="gplay-strip" aria-label="Holes">
      {holes.map((h, i) => {
        const s = scores[h.hole_no]
        const kind = scoreKind(s?.strokes, h.par, s?.picked_up)
        const shown = s?.picked_up ? 'P' : s?.strokes ?? '·'
        return (
          <button key={h.hole_no} ref={i === at ? current : null} type="button" onClick={() => onPick(i)}
            className={`gplay-strip-hole${kind ? ` gplay-kind-${kind}` : ''}`} aria-current={i === at ? 'true' : undefined}
            aria-label={`Hole ${h.hole_no}, par ${h.par}${kind ? `: ${s.picked_up ? 'picked up' : `${s.strokes}, ${KIND_NAMES[kind]}`}` : ''}`}>
            <span className="gplay-strip-no">{h.hole_no}</span>
            <span className="gplay-strip-score">{shown}</span>
          </button>
        )
      })}
    </nav>
  )
}

// Swipe left / right for the next / previous hole (not on the map: a tap there measures; not on the strip: it scrolls).
function SwipeArea({ onPrev, onNext, children }) {
  const start = useRef(null)
  const down = (e) => {
    const t = e.touches[0]
    start.current = e.target.closest?.('svg, .gplay-clubs, .gplay-chips') ? null : [t.clientX, t.clientY]
  }
  const up = (e) => {
    if (!start.current) return
    const t = e.changedTouches[0]
    const dx = t.clientX - start.current[0]
    const dy = t.clientY - start.current[1]
    start.current = null
    if (Math.abs(dx) > 70 && Math.abs(dx) > 1.6 * Math.abs(dy)) (dx < 0 ? onNext : onPrev)()
  }
  return <div className="gplay-swipe" onTouchStart={down} onTouchEnd={up}>{children}</div>
}
