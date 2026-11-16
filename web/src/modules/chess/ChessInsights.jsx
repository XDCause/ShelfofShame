import { useCallback, useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { BarList } from '../../components/charts.jsx'
import { useApp } from '../../core/app-context.js'
import PlayBoard from './PlayBoard.jsx'
import { fmtSecs, hasClock, paceBars, recordText, skillChange, weakestSkill } from './insightHelpers.js'

// What your reviewed games say about you (api/app/chess_insights.py): skill scores against your own history, games where
// you let a won position go, endgames by type, clock habits - on the Dashboard - and "Your puzzles": your own mistakes
// drilled with spaced repetition (the opening trainer's scheduler).

const moveNo = (ply) => `${Math.ceil(ply / 2)}${ply % 2 ? '.' : '...'}`
const HOWS = { timeout: 'on time', resigned: 'resigned', checkmated: 'mated' }

// The Dashboard's cards. Nothing shows until a game has been reviewed.
export function InsightCards() {
  const { refreshKey, openPanel } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => { api.chessInsights().then(setData).catch(() => setData(null)) }, [refreshKey])
  if (!data?.reviewed) return null
  const weak = weakestSkill(data.skills)
  return (
    <>
      <section className="card ci-card">
        <h3 className="section-title">Your skills <span className="muted small">from {data.reviewed} reviewed game{data.reviewed === 1 ? '' : 's'}, against your own history</span></h3>
        <BarList title="Skill scores out of 100" valueLabel="score"
          rows={data.skills.filter((s) => s.score != null).map((s) => ({ label: s.label, value: s.score, text: `${Math.round(s.score)}` }))} />
        <ul className="list compact ci-skills">
          {data.skills.map((s) => {
            const ch = skillChange(s)
            return (
              <li key={s.id}><span className="grow"><strong>{s.label}</strong> <span className="muted small">{s.how}</span></span>
                <span className={`small ci-change ci-${ch.tone}`}>
                  {s.score == null ? 'not enough games yet' : `${s.games} game${s.games === 1 ? '' : 's'}${s.recent != null ? ` · lately ${Math.round(s.recent)}` : ''}${ch.text ? ` · ${ch.text}` : ''}`}
                </span></li>
            )
          })}
        </ul>
        {weak && <p className="small">Weakest so far: <strong>{weak.label}</strong>.</p>}
      </section>

      {data.lost_won.length > 0 && (
        <section className="card ci-card">
          <h3 className="section-title">Won positions you let go <span className="muted small">({data.lost_won.length})</span></h3>
          <p className="muted small">Games where you had 80% or more winning chances and didn't win. Tap one to see the move where it slipped.</p>
          <ul className="list plain-list">
            {data.lost_won.slice(0, 8).map((g) => (
              <li key={g.game_id}>
                <button type="button" className="row-button" onClick={() => openPanel('chessgame', { id: g.game_id, ply: g.ply })}>
                  <span className="grow">
                    <span className="item-title">vs {g.opp_name} · {g.result === 'draw' ? 'drawn' : `lost${HOWS[g.how] ? ` (${HOWS[g.how]})` : ''}`}</span>
                    <span className="item-meta">{shortDate(g.played_at)} · you were {g.peak}% to win
                      {g.san && ` · slipped at ${moveNo(g.ply)} ${g.san}${g.best ? ` (best was ${g.best})` : ''}`}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.endgames.length > 0 && (
        <section className="card ci-card">
          <h3 className="section-title">Endgames by type</h3>
          <p className="muted small">By the pieces left when the endgame began.</p>
          <ul className="list compact">
            {data.endgames.map((e) => (
              <li key={e.type} className="cr-summary-row"><span className="grow">{e.type[0].toUpperCase() + e.type.slice(1)}</span>
                <span className="muted small">{e.games} game{e.games === 1 ? '' : 's'} · {e.accuracy ?? '–'}% accuracy · {recordText(e)}</span></li>
            ))}
          </ul>
        </section>
      )}

      {data.time && <TimeCard time={data.time} />}
    </>
  )
}

function TimeCard({ time }) {
  const phases = Object.entries(time.avg_spent).filter(([, v]) => v != null)
  return (
    <section className="card ci-card">
      <h3 className="section-title">Your clock <span className="muted small">{time.games} reviewed game{time.games === 1 ? '' : 's'} with times</span></h3>
      <p className="small">
        {time.bad_moves > 0 ? <><strong>{time.bad_in_trouble}</strong> of your {time.bad_moves} mistakes and blunders came with little time left.</> : 'No mistakes or blunders in these games.'}
        {time.flagged > 0 && <> You lost {time.flagged} on time.</>}
      </p>
      {phases.length > 0 && <p className="muted small">Average time a move: {phases.map(([k, v]) => `${k} ${fmtSecs(v)}`).join(' · ')}</p>}
    </section>
  )
}

// Time spent on each move: one bar a move, yours in colour and theirs in grey; a ring on moves made short of time, red for a
// mistake in a hurry. The move you're looking at is marked. Hidden when the game has no clock.
export function ClockChart({ moves, ply, mine }) {
  if (!hasClock(moves)) return null
  const bars = paceBars(moves)
  const rushed = bars.filter((b) => b.colour === mine && b.low && b.bad).length
  return (
    <div className="ci-clock">
      <div className="ci-bars" role="img" aria-label={`Time spent on each move. ${rushed ? `${rushed} of your mistakes came short of time.` : ''}`}>
        {bars.map((b) => (
          <span key={b.ply} className={`ci-bar${b.colour === mine ? ' mine' : ''}${b.low ? ' low' : ''}${b.low && b.bad ? ' rushed' : ''}${b.ply === ply ? ' now' : ''}`}
            style={{ height: `${b.h}%` }} />
        ))}
      </div>
      <p className="muted small ci-clock-read">Time spent a move (yours in colour){rushed > 0 && <> · <strong>{rushed}</strong> of your mistakes in time trouble (red)</>}</p>
    </div>
  )
}

// "Your puzzles": the positions where you went wrong, with the engine's move to find.
export function PuzzlesView() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [at, setAt] = useState(0)
  const [note, setNote] = useState('')
  const load = useCallback(() => api.chessPuzzles().then((d) => { setData(d); setAt(0) }).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load, refreshKey])
  const find = async () => {
    setNote('')
    try {
      const r = await api.syncChessPuzzles()
      setNote(r.added ? `${r.added} new puzzle${r.added === 1 ? '' : 's'} from your reviews.` : 'No new puzzles in your reviews.')
      await load()
    } catch (e) { setError(e.message) }
  }
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const card = data.cards[at]
  return (
    <section className="page chess ci-puzzles">
      <div className="card ci-card">
        <h3 className="section-title">Your puzzles</h3>
        <p className="small">Every move of yours that a game review called a mistake, miss or blunder, as a puzzle: find the engine's move.
          Ones you get right come back after a day, then six, then further apart; ones you miss come back soon.</p>
        <p className="muted small">{data.total} puzzle{data.total === 1 ? '' : 's'} · {data.due} due · {data.new} new · {data.learned} well learned</p>
        <div className="button-row">
          <button type="button" className="secondary" onClick={find}>Look for new puzzles in my reviews</button>
          {note && <span className="muted small" aria-live="polite">{note}</span>}
        </div>
      </div>
      {data.total === 0 && <p className="muted">No puzzles yet. Review a game (open it under Games and press Review this game) and its mistakes show up here.</p>}
      {data.total > 0 && !card && <p className="alert ok">All done for now. {data.due === 0 ? 'Nothing is due: come back later.' : ''}</p>}
      {card && <Puzzle key={card.puzzle_id} card={card} index={at} count={data.cards.length} onNext={() => setAt(at + 1)} />}
    </section>
  )
}

function Puzzle({ card, index, count, onNext }) {
  const { openPanel } = useApp()
  const [result, setResult] = useState(null)             // null | 'right' | 'wrong' | 'shown'
  const [reported, setReported] = useState(false)
  const report = (correct) => {
    if (reported) return
    setReported(true)
    api.answerChessPuzzle(card.puzzle_id, correct).catch(() => {})
  }
  const done = result === 'right' || result === 'shown'
  const line = card.best_line ?? []
  return (
    <div className="card ci-puzzle">
      <div className="section-head">
        <h4 className="section-title">Puzzle {index + 1} of {count}</h4>
        <button type="button" className="plain small" onClick={() => openPanel('chessgame', { id: card.game_id, ply: card.ply })}>
          The game, vs {card.opp_name} →</button>
      </div>
      <p className="small">{card.colour === 'white' ? 'White' : 'Black'} to move. In your game ({shortDate(card.played_at)}) you played <strong>{card.played_san}</strong>,
        a {card.kind}. What was better?</p>
      <PlayBoard fen={card.fen} orientation={card.colour} label={`Find a better move than ${card.played_san}`}
        arrows={done ? [{ from: card.best_uci.slice(0, 2), to: card.best_uci.slice(2, 4), colour: 'best' }] : []}
        onMove={done ? undefined : (mv) => {
          const ok = mv.uci === card.best_uci
          setResult(ok ? 'right' : 'wrong')
          report(ok)
        }} />
      <div aria-live="polite">
        {result === 'right' && <p className="alert ok small">Yes - {card.best_san}!{line.length > 1 && ` The line: ${line.slice(0, 5).join(' ')}.`}</p>}
        {result === 'wrong' && <p className="alert low small">Not that one. Try again, or see the answer.</p>}
        {result === 'shown' && <p className="small">The engine's move: <strong>{card.best_san}</strong>{line.length > 1 && <>, then {line.slice(1, 5).join(' ')}</>}.</p>}
      </div>
      <div className="button-row">
        {done ? <button type="button" className="primary" onClick={onNext}>Next</button>
          : <button type="button" className="secondary" onClick={() => { report(false); setResult('shown') }}>Show me</button>}
        {!done && <button type="button" className="plain" onClick={() => { report(false); onNext() }}>Skip</button>}
      </div>
    </div>
  )
}
