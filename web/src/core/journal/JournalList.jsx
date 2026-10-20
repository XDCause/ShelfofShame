import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, imageUrl, isoDay, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import { MOODS, moodOf, pageFace } from './moods.js'
import TodoList from './TodoList.jsx'
import EmptyState from '../EmptyState.jsx'
import { JournalIcon } from '../../components/icons.jsx'

const dayOf = (day) => new Date(`${day}T12:00:00`)
const monthOf = (day) => dayOf(day).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })
// "Today", "Yesterday", "Monday 12 October" (and the year, if it isn't this year).
function dayName(day) {
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (day === isoDay(today)) return 'Today'
  if (day === isoDay(yesterday)) return 'Yesterday'
  const sameYear = dayOf(day).getFullYear() === today.getFullYear()
  return dayOf(day).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long', ...(sameYear ? {} : { year: 'numeric' }) })
}

// Group by day (each with that day's mood) or by month; the choice is remembered on this device.
const GROUP_KEY = 'offtheclock.journalGroups'
const readGrouping = () => { try { return localStorage.getItem(GROUP_KEY) === 'month' ? 'month' : 'day' } catch { return 'day' } }
const saveGrouping = (g) => { try { localStorage.setItem(GROUP_KEY, g) } catch { /* not important */ } }

// What kind of page it is, in the card's corner.
const KIND_PILL = { notes: ['Journal', 'teal'], whiteboard: ['Whiteboard', 'purple'] }

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

// All journal pages as cards: search, filter by tag or mood, newest or oldest first (pinned always
// on top), with a heading per day or per month. Open to-dos from every page sit above them.
export default function JournalList() {
  const { refreshKey } = useApp()
  const newPage = useNewPage()
  const [pages, setPages] = useState(null)
  const [tags, setTags] = useState([])
  const [q, setQ] = useState('')
  const [tag, setTag] = useState('')
  const [mood, setMood] = useState('')
  const [oldest, setOldest] = useState(false)
  const [grouping, setGrouping] = useState(readGrouping)
  const [error, setError] = useState('')

  useEffect(() => {
    const wait = setTimeout(() => {
      api.listPages({ q, tag, mood }).then(setPages).catch((e) => setError(e.message))
    }, q ? 250 : 0)                                         // don't search on every keystroke
    return () => clearTimeout(wait)
  }, [q, tag, mood, refreshKey])
  useEffect(() => { api.journalTags().then(setTags).catch(() => {}) }, [refreshKey])

  // Pinned first, then a heading per day (or month).
  const pinned = (pages ?? []).filter((p) => p.pinned)
  const rest = (pages ?? []).filter((p) => !p.pinned)
  const groups = []
  for (const p of [...pinned, ...(oldest ? [...rest].reverse() : rest)]) {
    const name = p.pinned ? 'Pinned' : grouping === 'day' ? dayName(p.entry_date) : monthOf(p.entry_date)
    if (groups.at(-1)?.name !== name) groups.push({ name, pages: [], day: !p.pinned && grouping === 'day' })
    groups.at(-1).pages.push(p)
  }
  // A day's heading shows how it felt: the mood of its most recently edited page with one.
  const dayMood = (g) => moodOf([...g.pages].filter((p) => p.mood)
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0]?.mood)

  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" placeholder="Search the journal..." value={q}
          onChange={(e) => setQ(e.target.value)} aria-label="Search the journal" />
        <button type="button" className="secondary" onClick={() => newPage({ kind: 'whiteboard' })}>+ Whiteboard</button>
        <button type="button" className="primary" onClick={() => newPage()}>+ New page</button>
      </div>
      <div className="filters">
        <div className="chip-row" role="group" aria-label="Tags">
          <button type="button" className="chip-filter" aria-pressed={!tag} onClick={() => setTag('')}>All</button>
          {tags.map((t) => (
            <button key={t.name} type="button" className="chip-filter" aria-pressed={tag === t.name}
              onClick={() => setTag(tag === t.name ? '' : t.name)}>
              #{t.name} <span className="chip-count">{t.pages}</span>
            </button>
          ))}
        </div>
        <div className="chip-row mood-filter" role="group" aria-label="Mood">
          {MOODS.map((m) => (
            <button key={m.id} type="button" className="chip-filter" aria-pressed={mood === m.id}
              title={`${m.label} days`} aria-label={`${m.label} days`}
              onClick={() => setMood(mood === m.id ? '' : m.id)}>{m.face}</button>
          ))}
        </div>
        <span className="filters-spacer" aria-hidden="true" />
        <div className="segmented" role="group" aria-label="Group by">
          {[['day', 'Day'], ['month', 'Month']].map(([g, label]) => (
            <button key={g} type="button" aria-pressed={grouping === g}
              onClick={() => { setGrouping(g); saveGrouping(g) }}>{label}</button>
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
      {!q && !tag && !mood && <TodoList card />}
      {pages && pages.length === 0 && (
        q || tag || mood ? <p className="empty card">No pages match.</p> : (
          <EmptyState Icon={JournalIcon} title="Your journal is empty" action="+ New page" onAction={() => newPage()}>
            Write about a build, a game night or your day - @mention a kit or a game to link them.</EmptyState>
        )
      )}
      {groups.map((g) => (
        <div key={g.name}>
          <h3 className={g.day ? 'section-title day-heading' : 'section-title'}>
            {g.name}
            {g.day && dayMood(g) && <span className={`pill ${dayMood(g).tone}`} title={`Felt ${dayMood(g).label.toLowerCase()}`}>
              {dayMood(g).face} {dayMood(g).label}</span>}
          </h3>
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
          : <span className="journal-thumb emoji" aria-hidden="true">{pageFace(p)}</span>}
        <span className="grow">
          <span className="journal-card-head">
            <span className="item-title">{picture && p.mood ? `${moodOf(p.mood).face} ` : ''}{p.title || 'Untitled'}</span>
            <span className="card-pills">
              <span className={`pill ${KIND_PILL[p.kind][1]}`}>{KIND_PILL[p.kind][0]}</span>
              {p.pinned && <span className="pill low">Pinned</span>}
            </span>
          </span>
          {first && <span className="pill tint">#{first}</span>}
          {p.mood && <span className={`mood-line ${moodOf(p.mood).tone}`}>{moodOf(p.mood).label}
            {p.mood_words.length > 0 && <span className="muted"> · {p.mood_words.join(', ')}</span>}</span>}
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
        <span className="page-icon" aria-hidden="true">{pageFace(p)}</span>
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
