import { useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { BookIcon } from '../../components/icons.jsx'
import ScanButton from '../../components/ScanButton.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// Pieces the reading pages share: covers, stars, shelves, progress, adding a book, the goal and
// the Goodreads import.

export const SHELVES = [['want', 'Want to read'], ['reading', 'Reading'], ['finished', 'Finished'], ['dnf', "Didn't finish"]]
const shelfName = (s) => Object.fromEntries(SHELVES)[s] ?? s
const SHELF_TONE = { want: 'tint', reading: 'low', finished: 'ok', dnf: 'out' }

export const useReadingSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`reading-summary-${refreshKey}`, () => api.readingSummary())
}

// The cover from Open Library, or a plain coloured "book" with the title on it.
export function BookCover({ book: b, className = 'book-cover' }) {
  const [failed, setFailed] = useState(false)
  if (b.cover_url && !failed) {
    return <img className={className} src={b.cover_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
  }
  const hue = [...(b.title ?? '')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7)
  return (
    <span className={`${className} cover-blank`} style={{ '--cover-hue': hue }} aria-hidden="true">
      <BookIcon size={18} /><span>{b.title}</span>
    </span>
  )
}

export function ShelfPill({ status }) {
  return <span className={`pill ${SHELF_TONE[status]}`}>{shelfName(status)}</span>
}

// 3.5 -> "3½"
export const starsText = (v) => `${Math.floor(v)}${v % 1 ? '½' : ''}`.replace(/^0½/, '½')

// ★★★½☆ - shown, or (with onChange) tapped to rate: the left half of a star gives a half, the right
// half a whole one; tapping your current rating clears it. (Keyboard: Enter gives whole stars, the
// arrow keys step by halves.)
export function Stars({ value, onChange, size = '' }) {
  const v = value == null ? 0 : Number(value)
  if (!onChange) {
    return v ? (
      <span className={`stars ${size}`} role="img" aria-label={`${v} out of 5 stars`}>
        <span className="stars-off" aria-hidden="true">★★★★★</span>
        <span className="stars-on" aria-hidden="true" style={{ width: `${(v / 5) * 100}%` }}>★★★★★</span>
      </span>
    ) : null
  }
  const pick = (n, e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const half = e.detail > 0 && e.clientX < box.left + box.width * 0.4    // left 40% = a half; detail 0 = keyboard
    const next = half ? n - 0.5 : n
    onChange(next === v ? null : next)
  }
  const keys = (e) => {
    const step = { ArrowRight: 0.5, ArrowUp: 0.5, ArrowLeft: -0.5, ArrowDown: -0.5 }[e.key]
    if (!step) return
    e.preventDefault()
    const next = Math.min(5, Math.max(0, v + step))
    onChange(next || null)
  }
  return (
    <span className="stars-input" role="group" aria-label={`Your rating${v ? `: ${v} out of 5` : ''}`} onKeyDown={keys}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" className={v >= n ? 'on' : v === n - 0.5 ? 'half' : ''} aria-pressed={v === n}
          aria-label={`${n} star${n === 1 ? '' : 's'}`} onClick={(e) => pick(n, e)}>★</button>
      ))}
      {v > 0 && <span className="stars-value">{starsText(v)}</span>}
    </span>
  )
}

// "p. 120 of 496 · 24%" with a bar.
export function Progress({ book: b }) {
  if (b.status === 'finished') return null
  return (
    <span className="book-progress">
      <span className="item-meta">
        {b.current_page != null ? `p. ${b.current_page}${b.pages ? ` of ${b.pages}` : ''}` : b.pages ? `${b.pages} pages` : 'Not started'}
        {b.percent != null && b.current_page != null && ` · ${b.percent}%`}
      </span>
      {b.percent != null && <span className="fill-bar tint"><span style={{ width: `${b.percent}%` }} /></span>}
    </span>
  )
}

