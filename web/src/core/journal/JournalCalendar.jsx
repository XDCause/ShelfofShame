import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, isoDay } from '../../api.js'
import { useApp } from '../app-context.js'
import { useNewPage } from './JournalList.jsx'
import { moodOf } from './moods.js'

const NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const monthKey = (d) => isoDay(d).slice(0, 7)

// Journal > Calendar: a month, each day with its mood face (or a dot for a page without one); a day opens its page,
// an empty day you can still write about starts one. Your writing streak is on top, like Day One's.
export default function JournalCalendar() {
  const { refreshKey } = useApp()
  const newPage = useNewPage()
  const [month, setMonth] = useState(() => monthKey(new Date()))
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.journalCalendar(month).then(setData).catch((e) => setError(e.message)) }, [month, refreshKey])

  const first = new Date(`${month}-01T12:00:00`)
  const shift = (by) => { const d = new Date(first); d.setMonth(d.getMonth() + by); setMonth(monthKey(d)) }
  const lead = (first.getDay() + 6) % 7                  // Monday first
  const length = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate()
  const today = isoDay(new Date())
  const byDay = Object.fromEntries((data?.days ?? []).map((d) => [d.day, d]))
  const s = data?.streak

  return (
    <section className="page">
      {error && <p className="alert error">{error}</p>}
      {s && (
        <div className="jcal-streak card">
          <span className="jcal-streak-big">{s.current > 0 ? '🔥' : '🌱'} {s.current} <small>day{s.current === 1 ? '' : 's'} in a row</small></span>
          <span className="muted">Longest: {s.longest} day{s.longest === 1 ? '' : 's'}</span>
          <span className={s.today ? 'pill ok' : 'pill low'}>{s.today ? 'Written today ✓' : 'Not written today yet'}</span>
          {!s.today && <button type="button" className="primary" onClick={() => newPage()}>Write today</button>}
        </div>
      )}
      <div className="jcal-head">
        <button type="button" className="plain" onClick={() => shift(-1)} aria-label="Previous month">‹</button>
        <h2 className="jcal-title">{first.toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })}</h2>
        <button type="button" className="plain" onClick={() => shift(1)} aria-label="Next month">›</button>
        {month !== monthKey(new Date()) && <button type="button" className="secondary" onClick={() => setMonth(monthKey(new Date()))}>This month</button>}
      </div>
      <div className="jcal-grid" role="group" aria-label="Journal days">
        {NAMES.map((n) => <span key={n} className="jcal-name" aria-hidden="true">{n}</span>)}
        {Array.from({ length: lead }, (_, i) => <span key={`x${i}`} aria-hidden="true" />)}
        {Array.from({ length }, (_, i) => {
          const day = `${month}-${String(i + 1).padStart(2, '0')}`
          const d = byDay[day]
          const mood = moodOf(d?.mood)
          const label = `${i + 1} ${first.toLocaleDateString('en-AU', { month: 'long' })}`
          const cls = `jcal-day${d ? ' written' : ''}${day === today ? ' today' : ''}${mood ? ` ${mood.tone}` : ''}`
          if (d) {
            return (
              <Link key={day} to={`/journal/${d.page_id}`} className={cls}
                aria-label={`${label}: ${d.pages} page${d.pages === 1 ? '' : 's'}${mood ? `, ${mood.label}` : ''}`}>
                <span className="jcal-num">{i + 1}</span>
                <span className="jcal-face" aria-hidden="true">{mood?.face ?? '•'}</span>
                {d.pages > 1 && <span className="jcal-more" aria-hidden="true">+{d.pages - 1}</span>}
              </Link>
            )
          }
          return day <= today ? (
            <button key={day} type="button" className={cls} aria-label={`${label}: write a page`}
              onClick={() => newPage({ entry_date: day })}>
              <span className="jcal-num">{i + 1}</span>
            </button>
          ) : <span key={day} className={`${cls} future`}><span className="jcal-num">{i + 1}</span></span>
        })}
      </div>
      <p className="muted small">A face is that day's mood; a dot, a page without one. Tap an empty day to write about it.</p>
    </section>
  )
}
