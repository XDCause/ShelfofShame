import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, clock, dayDate, isoDay, today } from '../../api.js'
import { ChevronIcon } from '../../components/icons.jsx'
import { MODULES } from '../../modules/index.js'
import { KIND_ICON, VERB_TONE } from '../activityKinds.js'
import { useApp } from '../app-context.js'
import { useNewPage } from '../journal/JournalList.jsx'
import { moodOf } from '../journal/moods.js'

// Colours: planned events by hobby, what happened by kind (dots) and verb (like Recent activity).
const HOBBY_TONE = { models: 'purple', boardgames: 'teal', volleyball: 'low', videogames: 'purple', chess: 'tint', reading: 'low', car: 'ok', travel: 'teal', shooting: 'out' }
const KIND_TONE = { model: 'purple', supply: 'ok', page: 'teal', game: 'teal', volleyball: 'low', gear: 'ok', videogame: 'purple',
  chess: 'tint', book: 'low', goal: 'ok' }
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const hobbyName = (id) => MODULES.find((m) => m.id === id)?.name

// The six weeks (Monday first) that show a month.
function gridFor(month) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1, 12)
  const start = new Date(first)
  start.setDate(1 - ((first.getDay() + 6) % 7))
  return Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d })
}

// The calendar (core): a month of planned events and what happened, then the chosen day in full.
// ?day=YYYY-MM-DD picks the day (and so the month), so a day can be linked to.
export default function CalendarPage() {
  const { refreshKey, openPanel, openThing } = useApp()
  const newPage = useNewPage()
  const [params, setParams] = useSearchParams()
  const selected = params.get('day') ?? today()
  const month = dayDate(selected)
  const monthKey = selected.slice(0, 7)                                   // YYYY-MM
  const days = useMemo(() => gridFor(dayDate(`${monthKey}-01`)), [monthKey])
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const start = isoDay(days[0])
  const end = isoDay(days.at(-1))
  useEffect(() => {
    api.calendar(start, end).then((d) => { setData(d); setError('') }).catch((e) => setError(e.message))
  }, [start, end, refreshKey])

  const byDay = useMemo(() => {
    const map = {}
    for (const e of data?.events ?? []) (map[e.day] ??= { events: [], happened: [] }).events.push(e)
    for (const h of data?.happened ?? []) (map[h.day] ??= { events: [], happened: [] }).happened.push(h)
    for (const m of data?.moods ?? []) (map[m.day] ??= { events: [], happened: [] }).mood = m
    for (const d of Object.values(map)) d.happened.reverse() // oldest first within the day
    return map
  }, [data])

  const pick = (iso) => setParams(iso === today() ? {} : { day: iso }, { replace: true })
  const shiftMonth = (n) => {
    const d = new Date(month.getFullYear(), month.getMonth() + n, 1, 12)
    pick(isoDay(d))
  }
  const chosen = byDay[selected] ?? { events: [], happened: [] }

  return (
    <section className="page calendar">
      <div className="toolbar calendar-head">
        <h2 className="calendar-month">{month.toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })}</h2>
        <div className="button-row">
          <button type="button" className="icon-btn" aria-label="Previous month" onClick={() => shiftMonth(-1)}>
            <ChevronIcon size={18} style={{ transform: 'scaleX(-1)' }} /></button>
          <button type="button" className="secondary" onClick={() => pick(today())}>Today</button>
          <button type="button" className="icon-btn" aria-label="Next month" onClick={() => shiftMonth(1)}><ChevronIcon size={18} /></button>
          <button type="button" className="primary" onClick={() => openPanel('event', { day: selected })}>+ Add event</button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}

      <div className="calendar-layout">
        <div className="month card" role="grid" aria-label="Month">
          {WEEKDAYS.map((w) => <span key={w} className="weekday" role="columnheader">{w}</span>)}
          {days.map((d) => {
            const iso = isoDay(d)
            const day = byDay[iso]
            const kinds = [...new Set(day?.happened.map((h) => h.kind) ?? [])]
            return (
              <button key={iso} type="button" role="gridcell" aria-selected={iso === selected}
                className={['day', d.getMonth() !== month.getMonth() && 'other', iso === today() && 'today'].filter(Boolean).join(' ')}
                onClick={() => pick(iso)} aria-label={`${d.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}${day?.events.length ? `, ${day.events.length} planned` : ''}`}>
                <span className="day-top">
                  <span className="day-num">{d.getDate()}</span>
                  {day?.mood && <span className="day-mood" title={moodOf(day.mood.mood).label}>{moodOf(day.mood.mood).face}</span>}
                </span>
                {day?.events.slice(0, 2).map((e) => (
                  <span key={`${e.event_id}`} className={`day-event ${HOBBY_TONE[e.hobby] ?? 'tint'}${e.start_time ? '' : ' all-day'}`}>
                    {e.start_time && <span className="day-time">{clock(e.start_time)}</span>} {e.title}
                  </span>
                ))}
                {day?.events.length > 2 && <span className="day-more">+{day.events.length - 2} more</span>}
                {kinds.length > 0 && (
                  <span className="day-dots" aria-hidden="true">
                    {kinds.slice(0, 4).map((k) => {
                      const Icon = KIND_ICON[k]
                      return Icon ? <span key={k} className={`day-icon ${KIND_TONE[k] ?? ''}`}><Icon size={12} /></span>
                        : <span key={k} className={`dot ${KIND_TONE[k] ?? ''}`} />
                    })}
                    {kinds.length > 4 && <span className="day-more-kinds">+{kinds.length - 4}</span>}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <aside className="card day-detail" aria-label="The chosen day">
          <h3 className="home-card-title">{dayDate(selected).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</h3>
          {chosen.mood && (
            <p className={`mood-line ${moodOf(chosen.mood.mood).tone}`}>
              {moodOf(chosen.mood.mood).face} Felt {moodOf(chosen.mood.mood).label.toLowerCase()}
              {chosen.mood.mood_words.length > 0 && <span className="muted"> · {chosen.mood.mood_words.join(', ')}</span>}
            </p>
          )}
          <h4 className="section-title">Planned</h4>
          {chosen.events.length === 0 ? <p className="muted small">Nothing planned.</p> : (
            <ul className="list plain-list">
              {chosen.events.map((e) => (
                <li key={e.event_id}>
                  <button type="button" className="row-button" onClick={() => openPanel('event', { id: e.event_id, day: selected })}>
                    <span className={`time-block ${HOBBY_TONE[e.hobby] ?? 'tint'}`}>{e.start_time ? clock(e.start_time) : 'All day'}</span>
                    <span className="grow">
                      <span className="item-title">{e.title}</span>
                      <span className="item-meta">{[e.end_time && `until ${clock(e.end_time)}`, e.location, hobbyName(e.hobby),
                        e.repeats !== 'never' && (e.repeats === 'weekly' ? 'every week' : 'every two weeks')].filter(Boolean).join(' · ')}</span>
                    </span>
                    {e.hobby === 'volleyball' && (e.logged_id ? <span className="pill ok">Result in ✓</span>
                      : selected <= today() && <span className="pill low">Log the result</span>)}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h4 className="section-title">What happened</h4>
          {chosen.happened.length === 0 ? <p className="muted small">{selected > today() ? 'Not yet.' : 'Nothing recorded.'}</p> : (
            <ul className="list plain-list">
              {chosen.happened.map((h, i) => {
                const Icon = KIND_ICON[h.kind]
                return (
                  <li key={`${h.kind}-${h.ref}-${h.verb}-${i}`}>
                    <button type="button" className="row-button" onClick={() => openThing(h.kind, h.ref)} disabled={!h.ref}>
                      {h.photo_url ? <img className="thumb" src={h.photo_url} alt="" loading="lazy" />
                        : <span className={`thumb thumb-icon ${VERB_TONE[h.verb]}`} aria-hidden="true"><Icon size={20} /></span>}
                      <span className="grow">
                        <span className="item-title">{h.title}</span>
                        {h.detail && <span className="item-meta">{h.detail}</span>}
                      </span>
                      <span className={`pill ${VERB_TONE[h.verb]}`}>{h.verb}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          <div className="button-row day-actions">
            <button type="button" className="secondary" onClick={() => openPanel('event', { day: selected })}>+ Event on this day</button>
            <button type="button" className="plain" onClick={() => newPage({
              title: dayDate(selected).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' }),
              entry_date: selected,
            })}>Write about this day</button>
          </div>
        </aside>
      </div>
    </section>
  )
}

// Home: the next few things on the calendar.
export function ComingUp() {
  const { refreshKey, openPanel } = useApp()
  const [events, setEvents] = useState(null)
  useEffect(() => { api.upcoming(4).then(setEvents).catch(() => setEvents([])) }, [refreshKey])
  return (
    <section className="card home-card" aria-labelledby="home-coming">
      <h2 id="home-coming" className="home-card-title">Coming up
        <Link to="/calendar" className="small">Calendar →</Link></h2>
      {!events ? <p className="muted small">Loading...</p> : events.length === 0 ? (
        <p className="muted small">Nothing planned. <button type="button" className="plain small" onClick={() => openPanel('event', {})}>Add an event</button></p>
      ) : (
        <ul className="list plain-list">
          {events.map((e) => {
            const d = dayDate(e.day)
            return (
              <li key={`${e.event_id}-${e.day}`}>
                <button type="button" className="row-button" onClick={() => openPanel('event', { id: e.event_id, day: e.day })}>
                  <span className={`date-chip ${HOBBY_TONE[e.hobby] ?? 'tint'}`}>
                    <small>{d.toLocaleDateString('en-AU', { weekday: 'short' })}</small><strong>{d.getDate()}</strong>
                  </span>
                  <span className="grow">
                    <span className="item-title">{e.title}</span>
                    <span className="item-meta">{[e.day === today() ? 'Today' : null, e.start_time ? clock(e.start_time) : 'All day', e.location].filter(Boolean).join(' · ')}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
