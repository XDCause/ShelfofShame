import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { BarList, ColumnChart } from '../../components/charts.jsx'
import { BookIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { BookCover, Stars } from './readingParts.jsx'

// Reading's year in review and your own challenges (api/app/reading_more.py). Private: nothing here is shared.

const plural = (n, one, many = `${one}s`) => `${n.toLocaleString()} ${n === 1 ? one : many}`
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const LENGTHS = { short: 'Short (under 250 pages)', medium: 'Medium (250-499)', long: 'Long (500 and over)' }
const FORMAT_NAMES = { paper: 'Paper', ebook: 'Ebook', audio: 'Audiobook', unknown: 'Format not set' }

// A year of reading: books and pages, by month, format and length, your longest and favourite, genres, authors.
export function YearView() {
  const { refreshKey, openPanel } = useApp()
  const [year, setYear] = useState(null)        // null = the server's current year
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.readingReview(year).then(setR).catch((e) => setError(e.message)) }, [year, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!r) return <p className="muted loading">Loading...</p>
  const months = r.by_month.map((m, i) => ({ label: MONTHS[i], value: m.books, tip: `${MONTHS[i]} ${r.year}: ${plural(m.pages, 'page')} read` }))
  const pages = r.by_month.map((m, i) => ({ label: MONTHS[i], value: m.pages, tip: `${MONTHS[i]} ${r.year}` }))
  const bars = (rows, names = {}) => rows.map((x) => ({ label: names[x.label] ?? x.label, value: x.books, text: plural(x.books, 'book') }))
  const book = (b, what) => b && (
    <section className="card home-card rdm-highlight">
      <h2 className="home-card-title">{what}</h2>
      <button type="button" className="row-button" onClick={() => openPanel('book', { id: b.book_id })}>
        <BookCover book={b} className="book-cover" />
        <span className="grow">
          <span className="item-title">{b.title}</span>
          <span className="item-meta">{[b.author, b.pages && `${b.pages} pages`].filter(Boolean).join(' · ')}</span>
          {b.rating ? <Stars value={b.rating} size="small" /> : null}
        </span>
      </button>
    </section>
  )
  return (
    <section className="page stats reading">
      <div className="toolbar">
        <label className="small">Year <select value={r.year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Year">
          {r.years.map((y) => <option key={y} value={y}>{y}</option>)}</select></label>
      </div>
      {r.books === 0 ? (
        <EmptyState Icon={BookIcon} title={`No books finished in ${r.year}`}>Finish a book and your year in review fills in.</EmptyState>
      ) : (
        <>
          <div className="home-stats">
            <Stat to="/reading/books?status=finished" Icon={TrophyIcon} tone="ok" value={r.books} label={`Books in ${r.year}`}
              sub={r.rereads ? `${plural(r.rereads, 're-read')} among them` : r.average_rating ? `${r.average_rating}★ average` : 'finished'} />
            <Stat to="/reading/stats" Icon={BookIcon} tone="tint" value={r.pages_read.toLocaleString()} label="Pages read"
              sub={`${r.pages_a_day} pages a day`} />
            <Stat to="/reading/books?status=finished" Icon={BookIcon} tone="purple" value={r.average_pages ?? '—'} label="Average length" sub="pages" />
            <Stat to="/reading/books?status=finished" Icon={BookIcon} tone="teal" value={r.new_authors} label="New authors"
              sub={r.five_stars ? `${plural(r.five_stars, 'five-star read')}` : r.gave_up ? `${plural(r.gave_up, 'book')} given up` : 'first time this year'} />
          </div>
          <div className="home-grid">
            <section className="card home-card wide-card">
              <h2 className="home-card-title">Books finished each month</h2>
              <ColumnChart title="Month" rows={months} valueLabel="books" labelValues />
            </section>
            <section className="card home-card wide-card">
              <h2 className="home-card-title">Pages read each month</h2>
              <ColumnChart title="Month" rows={pages} valueLabel="pages" />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">By length</h2>
              <BarList title="Length" valueLabel="Books" rows={bars(r.by_length, LENGTHS)} />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">By format</h2>
              <BarList title="Format" valueLabel="Books" rows={bars(r.by_format, FORMAT_NAMES)} />
            </section>
            {book(r.longest, 'Longest book')}
            {book(r.favourite, 'Favourite')}
            {r.genres.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Genres</h2>
                <BarList title="Genre" valueLabel="Books" rows={bars(r.genres)} />
              </section>
            )}
            {r.authors.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Authors you read most</h2>
                <BarList title="Author" valueLabel="Books" rows={bars(r.authors)} />
              </section>
            )}
          </div>
          <p className="muted small">Private to you. Pages a day counts the pages you logged (and books you finished without logging) over {plural(r.days, 'day')}.</p>
        </>
      )}
    </section>
  )
}

const RULES = [['tag', 'Books with my tag'], ['genre', 'Books in a genre'], ['pages_over', 'Books with more than N pages'], ['manual', 'Books I tick off myself']]
const RULE_TEXT = { tag: (c) => `tagged "${c.rule_value}"`, genre: (c) => `in the genre "${c.rule_value}"`,
  pages_over: (c) => `over ${c.rule_value} pages`, manual: () => 'ticked off by you' }

