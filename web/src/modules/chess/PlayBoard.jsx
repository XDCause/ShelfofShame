import { useEffect, useMemo, useRef, useState } from 'react'

// A chess board for one position that you can play on: tap (or click) a piece, then where it goes - the legal moves
// light up (chess.js, loaded with the board). Used by the game review ("Retry": find the better move) and the opening
// trainer. Arrows (best move, theory) and coloured squares (a move's from / to, a mark on a square) are drawn over it.
//   fen          the position
//   orientation  'white' | 'black' (whose side is at the bottom)
//   onMove       (move) => void: {san, uci, from, to, fen} after a legal move; leave it out for a board to look at
//   arrows       [{from, to, colour}]  (colour: 'best' | 'theory' | 'played' | 'bad')
//   marks        {square: 'from' | 'to' | 'good' | 'bad' | 'hint'}
//   badge        {square, kind, label}: a move's class shown on its square (the review's icons)
//   evalBar      a number 0-100: White's win chance, drawn as a bar beside the board
//   label        what the board shows, for screen readers

export const PIECE = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' }
const FILES = 'abcdefgh'
const ARROW_COLOUR = { best: 'var(--ok)', theory: 'var(--teal)', played: 'var(--muted)', bad: 'var(--out)' }

const centre = (sq, flipped) => {
  const f = FILES.indexOf(sq[0])
  const r = Number(sq[1])
  const x = flipped ? 7 - f : f
  const y = flipped ? r - 1 : 8 - r
  return [x * 12.5 + 6.25, y * 12.5 + 6.25]
}

export function useChessJs() {
  const [Chess, setChess] = useState(null)
  useEffect(() => { import('chess.js').then((m) => setChess(() => m.Chess)) }, [])
  return Chess
}

export default function PlayBoard({ fen, orientation = 'white', onMove, arrows = [], marks = {}, badge = null, evalBar = null, label }) {
  const Chess = useChessJs()
  const [picked, setPicked] = useState(null)
  const game = useMemo(() => {
    if (!Chess) return null
    try { return new Chess(fen) } catch { return null }
  }, [Chess, fen])
  useEffect(() => setPicked(null), [fen])
  const boardRef = useRef(null)
  if (!game) return <div className="chess-board pb-board" aria-busy="true" />
  const flipped = orientation === 'black'
  const grid = game.board()
  const rows = flipped ? [...grid].reverse().map((row) => [...row].reverse()) : grid
  const targets = picked ? new Map(game.moves({ square: picked, verbose: true }).map((m) => [m.to, m])) : new Map()
  const tap = (square) => {
    if (!onMove) return
    if (picked && targets.has(square)) {
      const options = game.moves({ square: picked, verbose: true }).filter((m) => m.to === square)
      const m = options.find((o) => !o.promotion || o.promotion === 'q') ?? options[0]       // (promote to a queen)
      const next = new Chess(fen)
      const done = next.move({ from: m.from, to: m.to, promotion: m.promotion })
      setPicked(null)
      onMove({ san: done.san, uci: `${done.from}${done.to}${done.promotion ?? ''}`, from: done.from, to: done.to, fen: next.fen() })
      return
    }
    const piece = game.get(square)
    setPicked(piece && piece.color === game.turn() && picked !== square ? square : null)
  }
  return (
    <div className={`pb-wrap${evalBar != null ? ' with-bar' : ''}`}>
      {evalBar != null && (
        <div className={`pb-eval${flipped ? ' flipped' : ''}`} role="meter" aria-label="Who's winning (White's chance)"
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(evalBar)}>
          <span className="pb-eval-white" style={{ height: `${evalBar}%` }} />
        </div>
      )}
      <div className="chess-board pb-board" ref={boardRef} role={onMove ? 'grid' : 'img'} aria-label={label ?? 'Chess board'}>
        {rows.map((row, r) => row.map((sq, f) => {
          const rank = flipped ? r + 1 : 8 - r
          const file = FILES[flipped ? 7 - f : f]
          const name = `${file}${rank}`
          const dark = (FILES.indexOf(file) + rank) % 2 === 1
          const mark = marks[name]
          const cls = `sq ${dark ? 'dark' : 'light'}${mark ? ` pb-${mark}` : ''}${picked === name ? ' pb-picked' : ''}${targets.has(name) ? ' pb-target' : ''}`
          const inner = (
            <>
              {sq && <span className={`pc ${sq.color === 'w' ? 'w' : 'b'}`}>{PIECE[sq.type]}</span>}
              {f === 0 && <span className="coord rank">{rank}</span>}
              {r === 7 && <span className="coord file">{file}</span>}
              {badge?.square === name && <span className={`pb-badge cr-${badge.kind}`} aria-hidden="true">{badge.label}</span>}
            </>
          )
          return onMove ? (
            <button key={name} type="button" className={cls} onClick={() => tap(name)}
              aria-label={`${name}${sq ? ` ${sq.color === 'w' ? 'white' : 'black'} ${{ k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' }[sq.type]}` : ''}`}>
              {inner}
            </button>
          ) : <span key={name} className={cls}>{inner}</span>
        }))}
        {arrows.length > 0 && (
          <svg className="pb-arrows" viewBox="0 0 100 100" aria-hidden="true">
            <defs>
              {Object.entries(ARROW_COLOUR).map(([k, c]) => (
                <marker key={k} id={`pb-head-${k}`} viewBox="0 0 10 10" refX="5" refY="5" markerWidth="3" markerHeight="3" orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" fill={c} />
                </marker>
              ))}
            </defs>
            {arrows.map((a) => {
              const [x1, y1] = centre(a.from, flipped)
              const [x2, y2] = centre(a.to, flipped)
              const len = Math.hypot(x2 - x1, y2 - y1)
              const k = (len - 3.5) / len
              return <line key={`${a.from}${a.to}${a.colour}`} x1={x1} y1={y1} x2={x1 + (x2 - x1) * k} y2={y1 + (y2 - y1) * k}
                stroke={ARROW_COLOUR[a.colour] ?? ARROW_COLOUR.best} strokeWidth="2.2" strokeLinecap="round" opacity="0.85"
                markerEnd={`url(#pb-head-${a.colour in ARROW_COLOUR ? a.colour : 'best'})`} />
            })}
          </svg>
        )}
      </div>
    </div>
  )
}
