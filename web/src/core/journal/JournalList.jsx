import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import TodoList from './TodoList.jsx'

const monthOf = (day) => new Date(`${day}T12:00:00`).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })

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

// All journal pages: search, filter by tag, pinned on top, then by month, newest first.
export default function JournalList() {
  const { refreshKey } = useApp()
  const newPage = useNewPage()
  const [pages, setPages] = useState(null)
  const [tags, setTags] = useState([])
  const [q, setQ] = useState('')
  const [tag, setTag] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const wait = setTimeout(() => {
      api.listPages({ q, tag }).then(setPages).catch((e) => setError(e.message))
    }, q ? 250 : 0)                                         // don't search on every keystroke
    return () => clearTimeout(wait)
  }, [q, tag, refreshKey])
  useEffect(() => { api.journalTags().then(setTags).catch(() => {}) }, [refreshKey])

  // Pinned first, then a heading per month.
  const groups = []
  for (const p of pages ?? []) {
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
      {tags.length > 0 && (
        <div className="chip-row" aria-label="Tags">
          {tags.map((t) => (
            <button key={t.name} type="button" className="chip-filter" aria-pressed={tag === t.name}
              onClick={() => setTag(tag === t.name ? '' : t.name)}>
              #{t.name} <span className="chip-count">{t.pages}</span>
            </button>
          ))}
        </div>
      )}
      {error && <p className="alert error">{error}</p>}
      {!q && !tag && <TodoList card />}
      {pages && pages.length === 0 && (
        <p className="empty card">{q || tag ? 'No pages match.' : 'No pages yet. Start one with "+ New page".'}</p>
      )}
      {groups.map((g) => (
        <div key={g.name}>
          <h3 className="section-title">{g.name}</h3>
          <ul className="list journal-list">
            {g.pages.map((p) => <PageRow key={p.page_id} page={p} />)}
          </ul>
        </div>
      ))}
    </section>
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
