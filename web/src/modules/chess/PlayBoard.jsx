import { useEffect, useMemo, useRef, useState } from 'react'

// A chess board for one position that you can play on: tap (or click) a piece, then where it goes - or drag it there
// (pointer events: mouse, finger or pen) - the legal moves light up (chess.js, loaded with the board). Used by the game review ("Retry": find the better move) and the opening
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
  // A drag: {from, x, y} (x / y: the pointer within the board, in px) once the pointer has moved a few px from where it
  // went down; until then it's a tap and the square's click handles it. justDragged swallows the click a drop can fire.
  const [drag, setDrag] = useState(null)
  const press = useRef(null)
  const justDragged = useRef(false)
  if (!game) return <div className="chess-board pb-board" aria-busy="true" />
  const flipped = orientation === 'black'
  const grid = game.board()
  const rows = flipped ? [...grid].reverse().map((row) => [...row].reverse()) : grid
  const targets = picked ? new Map(game.moves({ square: picked, verbose: true }).map((m) => [m.to, m])) : new Map()
  const play = (from, to) => {
    const options = game.moves({ square: from, verbose: true }).filter((m) => m.to === to)
    if (!options.length) return false
    const m = options.find((o) => !o.promotion || o.promotion === 'q') ?? options[0]       // (promote to a queen)
    const next = new Chess(fen)
    const done = next.move({ from: m.from, to: m.to, promotion: m.promotion })
    setPicked(null)
    onMove({ san: done.san, uci: `${done.from}${done.to}${done.promotion ?? ''}`, from: done.from, to: done.to, fen: next.fen() })
    return true
  }
  const tap = (square) => {
    if (!onMove) return
    if (justDragged.current) { justDragged.current = false; return }
    if (picked && targets.has(square)) { play(picked, square); return }
    const piece = game.get(square)
    setPicked(piece && piece.color === game.turn() && picked !== square ? square : null)
  }
  // The square under a point on the screen (null off the board).
  const squareAt = (clientX, clientY) => {
    const box = boardRef.current.getBoundingClientRect()
    const x = Math.floor(((clientX - box.left) / box.width) * 8)
    const y = Math.floor(((clientY - box.top) / box.height) * 8)
    if (x < 0 || x > 7 || y < 0 || y > 7) return null
    return `${FILES[flipped ? 7 - x : x]}${flipped ? y + 1 : 8 - y}`
  }
  const down = (e) => {
    justDragged.current = false
    if (!onMove || e.button !== 0) return
    const square = squareAt(e.clientX, e.clientY)
    const piece = square && game.get(square)
    press.current = piece && piece.color === game.turn() ? { from: square, x: e.clientX, y: e.clientY, id: e.pointerId } : null
  }
  const moveTo = (e) => {
    const p = press.current
    if (!p || e.pointerId !== p.id) return
    if (!p.dragging && Math.hypot(e.clientX - p.x, e.clientY - p.y) < 6) return
    if (!p.dragging) {
      p.dragging = true
      boardRef.current.setPointerCapture?.(e.pointerId)
      setPicked(p.from)
    }
    const box = boardRef.current.getBoundingClientRect()
    setDrag({ from: p.from, x: e.clientX - box.left, y: e.clientY - box.top })
  }
  const up = (e) => {
    const p = press.current
    press.current = null
    if (!p?.dragging) return
    setDrag(null)
    justDragged.current = true
    const to = squareAt(e.clientX, e.clientY)
    if (!(to && to !== p.from && play(p.from, to))) setPicked(null)
  }
  const cancel = () => { press.current = null; setDrag(null); setPicked(null) }
  return (
    <div className={`pb-wrap${evalBar != null ? ' with-bar' : ''}`}>
      {evalBar != null && (
        <div className={`pb-eval${flipped ? ' flipped' : ''}`} role="meter" aria-label="Who's winning (White's chance)"
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(evalBar)}>
          <span className="pb-eval-white" style={{ height: `${evalBar}%` }} />
        </div>
      )}
      <div className={`chess-board pb-board${onMove ? ' pb-playable' : ''}${drag ? ' pb-dragging' : ''}`} ref={boardRef}
        role={onMove ? 'grid' : 'img'} aria-label={label ?? 'Chess board'}
        onPointerDown={onMove ? down : undefined} onPointerMove={onMove ? moveTo : undefined}
        onPointerUp={onMove ? up : undefined} onPointerCancel={onMove ? cancel : undefined}>
        {rows.map((row, r) => row.map((sq, f) => {
          const rank = flipped ? r + 1 : 8 - r
          const file = FILES[flipped ? 7 - f : f]
          const name = `${file}${rank}`
          const dark = (FILES.indexOf(file) + rank) % 2 === 1
          const mark = marks[name]
          const cls = `sq ${dark ? 'dark' : 'light'}${mark ? ` pb-${mark}` : ''}${picked === name ? ' pb-picked' : ''}${targets.has(name) ? ' pb-target' : ''}`
          const inner = (
            <>
              {sq && <span className={`pc ${sq.color === 'w' ? 'w' : 'b'}${drag?.from === name ? ' pb-lifted' : ''}`}>{PIECE[sq.type]}</span>}
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
        {drag && (() => {
          const p = game.get(drag.from)
          return <span className={`pc ${p.color === 'w' ? 'w' : 'b'} pb-ghost`} aria-hidden="true"
            style={{ left: `${drag.x}px`, top: `${drag.y}px` }}>{PIECE[p.type]}</span>
        })()}
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
