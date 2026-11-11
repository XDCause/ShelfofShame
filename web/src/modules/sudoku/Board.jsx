import { bit, engineFor, sym } from './engine.js'

// The board (9 x 9 or 16 x 16): each cell a button (its digit, or its notes as a small grid). `look(c)` says how a cell
// looks (a list of class names); `struck(c, d)` marks a note a hint rules out. Thick lines between the boxes.
// Its size comes from its own width (a container), not the window's - so it stays square and its digits fit however
// the window is sized, with or without the sidebar.
export default function Board({ size = 9, variant = 'classic', values, notes, given, sel, onSelect, look = () => [], struck = () => false, label = 'Sudoku board',
  hidden = false, theme = 'classic' }) {
  const e = engineFor(size, variant)
  const ds = Array.from({ length: size }, (_, i) => i + 1)
  return (
    <div className={`sdk-board-box sdk-theme-${theme}`}>
      <div className={`sdk-board${hidden ? ' sdk-hidden' : ''}${size === 16 ? ' giant' : ''}`} role="grid" aria-label={label}
        style={{ '--n': size }}>
        {Array.from({ length: size }, (_, r) => (
          <div key={r} role="row" className="sdk-row">
            {Array.from({ length: size }, (_, c) => {
              const i = r * size + c
              const v = values[i]
              const cls = ['sdk-cell', given[i] ? 'given' : 'mine', sel === i && 'sel', c % e.B === e.B - 1 && c < size - 1 && 'edge-r',
                r % e.B === e.B - 1 && r < size - 1 && 'edge-b', (e.onDiag(i, 0) || e.onDiag(i, 1)) && 'diag', ...look(i)].filter(Boolean).join(' ')
              return (
                <button key={c} type="button" role="gridcell" className={cls} onClick={() => onSelect(i)} tabIndex={sel === i || (sel == null && i === 0) ? 0 : -1}
                  aria-selected={sel === i}
                  aria-label={`Row ${r + 1}, column ${c + 1}, box ${e.boxOf(i) + 1}: ${v ? `${sym(v)}${given[i] ? ' (clue)' : ''}` : notes[i] ? `notes ${ds.filter((d) => notes[i] & bit(d)).map(sym).join(' ')}` : 'empty'}`}>
                  {hidden ? null : v ? <span className="sdk-digit">{sym(v)}</span> : notes[i] ? (
                    <span className="sdk-notes" aria-hidden="true">
                      {ds.map((d) => <span key={d} className={struck(i, d) ? 'struck' : ''}>{notes[i] & bit(d) ? sym(d) : ''}</span>)}
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
