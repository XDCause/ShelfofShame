import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import Board from './Board.jsx'
import { ClockChart } from './ChessInsights.jsx'
import { timeNote } from './insightHelpers.js'
import PlayBoard, { useChessJs } from './PlayBoard.jsx'

// Game review (api/app/chess_review.py), much like chess.com's: press "Review this game" and Stockfish looks at every
// position (about a minute; kept, so it opens at once next time). Then: each side's accuracy and a game rating, how
// many of each kind of move, the board with a bar for who's winning, a graph of the whole game (tap it to jump), every
// move judged with the best move and the line the engine expected, the opening and where it left theory - and
// "Retry your mistakes": back to each of your bad moves to find the better one.

export const KINDS = {
  brilliant: { label: 'Brilliant', sym: '!!' },
  great: { label: 'Great', sym: '!' },
  best: { label: 'Best', sym: '★' },
  excellent: { label: 'Excellent', sym: '✓' },
  good: { label: 'Good', sym: '✓' },
  book: { label: 'Book', sym: '◆' },
  forced: { label: 'Forced', sym: '→' },
  inaccuracy: { label: 'Inaccuracy', sym: '?!' },
  mistake: { label: 'Mistake', sym: '?' },
  miss: { label: 'Miss', sym: '✕' },
  blunder: { label: 'Blunder', sym: '??' },
}
const BAD = new Set(['inaccuracy', 'mistake', 'miss', 'blunder'])
const SHOWN = new Set(['brilliant', 'great', 'inaccuracy', 'mistake', 'miss', 'blunder'])

const moveNo = (ply) => `${Math.ceil(ply / 2)}${ply % 2 ? '.' : '...'}`
export const evalText = (e) => (!e ? '' : e.mate != null ? `${e.mate > 0 ? '' : '-'}M${Math.abs(e.mate)}` : `${e.cp > 0 ? '+' : ''}${(e.cp / 100).toFixed(2)}`)
const pct = (n) => `${Math.round(n)}%`

// Why a move got its mark, in words.
export function explain(m, prevWin, mine) {
  const k = KINDS[m.kind]
  const who = mine ? 'your' : 'their'
  const before = m.colour === 'white' ? prevWin : 100 - prevWin
  const after = m.colour === 'white' ? m.win_white : 100 - m.win_white
  if (m.kind === 'book') return 'A known opening move.'
  if (m.kind === 'forced') return 'The only legal move.'
  if (m.kind === 'brilliant') return `A sacrifice that works: the piece can be taken, but ${m.san} is as good as the engine's best.`
  if (m.kind === 'great') return 'The only good move here: anything else would have thrown a lot away.'
  if (m.kind === 'best') return "The engine's choice."
  if (m.kind === 'excellent' || m.kind === 'good') return `Close to the best (${m.best}): ${who} winning chances barely moved.`
  const drop = `${who[0].toUpperCase() + who.slice(1)} winning chances went from ${pct(before)} to ${pct(after)}.`
  if (m.kind === 'miss') return `${k.label}: the opponent had just gone wrong, and this let them off. ${drop}`
  return `${k.label}. ${drop}`
}

