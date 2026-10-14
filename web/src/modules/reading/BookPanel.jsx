import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { BookCover, Progress, ProgressForm, SHELVES, Stars } from './readingParts.jsx'

const FORMATS = [['', 'Not set'], ['paper', 'Paper'], ['ebook', 'Ebook'], ['audio', 'Audiobook']]

// One book: its shelf, where you're up to (and every update), your stars and review, saved
// quotes, journal pages about it, and its details.
export default function BookPanel({ id, onClose }) {
  const { changed, showToast } = useApp()
  const [book, setBook] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [review, setReview] = useState('')
  const [saved, setSaved] = useState('')
  useEffect(() => {
    api.book(id).then((b) => { setBook(b); setReview(b.review ?? '') }).catch((e) => setError(e.message))
  }, [id])
  if (!book) return <Drawer title="Book" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted loading">Loading...</p>}</Drawer>

  const update = async (data) => {
    try {
      setBook(await api.updateBook(id, data))
      changed()
    } catch (e) {
      setError(e.message)
    }
  }
  const saveReview = async () => {
    if ((book.review ?? '') === review) return
    await update({ review })
    setSaved('Saved ✓')
  }
  const remove = async () => {
    await api.deleteBook(id)
    showToast(`Removed ${book.title}`)
    changed()
    onClose()
  }
  const reload = (b) => { setBook(b); setReview(b.review ?? '') }
  const footer = (
    <>
      {book.ol_work && <a className="button secondary" href={`https://openlibrary.org/works/${book.ol_work}`} target="_blank" rel="noreferrer">Open Library ↗</a>}
      <span className="spacer" />
      {!editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>}
      <button type="button" className="plain destructive" onClick={remove}>Remove</button>
    </>
  )
  return (
    <Drawer title={book.title} onClose={onClose} footer={footer} wide>
      <section className="panel-section book-head">
        <BookCover book={book} className="book-cover large" />
        <div className="grow">
          <p className="book-author">{book.author ?? 'Unknown author'}</p>
          <p className="muted small">{[book.year, book.pages && `${book.pages} pages`, book.format && FORMATS.find(([f]) => f === book.format)?.[1]]
            .filter(Boolean).join(' · ')}</p>
          {book.genres.length > 0 && <p className="chips">{book.genres.map((g) => <span key={g} className="chip">{g}</span>)}</p>}
          <p className="muted small">
            {book.started_on && `Started ${shortDate(book.started_on)}`}{book.started_on && book.finished_on && ' · '}
            {book.finished_on && `${book.status === 'dnf' ? 'Stopped' : 'Finished'} ${shortDate(book.finished_on)}`}
          </p>
        </div>
      </section>

      <section className="panel-section">
        <div className="segmented" role="group" aria-label="Shelf">
          {SHELVES.map(([s, label]) => <button key={s} type="button" aria-pressed={book.status === s} onClick={() => update({ status: s })}>{label}</button>)}
        </div>
      </section>

      {editing && <BookForm book={book} onSaved={(b) => { reload(b); setEditing(false); changed() }} onCancel={() => setEditing(false)} />}

      {book.status !== 'finished' && (
        <section className="panel-section">
          <h3 className="section-title">Where you're up to</h3>
          <Progress book={book} />
          <ProgressForm book={book} onSaved={reload} />
        </section>
      )}

      {(book.status === 'finished' || book.status === 'dnf' || book.rating || book.review) && (
        <section className="panel-section">
          <h3 className="section-title">What you thought</h3>
          <Stars value={book.rating} onChange={(rating) => update({ rating })} />
          <label className="field">Review
            <textarea rows={4} value={review} onChange={(e) => { setReview(e.target.value); setSaved('') }} onBlur={saveReview}
              placeholder="What stayed with you?" /></label>
          {saved && <span className="muted small">{saved}</span>}
        </section>
      )}

      <Quotes book={book} onChange={reload} />

      {book.log.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Reading log</h3>
          <ul className="list plain-list reading-log">
            {book.log.map((l) => (
              <li key={l.log_id}>
                <span className="grow">
                  <strong>{shortDate(l.logged_on)}</strong> · to p. {l.page} <span className="muted">({l.pages} page{l.pages === 1 ? '' : 's'}{l.minutes && `, ${l.minutes} min`})</span>
                </span>
                <button type="button" className="icon-btn" aria-label={`Remove the update on ${shortDate(l.logged_on)}`}
                  onClick={async () => { await api.deleteReadingLog(l.log_id); reload(await api.book(id)); changed() }}>✕</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && <p className="alert error small">{error}</p>}
      <JournalMentions kind="book" id={book.book_id} name={book.title} onLeave={onClose} />
    </Drawer>
  )
}

function Quotes({ book, onChange }) {
  const [text, setText] = useState('')
  const [page, setPage] = useState('')
  const [open, setOpen] = useState(false)
  const add = async (e) => {
    e.preventDefault()
    onChange(await api.addQuote(book.book_id, { text, page: page === '' ? null : Number(page) }))
    setText('')
    setPage('')
    setOpen(false)
  }
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Quotes</h3>
        {!open && <button type="button" className="plain small" onClick={() => setOpen(true)}>+ Save a quote</button>}
      </div>
      {open && (
        <form className="quote-form" onSubmit={add}>
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} required autoFocus aria-label="Quote" placeholder="The words..." />
          <div className="button-row">
            <label className="small">Page <input type="number" min="0" value={page} onChange={(e) => setPage(e.target.value)} aria-label="Page" /></label>
            <button type="submit" className="primary small">Save quote</button>
            <button type="button" className="plain small" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </form>
      )}
      {book.quotes_list.length === 0 && !open ? <p className="muted small">Lines worth keeping go here.</p> : (
        <ul className="quote-list">
          {book.quotes_list.map((q) => (
            <li key={q.quote_id}>
              <blockquote>{q.text}</blockquote>
              <span className="muted small">{q.page != null && `p. ${q.page}`}</span>
              <button type="button" className="icon-btn" aria-label="Remove this quote"
                onClick={async () => { await api.deleteQuote(q.quote_id); onChange(await api.book(book.book_id)) }}>✕</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function BookForm({ book, onSaved, onCancel }) {
  const [f, setF] = useState({
    title: book.title, author: book.author ?? '', pages: book.pages ?? '', year: book.year ?? '', isbn: book.isbn ?? '',
    format: book.format ?? '', genres: book.genres.join(', '), started_on: book.started_on ?? '', finished_on: book.finished_on ?? '',
  })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    setError('')
    const num = (v) => (v === '' ? null : Number(v))
    try {
      onSaved(await api.updateBook(book.book_id, {
        ...f, pages: num(f.pages), year: num(f.year), format: f.format || null, started_on: f.started_on || null,
        finished_on: f.finished_on || null, genres: f.genres.split(',').map((g) => g.trim()).filter(Boolean),
      }))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <section className="panel-section">
      <form className="book-form" onSubmit={save}>
        <label>Title<input value={f.title} onChange={set('title')} required /></label>
        <label>Author<input value={f.author} onChange={set('author')} /></label>
        <label>Pages<input type="number" min="1" value={f.pages} onChange={set('pages')} /></label>
        <label>First published<input type="number" value={f.year} onChange={set('year')} /></label>
        <label>ISBN<input value={f.isbn} onChange={set('isbn')} inputMode="numeric" /></label>
        <label>Format<select value={f.format} onChange={set('format')}>{FORMATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label>Genres<input value={f.genres} onChange={set('genres')} placeholder="Fantasy, Mystery" /></label>
        <label>Started<input type="date" value={f.started_on} onChange={set('started_on')} /></label>
        <label>Finished<input type="date" value={f.finished_on} onChange={set('finished_on')} /></label>
        <div className="button-row">
          <button type="submit" className="primary">Save details</button>
          <button type="button" className="plain" onClick={onCancel}>Cancel</button>
        </div>
        {error && <p className="alert error small">{error}</p>}
      </form>
    </section>
  )
}
