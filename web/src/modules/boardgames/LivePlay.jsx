import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { FunPicker, PlayPhotos, PlayerPicker, SeatScores, clock, places, placeText, scoreText, seatKey, seatTotal, seatsOut } from './tableParts.jsx'

// Play a board game as it happens (user, 2026-11-15: "let me click a button and it starts the timer for the teach and
// the gameplay"). Start: the game, who's playing (your usual people first, groups in a tap), where, expansions. Then
// the clock runs through setup -> teach -> playing (pause for a break), you pick who goes first, keep score as you
// go (+/- or the game's score sheet), count rounds, take photos. Finish: final scores, who won, how good it was -
// saved as a play. "Next game" starts again with the same people and place.
// The server keeps the times (api/app/boardgames_live.py): a phone that locks or reloads loses nothing.
//   openPanel('liveplay')               start one (a game picker)
//   openPanel('liveplay', { gameId })   start one of this game
//   openPanel('liveplay', { id })       carry on with one going now
export default function LivePlayPanel({ id = null, gameId = null, onClose }) {
  const { changed } = useApp()
  const [liveId, setLiveId] = useState(id)
  const [again, setAgain] = useState(null)      // "Next game": the same people and place
  const started = (live) => { setLiveId(live.live_id); changed() }
  if (liveId) {
    return <LiveView key={liveId} id={liveId} onClose={onClose}
      onNext={(seats, location) => { setAgain({ seats, location }); setLiveId(null) }} />
  }
  return <StartPlay gameId={gameId} again={again} onStarted={started} onClose={onClose} />
}

const ELSEWHERE = 'elsewhere'