// "I'm on page __": logs the pages since last time. At the last page it offers Finished.
export function ProgressForm({ book: b, onSaved, compact = false }) {
  const { changed, showToast } = useApp()
  const [page, setPage] = useState('')
  const [minutes, setMinutes] = useState('')
  const [end, setEnd] = useState(false)
  const [error, setError] = useState('')
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const r = await api.bookProgress(b.book_id, { page: Number(page), ...(minutes && { minutes: Number(minutes) }) })
      const read = r.log[0]?.pages ?? 0
      setPage('')
      setMinutes('')
      setEnd(r.at_the_end)
      showToast(`${b.title}: ${read} page${read === 1 ? '' : 's'} read`)
      onSaved?.(r)
      if (!r.at_the_end) changed()
    } catch (err) {
      setError(err.message)
    }
  }
  const finish = async () => {
    const r = await api.updateBook(b.book_id, { status: 'finished' })
    setEnd(false)
    showToast(`Finished ${b.title} 🎉`)
    onSaved?.(r)
    changed()
  }
  if (end) {
    return (
      <div className="progress-end">
        <span>That's the last page!</span>
        <button type="button" className="primary small" onClick={finish}>Mark as finished</button>
        <button type="button" className="plain small" onClick={() => { setEnd(false); changed() }}>Not yet</button>
      </div>
    )
  }
  return (
    <form className={compact ? 'progress-form compact' : 'progress-form'} onSubmit={save}>
      <label>{compact ? 'Page' : "I'm on page"}
        <input type="number" min="0" max={b.pages ?? undefined} value={page} onChange={(e) => setPage(e.target.value)} required
          placeholder={b.current_page != null ? String(b.current_page) : '0'} aria-label={`Page you're on in ${b.title}`} /></label>
      {!compact && <label>Minutes (optional)<input type="number" min="1" max="1440" value={minutes} onChange={(e) => setMinutes(e.target.value)} /></label>}
      <button type="submit" className="primary small">Update</button>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}

