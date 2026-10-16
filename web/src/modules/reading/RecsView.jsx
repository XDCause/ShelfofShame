import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, timeAgo } from '../../api.js'
import { SparkleIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { BookCover, starsText } from './readingParts.jsx'

// "For you": books picked from Open Library (api/app/reading_recs.py) - more by the authors you
// rated 4★ or more, and well-rated books in the genres you read, from authors new to you. Each
// can go straight onto your want-to-read shelf, or be hidden for good.

// The suggestions, refreshed in the background when they're due (a week old, or your top authors /
// genres changed) - started once per visit, polled while it runs.
function useRecs() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const started = useRef(false)
  const load = useCallback(() => api.bookRecs().then(setData).catch((e) => setError(e.message)), [])
  const refresh = useCallback(() => {
    started.current = true
    setData((d) => d && { ...d, refresh: { ...d.refresh, running: true, done: 0, error: null } })
    api.refreshBookRecs().catch((e) => setError(e.message))
  }, [])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (data?.stale && !data.refresh.running && !started.current) refresh()
  }, [data, refresh])
  const running = data?.refresh.running
  useEffect(() => {
    if (!running) return undefined
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [running, load])
  return { data, setData, error, refresh, load }
}

export function RecsView() {
  const { data, setData, error, refresh, load } = useRecs()
  const { openPanel } = useApp()
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const r = data.refresh
  const drop = (work) => setData((d) => ({
    ...d, sections: d.sections.map((s) => ({ ...s, books: s.books.filter((b) => b.ol_work !== work) })).filter((s) => s.books.length),
  }))
  const bringBack = async () => { await api.bringBackBookRecs(); load() }
  if (!data.has_seeds) {
    return (
      <section className="page reading">
        <EmptyState Icon={SparkleIcon} title="Nothing to go on yet" action="+ Add a book" onAction={() => openPanel('addbook', { status: 'finished' })}>
          Rate the books you've finished (4★ and up counts) and add some you want to read - suggestions are picked from those.</EmptyState>
      </section>
    )
  }
  return (
    <section className="page reading recs">
      <div className="recs-head">
        <p className="muted small">
          Picked from <a href="https://openlibrary.org" target="_blank" rel="noreferrer">Open Library</a> using
          {data.seeds.authors.length > 0 && <> the authors you rated highest ({data.seeds.authors.map((a) => a.name).join(', ')})</>}
          {data.seeds.authors.length > 0 && data.seeds.genres.length > 0 && ' and'}
          {data.seeds.genres.length > 0 && <> the genres you read most ({data.seeds.genres.join(', ')})</>}.
          {data.refreshed_at && !r.running && <> Updated {timeAgo(data.refreshed_at)}.</>}
        </p>
        <button type="button" className="secondary small" onClick={refresh} disabled={r.running}>
          {r.running ? `Looking... ${r.done} of ${r.total || '?'}` : 'Refresh'}
        </button>
      </div>
      {r.error && <p className="alert error">{r.error} The suggestions below are from last time.</p>}
      {data.sections.length === 0 && (r.running
        ? <p className="muted loading">Asking Open Library for books you might like...</p>
        : <p className="empty card">No suggestions this time - rate a few more books, or press Refresh.</p>)}
      {data.sections.map((s) => (
        <section key={`${s.kind}:${s.reason}`} className="recs-section">
          <div className="recs-section-head">
            <h2 className="home-card-title">{s.kind === 'author' ? `More by ${s.reason}` : `Popular now in ${s.reason}`}</h2>
            <span className="muted small">
              {s.kind === 'author' ? `You gave ${s.seed} ${starsText(Number(s.seed_rating))}★` : 'Well rated on Open Library, by authors new to you'}
            </span>
          </div>
          <ul className="book-grid recs-grid">
            {s.books.map((b) => <li key={b.ol_work}><RecCard book={b} onGone={drop} /></li>)}
          </ul>
        </section>
      ))}
      {data.dismissed > 0 && (
        <p className="muted small">
          {data.dismissed} hidden as not interested · <button type="button" className="plain small" onClick={bringBack}>Bring them back</button>
        </p>
      )}
    </section>
  )
}

function RecCard({ book: b, onGone }) {
  const { changed, showToast, openPanel } = useApp()
  const [busy, setBusy] = useState(false)
  const want = async () => {
    setBusy(true)
    try {
      const book = await api.wantBookRec(b.ol_work)
      onGone(b.ol_work)
      changed()
      showToast(`Added to Want to read: ${b.title}`, { label: 'Open', run: () => openPanel('book', { id: book.book_id }) })
    } catch (e) {
      showToast(e.message)
      setBusy(false)
    }
  }
  const hide = async () => {
    setBusy(true)
    try {
      await api.dismissBookRec(b.ol_work)
      onGone(b.ol_work)
    } catch (e) {
      showToast(e.message)
      setBusy(false)
    }
  }
  return (
    <div className="book-card rec-card">
      <a href={`https://openlibrary.org/works/${b.ol_work}`} target="_blank" rel="noreferrer" title="See it on Open Library">
        <BookCover book={b} className="book-cover" />
      </a>
      <span className="book-card-text">
        <span className="item-title">{b.title}</span>
        <span className="item-meta">{[b.author, b.year].filter(Boolean).join(' · ')}</span>
        {b.ol_rating && <span className="item-meta rec-rating"><span className="stars">★</span> {Number(b.ol_rating).toFixed(1)} · {b.ol_ratings.toLocaleString()} ratings</span>}
      </span>
      <span className="rec-actions">
        <button type="button" className="primary small" onClick={want} disabled={busy}>+ Want to read</button>
        <button type="button" className="plain small" onClick={hide} disabled={busy}>Not interested</button>
      </span>
    </div>
  )
}

// Dashboard card: a few suggestions (the first of each section, then the rest), linking to the page.
export function RecsCard() {
  const [data, setData] = useState(null)
  useEffect(() => { api.bookRecs().then(setData).catch(() => {}) }, [])
  if (!data?.has_seeds) return null
  const rows = data.sections.map((s) => s.books)
  const picks = []
  for (let i = 0; picks.length < 5 && rows.some((r) => r[i]); i++) rows.forEach((r) => r[i] && picks.length < 5 && picks.push(r[i]))
  return (
    <section className="card home-card wide-card">
      <h2 className="home-card-title">You might like</h2>
      {picks.length === 0 ? <p className="muted small">Suggestions from the authors and genres you love.</p> : (
        <div className="cover-row">
          {picks.map((b) => (
            <Link key={b.ol_work} className="cover-card" to="/reading/foryou">
              <BookCover book={b} className="book-cover" />
              <span className="cover-card-title">{b.title}</span>
              <span className="muted small">{b.author}</span>
            </Link>
          ))}
        </div>
      )}
      <Link className="button plain small" to="/reading/foryou">{picks.length ? 'More suggestions →' : 'See suggestions →'}</Link>
    </section>
  )
}