export default function GameReview({ game, startPly }) {
  const [review, setReview] = useState(null)
  const [error, setError] = useState('')
  const { changed } = useApp()
  useEffect(() => {
    let live = true
    let timer = null
    const look = () => api.chessReview(game.game_id).then((r) => {
      if (!live) return
      setReview(r)
      if (r.status === 'running') timer = setTimeout(look, 1500)
      if (r.status === 'done' && review?.status === 'running') changed()
    }).catch((e) => live && setError(e.message))
    look()
    return () => { live = false; clearTimeout(timer) }
  }, [game.game_id, review?.status === 'running'])           // eslint-disable-line react-hooks/exhaustive-deps
  const start = async (again = false) => {
    setError('')
    try { setReview(await api.startChessReview(game.game_id, again)) } catch (e) { setError(e.message) }
  }
  if (!game.pgn) return null
  if (!review) return <Board pgn={game.pgn} colour={game.colour} />
  if (review.status === 'done') return <ReviewView game={game} review={review} startPly={startPly} onAgain={() => start(true)} />
  return (
    <>
      <div className="card cr-start">
        {review.status === 'running' ? (
          <>
            <p><strong>Reviewing...</strong> Stockfish is looking at every position.</p>
            <div className="cr-progress" role="progressbar" aria-label="Review progress" aria-valuemin={0}
              aria-valuemax={review.total_plies || 1} aria-valuenow={review.done_plies}>
              <span style={{ width: `${review.total_plies ? (100 * review.done_plies) / review.total_plies : 3}%` }} />
            </div>
            <p className="muted small">{review.total_plies ? `${review.done_plies} of ${review.total_plies} positions` : 'Starting the engine...'}</p>
          </>
        ) : (
          <>
            <p><strong>Game review</strong>: accuracy, blunders and brilliant moves, what you should have played, and where
              you left the opening's theory.</p>
            {review.status === 'failed' && <p className="alert error small">{review.error}</p>}
            <button type="button" className="primary" onClick={() => start(review.status === 'failed')}>
              {review.status === 'failed' ? 'Try the review again' : 'Review this game'}</button>
            <span className="muted small"> about a minute</span>
          </>
        )}
        {error && <p className="alert error small">{error}</p>}
      </div>
      <Board pgn={game.pgn} colour={game.colour} />
    </>
  )
}

// Every position's FEN: the start, then after each move (from the review's FEN-before and the move).
function useFens(moves) {
  const Chess = useChessJs()
  return useMemo(() => {
    if (!Chess || !moves.length) return null
    const out = [moves[0].fen_before]
    for (const m of moves) {
      const c = new Chess(m.fen_before)
      c.move({ from: m.uci.slice(0, 2), to: m.uci.slice(2, 4), promotion: m.uci[4] })
      out.push(c.fen())
    }
    return out
  }, [Chess, moves])
}