// Adding a book: search Open Library by title / author, scan or type the ISBN, or type it in.
export function AddBookPanel({ onClose, status: startStatus = 'want' }) {
  const { changed, openPanel, showToast } = useApp()
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(startStatus)
  const [manual, setManual] = useState(false)
  const asked = useRef(0)

  const search = async (text) => {
    const n = ++asked.current
    setBusy(true)
    setError('')
    try {
      const r = await api.readingLookup(text)
      if (n === asked.current) setResults(r.results)
      return r
    } catch (e) {
      if (n === asked.current) setError(e.message)
      throw e
    } finally {
      if (n === asked.current) setBusy(false)
    }
  }
  useEffect(() => {
    if (q.trim().length < 3) return undefined
    const t = setTimeout(() => search(q.trim()).catch(() => {}), 450)
    return () => clearTimeout(t)
  }, [q])

  const scanned = async (barcode) => {
    setQ(barcode)
    const r = await search(barcode)
    if (!r.isbn) throw new Error("That barcode isn't a book's ISBN (it starts 978 or 979).")
    if (!r.results.length) {
      setManual(true)
      throw new Error("Open Library doesn't know that ISBN - type the book in below.")
    }
  }
  const add = async (book) => {
    try {
      const saved = await api.addBook({ ...book, status })
      changed()
      showToast(`Added ${saved.title}`)
      onClose()
      openPanel('book', { id: saved.book_id })
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <Drawer title="Add a book" onClose={onClose} wide>
      <section className="panel-section">
        <div className="segmented" role="group" aria-label="Shelf">
          {SHELVES.slice(0, 3).map(([id, label]) => <button key={id} type="button" aria-pressed={status === id} onClick={() => setStatus(id)}>{label}</button>)}
        </div>
        <div className="lookup-row">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} autoFocus
            placeholder="Title, author or ISBN" aria-label="Find a book" />
          <ScanButton onBarcode={scanned} label="Scan ISBN" />
        </div>
        {error && <p className="alert error small">{error}</p>}
        {busy && <p className="muted small">Looking on Open Library...</p>}
      </section>
      {results && (
        <ul className="list plain-list book-results">
          {results.length === 0 && !busy && <li className="muted small">Nothing found. Try fewer words, or type it in.</li>}
          {results.map((r, i) => (
            <li key={`${r.ol_work}-${i}`}>
              <div className="row-button static">
                <BookCover book={r} className="book-cover small" />
                <span className="grow">
                  <span className="item-title">{r.title}</span>
                  <span className="item-meta">{[r.author, r.year, r.pages && `${r.pages} pages`].filter(Boolean).join(' · ')}</span>
                  {r.genres.length > 0 && <span className="item-meta">{r.genres.join(', ')}</span>}
                </span>
                {r.book_id ? (
                  <button type="button" className="secondary small" onClick={() => { onClose(); openPanel('book', { id: r.book_id }) }}>
                    {shelfName(r.my_status)} ›</button>
                ) : <button type="button" className="primary small" onClick={() => add(r)}>Add</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <section className="panel-section">
        {manual ? <ManualBook onAdd={add} /> : (
          <button type="button" className="plain small" onClick={() => setManual(true)}>Not there? Type it in</button>
        )}
      </section>
    </Drawer>
  )
}

function ManualBook({ onAdd }) {
  const [f, setF] = useState({ title: '', author: '', pages: '', isbn: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <form className="book-form" onSubmit={(e) => { e.preventDefault(); onAdd({ ...f, pages: f.pages ? Number(f.pages) : null }) }}>
      <label>Title<input value={f.title} onChange={set('title')} required /></label>
      <label>Author<input value={f.author} onChange={set('author')} /></label>
      <label>Pages<input type="number" min="1" value={f.pages} onChange={set('pages')} /></label>
      <label>ISBN<input value={f.isbn} onChange={set('isbn')} inputMode="numeric" /></label>
      <button type="submit" className="primary">Add book</button>
    </form>
  )
}

// This year's goal: books finished, a bar with where you'd be reading steadily, ahead / behind.
export function GoalCard({ summary: s }) {
  const { changed } = useApp()
  const g = s.goal
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(g.goal ?? 12))
  const [error, setError] = useState('')
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.setReadingGoal(Number(value))
      setEditing(false)
      changed()
    } catch (err) {
      setError(err.message)
    }
  }
  const form = (
    <form className="goal-edit" onSubmit={save}>
      <label className="small">Books in {g.year} <input type="number" min="1" max="1000" value={value}
        onChange={(e) => setValue(e.target.value)} aria-label="Books to read this year" /></label>
      <button type="submit" className="primary small">Save</button>
      {g.goal && <button type="button" className="plain small" onClick={() => setEditing(false)}>Cancel</button>}
    </form>
  )
  if (!g.goal) {
    return (
      <section className="card goal-card" aria-label="Reading goal">
        <span className="goal-label">{g.year} reading goal</span>
        <p className="muted small">{g.finished} book{g.finished === 1 ? '' : 's'} finished so far this year. How many are you aiming for?</p>
        {form}
        {error && <p className="alert error small">{error}</p>}
      </section>
    )
  }
  const pace = Math.min(100, (100 * g.on_pace) / g.goal)
  const ahead = Math.round(g.ahead_by)
  return (
    <section className="card goal-card" aria-label="Reading goal">
      <div className="goal-head">
        <span>
          <span className="goal-label">{g.year} reading goal</span>
          <strong className="goal-percent">{g.finished} <span className="goal-of">of {g.goal} books</span></strong>
        </span>
        {editing ? form : (
          <button type="button" className="plain small" onClick={() => { setValue(String(g.goal)); setEditing(true) }}>Goal {g.goal} · change</button>
        )}
      </div>
      <div className="goal-bar" role="img" aria-label={`${g.finished} of ${g.goal} books; on pace would be ${Math.round(g.on_pace)}`}>
        <span className="goal-fill" style={{ width: `${Math.min(100, g.percent)}%` }} />
        {!g.reached && <span className="goal-marker" style={{ left: `${pace}%` }}><span>On pace {Math.round(g.on_pace)}</span></span>}
      </div>
      <p className="goal-detail">
        {g.reached ? <strong className="ok-text">Goal reached! 🎉</strong>
          : ahead > 0 ? <><strong className="ok-text">{ahead} book{ahead === 1 ? '' : 's'} ahead</strong> of pace</>
            : ahead < 0 ? <><strong>{-ahead} book{ahead === -1 ? '' : 's'} behind</strong> pace</>
              : <strong>Right on pace</strong>}
        {!g.reached && ` · ${g.left} to go in ${g.days_left} days`}
      </p>
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

// Goodreads: My Books → Import and export → Export library, then choose the CSV here. Covers are
// looked up afterwards, about one a second (the progress shows here).
export function GoodreadsImport() {
  const { changed } = useApp()
  const [result, setResult] = useState(null)
  const [covers, setCovers] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!covers?.running) return undefined
    const t = setInterval(() => api.coverStatus().then((c) => { setCovers(c); if (!c.running) changed() }).catch(() => {}), 2000)
    return () => clearInterval(t)
  }, [covers?.running, changed])
  const pick = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const r = await api.importGoodreads(file)
      setResult(r)
      setCovers({ ...r.covers, running: true })
      changed()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="goodreads-import">
      <p className="small muted">On Goodreads: <strong>My Books → Import and export → Export library</strong>, then choose the
        file here. Shelves, ratings, dates read and reviews come across; importing again updates them.</p>
      <label className="button secondary">{busy ? 'Importing...' : 'Choose goodreads_library_export.csv'}
        <input type="file" accept=".csv,text/csv" onChange={pick} hidden disabled={busy} /></label>
      {result && <p className="alert ok small">{result.added} book{result.added === 1 ? '' : 's'} added, {result.updated} updated.</p>}
      {covers && (covers.running ? (
        <p className="muted small">Finding covers on Open Library... {covers.done} of {covers.total}</p>
      ) : covers.total > 0 && <p className="muted small">Covers found for {covers.found} of {covers.total} books.{covers.error && ` (${covers.error})`}</p>)}
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}
