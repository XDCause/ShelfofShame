import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { BarList, ColumnChart } from '../../components/charts.jsx'
import Fold from '../../components/Fold.jsx'
import { BookIcon, QuoteIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat from '../../core/Stat.jsx'
import EmptyState from '../../core/EmptyState.jsx'
import { UnlockCalendar } from '../videogames/StatsView.jsx'
import { RecsCard } from './RecsView.jsx'
import { BookCover, GoalCard, GoodreadsImport, Progress, ProgressForm, SHELVES, ShelfPill, Stars, seriesText, starsText, useReadingSummary } from './readingParts.jsx'

// The Reading hobby's pages: a dashboard (the goal, what you're reading now, up next, latest
// finished), your books by shelf, stats, and every saved quote.

const plural = (n, one, many = `${one}s`) => `${n.toLocaleString()} ${n === 1 ? one : many}`

export function Dashboard() {
  const { data: s, error } = useReadingSummary()
  const { openPanel } = useApp()
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const empty = Object.values(s.counts).every((n) => n === 0)
  return (
    <section className="page reading">
      {empty ? (
        <section className="card empty-start">
          <h2 className="home-card-title">Start your bookshelf</h2>
          <p className="muted small">Add the book you're reading now, or bring everything across from Goodreads.</p>
          <div className="button-row">
            <button type="button" className="primary" onClick={() => openPanel('addbook', { status: 'reading' })}>+ Add a book</button>
          </div>
          <Fold title="Import from Goodreads"><GoodreadsImport /></Fold>
        </section>
      ) : (
        <>
          <GoalCard summary={s} />
          <div className="home-stats">
            <Stat to="/reading/books?status=finished" Icon={TrophyIcon} tone="ok" value={s.year.books} label={`Books in ${s.goal.year}`}
              sub={s.year.rating ? `${s.year.rating}★ average` : 'finished this year'} />
            <Stat to="/reading/stats" Icon={BookIcon} tone="tint" value={s.year.pages_read.toLocaleString()} label="Pages this year"
              sub={`${plural(s.week.pages, 'page')} in the last 7 days`} />
            <Stat to="/reading/stats" Icon={BookIcon} tone="teal" value={plural(s.streak.current, 'day')} label="Reading streak"
              sub={s.streak.longest ? `longest ${plural(s.streak.longest, 'day')}` : 'update your page to start one'} />
            <Stat to="/reading/quotes" Icon={QuoteIcon} tone="purple" value={s.quotes} label="Quotes saved"
              sub={`${s.counts.owned} on your shelf · ${s.counts.want} wanted`} />
          </div>
          <div className="home-grid">
            <div className="home-stack">
              <section className="card home-card">
                <div className="section-head">
                  <h2 className="home-card-title">Reading now</h2>
                  <button type="button" className="plain small" onClick={() => openPanel('addbook', { status: 'reading' })}>+ Add a book</button>
                </div>
                {s.reading.length === 0 ? <p className="muted small">Nothing on the go. Pick something from your want-to-read list!</p> : (
                  <ul className="reading-now">{s.reading.map((b) => <ReadingNow key={b.book_id} book={b} />)}</ul>
                )}
              </section>
              <section className="card home-card">
                <h2 className="home-card-title">Up next</h2>
                {s.next_up.length === 0 ? <p className="muted small">Add books you want to read.</p> : (
                  <ul className="list plain-list">{s.next_up.map((b) => <BookRow key={b.book_id} book={b} />)}</ul>
                )}
                <Link className="button plain small" to="/reading/books?status=want">Want to read →</Link>
              </section>
            </div>
            <div className="home-stack">
              <section className="card home-card">
                <h2 className="home-card-title">Recently finished</h2>
                {s.finished.length === 0 ? <p className="muted small">Your finished books will show here.</p> : (
                  <div className="cover-row">{s.finished.map((b) => <CoverCard key={b.book_id} book={b} />)}</div>
                )}
                <Link className="button plain small" to="/reading/books?status=finished">All finished →</Link>
              </section>
              <RecsCard />
            </div>
          </div>
          {s.covers?.running && <p className="muted small">Finding covers on Open Library... {s.covers.done} of {s.covers.total}</p>}
        </>
      )}
    </section>
  )
}

// A book you're reading: the cover, how far through, and the page box right there.
function ReadingNow({ book: b }) {
  const { openPanel } = useApp()
  return (
    <li className="reading-now-item">
      <button type="button" className="cover-button" onClick={() => openPanel('book', { id: b.book_id })} aria-label={`Open ${b.title}`}>
        <BookCover book={b} className="book-cover" />
      </button>
      <span className="grow">
        <button type="button" className="link-title" onClick={() => openPanel('book', { id: b.book_id })}>{b.title}</button>
        <span className="item-meta">{b.author}{b.last_read && ` · last read ${shortDate(b.last_read)}`}</span>
        <Progress book={b} />
        <ProgressForm book={b} compact />
      </span>
    </li>
  )
}

function CoverCard({ book: b }) {
  const { openPanel } = useApp()
  return (
    <button type="button" className="cover-card" onClick={() => openPanel('book', { id: b.book_id })}>
      <BookCover book={b} className="book-cover" />
      <span className="cover-card-title">{b.title}</span>
      <Stars value={b.rating} size="small" />
    </button>
  )
}

function BookRow({ book: b }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('book', { id: b.book_id })}>
        <BookCover book={b} className="book-cover small" />
        <span className="grow">
          <span className="item-title">{b.title}</span>
          <span className="item-meta">{[b.author, b.pages && `${b.pages} pages`].filter(Boolean).join(' · ')}</span>
          {b.status === 'reading' && <Progress book={b} />}
        </span>
        {b.status === 'finished' ? <Stars value={b.rating} size="small" /> : <ShelfPill status={b.status} />}
      </button>
    </li>
  )
}

