import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import PlayBoard, { useChessJs } from './PlayBoard.jsx'
import { epdOf, formatLine, pickReply, progressText, suggestColour, uciSquares } from './openingHelpers.js'

// The Openings tab's "Train": the openings you are learning (with how far you are), "Learn an opening" (pick one, pick
// your colour, the app works out the lines and the replies to expect), and the drill - learn new moves, then review the
// ones that are due. The scheduling is the server's (api/app/chess_trainer.py: right -> 1 day, 6 days, then longer;
// wrong -> back soon). Pages only read when they open: nothing is written until you answer or press a button.

const SUGGESTIONS = ['Italian Game', 'Ruy Lopez', "Queen's Gambit", 'London System', 'Sicilian Defense', 'French Defense', 'Caro-Kann Defense', "King's Indian Defense"]

export default function OpeningTrainer({ prefill, onExplore }) {
  const [view, setView] = useState(prefill ? { kind: 'add' } : { kind: 'list' })
  const [listKey, setListKey] = useState(0)
  const back = () => { setView({ kind: 'list' }); setListKey((k) => k + 1) }
  if (view.kind === 'add') return <AddOpening prefill={prefill} onDone={back} onCancel={back} />
  if (view.kind === 'drill') return <DrillSession rep={view.rep} mode={view.mode} onExit={back} />
  return <RepertoireList key={listKey} onAdd={() => setView({ kind: 'add' })} onDrill={(rep, mode) => setView({ kind: 'drill', rep, mode })}
    onExplore={onExplore} />
}

