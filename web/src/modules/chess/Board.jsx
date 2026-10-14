import { useEffect, useMemo, useState } from 'react'

// A game's moves on a board: step through them (buttons, ← / → keys, or tap a move), from your side
// (Black at the bottom when you played Black). The moves are read with chess.js (loaded only when
// a game is opened); the board is drawn here - 64 squares and the pieces as chess symbols.

const PIECE = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' }
const FILES = 'abcdefgh'

// Every position of the game: [{board, move}] - board = chess.js's 8x8 (rank 8 first), move = what
// led to it (from / to / san), or null for the start.
async function positionsOf(pgn) {
  const { Chess } = await import('chess.js')
  const game = new Chess()
  game.loadPgn(pgn)
  const start = game.getHeaders().FEN
  const replay = start ? new Chess(start) : new Chess()
  const out = [{ board: replay.board(), move: null }]
  for (const m of game.history({ verbose: true })) {
    replay.move(m.san)
    out.push({ board: replay.board(), move: { from: m.from, to: m.to, san: m.san } })
  }
  return out
}

export default function Board({ pgn, colour = 'white' }) {
  const [positions, setPositions] = useState(null)
  const [error, setError] = useState('')
  const [ply, setPly] = useState(0)
  useEffect(() => {
    let live = true
    setPositions(null)
    setError('')
    positionsOf(pgn).then((p) => { if (live) { setPositions(p); setPly(p.length - 1) } })
      .catch(() => live && setError("These moves couldn't be read."))
    return () => { live = false }
  }, [pgn])
  const last = positions ? positions.length - 1 : 0
  useEffect(() => {
    const keys = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      if (e.key === 'ArrowLeft') setPly((p) => Math.max(0, p - 1))
      else if (e.key === 'ArrowRight') setPly((p) => Math.min(last, p + 1))
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', keys)
    return () => window.removeEventListener('keydown', keys)
  }, [last])
  const moves = useMemo(() => (positions ?? []).slice(1).map((p) => p.move.san), [positions])

  if (error) return <p className="muted small">{error}</p>
  if (!positions) return <p className="muted small">Setting up the board...</p>
  const { board, move } = positions[ply]
  const flipped = colour === 'black'
  const ranks = flipped ? [...board].reverse().map((row) => [...row].reverse()) : board
  return (
    <div className="chess-replay">
      <div className="chess-board" role="img" aria-label={move ? `After ${Math.ceil(ply / 2)}${ply % 2 ? '.' : '...'} ${move.san}` : 'Starting position'}>
        {ranks.map((row, r) => row.map((sq, f) => {
          const rank = flipped ? r + 1 : 8 - r
          const file = FILES[flipped ? 7 - f : f]
          const name = `${file}${rank}`
          const dark = (FILES.indexOf(file) + rank) % 2 === 1     // a1 (0 + 1) is dark
          const moved = move && (move.from === name || move.to === name)
          return (
            <span key={name} className={`sq ${dark ? 'dark' : 'light'}${moved ? ' moved' : ''}`}>
              {sq && <span className={`pc ${sq.color === 'w' ? 'w' : 'b'}`}>{PIECE[sq.type]}</span>}
              {f === 0 && <span className="coord rank">{rank}</span>}
              {r === 7 && <span className="coord file">{file}</span>}
            </span>
          )
        }))}
      </div>
      <div className="chess-controls">
        <button type="button" className="secondary" onClick={() => setPly(0)} disabled={ply === 0} aria-label="Start">⏮</button>
        <button type="button" className="secondary" onClick={() => setPly(ply - 1)} disabled={ply === 0} aria-label="Back one move">◀</button>
        <span className="muted small chess-ply">{ply === 0 ? 'Start' : `${Math.ceil(ply / 2)}${ply % 2 ? '.' : '...'} ${move.san}`}</span>
        <button type="button" className="secondary" onClick={() => setPly(ply + 1)} disabled={ply === last} aria-label="Forward one move">▶</button>
        <button type="button" className="secondary" onClick={() => setPly(last)} disabled={ply === last} aria-label="End">⏭</button>
      </div>
      <ol className="chess-moves" aria-label="Moves">
        {moves.reduce((pairs, san, i) => (i % 2 ? pairs[pairs.length - 1].push([san, i + 1]) : pairs.push([[san, i + 1]]), pairs), [])
          .map((pair, n) => (
            <li key={n}>
              <span className="muted">{n + 1}.</span>
              {pair.map(([san, p]) => (
                <button key={p} type="button" className={p === ply ? 'plain on' : 'plain'} onClick={() => setPly(p)}>{san}</button>
              ))}
            </li>
          ))}
      </ol>
    </div>
  )
}