function ReviewView({ game, review, startPly, onAgain }) {
  const { moves, summary } = review
  const fens = useFens(moves)
  const Chess = useChessJs()
  const [ply, setPly] = useState(startPly ? Math.min(startPly, moves.length) : moves.length)
  const [line, setLine] = useState(null)              // showing the engine's line: {from: ply, fens, sans, at}
  const [retry, setRetry] = useState(null)            // retrying your mistakes: {list, at, result}
  const mine = game.colour
  const last = moves.length
  const wins = [summary.start_win_white, ...moves.map((m) => m.win_white)]
  useEffect(() => {
    const keys = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(e.target.tagName) && e.target.closest('.pb-board')) return
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || retry) return
      if (e.key === 'ArrowLeft') { setLine(null); setPly((p) => Math.max(0, p - 1)) } else if (e.key === 'ArrowRight') { setLine(null); setPly((p) => Math.min(last, p + 1)) } else return
      e.preventDefault()
    }
    window.addEventListener('keydown', keys)
    return () => window.removeEventListener('keydown', keys)
  }, [last, retry])
  if (!fens) return <p className="muted small">Setting up the board...</p>

  const m = ply ? moves[ply - 1] : null
  const go = (p) => { setLine(null); setPly(Math.max(0, Math.min(last, p))) }
  const myBad = moves.filter((x) => x.colour === mine && BAD.has(x.kind))
  const keyMoments = summary.key_moments ?? []
  const nextKey = keyMoments.find((k) => k > ply) ?? keyMoments[0]
  const showLine = () => {
    const c = new Chess(m.fen_before)
    const lineFens = [m.fen_before]
    const sans = []
    for (const san of m.best_line) {
      try { c.move(san) } catch { break }
      lineFens.push(c.fen())
      sans.push(san)
    }
    setLine({ fens: lineFens, sans, at: 1 })
  }
  const shownFen = line ? line.fens[line.at] : fens[ply]
  const arrows = []
  const marks = {}
  if (!line && m) {
    marks[m.uci.slice(0, 2)] = 'from'
    marks[m.uci.slice(2, 4)] = 'to'
    if (m.best_uci && m.best_uci !== m.uci && m.kind !== 'book') arrows.push({ from: m.best_uci.slice(0, 2), to: m.best_uci.slice(2, 4), colour: 'best' })
  }
  const side = (colour) => summary.sides[colour]
  const youAre = (colour) => (colour === mine ? 'You' : game.opp_name)
  const ratingOf = (colour) => (colour === mine ? game.my_rating : game.opp_rating)

  if (retry) return <Retry game={game} moves={myBad} retry={retry} setRetry={setRetry} />
  return (
    <div className="cr-review">
      <div className="cr-sides">
        {['white', 'black'].map((c) => (
          <div key={c} className={`card cr-side${c === mine ? ' mine' : ''}`}>
            <span className="cr-side-name">{youAre(c)} <span className="muted small">({c === 'white' ? 'White' : 'Black'})</span></span>
            <strong className="cr-accuracy">{side(c).accuracy != null ? `${side(c).accuracy}` : '–'}<small>% accuracy</small></strong>
            <span className="muted small">Rated {ratingOf(c) ?? '?'} then · played like ~{side(c).game_rating ?? '?'}</span>
          </div>
        ))}
      </div>

      <table className="cr-counts">
        <caption className="visually-hidden">How many of each kind of move</caption>
        <thead><tr><th scope="col">Move</th><th scope="col">{youAre('white')}</th><th scope="col">{youAre('black')}</th></tr></thead>
        <tbody>
          {Object.entries(KINDS).filter(([k]) => side('white').counts[k] || side('black').counts[k]).map(([k, v]) => (
            <tr key={k} className={`cr-${k}`}>
              <th scope="row"><span className="cr-sym" aria-hidden="true">{v.sym}</span> {v.label}</th>
              <td>{side('white').counts[k]}</td><td>{side('black').counts[k]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small cr-phases">Your accuracy: {['opening', 'middlegame', 'endgame'].map((ph) => side(mine).phases[ph] != null
        && `${ph} ${side(mine).phases[ph]}%`).filter(Boolean).join(' · ')}</p>

      {summary.opening && <OpeningNote summary={summary} mine={mine} onJump={go} />}

      <div className="cr-main">
        <div className="cr-board-col">
          <PlayBoard fen={shownFen} orientation={mine} arrows={arrows} marks={marks} evalBar={line ? null : wins[ply]}
            badge={!line && m ? { square: m.uci.slice(2, 4), kind: m.kind, label: KINDS[m.kind].sym } : null}
            label={m ? `After ${moveNo(ply)} ${m.san}` : 'Starting position'} />
          <div className="chess-controls">
            <button type="button" className="secondary" onClick={() => go(0)} disabled={ply === 0 && !line} aria-label="Start">⏮</button>
            <button type="button" className="secondary" onClick={() => go(ply - 1)} disabled={ply === 0} aria-label="Back one move">◀</button>
            <span className="muted small chess-ply">{m ? `${moveNo(ply)} ${m.san}` : 'Start'} {m && <span className="cr-eval">{evalText(m.eval)}</span>}</span>
            <button type="button" className="secondary" onClick={() => go(ply + 1)} disabled={ply === last} aria-label="Forward one move">▶</button>
            <button type="button" className="secondary" onClick={() => go(last)} disabled={ply === last} aria-label="End">⏭</button>
          </div>
          <EvalGraph wins={wins} moves={moves} ply={ply} onPick={go} />
          <ClockChart moves={moves} ply={ply} mine={mine} />
        </div>
        <div className="cr-side-col">
          {m ? (
            <div className={`card cr-move cr-${m.kind}`} aria-live="polite">
              <p className="cr-move-head"><span className="cr-sym" aria-hidden="true">{KINDS[m.kind].sym}</span>
                <strong>{moveNo(ply)} {m.san}</strong> is {['a', 'e', 'i', 'o', 'u'].includes(KINDS[m.kind].label[0].toLowerCase()) ? 'an' : 'a'} {KINDS[m.kind].label.toLowerCase()} move
                <span className="cr-eval">{evalText(m.eval)}</span></p>
              <p className="small">{explain(m, wins[ply - 1], m.colour === mine)}</p>
              {m.clock != null && <p className="muted small">{timeNote(m)}</p>}
              {m.best && m.best !== m.san && m.kind !== 'book' && (
                <p className="small"><strong>Best was {moveNo(ply)} {m.best}</strong>{m.best_line.length > 1 && <span className="muted"> then {m.best_line.slice(1, 5).join(' ')}</span>}</p>
              )}
              {m.best_line.length > 0 && !line && <button type="button" className="secondary small" onClick={showLine}>
                {m.best === m.san ? 'Show the line' : `Show ${m.best} and the line`}</button>}
              {line && (
                <div className="cr-line">
                  <span className="small">{line.sans.map((s, i) => <button key={i} type="button" className={`plain small${line.at === i + 1 ? ' on' : ''}`}
                    onClick={() => setLine({ ...line, at: i + 1 })}>{s}</button>)}</span>
                  <span className="button-row">
                    <button type="button" className="secondary small" disabled={line.at <= 1} onClick={() => setLine({ ...line, at: line.at - 1 })} aria-label="Back in the line">◀</button>
                    <button type="button" className="secondary small" disabled={line.at >= line.fens.length - 1} onClick={() => setLine({ ...line, at: line.at + 1 })} aria-label="Forward in the line">▶</button>
                    <button type="button" className="plain small" onClick={() => setLine(null)}>Back to the game</button>
                  </span>
                </div>
              )}
            </div>
          ) : <div className="card cr-move"><p className="small">Step through the game, tap a move, or jump to the key moments.</p></div>}
          <div className="button-row cr-actions">
            {keyMoments.length > 0 && <button type="button" className="secondary small" onClick={() => go(nextKey)}>Next key moment →</button>}
            {myBad.length > 0 && <button type="button" className="primary small" onClick={() => setRetry({ at: 0, result: null })}>
              Retry your mistakes ({myBad.length})</button>}
          </div>
          <ol className="chess-moves cr-moves" aria-label="Moves">
            {moves.reduce((pairs, x, i) => (i % 2 ? pairs[pairs.length - 1].push(x) : pairs.push([x]), pairs), []).map((pair, n) => (
              <li key={n}>
                <span className="muted">{n + 1}.</span>
                {pair.map((x) => (
                  <button key={x.ply} type="button" className={`plain cr-${x.kind}${x.ply === ply ? ' on' : ''}`} onClick={() => go(x.ply)}
                    title={KINDS[x.kind].label}>
                    {x.san}{SHOWN.has(x.kind) && <span className="cr-sym" aria-label={KINDS[x.kind].label}>{KINDS[x.kind].sym}</span>}
                  </button>
                ))}
              </li>
            ))}
          </ol>
          <p className="muted small">{review.engine}, depth {review.depth}. <button type="button" className="plain small" onClick={onAgain}>Review again</button></p>
        </div>
      </div>
    </div>
  )
}

// The opening, and where the game left known theory: "instead of going there, do this".
function OpeningNote({ summary, mine, onJump }) {
  const d = summary.deviation
  const yours = d && d.colour === mine
  return (
    <div className="card cr-opening">
      <p><span className="cr-opening-label">Opening</span> <strong>{summary.opening.name}</strong> <span className="muted small">{summary.opening.eco}</span></p>
      {d && (
        <p className="small">
          {yours ? 'You' : 'Your opponent'} left the book at <button type="button" className="link-title inline" onClick={() => onJump(d.ply)}>
            {moveNo(d.ply)} {d.played}</button>.
          {d.theory.length > 0 && <> Theory plays {d.theory.slice(0, 3).map((t, i) => (
            <span key={t.san}>{i ? ' or ' : ' '}<strong>{moveNo(d.ply)} {t.san}</strong>{t.name && <span className="muted"> ({t.name})</span>}</span>))}.</>}
          {d.best && <> The engine liked <strong>{d.best}</strong>.</>}
          {yours && d.theory[0] && <> Next time in this position, play <strong>{d.theory[0].san}</strong> instead of {d.played}.</>}
        </p>
      )}
    </div>
  )
}

// White's winning chance through the game: white above, dark below, tap / drag / arrow keys to move through it.
// Dots mark the brilliant, great and bad moves (with their symbol in the readout).
function EvalGraph({ wins, moves, ply, onPick }) {
  const ref = useRef(null)
  const [hover, setHover] = useState(null)
  const n = wins.length - 1
  const x = (i) => (n ? (i / n) * 100 : 0)
  const y = (w) => 100 - w
  const area = `M0,100 ${wins.map((w, i) => `L${x(i)},${y(w)}`).join(' ')} L100,100 Z`
  const at = (e) => {
    const r = ref.current.getBoundingClientRect()
    return Math.max(0, Math.min(n, Math.round(((e.clientX - r.left) / r.width) * n)))
  }
  const shown = hover ?? ply
  const hm = shown ? moves[shown - 1] : null
  return (
    <div className="cr-graph-wrap">
      <div ref={ref} className="cr-graph" role="slider" tabIndex={0} aria-label="Who was winning, move by move" aria-valuemin={0}
        aria-valuemax={n} aria-valuenow={ply} aria-valuetext={hm ? `${moveNo(shown)} ${hm.san}: White ${pct(wins[shown])}` : 'Start'}
        onPointerMove={(e) => setHover(at(e))} onPointerLeave={() => setHover(null)} onClick={(e) => onPick(at(e))}
        onKeyDown={(e) => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.stopPropagation(); e.preventDefault(); onPick(ply + (e.key === 'ArrowLeft' ? -1 : 1)) } }}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <rect x="0" y="0" width="100" height="100" className="cr-graph-black" />
          <path d={area} className="cr-graph-white" />
          <line x1="0" y1="50" x2="100" y2="50" className="cr-graph-mid" vectorEffect="non-scaling-stroke" />
          <line x1={x(shown)} y1="0" x2={x(shown)} y2="100" className="cr-graph-cursor" vectorEffect="non-scaling-stroke" />
        </svg>
        {moves.map((m) => SHOWN.has(m.kind) && (
          <span key={m.ply} className={`cr-dot cr-${m.kind}`} style={{ left: `${x(m.ply)}%`, top: `${y(m.win_white)}%` }} aria-hidden="true" />
        ))}
      </div>
      <p className="muted small cr-graph-read">{hm ? <>{moveNo(shown)} {hm.san}{SHOWN.has(hm.kind) && ` ${KINDS[hm.kind].sym} ${KINDS[hm.kind].label}`} · White {pct(wins[shown])} · {evalText(hm.eval)}</> : 'Start: tap the graph to jump to a move'}</p>
    </div>
  )
}

