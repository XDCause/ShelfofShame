import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import Board from './Board.jsx'
import { SYMBOLS, TECHNIQUE, engineFor, sym } from './engine.js'

// The solving path: the whole logical solution of a puzzle as a list of steps (engine.solvePath - the same walk that
// grades it), to step through with the board showing each one: the area it looks at (amber), the cells it's about, the
// digit it places and the notes it rules out (crossed out in red). Opened from a finished game.
const digits = (s) => [...s].map((ch) => SYMBOLS.indexOf(ch))

export default function SolvePath({ record, onClose }) {
  const size = record.size ?? 9
  const eng = engineFor(size, record.variant)
  const path = useMemo(() => eng.solvePath(digits(record.puzzle)), [eng, record.puzzle])
  const given = useMemo(() => digits(record.puzzle).map(Boolean), [record.puzzle])
  const [at, setAt] = useState(0)
  const [showNotes, setShowNotes] = useState(true)
  const { steps } = path
  const step = steps[at]                                         // (none at the very end)
  const end = path.solved ? { values: digits(record.solution), cands: new Array(size * size).fill(0) } : path.stuck
  const shown = step ?? end
  const counts = useMemo(() => {
    const out = {}
    for (const s of steps) out[s.technique] = (out[s.technique] ?? 0) + 1
    return Object.entries(out)
  }, [steps])
  const go = (n) => setAt(Math.max(0, Math.min(steps.length, n)))

  const areas = new Set(step ? step.units.flatMap((u) => eng.UNITS[u]) : [])
  const cells = new Set(step ? [...step.cells, ...(step.place ? [step.place.cell] : [])] : [])
  const elim = new Set(step ? step.eliminate.map((e) => `${e.cell}:${e.digit}`) : [])
  const look = (i) => [areas.has(i) && 'hint-area', cells.has(i) && 'hint-cell', step?.eliminate.some((e) => e.cell === i) && 'hint-elim'].filter(Boolean)
  const what = (s) => (s.place ? `${eng.cellName(s.place.cell)} = ${sym(s.place.digit)}` : `rules out ${s.eliminate.length} note${s.eliminate.length === 1 ? '' : 's'}`)

  return (
    <section className={`page sudoku sdk-play${size === 16 ? ' giant' : ''}`}>
      <div className="sdk-layout">
        <div className="sdk-board-wrap">
          <Board size={size} variant={record.variant} values={shown.values} notes={showNotes ? shown.cands : new Array(size * size).fill(0)}
            given={given} sel={null} onSelect={() => {}} look={look} struck={(i, d) => elim.has(`${i}:${d}`)} label="The puzzle at this step of the solution" />
        </div>
        <div className="sdk-side sdk-path">
          <div className="section-head">
            <h2 className="home-card-title">The solving path</h2>
            <button type="button" className="plain small" onClick={onClose}>Back</button>
          </div>
          <p className="muted small">{path.solved ? `${steps.length} steps, from the clues to the answer.` : `${steps.length} steps, then it needs more than these techniques (chains or trial and error).`}
            {' '}{counts.map(([k, n]) => `${TECHNIQUE[k].name} ×${n}`).join(' · ')}</p>
          <div className="sdk-path-now card" aria-live="polite">
            {step ? (
              <>
                <p><strong>Step {at + 1} of {steps.length}: {step.name}</strong> <span className="muted small">{what(step)}</span></p>
                <p className="small">{step.text}</p>
                <Link className="button plain small" to={`/sudoku/learn#${step.technique}`}>What's a {step.name}?</Link>
              </>
            ) : <p className="small">{path.solved ? 'Solved: every cell is filled.' : 'Stuck here: none of the techniques in the app helps from this board.'}</p>}
          </div>
          <div className="sdk-path-controls">
            <button type="button" className="secondary" onClick={() => go(0)} disabled={at === 0} aria-label="First step">⏮</button>
            <button type="button" className="secondary" onClick={() => go(at - 1)} disabled={at === 0} aria-label="Previous step">◀</button>
            <input type="range" min="0" max={steps.length} value={at} aria-label="Step" onChange={(e) => go(Number(e.target.value))} />
            <button type="button" className="secondary" onClick={() => go(at + 1)} disabled={at >= steps.length} aria-label="Next step">▶</button>
            <button type="button" className="secondary" onClick={() => go(steps.length)} disabled={at >= steps.length} aria-label="Last step">⏭</button>
          </div>
          <label className="check small"><input type="checkbox" checked={showNotes} onChange={(e) => setShowNotes(e.target.checked)} /> Show every cell's candidates</label>
          <ol className="sdk-path-list small" aria-label="Steps">
            {steps.map((s, i) => (
              <li key={i}><button type="button" className={`plain small${i === at ? ' on' : ''}`} aria-current={i === at ? 'step' : undefined} onClick={() => setAt(i)}>
                {i + 1}. {s.name} <span className="muted">{what(s)}</span></button></li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  )
}
