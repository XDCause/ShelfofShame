import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, imageUrl, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import TodoList from './TodoList.jsx'

const dayOf = (day) => new Date(`${day}T12:00:00`)
const monthOf = (day) => dayOf(day).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })

// A page's picture: its first photo, else the box photo of a kit (or supply) it mentions.
const pictureOf = (p) => p.cover_url || (p.product_info_id ? imageUrl(p) : null)

// Make a page and open it. `title` / `content` pre-fill it (e.g. today's date, or a mention).
export function useNewPage() {
  const navigate = useNavigate()
  const { changed } = useApp()
  return async (page = {}) => {
    const created = await api.addPage(page)
    changed()
    navigate(`/journal/${created.page_id}`)
  }
}

// All journal pages as cards: search, filter by tag, newest or oldest first (pinned always on top),
// with a heading per month. Open to-dos from every page sit above them.
export default function JournalList() {
  const { refreshKey } = useApp()
  const newPage = useNewPage()
  const [pages, setPages] = useState(null)
  const [tags, setTags] = useState([])
  const [q, setQ] = useState('')
  const [tag, setTag] = useState('')
  const [oldest, setOldest] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const wait = setTimeout(() => {
      api.listPages({ q, tag }).then(setPages).catch((e) => setError(e.message))
    }, q ? 250 : 0)                                         // don't search on every keystroke
    return () => clearTimeout(wait)
  }, [q, tag, refreshKey])
  useEffect(() => { api.journalTags().then(setTags).catch(() => {}) }, [refreshKey])

  // Pinned first, then a heading per month.
  const pinned = (pages ?? []).filter((p) => p.pinned)
  const rest = (pages ?? []).filter((p) => !p.pinned)
  const groups = []
  for (const p of [...pinned, ...(oldest ? [...rest].reverse() : rest)]) {
    const name = p.pinned ? 'Pinned' : monthOf(p.entry_date)
    if (groups.at(-1)?.name !== name) groups.push({ name, pages: [] })
    groups.at(-1).pages.push(p)
  }

  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" placeholder="Search the journal..." value={q}
          onChange={(e) => setQ(e.target.value)} aria-label="Search the journal" />
        <button type="button" className="primary" onClick={() => newPage()}>+ New page</button>
      </div>
      <div className="filters">
        <div className="chip-row" aria-label="Tags">
          <button type="button" className="chip-filter" aria-pressed={!tag} onClick={() => setTag('')}>All</button>
          {tags.map((t) => (
            <button key={t.name} type="button" className="chip-filter" aria-pressed={tag === t.name}
              onClick={() => setTag(tag === t.name ? '' : t.name)}>
              #{t.name} <span className="chip-count">{t.pages}</span>
            </button>
          ))}
        </div>
        <label className="sort view-controls">
          <span className="muted small">Sort</span>
          <select value={oldest ? 'oldest' : 'newest'} onChange={(e) => setOldest(e.target.value === 'oldest')} aria-label="Sort pages">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </label>
      </div>
      {error && <p className="alert error">{error}</p>}
      {!q && !tag && <TodoList card />}
      {pages && pages.length === 0 && (
        <p className="empty card">{q || tag ? 'No pages match.' : 'No pages yet. Start one with "+ New page".'}</p>
      )}
      {groups.map((g) => (
        <div key={g.name}>
          <h3 className="section-title">{g.name}</h3>
          <ul className="journal-cards">
            {g.pages.map((p) => <PageCard key={p.page_id} page={p} />)}
          </ul>
        </div>
      ))}
    </section>
  )
}

// A page as a card: the day it's about, its picture, title, first tag, a few lines, other tags.
function PageCard({ page: p }) {
  const day = dayOf(p.entry_date)
  const picture = pictureOf(p)
  const [first, ...others] = p.tags
  return (
    <li>
      <Link to={`/journal/${p.page_id}`} className="journal-card">
        <span className="date-block" aria-label={shortDate(p.entry_date)}>
          <strong>{day.getDate()}</strong>
          <span>{day.toLocaleDateString('en-AU', { month: 'short' })}</span>
          <span>{day.getFullYear()}</span>
        </span>
        {picture ? <img className="journal-thumb" src={picture} alt="" loading="lazy" />
          : <span className="journal-thumb emoji" aria-hidden="true">{p.icon || '📝'}</span>}
        <span className="grow">
          <span className="journal-card-head">
            <span className="item-title">{picture && p.icon ? `${p.icon} ` : ''}{p.title || 'Untitled'}</span>
            {p.pinned && <span className="pill low">Pinned</span>}
          </span>
          {first && <span className="pill tint">#{first}</span>}
          {p.snippet && <span className="page-snippet two-lines">{p.snippet.replace(/\n/g, ' · ')}</span>}
          {others.length > 0 && <span className="chips">{others.map((t) => <span key={t} className="chip">#{t}</span>)}</span>}
        </span>
      </Link>
    </li>
  )
}

export function PageRow({ page: p, onClick }) {
  return (
    <li>
      <Link to={`/journal/${p.page_id}`} className="page-row" onClick={onClick}>
        <span className="page-icon" aria-hidden="true">{p.icon || '📝'}</span>
        <span className="grow">
          <span className="item-title">{p.title || 'Untitled'}</span>
          {p.snippet && <span className="page-snippet">{p.snippet.split('\n')[0]}</span>}
          {p.tags.length > 0 && <span className="page-tags">{p.tags.map((t) => `#${t}`).join(' ')}</span>}
        </span>
        <span className="muted small">{shortDate(p.entry_date)}</span>
      </Link>
    </li>
  )
}
