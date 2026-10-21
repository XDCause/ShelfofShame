import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, dayDate, isoDay, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import { BUILT_IN, promptFor, quote, para, reviewPage, todayPage } from './blocks.js'
import { pageFace } from './moods.js'

// The journal's extras (2026-10-21, from a scan of Day One, Apple Journal, Notion and reMarkable): Write about today,
// On this day, templates, notebooks, a page's place / weather / paper, and a prompt for an empty page.

const weekday = (iso) => dayDate(iso).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'short' })
export const NOTEBOOK_COLOURS = ['teal', 'purple', 'ok', 'low', 'tint', 'out']
export const weatherText = (w) => (w ? `${w.icon ?? ''} ${w.max != null ? `${Math.round(w.max)}°` : ''}${w.min != null ? ` / ${Math.round(w.min)}°` : ''}`.trim() : '')

// "Write about today": what the app saw you do today (every hobby's log), made into a page with one tap - Apple
// Journal's suggestions, from your own hobbies. Hidden on a day with nothing logged.
export function TodayCard({ newPage }) {
  const { refreshKey } = useApp()
  const [today, setToday] = useState(null)
  useEffect(() => { api.journalToday().then(setToday).catch(() => setToday(null)) }, [refreshKey])
  if (!today || today.did.length === 0) return null
  const shown = today.did.slice(0, 5)
  return (
    <section className="card jx-card" aria-labelledby="jx-today">
      <h2 id="jx-today" className="jx-card-title">✍️ Write about today</h2>
      <ul className="jx-did">
        {shown.map((d, i) => (
          <li key={`${d.kind}-${d.ref}-${i}`}>{d.verb} <strong>{d.title}</strong>{d.detail && <span className="muted"> · {d.detail}</span>}</li>
        ))}
        {today.did.length > shown.length && <li className="muted">and {today.did.length - shown.length} more</li>}
      </ul>
      <div className="jx-card-foot">
        <button type="button" className="secondary" onClick={() => newPage({ title: '', content: todayPage(today.did) })}>
          Start a page from today</button>
        {today.pages.length > 0 && (
          <span className="muted small">Written today: {today.pages.map((p, i) => (
            <span key={p.page_id}>{i > 0 && ', '}<Link to={`/journal/${p.page_id}`}>{p.title || 'Untitled'}</Link></span>
          ))}</span>
        )}
      </div>
    </section>
  )
}

// On this day: pages (and what you did) on this date in earlier years. compact: one line each (Home's journal card).
export function OnThisDay({ compact = false }) {
  const { refreshKey } = useApp()
  const [years, setYears] = useState(null)
  useEffect(() => { api.onThisDay().then(setYears).catch(() => setYears([])) }, [refreshKey])
  if (!years?.length) return null
  const ago = (n) => (n === 1 ? 'A year ago' : `${n} years ago`)
  if (compact) {
    return (
      <div className="jx-otd-compact">
        <h3 className="section-title">On this day</h3>
        <ul className="list compact">
          {years.map((y) => (
            <li key={y.day}>
              <span className="muted small">{ago(y.years_ago)}</span>{' '}
              {y.pages[0] ? <Link to={`/journal/${y.pages[0].page_id}`}>{pageFace(y.pages[0])} {y.pages[0].title || 'Untitled'}</Link>
                : <span>{y.did[0].verb} {y.did[0].title}</span>}
            </li>
          ))}
        </ul>
      </div>
    )
  }
  return (
    <section className="card jx-card" aria-labelledby="jx-otd">
      <h2 id="jx-otd" className="jx-card-title">🕰️ On this day</h2>
      {years.map((y) => (
        <div key={y.day} className="jx-otd-year">
          <h3 className="section-title">{ago(y.years_ago)} · {shortDate(y.day)}</h3>
          <ul className="jx-did">
            {y.pages.map((p) => (
              <li key={p.page_id}><Link to={`/journal/${p.page_id}`}>{pageFace(p)} {p.title || 'Untitled'}</Link>
                {p.snippet && <span className="muted"> · {p.snippet.split('\n')[0].slice(0, 90)}</span>}</li>
            ))}
            {y.did.map((d, i) => <li key={`${d.kind}-${i}`}>{d.verb} <strong>{d.title}</strong></li>)}
          </ul>
        </div>
      ))}
    </section>
  )
}