function StartPlay({ gameId, again, onStarted, onClose }) {
  const [games, setGames] = useState(null)
  const [roster, setRoster] = useState(null)
  const [pick, setPick] = useState(gameId ? String(gameId) : '')
  const [otherName, setOtherName] = useState('')
  const [game, setGame] = useState(null)        // the picked game in full (its expansions, players)
  const [seats, setSeats] = useState(again?.seats ?? [])
  const [location, setLocation] = useState(again?.location ?? '')
  const [expansions, setExpansions] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    Promise.all([api.listBoardGames(), api.boardGamePlayers()]).then(([gs, r]) => {
      setGames(gs.filter((g) => g.status !== 'Gone' && g.status !== 'Wanted' && g.kind === 'game'))
      setRoster(r)
      if (!again) {                                // you're at the table: you're playing
        const me = r.players.find((p) => p.is_me)
        if (me) setSeats([{ player_id: me.player_id, name: me.name, is_me: true, adds: [] }])
      }
    }).catch((e) => setError(e.message))
  }, [])                                           // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setExpansions([])
    if (!pick || pick === ELSEWHERE) { setGame(null); return }
    api.getBoardGame(pick).then(setGame).catch(() => setGame(null))
  }, [pick])

  const start = async (stage) => {
    if (!pick || (pick === ELSEWHERE && !otherName.trim())) { setError('Which game?'); return }
    setBusy(true)
    setError('')
    try {
      onStarted(await api.startLivePlay({
        ...(pick === ELSEWHERE ? { game_name: otherName.trim() } : { game_id: Number(pick) }),
        seats: seatsOut(seats.map((s) => ({ ...s, score: null, parts: null, adds: [], won: null }))),
        location: location.trim() || null, expansions, stage,
      }))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const footer = (
    <>
      <button type="button" className="primary" onClick={() => start('setup')} disabled={busy}>Start: setting up</button>
      <button type="button" className="secondary" onClick={() => start('teach')} disabled={busy}>Set up: start the teach</button>
      <button type="button" className="plain" onClick={() => start('play')} disabled={busy}>Straight to playing</button>
    </>
  )
  return (
    <Drawer title="Start a play" onClose={onClose} footer={games && footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!games || !roster ? <p className="muted">Loading...</p> : (
        <>
          <section className="panel-section">
            <label className="field wide">
              <span className="field-label">Game</span>
              <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Game">
                <option value="">Choose...</option>
                {games.filter((g) => g.status !== 'Played elsewhere').map((g) => <option key={g.game_id} value={g.game_id}>{g.name}</option>)}
                {games.some((g) => g.status === 'Played elsewhere') && (
                  <optgroup label="Played elsewhere">
                    {games.filter((g) => g.status === 'Played elsewhere').map((g) => <option key={g.game_id} value={g.game_id}>{g.name}</option>)}
                  </optgroup>
                )}
                <option value={ELSEWHERE}>Someone else's game (not in my list)...</option>
              </select>
            </label>
            {pick === ELSEWHERE && (
              <label className="field wide">
                <span className="field-label">Their game</span>
                <input value={otherName} onChange={(e) => setOtherName(e.target.value)} placeholder="e.g. Ark Nova" aria-label="Their game" autoFocus />
                <span className="hint">Added to your games as "Played elsewhere".</span>
              </label>
            )}
            {game?.stats?.avg_teach != null && (
              <p className="muted small">Usually: {game.stats.avg_teach} min to teach, {game.stats.avg_minutes ?? '?'} min to play.</p>
            )}
          </section>
          <section className="panel-section">
            <h4 className="section-title">Who's playing</h4>
            <PlayerPicker chosen={seats} onChange={setSeats} roster={roster} max={game?.max_players} />
          </section>
          <section className="panel-section">
            <label className="field wide">
              <span className="field-label">Where</span>
              <input value={location} onChange={(e) => setLocation(e.target.value)} list="bgt-places" placeholder="e.g. Home, a games cafe, an event"
                aria-label="Where" maxLength={120} />
              <datalist id="bgt-places">{roster.places.map((p) => <option key={p} value={p} />)}</datalist>
            </label>
            {game?.add_on_list?.length > 0 && (
              <fieldset className="bgt-expansions">
                <legend className="field-label">Expansions in</legend>
                {game.add_on_list.map((e) => (
                  <label key={e.game_id} className="check-row">
                    <input type="checkbox" checked={expansions.includes(e.game_id)}
                      onChange={(ev) => setExpansions(ev.target.checked ? [...expansions, e.game_id] : expansions.filter((x) => x !== e.game_id))} />
                    {e.name}
                  </label>
                ))}
              </fieldset>
            )}
          </section>
        </>
      )}
    </Drawer>
  )
}

const STAGES = [['setup', 'Setting up'], ['teach', 'The teach'], ['play', 'Playing']]

// Keep the phone's screen on while a play is open (where the browser lets a page ask).
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

// A second-by-second tick while something runs.
function useTick(running) {
  const [, setN] = useState(0)
  useEffect(() => {
    if (!running) return undefined
    const t = setInterval(() => setN((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [running])
}

function LiveView({ id, onClose, onNext }) {
  const { changed, showToast } = useApp()
  const [live, setLive] = useState(null)
  const [seats, setSeats] = useState([])
  const [anchor, setAnchor] = useState(0)        // when the server's timings arrived (Date.now())
  const [error, setError] = useState('')
  const [editingPlayers, setEditingPlayers] = useState(false)
  const [roster, setRoster] = useState(null)
  const [finishing, setFinishing] = useState(false)
  const [confirmThrow, setConfirmThrow] = useState(false)
  const [picking, setPicking] = useState(null)   // the name flashing while "who goes first" spins
  const [amount, setAmount] = useState({})       // a custom +/- amount per seat
  const [notes, setNotes] = useState('')
  const [teachNotes, setTeachNotes] = useState(null)
  const save = useRef(null)
  useScreenOn()

  const show = useCallback((l, keepSeats = false) => {
    setLive(l)
    setAnchor(Date.now())
    if (!keepSeats) setSeats(l.seats)
  }, [])
  useEffect(() => {
    api.livePlay(id).then((l) => { show(l); setNotes(l.notes ?? '') }).catch((e) => setError(e.message))
  }, [id, show])
  useTick(!!live?.stage)
  const run = async (fn) => {
    setError('')
    try { await fn() } catch (e) { setError(e.message) }
  }
  // Scores: shown at once, sent a moment after the last tap (the server keeps them if the phone dies).
  const changeSeats = (next, now = false) => {
    setSeats(next)
    clearTimeout(save.current)
    const send = () => run(async () => show(await api.updateLivePlay(id, { seats: seatsOut(next) }), true))
    if (now) send()
    else save.current = setTimeout(send, 700)
  }
  useEffect(() => () => clearTimeout(save.current), [])

  if (!live) {
    return <Drawer title="Playing" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  }
  if (finishing) {
    return <FinishPlay live={live} seats={seats} notes={notes} onBack={() => setFinishing(false)} onClose={onClose}
      onSaved={(r) => { changed(); showToast(`Logged a play of ${live.game_name}`); return r }}
      onNext={() => onNext(seats.map((s) => ({ player_id: s.player_id, name: s.name, is_me: s.is_me, adds: [] })), live.location ?? '')} />
  }

  const since = (Date.now() - anchor) / 1000
  const secs = { ...live.seconds, ...(live.stage ? { [live.stage]: live.seconds[live.stage] + since } : {}) }
  const totalSecs = secs.setup + secs.teach + secs.play
  const shownStage = live.stage ?? live.last_stage
  const stage = (to) => run(async () => show(await api.liveStage(id, to), true))
  const scoring = live.scoring
  const ranks = places(seats, scoring)
  const firstIdx = seats.findIndex((s) => s.player_id === live.first_player_id)
  const order = firstIdx > 0 ? [...seats.slice(firstIdx), ...seats.slice(0, firstIdx)] : seats
  const bump = (s, by) => changeSeats(seats.map((x) => (seatKey(x) === seatKey(s) ? { ...x, score: null, adds: [...(x.adds ?? []), by] } : x)))
  const undo = (s) => changeSeats(seats.map((x) => (seatKey(x) === seatKey(s) ? { ...x, adds: (x.adds ?? []).slice(0, -1) } : x)))
  const setPart = (s, part, v) => changeSeats(seats.map((x) => (seatKey(x) === seatKey(s) ? { ...x, score: null, parts: { ...x.parts, [part]: v } } : x)))
  const pickFirst = () => {
    if (seats.length < 2) return
    const winner = seats[Math.floor(Math.random() * seats.length)]
    let n = 0
    const spin = setInterval(() => {
      setPicking(seats[n % seats.length].name)
      n += 1
      if (n > 10 + seats.indexOf(winner)) {
        clearInterval(spin)
        setPicking(null)
        run(async () => show(await api.updateLivePlay(id, { first_player_id: winner.player_id }), true))
      }
    }, 90)
  }
  const footer = confirmThrow ? (
    <span className="confirm">Throw this play away? Nothing is saved.
      <button type="button" className="danger" onClick={() => run(async () => { await api.discardLivePlay(id); changed(); onClose() })}>Throw away</button>
      <button type="button" className="plain" onClick={() => setConfirmThrow(false)}>Keep playing</button>
    </span>
  ) : (
    <>
      <button type="button" className="primary" onClick={() => { clearTimeout(save.current); setFinishing(true) }}>Finish</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirmThrow(true)}>Throw away</button>
    </>
  )
  return (
    <Drawer title={live.game_name} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <section className="bgt-clock" aria-label="The clock">
        <p className="bgt-clock-stage">{live.paused ? 'Paused' : STAGES.find(([k]) => k === shownStage)?.[1]}</p>
        <p className="bgt-clock-time" role="timer" aria-live="off">{clock(secs[shownStage] ?? 0)}</p>
        <p className="muted small">{clock(totalSecs)} in all{live.location && ` · ${live.location}`}</p>
        <div className="segmented bgt-stages" role="group" aria-label="Stage">
          {STAGES.map(([k, label]) => (
            <button key={k} type="button" aria-pressed={live.stage === k} onClick={() => stage(k)}>
              {label}<span className="bgt-stage-time">{clock(secs[k])}</span></button>
          ))}
        </div>
        <div className="button-row bgt-clock-buttons">
          {live.paused
            ? <button type="button" className="primary" onClick={() => stage('resume')}>Carry on</button>
            : <button type="button" className="secondary" onClick={() => stage('pause')}>Pause (a break)</button>}
          <span className="bgt-rounds" role="group" aria-label="Round">
            <button type="button" className="icon-btn" aria-label="One round back" disabled={!live.rounds}
              onClick={() => run(async () => show(await api.updateLivePlay(id, { rounds: Math.max(0, live.rounds - 1) }), true))}>−</button>
            <span>{live.rounds ? `Round ${live.rounds}` : 'Rounds'}</span>
            <button type="button" className="icon-btn" aria-label="Next round"
              onClick={() => run(async () => show(await api.updateLivePlay(id, { rounds: live.rounds + 1 }), true))}>+</button>
          </span>
        </div>
      </section>

      {(shownStage === 'teach' || live.teach_notes) && (
        <details className="fold bgt-teach" open={shownStage === 'teach'}>
          <summary><span className="fold-title">Teach notes</span></summary>
          <div className="fold-body">
            {teachNotes == null ? (
              <>
                {live.teach_notes ? <p className="detail-desc">{live.teach_notes}</p>
                  : <p className="muted small">Nothing yet: what to cover when you teach {live.game_name} (the goal, a turn, how it ends, tips).</p>}
                <button type="button" className="plain small" onClick={() => setTeachNotes(live.teach_notes ?? '')}>{live.teach_notes ? 'Edit' : 'Write some'}</button>
              </>
            ) : (
              <>
                <textarea value={teachNotes} onChange={(e) => setTeachNotes(e.target.value)} rows={5} aria-label="Teach notes" />
                <div className="button-row">
                  <button type="button" className="secondary" onClick={() => run(async () => {
                    await api.updateBoardGame(live.game_id, { teach_notes: teachNotes })
                    setLive({ ...live, teach_notes: teachNotes.trim() || null })
                    setTeachNotes(null)
                  })}>Save notes</button>
                  <button type="button" className="plain" onClick={() => setTeachNotes(null)}>Cancel</button>
                </div>
              </>
            )}
          </div>
        </details>
      )}

      <section className="panel-section">
        <div className="section-head">
          <h4 className="section-title">{scoring === 'coop' || scoring === 'none' ? 'Playing' : 'Scores'}</h4>
          <span className="button-row">
            {seats.length > 1 && <button type="button" className="secondary small" onClick={pickFirst} disabled={!!picking}>🎲 Who goes first?</button>}
            <button type="button" className="plain small" onClick={() => {
              if (!roster) api.boardGamePlayers().then(setRoster).catch((e) => setError(e.message))
              setEditingPlayers(!editingPlayers)
            }}>{editingPlayers ? 'Done' : 'Players'}</button>
          </span>
        </div>
        {picking && <p className="bgt-first spinning" aria-live="polite">🎲 {picking}...</p>}
        {!picking && firstIdx >= 0 && <p className="bgt-first" aria-live="polite">🎲 {seats[firstIdx].name} goes first</p>}
        {editingPlayers && roster && <PlayerPicker chosen={seats} roster={roster} max={live.max_players}
          onChange={(next) => changeSeats(next, true)} />}
        {seats.length === 0 && !editingPlayers && <p className="muted small">No players yet: tap Players to add who's playing.</p>}
        <ul className="bgt-board">
          {order.map((s) => {
            const i = seats.indexOf(s)
            const total = seatTotal(s)
            return (
              <li key={seatKey(s)} className={`bgt-seat${ranks[i] === 1 && total != null ? ' leading' : ''}`}>
                <div className="bgt-seat-head">
                  <span className="bgt-seat-name">{s.name}
                    {s.player_id === live.first_player_id && <span className="pill">First</span>}
                    {s.first_time && <span className="pill teal">First play!</span>}</span>
                  {scoring !== 'coop' && scoring !== 'none' && (
                    <span className="bgt-seat-total" aria-label={`${s.name}: ${scoreText(total) || 'no score'}`}>
                      {scoreText(total) || '0'}{ranks[i] && <small className="muted"> {placeText(ranks[i])}</small>}</span>
                  )}
                </div>
                {scoring !== 'coop' && scoring !== 'none' && (live.score_parts?.length ? (
                  <div className="bgt-parts">
                    {live.score_parts.map((p) => (
                      <label key={p} className="bgt-part">{p}
                        <input type="number" inputMode="decimal" step="any" value={s.parts?.[p] ?? ''} aria-label={`${s.name}: ${p}`}
                          onChange={(e) => setPart(s, p, e.target.value)} />
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="bgt-bumps">
                    <button type="button" className="secondary" aria-label={`${s.name} minus 1`} onClick={() => bump(s, -1)}>−1</button>
                    <button type="button" className="secondary" aria-label={`${s.name} plus 1`} onClick={() => bump(s, 1)}>+1</button>
                    <button type="button" className="secondary" aria-label={`${s.name} plus 5`} onClick={() => bump(s, 5)}>+5</button>
                    <input type="number" inputMode="decimal" step="any" placeholder="±" aria-label={`Add to ${s.name}'s score`}
                      value={amount[seatKey(s)] ?? ''} onChange={(e) => setAmount({ ...amount, [seatKey(s)]: e.target.value })}
                      onKeyDown={(e) => { if (e.key === 'Enter' && e.target.value) { bump(s, Number(e.target.value)); setAmount({ ...amount, [seatKey(s)]: '' }) } }} />
                    <button type="button" className="plain small" disabled={!amount[seatKey(s)]}
                      onClick={() => { bump(s, Number(amount[seatKey(s)])); setAmount({ ...amount, [seatKey(s)]: '' }) }}>Add</button>
                    {s.adds?.length > 0 && <button type="button" className="plain small" onClick={() => undo(s)}
                      title={s.adds.map((a) => (a > 0 ? `+${a}` : a)).join(' ')}>Undo</button>}
                  </div>
                ))}
              </li>
            )
          })}
        </ul>
      </section>

      <section className="panel-section">
        <h4 className="section-title">Photos</h4>
        <PlayPhotos photos={live.photos} onAdd={async (blob) => {
          const p = await api.addLivePhoto(id, blob)
          setLive((l) => ({ ...l, photos: [...l.photos, p] }))
        }} />
      </section>
      <section className="panel-section">
        <label className="field wide">
          <span className="field-label">Notes</span>
          <textarea value={notes} rows={3} placeholder="Rules questions, funny moments, a house rule..." aria-label="Notes"
            onChange={(e) => setNotes(e.target.value)}
            onBlur={() => notes !== (live.notes ?? '') && run(async () => show(await api.updateLivePlay(id, { notes }), true))} />
        </label>
      </section>
    </Drawer>
  )
}

// The end: final scores (change any), who won, how it went - then it's saved as a play.
function FinishPlay({ live, seats: liveSeats, notes, onBack, onClose, onSaved, onNext }) {
  const [seats, setSeats] = useState(liveSeats.map((s) => ({ ...s, won: s.won || null })))
  const [unfinished, setUnfinished] = useState(false)
  const [coopWon, setCoopWon] = useState(null)
  const [fun, setFun] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(null)        // {play, highlights}
  const save = async () => {
    if (live.scoring === 'coop' && !unfinished && coopWon == null) { setError('Did you win?'); return }
    setBusy(true)
    setError('')
    try {
      await api.updateLivePlay(live.live_id, { notes })
      setDone(onSaved(await api.finishLivePlay(live.live_id, {
        finished: !unfinished, coop_won: coopWon, fun, seats: seatsOut(seats),
      })))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  if (done) {
    const p = done.play
    return (
      <Drawer title="Saved" onClose={onClose} footer={(
        <>
          <button type="button" className="primary" onClick={onNext}>Next game (same people)</button>
          <button type="button" className="plain" onClick={onClose}>Done</button>
        </>
      )}>
        <div className="bgt-done">
          <p className="bgt-done-title">{p.finished ? (p.winner ? `🏆 ${p.winner}` : live.scoring === 'coop' ? 'The game won this time' : 'Played') : 'Abandoned'}</p>
          <p className="muted">{live.game_name} · {[p.setup_minutes != null && `setup ${p.setup_minutes} min`, p.teach_minutes != null && `teach ${p.teach_minutes} min`,
            p.minutes != null && `played ${p.minutes} min`].filter(Boolean).join(' · ')}</p>
          {done.highlights.map((h) => <p key={h} className="alert ok small">⭐ {h}</p>)}
          {p.seats.some((s) => s.first_time) && (
            <p className="muted small">First play for {p.seats.filter((s) => s.first_time).map((s) => s.name).join(', ')}.</p>
          )}
        </div>
      </Drawer>
    )
  }
  return (
    <Drawer title={`Finish ${live.game_name}`} onClose={onClose} footer={(
      <>
        <button type="button" className="primary" onClick={save} disabled={busy}>{busy ? 'Saving...' : 'Save the play'}</button>
        <button type="button" className="plain" onClick={onBack} disabled={busy}>Back to the game</button>
      </>
    )}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <label className="all-day-switch">
        <input type="checkbox" role="switch" checked={unfinished} onChange={(e) => setUnfinished(e.target.checked)} />
        <span>Didn't finish (abandoned)</span>
      </label>
      {!unfinished && (
        <section className="panel-section">
          <h4 className="section-title">{live.scoring === 'coop' ? 'How did it go?' : 'Final scores'}</h4>
          <SeatScores seats={seats} onChange={setSeats} scoring={live.scoring} parts={live.score_parts ?? []}
            coopWon={coopWon} onCoopWon={setCoopWon} />
          {live.scoring !== 'coop' && <p className="muted small">The best score wins; a tie is shared - tap 🏆 to pick the winner yourself.</p>}
        </section>
      )}
      <section className="panel-section"><FunPicker value={fun} onChange={setFun} /></section>
    </Drawer>
  )
}
