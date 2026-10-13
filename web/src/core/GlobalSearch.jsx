import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { BoxIcon, DiceIcon, GamepadIcon, JournalIcon, PlaneIcon, SearchIcon, ShoeIcon } from '../components/icons.jsx'
import { useApp } from './app-context.js'

const ICON = { model: PlaneIcon, supply: BoxIcon, page: JournalIcon, game: DiceIcon, gear: ShoeIcon, videogame: GamepadIcon }
const WHAT = { model: 'Kit', supply: 'Supply', page: 'Journal page', game: 'Board game', gear: 'Gear', videogame: 'Video game' }
const isMac = /Mac|iPhone|iPad/.test(navigator.platform)

// Search everything from the nav bar: kits, supplies, journal pages, board games and gear. Ctrl+K (⌘K) jumps here;
// arrows + Enter pick a result. On phones it's a button that opens the box.
export default function GlobalSearch() {
  const { openThing } = useApp()
  const input = useRef(null)
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)          // phones: the box is showing

  useEffect(() => {
    const key = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
        setTimeout(() => input.current?.focus())
      }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [])

  useEffect(() => {
    if (!q.trim()) { setResults([]); return }
    const wait = setTimeout(() => {
      api.mentionable(q.trim()).then((r) => { setResults(r); setActive(0) }).catch(() => setResults([]))
    }, 200)
    return () => clearTimeout(wait)
  }, [q])

  const close = () => { setQ(''); setResults([]); setOpen(false); input.current?.blur() }
  const pick = (r) => {
    close()
    openThing(r.kind, r.id)
  }

  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && results[active]) pick(results[active])
    else if (e.key === 'Escape') { e.stopPropagation(); close() }
  }

  return (
    <div className={open ? 'global-search open' : 'global-search'}>
      <button type="button" className="icon-btn search-toggle" aria-label="Search everything"
        onClick={() => { setOpen(true); setTimeout(() => input.current?.focus()) }}><SearchIcon /></button>
      <label className="search-box">
        <SearchIcon size={18} />
        <input ref={input} type="search" value={q} placeholder="Search kits, supplies, games, the journal..."
          aria-label="Search everything" onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
          onBlur={() => setTimeout(() => { setResults([]); if (!q) setOpen(false) }, 150)} />
        <kbd>{isMac ? '⌘K' : 'Ctrl K'}</kbd>
      </label>
      {results.length > 0 && (
        <ul className="search-results" role="listbox" aria-label="Search results">
          {results.map((r, i) => {
            const Icon = ICON[r.kind]
            return (
              <li key={`${r.kind}-${r.id}`} role="option" aria-selected={i === active}>
                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => pick(r)}
                  onMouseEnter={() => setActive(i)}>
                  <span className={`thumb thumb-icon ${r.kind}`}><Icon size={18} /></span>
                  <span className="grow">{r.label}</span>
                  <span className="muted small">{WHAT[r.kind]}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