// "Templates": the built-in ones, yours (saved from a page), and a weekly / monthly review made from what you did.
export function TemplateMenu({ newPage }) {
  const { refreshKey, showToast } = useApp()
  const [saved, setSaved] = useState([])
  const menu = useRef(null)
  useEffect(() => { api.journalTemplates().then(setSaved).catch(() => {}) }, [refreshKey])
  const close = () => { if (menu.current) menu.current.open = false }
  const use = (page) => { close(); newPage(page) }
  const review = async (days) => {
    close()
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - (days - 1))
    try {
      const r = await api.journalReview(isoDay(start), isoDay(end))
      const name = days > 7 ? `Month to ${shortDate(isoDay(end))}` : `Week to ${shortDate(isoDay(end))}`
      newPage({ title: `Review: ${name}`, tags: ['review'], content: reviewPage(r, weekday) })
    } catch (e) {
      showToast(`Couldn't make the review: ${e.message}`)
    }
  }
  const remove = async (t) => {
    await api.deleteJournalTemplate(t.template_id)
    setSaved((all) => all.filter((x) => x.template_id !== t.template_id))
  }
  return (
    <details className="jx-menu" ref={menu}>
      <summary className="secondary">Templates ▾</summary>
      <div className="jx-menu-list" role="menu">
        <p className="jx-menu-head">Reviews</p>
        <button type="button" role="menuitem" onClick={() => review(7)}>Weekly review<span>Your week's moods, hobbies and goals</span></button>
        <button type="button" role="menuitem" onClick={() => review(30)}>Monthly review<span>The last 30 days, the same way</span></button>
        <p className="jx-menu-head">Templates</p>
        {BUILT_IN.map((t) => (
          <button key={t.key} type="button" role="menuitem" onClick={() => use(t.make())}>{t.name}<span>{t.hint}</span></button>
        ))}
        {saved.length > 0 && <p className="jx-menu-head">Yours</p>}
        {saved.map((t) => (
          <div key={t.template_id} className="jx-menu-row">
            <button type="button" role="menuitem" onClick={() => use({ title: t.title, content: t.content, tags: t.tags })}>{t.name}</button>
            <button type="button" className="plain jx-menu-x" aria-label={`Delete the ${t.name} template`} onClick={() => remove(t)}>×</button>
          </div>
        ))}
        {saved.length === 0 && <p className="muted small jx-menu-tip">Make your own: open a page, then "Save as template".</p>}
      </div>
    </details>
  )
}

// Notebook chips over the list (All / each one), with an Edit mode to rename, recolour or delete them.
export function NotebookFilter({ notebooks, value, onChange, onChanged }) {
  const [editing, setEditing] = useState(false)
  if (!notebooks.length) return null
  return (
    <div className="chip-row jx-notebooks" role="group" aria-label="Notebooks">
      <button type="button" className="chip-filter" aria-pressed={value == null} onClick={() => onChange(null)}>All notebooks</button>
      {notebooks.map((n) => (
        <button key={n.notebook_id} type="button" className="chip-filter" aria-pressed={value === n.notebook_id}
          onClick={() => onChange(value === n.notebook_id ? null : n.notebook_id)}>
          <i className={`jx-dot ${n.colour}`} aria-hidden="true" />{n.name} <span className="chip-count">{n.pages}</span>
        </button>
      ))}
      <button type="button" className="plain small" aria-expanded={editing} onClick={() => setEditing(!editing)}>{editing ? 'Done' : 'Edit'}</button>
      {editing && (
        <ul className="jx-nb-edit">
          {notebooks.map((n) => <NotebookRow key={n.notebook_id} notebook={n} onChanged={onChanged} />)}
        </ul>
      )}
    </div>
  )
}

function NotebookRow({ notebook: n, onChanged }) {
  const { showToast } = useApp()
  const [name, setName] = useState(n.name)
  const change = async (data) => {
    try { await api.changeNotebook(n.notebook_id, data); onChanged() } catch (e) { showToast(e.message) }
  }
  return (
    <li>
      <input value={name} onChange={(e) => setName(e.target.value)} aria-label="Notebook name" maxLength={40}
        onBlur={() => name.trim() && name.trim() !== n.name && change({ name: name.trim() })} />
      <select value={n.colour} onChange={(e) => change({ colour: e.target.value })} aria-label={`${n.name}'s colour`}>
        {NOTEBOOK_COLOURS.map((c) => <option key={c} value={c}>{c === 'ok' ? 'green' : c === 'low' ? 'amber' : c === 'out' ? 'red' : c === 'tint' ? 'pine' : c}</option>)}
      </select>
      <button type="button" className="plain destructive" onClick={async () => {
        await api.deleteNotebook(n.notebook_id)
        showToast(`${n.name} deleted (its pages are kept).`)
        onChanged()
      }}>Delete</button>
    </li>
  )
}