// "Retry your mistakes": your bad moves one by one - find the better move on the board.
function Retry({ game, moves, retry, setRetry }) {
  const m = moves[retry.at]
  const done = retry.at >= moves.length
  const [tries, setTries] = useState(0)
  const [result, setResult] = useState(null)        // 'right' | 'wrong' | 'shown'
  useEffect(() => { setTries(0); setResult(null) }, [retry.at])
  if (done) {
    return (
      <div className="card cr-retry">
        <p><strong>That's all {moves.length}.</strong> {retry.right ?? 0} found on the first try.</p>
        <button type="button" className="primary" onClick={() => setRetry(null)}>Back to the review</button>
      </div>
    )
  }
  const next = (firstTry) => setRetry({ ...retry, at: retry.at + 1, right: (retry.right ?? 0) + (firstTry ? 1 : 0) })
  return (
    <div className="cr-retry">
      <div className="section-head">
        <h4 className="section-title">Retry your mistakes · {retry.at + 1} of {moves.length}</h4>
        <button type="button" className="plain small" onClick={() => setRetry(null)}>Back to the review</button>
      </div>
      <p className="small">Move {moveNo(m.ply)} - you played <strong>{m.san}</strong> ({KINDS[m.kind].label.toLowerCase()}). Find a better move for {m.colour}.</p>
      <PlayBoard fen={m.fen_before} orientation={game.colour} label={`Find a better move than ${m.san}`}
        arrows={result === 'shown' || result === 'right' ? [{ from: m.best_uci.slice(0, 2), to: m.best_uci.slice(2, 4), colour: 'best' }] : []}
        onMove={result === 'right' || result === 'shown' ? undefined : (mv) => {
          setTries(tries + 1)
          setResult(mv.uci === m.best_uci ? 'right' : 'wrong')
        }} />
      <div aria-live="polite">
        {result === 'right' && <p className="alert ok small">Yes - {m.best}! {m.best_line.length > 1 && `The line: ${m.best_line.slice(0, 5).join(' ')}.`}</p>}
        {result === 'wrong' && <p className="alert low small">Not that one. Try again, or see the answer.</p>}
        {result === 'shown' && <p className="small">The engine's move: <strong>{m.best}</strong>{m.best_line.length > 1 && <>, then {m.best_line.slice(1, 5).join(' ')}</>}.</p>}
      </div>
      <div className="button-row">
        {(result === 'right' || result === 'shown') ? <button type="button" className="primary" onClick={() => next(result === 'right' && tries === 1)}>Next</button>
          : <button type="button" className="secondary" onClick={() => setResult('shown')}>Show me</button>}
        <button type="button" className="plain" onClick={() => next(false)}>Skip</button>
      </div>
    </div>
  )
}

// The Dashboard's card: what your reviewed games add up to.
export function ReviewsSummary() {
  const { refreshKey, openPanel } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => { api.chessReviews().then(setData).catch(() => setData(null)) }, [refreshKey])
  if (!data?.reviewed) return null
  const worst = [...data.games].sort((a, b) => (a.accuracy ?? 100) - (b.accuracy ?? 100))[0]
  return (
    <section className="card cr-summary">
      <h3 className="section-title">From {data.reviewed} reviewed game{data.reviewed === 1 ? '' : 's'}</h3>
      <div className="stat-grid">
        <div><span>Your accuracy</span><strong>{data.accuracy ?? '–'}%</strong></div>
        <div><span>Blunders a game</span><strong>{(data.kinds.blunder / data.reviewed).toFixed(1)}</strong>
          <small className="muted">{data.kinds.mistake + data.kinds.miss} mistakes and misses in all</small></div>
        <div><span>Brilliant / great</span><strong>{data.kinds.brilliant} / {data.kinds.great}</strong></div>
      </div>
      <p className="muted small">By phase: {Object.entries(data.phases).filter(([, v]) => v != null).map(([k, v]) => `${k} ${v}%`).join(' · ')}</p>
      {data.openings.length > 0 && (
        <ul className="list compact">
          {data.openings.slice(0, 5).map((o) => (
            <li key={o.opening} className="cr-summary-row"><span className="grow">{o.opening}</span>
              <span className="muted small">{o.games} game{o.games === 1 ? '' : 's'} · {o.accuracy ?? '–'}% · {o.blunders} blunder{o.blunders === 1 ? '' : 's'}</span></li>
          ))}
        </ul>
      )}
      {worst && <button type="button" className="plain small" onClick={() => openPanel('chessgame', { id: worst.game_id })}>
        Your least accurate reviewed game: vs {worst.opp_name} ({worst.accuracy}%) →</button>}
    </section>
  )
}