function RepertoireList({ onAdd, onDrill, onExplore }) {
  const [list, setList] = useState(null)
  const [error, setError] = useState(null)
  const [sure, setSure] = useState(null)
  const load = useCallback(() => api.trainerRepertoires().then((d) => setList(d.repertoires)).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])
  const building = list?.some((r) => r.status === 'building')
  useEffect(() => {
    if (!building) return undefined
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [building, load])
  const remove = (id) => api.deleteTrainerRepertoire(id).then(() => { setSure(null); load() }).catch((e) => setError(e.message))

  return (
    <section className="page ot-train">
      <div className="toolbar">
        <button type="button" className="primary" onClick={onAdd}>+ Learn an opening</button>
      </div>
      <p className="muted small">Pick an opening and your colour. The app builds the lines to learn - what you play, what the other side is likely
        to answer - and drills you on them, a little each day.</p>
      {error && <p className="alert error">{error}</p>}
      {!list && !error && <p className="muted loading">Loading...</p>}
      {list?.length === 0 && <p className="empty card">No openings yet. Start with "+ Learn an opening".</p>}
      <ul className="ot-reps">
        {list?.map((r) => {
          const p = r.progress
          const pct = p.total ? Math.round((100 * p.learned) / p.total) : 0
          return (
            <li key={r.repertoire_id} className="ot-rep card">
              <div className="ot-rep-head">
                <strong>{r.name}</strong>
                <span className="chip">{r.colour === 'white' ? 'As White' : 'As Black'}</span>
              </div>
              {r.moves && <p className="muted small">{formatLine(r.moves.split(' '))}</p>}
              {r.status === 'building' && <p className="small loading" role="status">Building the lines... {r.building?.message ?? ''}</p>}
              {r.status === 'failed' && <p className="alert error small">{r.error}</p>}
              {r.status === 'ready' && (
                <>
                  <div className="ot-progress" role="img" aria-label={`${p.learned} of ${p.total} learned`}><span style={{ width: `${pct}%` }} /></div>
                  <p className="small">{progressText(p)}</p>
                  {r.notes && <p className="muted small">{r.notes}</p>}
                </>
              )}
              <div className="ot-rep-actions">
                {r.status === 'ready' && (
                  <>
                    <button type="button" className="primary small" disabled={!p.new} onClick={() => onDrill(r, 'learn')}>Learn new ({p.new})</button>
                    <button type="button" className="secondary small" disabled={!p.due} onClick={() => onDrill(r, 'review')}>Review ({p.due})</button>
                    <button type="button" className="secondary small" onClick={() => onExplore(r.moves ? r.moves.split(' ') : [])}>Explore</button>
                  </>
                )}
                {sure === r.repertoire_id ? (
                  <>
                    <button type="button" className="danger small" onClick={() => remove(r.repertoire_id)}>Yes, delete it</button>
                    <button type="button" className="plain small" onClick={() => setSure(null)}>Keep it</button>
                  </>
                ) : <button type="button" className="plain small" onClick={() => setSure(r.repertoire_id)}>Delete</button>}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// Search the named openings, pick one (or a line from Explore), choose your colour, build.
function AddOpening({ prefill, onDone, onCancel }) {
  const start = prefill ? { name: prefill.name ?? 'Your line', moves: prefill.moves.join(' ') } : null
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [choice, setChoice] = useState(start)
  const [colour, setColour] = useState(start ? suggestColour(start.name) : 'white')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (q.trim().length < 2) return undefined
    let stale = false
    const t = setTimeout(() => {
      api.trainerSearch(q.trim()).then((d) => { if (!stale) setResults(d.openings) }).catch(() => { if (!stale) setResults([]) })
    }, 250)
    return () => { stale = true; clearTimeout(t) }
  }, [q])
  const shownResults = q.trim().length < 2 ? [] : results
  const pick = (o) => { setChoice(o); setColour(suggestColour(o.name)) }
  const build = () => {
    setBusy(true)
    api.addTrainerRepertoire({ colour, moves: choice.moves, name: choice.name })
      .then(onDone)
      .catch((e) => { setError(e.message); setBusy(false) })
  }
  return (
    <section className="page ot-add">
      <div className="toolbar"><button type="button" className="plain" onClick={onCancel}>← Your openings</button></div>
      {!choice ? (
        <>
          <label className="ot-search">
            <span className="muted small">Find an opening by name</span>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Sicilian Najdorf, London, Italian..." autoFocus />
          </label>
          {q.trim().length < 2 && (
            <div className="ot-suggest">
              {SUGGESTIONS.map((s) => <button key={s} type="button" className="chip as-button" onClick={() => setQ(s)}>{s}</button>)}
              <button type="button" className="chip as-button" onClick={() => setChoice({ name: 'Starting position', moves: '' })}>From move 1</button>
            </div>
          )}
          <ul className="ot-results">
            {shownResults.map((o) => (
              <li key={`${o.eco}-${o.moves}`}>
                <button type="button" className="row-button ot-result" onClick={() => pick(o)}>
                  <span className="grow"><span className="item-title">{o.name}</span>
                    <span className="item-meta">{o.eco} · {formatLine(o.moves.split(' '))}</span></span>
                </button>
              </li>
            ))}
          </ul>
          {q.trim().length >= 2 && shownResults.length === 0 && <p className="muted small">No named opening matches that.</p>}
        </>
      ) : (
        <div className="card ot-confirm">
          <strong>{choice.name}</strong>
          <p className="muted small">{choice.moves ? formatLine(choice.moves.split(' ')) : 'Everything from the first move'}</p>
          <div className="segmented" role="group" aria-label="Your colour">
            {[['white', 'I play White'], ['black', 'I play Black']].map(([id, label]) => (
              <button key={id} type="button" aria-pressed={colour === id} onClick={() => setColour(id)}>{label}</button>
            ))}
          </div>
          <p className="muted small">The app will ask Lichess (players near your rating, and masters) what is played from here, and Stockfish for the
            moves to play. It takes a minute and carries on in the background.</p>
          {error && <p className="alert error small">{error}</p>}
          <div className="ot-rep-actions">
            <button type="button" className="primary" disabled={busy} onClick={build}>{busy ? 'Starting...' : 'Build the lines'}</button>
            <button type="button" className="plain" onClick={() => { setChoice(null); setError(null) }}>Choose another</button>
          </div>
        </div>
      )}
    </section>
  )
}

// A session: 'learn' shows each new move (then asks it back); 'review' asks the cards that are due.
function DrillSession({ rep, mode, onExit }) {
  const Chess = useChessJs()
  const [deck, setDeck] = useState(null)             // { cards, replies }
  const [queue, setQueue] = useState([])
  const [phase, setPhase] = useState('loading')      // loading | show | ask | right | wrong | done
  const [after, setAfter] = useState(null)           // after a right answer: { fen, reply, replyFen, replyShown }
  const [played, setPlayed] = useState(null)         // the wrong move's squares
  const [hintFor, setHintFor] = useState(null)
  const [stats, setStats] = useState({ right: 0, wrong: 0 })
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let stale = false
    api.trainerDrill(rep.repertoire_id, mode).then((d) => {
      if (stale) return
      setDeck(d)
      setQueue(d.cards.map((c) => ({ ...c, retry: false })))
      setProgress(d.progress)
      setPhase(d.cards.length === 0 ? 'done' : mode === 'learn' ? 'show' : 'ask')
    }).catch((e) => { if (!stale) setError(e.message) })
    return () => { stale = true }
  }, [rep.repertoire_id, mode])

  const replySan = after?.reply?.san
  useEffect(() => {
    if (phase !== 'right' || !replySan) return undefined
    const t = setTimeout(() => setAfter((a) => (a ? { ...a, replyShown: true } : a)), 700)
    return () => clearTimeout(t)
  }, [phase, replySan])

  const card = queue[0]
  const total = deck?.cards.length ?? 0
  const remaining = queue.filter((c) => !c.retry).length

  const answer = (move) => {
    const ok = move.uci === card.move_uci
    if (!card.retry) {
      api.answerTrainerCard(card.card_id, ok, move.san).then((r) => setProgress(r.progress)).catch((e) => setError(e.message))
      setStats((s) => ({ right: s.right + (ok ? 1 : 0), wrong: s.wrong + (ok ? 0 : 1) }))
    }
    if (!ok) {
      setPlayed({ from: move.from, to: move.to })
      setPhase('wrong')
      return
    }
    const reply = pickReply(deck.replies[epdOf(move.fen)])
    let replyFen = null
    if (reply && Chess) {
      try {
        const g = new Chess(move.fen)
        g.move(reply.san)
        replyFen = g.fen()
      } catch { replyFen = null }
    }
    setAfter({ fen: move.fen, to: move.to, reply: replyFen ? reply : null, replyFen, replyShown: false })
    setPhase('right')
  }

  const next = () => {
    const [done, ...rest] = queue
    let nextQueue = rest
    if (phase === 'wrong') nextQueue = [...rest, { ...done, retry: true }]            // once more, just to practise
    else if (after?.reply) {                                                           // carry on down the line if that is a card
      const at = rest.findIndex((c) => c.epd === after.reply.epd)
      if (at > 0) nextQueue = [rest[at], ...rest.slice(0, at), ...rest.slice(at + 1)]
    }
    setQueue(nextQueue)
    setAfter(null)
    setPlayed(null)
    setPhase(nextQueue.length === 0 ? 'done' : mode === 'learn' && !nextQueue[0].retry ? 'show' : 'ask')
  }

  if (error && !deck) return <section className="page"><p className="alert error">{error}</p><button type="button" className="plain" onClick={onExit}>← Your openings</button></section>
  if (phase === 'loading') return <section className="page"><p className="muted loading">Loading...</p></section>
  if (phase === 'done') {
    return (
      <section className="page ot-done">
        <div className="card">
          <h2>{total === 0 ? (mode === 'learn' ? 'Nothing new to learn' : 'Nothing is due') : 'Session finished'}</h2>
          {total > 0 && <p>{stats.right} right{stats.wrong > 0 ? `, ${stats.wrong} to practise again` : ' - every one'}.</p>}
          {progress && <p className="muted small">{progressText(progress)}{progress.due ? '' : '. Nothing is due right now - come back tomorrow.'}</p>}
          {error && <p className="alert error small">{error}</p>}
          <button type="button" className="primary" onClick={onExit}>← Your openings</button>
        </div>
      </section>
    )
  }

  const move = uciSquares(card.move_uci)
  const showing = phase === 'right' && after
  const fen = !showing ? card.fen : after.replyShown && after.replyFen ? after.replyFen : after.fen
  const arrows = phase === 'show' || phase === 'wrong' ? [{ ...move, colour: 'best' }] : []
  const marks = phase === 'wrong' ? { [move.to]: 'good', ...(played ? { [played.to]: 'bad' } : {}) }
    : showing ? { [after.to]: 'good' } : hintFor === card.card_id && phase === 'ask' ? { [move.from]: 'hint' } : {}
  const line = card.line.length ? formatLine(card.line) : 'the start of the game'

  return (
    <section className="page ot-drill">
      <div className="toolbar">
        <button type="button" className="plain" onClick={onExit}>← Stop</button>
        <span className="muted small">{rep.name} · {mode === 'learn' ? 'Learning' : 'Review'} · {Math.min(total, total - remaining + 1)} of {total}</span>
      </div>
      <div className="ot-explore">
        <div className="ot-boardside">
          <PlayBoard fen={fen} orientation={rep.colour} onMove={phase === 'ask' ? answer : undefined} arrows={arrows} marks={marks}
            label={`Training board after ${line}`} />
        </div>
        <div className="ot-side" role="status" aria-live="polite">
          <p className="muted small">After {line}</p>
          {phase === 'show' && (
            <>
              <h3>Learn this move: {card.move_san}</h3>
              <p>{card.note}</p>
              <button type="button" className="primary" onClick={() => setPhase('ask')}>Got it - now you play it</button>
            </>
          )}
          {phase === 'ask' && (
            <>
              <h3>Your move{card.retry ? ' (once more)' : ''}</h3>
              <p className="muted small">Play the move from your {rep.name} lines.</p>
              <button type="button" className="plain small" onClick={() => setHintFor(card.card_id)}>Hint: which piece?</button>
            </>
          )}
          {phase === 'right' && (
            <>
              <h3 className="ot-right">Right: {card.move_san}</h3>
              <p>{card.note}</p>
              {after.reply && after.replyShown && <p>They play <strong>{after.reply.san}</strong> ({Math.round(after.reply.share)}% of the time).</p>}
              <button type="button" className="primary" onClick={next}>Next</button>
            </>
          )}
          {phase === 'wrong' && (
            <>
              <h3 className="ot-wrong">Not that one - play {card.move_san}</h3>
              <p>{card.note}</p>
              <p className="muted small">It comes back at the end of this session, and tomorrow.</p>
              <button type="button" className="primary" onClick={next}>Continue</button>
            </>
          )}
          {error && <p className="alert error small">{error}</p>}
        </div>
      </div>
    </section>
  )
}