// A page's notebook: pick one, or make a new one right here.
export function NotebookPicker({ value, onChange }) {
  const { showToast } = useApp()
  const [notebooks, setNotebooks] = useState([])
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  useEffect(() => { api.notebooks().then(setNotebooks).catch(() => {}) }, [])
  const add = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    try {
      const made = await api.addNotebook({ name: name.trim(), colour: NOTEBOOK_COLOURS[notebooks.length % NOTEBOOK_COLOURS.length] })
      setNotebooks((all) => [...all, made])
      onChange(made.notebook_id)
      setAdding(false)
      setName('')
    } catch (err) {
      showToast(err.message)
    }
  }
  if (adding) {
    return (
      <form className="jx-inline-form" onSubmit={add}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Notebook name" aria-label="New notebook's name" maxLength={40} autoFocus />
        <button type="submit" className="secondary">Add</button>
        <button type="button" className="plain" onClick={() => setAdding(false)}>Cancel</button>
      </form>
    )
  }
  return (
    <select className="jx-meta-select" value={value ?? ''} aria-label="Notebook"
      onChange={(e) => (e.target.value === 'new' ? setAdding(true) : onChange(e.target.value ? Number(e.target.value) : null))}>
      <option value="">No notebook</option>
      {notebooks.map((n) => <option key={n.notebook_id} value={n.notebook_id}>📓 {n.name}</option>)}
      <option value="new">+ New notebook…</option>
    </select>
  )
}

// Where a page was written: search a town (Open-Meteo's place names), use home, or remove it.
export function PlacePicker({ page, onChange }) {
  const menu = useRef(null)
  const [q, setQ] = useState('')
  const [found, setFound] = useState([])
  const [home, setHome] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.homePlace().then(setHome).catch(() => {}) }, [])
  const search = async (e) => {
    e.preventDefault()
    setError('')
    try { setFound(await api.gardenPlaces(q)) } catch (err) { setError(err.message) }
  }
  const pick = (place) => {
    if (menu.current) menu.current.open = false
    onChange(place ? { place_name: place.place_name ?? place.name, lat: place.lat, lon: place.lon } : { place_name: null, lat: null, lon: null })
  }
  return (
    <details className="jx-pop" ref={menu}>
      <summary className="chip jx-meta-chip">{page.place_name ? `📍 ${page.place_name}` : '+ Place'}</summary>
      <div className="jx-pop-body">
        {home && <button type="button" className="secondary" onClick={() => pick(home)}>📍 Home ({home.place_name})</button>}
        <form className="jx-inline-form" onSubmit={search}>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Town or suburb" aria-label="Find a place" />
          <button type="submit" className="secondary">Find</button>
        </form>
        {error && <p className="alert error small">{error}</p>}
        {found.length > 0 && (
          <ul className="jx-pop-list">
            {found.map((p) => (
              <li key={`${p.lat},${p.lon}`}><button type="button" className="plain" onClick={() => pick(p)}>{p.name}<span className="muted small"> {p.region}</span></button></li>
            ))}
          </ul>
        )}
        {page.place_name && <button type="button" className="plain destructive" onClick={() => pick(null)}>Remove the place</button>}
      </div>
    </details>
  )
}

// That day's weather where the page was written (or at home): one tap to add it.
export function WeatherChip({ page, onStamped }) {
  const { showToast } = useApp()
  const [busy, setBusy] = useState(false)
  if (page.weather) {
    const w = page.weather
    return (
      <span className="chip jx-meta-chip" title={`${w.sky ?? ''}${w.rain_mm ? `, ${w.rain_mm} mm of rain` : ''} (weather: Open-Meteo, CC BY 4.0)`}>
        {weatherText(w)}</span>
    )
  }
  return (
    <button type="button" className="chip jx-meta-chip" disabled={busy} onClick={async () => {
      setBusy(true)
      try { onStamped(await api.stampWeather(page.page_id)) } catch (e) { showToast(e.message) } finally { setBusy(false) }
    }}>{busy ? 'Asking…' : '+ Weather'}</button>
  )
}

export const PAPERS = [['plain', 'Plain'], ['lined', 'Lined'], ['grid', 'Grid'], ['dot', 'Dot']]

// A question for an empty page: today's (the same all day), Shuffle for another, "Write about this" to start with it.
export function PromptCard({ day, onUse }) {
  const [shift, setShift] = useState(0)
  const prompt = promptFor(day, shift)
  return (
    <aside className="jx-prompt" aria-label="A prompt">
      <span className="jx-prompt-label">💭 A prompt</span>
      <p className="jx-prompt-text">{prompt}</p>
      <div className="jx-prompt-actions">
        <button type="button" className="secondary" onClick={() => onUse([quote(prompt), para()])}>Write about this</button>
        <button type="button" className="plain" onClick={() => setShift(shift + 1)}>Shuffle</button>
      </div>
    </aside>
  )
}