// Your own challenges: a name, a target and a rule, with progress.
export function ChallengesView() {
  const { refreshKey, changed } = useApp()
  const [list, setList] = useState(null)
  const [tags, setTags] = useState([])
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  useEffect(() => {
    api.readingChallenges().then(setList).catch((e) => setError(e.message))
    api.readingTags().then(setTags).catch(() => {})
  }, [refreshKey])
  if (error && !list) return <p className="alert error">{error}</p>
  if (!list) return <p className="muted loading">Loading...</p>
  const run = async (fn) => {
    setError('')
    try { await fn(); changed() } catch (e) { setError(e.message) }
  }
  return (
    <section className="page reading">
      <div className="toolbar">
        <button type="button" className="primary" onClick={() => setAdding(true)}>+ New challenge</button>
      </div>
      {adding && <ChallengeForm tags={tags} onCancel={() => setAdding(false)}
        onSave={(data) => run(async () => { await api.addReadingChallenge(data); setAdding(false) })} />}
      {error && <p className="alert error small">{error}</p>}
      {list.length === 0 && !adding ? (
        <EmptyState Icon={TrophyIcon} title="No challenges yet" action="+ New challenge" onAction={() => setAdding(true)}>
          For example: 5 books over 500 pages, or 10 books you tag "new country". Progress counts the books you finish.</EmptyState>
      ) : (
        <ul className="rdm-challenges">
          {list.map((c) => <ChallengeCard key={c.challenge_id} challenge={c} run={run} />)}
        </ul>
      )}
    </section>
  )
}

function ChallengeForm({ tags, onSave, onCancel }) {
  const [f, setF] = useState({ name: '', target: '5', rule: 'tag', rule_value: '', year: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = (e) => {
    e.preventDefault()
    onSave({ name: f.name, target: Number(f.target), rule: f.rule, rule_value: f.rule === 'manual' ? null : f.rule_value,
      year: f.year ? Number(f.year) : null })
  }
  return (
    <form className="card rdm-form" onSubmit={submit}>
      <label>Name<input value={f.name} onChange={set('name')} required maxLength={120} placeholder="Books over 500 pages" /></label>
      <label>How many<input type="number" min="1" max="1000" value={f.target} onChange={set('target')} required /></label>
      <label>What counts<select value={f.rule} onChange={set('rule')}>{RULES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      {f.rule !== 'manual' && (
        <label>{f.rule === 'pages_over' ? 'Pages' : f.rule === 'tag' ? 'Tag' : 'Genre'}
          <input value={f.rule_value} onChange={set('rule_value')} required list={f.rule === 'tag' ? 'rdm-tag-list' : undefined}
            type={f.rule === 'pages_over' ? 'number' : 'text'} min="1" placeholder={f.rule === 'pages_over' ? '500' : f.rule === 'tag' ? 'new country' : 'Fantasy'} />
        </label>
      )}
      <datalist id="rdm-tag-list">{tags.map((t) => <option key={t.tag} value={t.tag} />)}</datalist>
      <label>Only books finished in (optional)<input type="number" min="2000" max="2100" value={f.year} onChange={set('year')} placeholder="any year" /></label>
      <div className="button-row">
        <button type="submit" className="primary">Start it</button>
        <button type="button" className="plain" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function ChallengeCard({ challenge: c, run }) {
  const { openPanel } = useApp()
  const [finished, setFinished] = useState(null)
  const [pick, setPick] = useState('')
  const open = async () => {
    if (!finished) setFinished((await api.books({ status: 'finished' })).books)
  }
  const ticked = new Set(c.books.map((b) => b.book_id))
  return (
    <li className="card rdm-challenge">
      <div className="section-head">
        <h2 className="home-card-title">{c.name}</h2>
        <button type="button" className="plain small destructive" aria-label={`Delete ${c.name}`}
          onClick={() => run(() => api.deleteReadingChallenge(c.challenge_id))}>Delete</button>
      </div>
      <p className="muted small">{c.target} {c.target === 1 ? 'book' : 'books'} {RULE_TEXT[c.rule](c)}{c.year ? `, finished in ${c.year}` : ''}</p>
      <p><strong>{c.done}</strong> of {c.target}{c.reached && ' - done!'}</p>
      <span className={`fill-bar ${c.reached ? 'ok' : 'tint'}`} role="progressbar" aria-label={`${c.name} progress`} aria-valuenow={c.percent} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${c.percent}%` }} /></span>
      {c.books.length > 0 && (
        <ul className="rdm-challenge-books">
          {c.books.map((b) => (
            <li key={b.book_id}>
              <button type="button" className="row-button" onClick={() => openPanel('book', { id: b.book_id })}>
                <BookCover book={b} className="book-cover small" />
                <span className="grow"><span className="item-title">{b.title}</span>
                  <span className="item-meta">{b.author}{b.finished_on && ` · ${shortDate(b.finished_on)}`}</span></span>
              </button>
              {c.rule === 'manual' && (
                <button type="button" className="plain small" aria-label={`Untick ${b.title}`}
                  onClick={() => run(() => api.untickChallengeBook(c.challenge_id, b.book_id))}>✕</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {c.rule === 'manual' && (
        <form className="button-row" onSubmit={(e) => { e.preventDefault(); if (pick) run(() => api.tickChallengeBook(c.challenge_id, Number(pick))).then(() => setPick('')) }}>
          <select value={pick} onFocus={open} onChange={(e) => setPick(e.target.value)} aria-label="A finished book to tick off">
            <option value="">{finished ? 'Tick off a finished book...' : 'Tick off a book...'}</option>
            {(finished ?? []).filter((b) => !ticked.has(b.book_id)).map((b) => <option key={b.book_id} value={b.book_id}>{b.title}</option>)}
          </select>
          <button type="submit" className="secondary small" disabled={!pick}>Tick</button>
        </form>
      )}
    </li>
  )
}