const SORTS = [['recent', 'Recently read'], ['finished', 'Date finished'], ['added', 'Date added'], ['title', 'Title'],
  ['author', 'Author'], ['rating', 'Your rating']]

// Every book: a shelf at a time (or all), search, sort; adding and the Goodreads import live here.
export function BooksView() {
  const { refreshKey, openPanel } = useApp()
  const params = new URLSearchParams(window.location.search)
  const [status, setStatus] = useState(params.get('status') ?? '')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState(params.get('status') === 'finished' ? 'finished' : 'recent')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (params.get('add') === '1') openPanel('addbook', {})
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const t = setTimeout(() => api.books({ status, q, sort }).then(setData).catch((e) => setError(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [status, q, sort, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  const counts = data?.counts ?? {}
  const all = Object.values(counts).reduce((a, b) => a + b, 0)
  return (
    <section className="page reading">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search titles, authors, genres..." aria-label="Search your books" />
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
          {SORTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <button type="button" className="primary" onClick={() => openPanel('addbook', { status: status || 'want' })}>+ Add a book</button>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Shelf">
        <button type="button" className="chip-filter" aria-pressed={status === ''} onClick={() => setStatus('')}>
          All <span className="chip-count">{all}</span></button>
        {SHELVES.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={status === id} onClick={() => setStatus(id)}>
            {label} <span className="chip-count">{counts[id] ?? 0}</span></button>
        ))}
      </div>
      {!data ? <p className="muted loading">Loading...</p> : data.books.length === 0 ? (
        q || all ? <p className="empty card">{q ? 'No books match that.' : 'Nothing on this shelf yet.'}</p> : (
          <EmptyState Icon={BookIcon} title="No books yet" action="+ Add a book" onAction={() => openPanel('addbook', {})}>
            Search by title, scan the ISBN, or import everything from Goodreads below.</EmptyState>
        )
      ) : (
        <ul className="book-grid">
          {data.books.map((b) => (
            <li key={b.book_id}>
              <button type="button" className="book-card" onClick={() => openPanel('book', { id: b.book_id })}>
                <BookCover book={b} className="book-cover" />
                <span className="book-card-text">
                  <span className="item-title">{b.title}</span>
                  <span className="item-meta">{b.author}</span>
                  {b.series && <span className="item-meta series-meta">{seriesText(b)}</span>}
                  {b.status === 'reading' ? <Progress book={b} />
                    : b.status === 'finished' ? <span className="item-meta"><Stars value={b.rating} size="small" />{b.finished_on && ` ${shortDate(b.finished_on)}`}</span>
                      : !status && <ShelfPill status={b.status} />}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Fold title="Import from Goodreads"><GoodreadsImport /></Fold>
    </section>
  )
}

const monthName = (ym, long = false) => new Date(`${ym}-15T12:00:00`)
  .toLocaleDateString('en-AU', long ? { month: 'long', year: 'numeric' } : { month: 'short', year: '2-digit' })

// Reading in numbers: a year of reading days, pages per month, books per year, genres, stars.
export function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const [st, setSt] = useState(null)
  const { data: s } = useReadingSummary()
  const [error, setError] = useState('')
  useEffect(() => { api.readingStats().then(setSt).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!st) return <p className="muted loading">Loading...</p>
  const f = st.facts
  const months = st.by_month.map((m) => ({ label: monthName(m.month), value: m.pages, tip: monthName(m.month, true) }))
  return (
    <section className="page stats">
      <div className="home-stats">
        <Stat to="/reading/books?status=finished" Icon={TrophyIcon} tone="ok" value={f.finished} label="Books finished"
          sub={`${f.pages.toLocaleString()} pages`} />
        <Stat to="/reading/books?status=finished" Icon={BookIcon} tone="purple" value={f.average_rating ? `${f.average_rating}★` : '—'}
          label="Average rating" sub="of the books you rated" />
        <Stat to="/reading/books" Icon={BookIcon} tone="tint" value={f.average_pages ?? '—'} label="Average length" sub="pages" />
        {f.quickest && <Stat to="/reading/books" Icon={BookIcon} tone="teal" value={plural(f.quickest.days, 'day')} label="Quickest read"
          sub={f.quickest.title} />}
      </div>
      <div className="home-grid">
        <UnlockCalendar title="Reading calendar" one="page" many="pages" today={st.today}
          days={st.days.map((d) => ({ day: d.day, count: d.pages }))}
          streak={s?.streak ?? { current: 0, longest: 0, longest_end: null }} />
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Pages read per month</h2>
          <p className="muted small chart-sub">Your page updates, plus finished books you never updated (all their pages, the month you finished)</p>
          {months.some((m) => m.value) ? <ColumnChart title="Month" rows={months} valueLabel="pages" tickEvery={3} />
            : <p className="muted small">Nothing read yet - update your page in a book and it shows here.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Books finished per year</h2>
          {st.by_year.length === 0 ? <p className="muted small">Nothing finished yet.</p> : (
            <ColumnChart title="Year" valueLabel="books" labelValues rows={st.by_year.map((y) => ({ label: String(y.year), value: y.books }))} />
          )}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Your ratings</h2>
          {st.ratings.some((r) => r.books) ? (
            <ColumnChart title="Stars" valueLabel="books" labelValues
              rows={st.ratings.filter((r) => r.stars % 1 === 0 || st.ratings.some((h) => h.stars % 1 && h.books))
                .map((r) => ({ label: `${starsText(r.stars)}★`, value: r.books }))} />
          ) : <p className="muted small">Rate a book you've finished and it shows here.</p>}
        </section>
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Genres you finish</h2>
          {st.genres.length === 0 ? <p className="muted small">Genres come from Open Library when you add a book (or set them in Edit details).</p> : (
            <BarList title="Genre" valueLabel="Books" rows={st.genres.map((g) => ({ label: g.genre, value: g.books, text: plural(g.books, 'book'), id: g.genre }))} />
          )}
        </section>
        {f.longest && (
          <section className="card home-card wide-card">
            <h2 className="home-card-title">Longest book</h2>
            <ul className="list plain-list"><BookRow book={f.longest} /></ul>
            <button type="button" className="plain small" onClick={() => openPanel('book', { id: f.longest.book_id })}>{f.longest.pages} pages ›</button>
          </section>
        )}
      </div>
    </section>
  )
}

// Every saved quote, newest first; search the words, the title or the author.
export function QuotesView() {
  const { refreshKey, openPanel } = useApp()
  const [q, setQ] = useState('')
  const [quotes, setQuotes] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const t = setTimeout(() => api.quotes(q).then(setQuotes).catch((e) => setError(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [q, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  return (
    <section className="page reading">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search quotes, titles, authors..." aria-label="Search quotes" />
      </div>
      {!quotes ? <p className="muted loading">Loading...</p> : quotes.length === 0 ? (
        q ? <p className="empty card">No quotes match that.</p> : (
          <EmptyState Icon={QuoteIcon} title="No quotes yet">Open a book and press "+ Save a quote" to keep a line you loved.</EmptyState>
        )
      ) : (
        <ul className="quote-wall">
          {quotes.map((x) => (
            <li key={x.quote_id} className="card">
              <blockquote>{x.text}</blockquote>
              <button type="button" className="row-button" onClick={() => openPanel('book', { id: x.book_id })}>
                <BookCover book={x} className="book-cover tiny" />
                <span className="item-meta">{x.title}{x.author && `, ${x.author}`}{x.page != null && ` · p. ${x.page}`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

