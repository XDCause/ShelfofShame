import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, dayDate, isoDay } from '../../api.js'
import { JournalIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import { PageRow } from './JournalList.jsx'
import { OnThisDay } from './JournalExtras.jsx'
import { moodOf } from './moods.js'

// The journal on the Home page: your week's moods, On this day (earlier years' pages) and the latest few pages. (Its to-dos are on Home's To-do card.)
// ("Write today's entry" is in the hero at the top of Home.)
export default function JournalHome() {
  const { refreshKey } = useApp()
  const [pages, setPages] = useState(null)
  useEffect(() => { api.listPages({ limit: 3 }).then(setPages).catch(() => setPages([])) }, [refreshKey])

  return (
    <section className="card home-card" aria-labelledby="home-journal">
      <h2 id="home-journal" className="home-card-title"><JournalIcon size={20} /> Journal
        <Link to="/journal" className="small">All pages →</Link></h2>
      <YourWeek />
      <OnThisDay compact />
      {pages?.length > 0 ? (
        <>
          <h3 className="section-title home-journal-title">Latest pages</h3>
          <ul className="list journal-list">{pages.map((p) => <PageRow key={p.page_id} page={p} />)}</ul>
        </>
      ) : pages && <p className="muted small">No pages yet. "Write today's entry" starts one.</p>}
    </section>
  )
}

// The last seven days, one face each (from that day's page), oldest first. A day with a mood opens
// its page; a day without one opens the calendar on that day.
function YourWeek() {
  const { refreshKey } = useApp()
  const [moods, setMoods] = useState(null)
  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - 6 + i); return isoDay(d) })
  const [start, end] = [days[0], days[6]]
  useEffect(() => {
    api.moods(start, end).then(setMoods).catch(() => setMoods([]))
  }, [refreshKey, start, end])
  if (!moods) return null
  const byDay = Object.fromEntries(moods.map((m) => [m.day, m]))
  return (
    <div className="your-week" role="group" aria-label="Your week">
      {days.map((day) => {
        const m = byDay[day]
        const mood = moodOf(m?.mood)
        const name = dayDate(day).toLocaleDateString('en-AU', { weekday: 'short' })
        return (
          <Link key={day} to={m ? `/journal/${m.page_id}` : `/calendar?day=${day}`}
            className={mood ? `week-day ${mood.tone}` : 'week-day empty'}
            title={mood ? `${name}: ${mood.label}${m.mood_words.length ? ` (${m.mood_words.join(', ')})` : ''}` : `${name}: no mood yet`}>
            <span className="week-face" aria-hidden="true">{mood?.face ?? '·'}</span>
            <span className="week-name">{name}</span>
          </Link>
        )
      })}
    </div>
  )
}
