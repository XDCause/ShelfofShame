import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, clock, dayDate, isoDay, today } from '../../api.js'
import { ChevronIcon } from '../../components/icons.jsx'
import { KIND_ICON, VERB_TONE } from '../activityKinds.js'
import { useApp } from '../app-context.js'
import { useNewPage } from '../journal/JournalList.jsx'
import { moodOf } from '../journal/moods.js'
import {
  BalanceCard, Countdowns, DRAG_TYPE, EventSearch, HOBBY_TONE, KIND_TONE, LayersMenu, QuickAdd, WEEKDAYS, hobbyName, isLogged,
  isoWeek, repeatText, useDropOnDay, useEventWeather, useLayers, useLogIt, weatherLine,
} from './calendarParts.jsx'
import { AgendaView, ToPlan, WeekView, YearView } from './CalendarViews.jsx'

const VIEWS = [['month', 'Month'], ['week', 'Week'], ['agenda', 'Agenda'], ['year', 'Year']]
// what each activity kind belongs to (for hiding a hobby's "what happened")
const KIND_HOBBY = { model: 'models', game: 'boardgames', volleyball: 'volleyball', videogame: 'videogames', chess: 'chess', book: 'reading',
  trip: 'travel', shoot: 'shooting', hike: 'hiking', planting: 'gardening', gcontainer: 'gardening', gspace: 'gardening' }
const longDay = (iso) => dayDate(iso).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })
const plus = (iso, n) => { const d = dayDate(iso); d.setDate(d.getDate() + n); return isoDay(d) }

// The six weeks (Monday first) that show a month.
function gridFor(month) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1, 12)
  const start = new Date(first)
  start.setDate(1 - ((first.getDay() + 6) % 7))
  return Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d })
}

// The calendar (core): Month, Week, Agenda or Year (?view=), a chosen day (?day=), what's shown (Show ▾), quick add in
// plain words, search, countdowns; events and to-dos drag to another day (the week: another time too).
export default function CalendarPage() {
  const [params, setParams] = useSearchParams()
  const view = params.get('view') ?? 'month'
  const selected = params.get('day') ?? today()
  const { refreshKey, openPanel } = useApp()
  const layers = useLayers()
  const weather = useEventWeather(layers.on('weather'))
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const monthDays = useMemo(() => gridFor(dayDate(`${selected.slice(0, 7)}-01`)), [selected])
  const [start, end] = view === 'week' ? [isoWeek(selected)[0], isoWeek(selected)[6]]
    : view === 'agenda' ? [selected, plus(selected, 59)] : [isoDay(monthDays[0]), isoDay(monthDays.at(-1))]
  useEffect(() => {
    if (view === 'year') return
    api.calendar(start, end).then((d) => { setData(d); setError('') }).catch((e) => setError(e.message))
  }, [start, end, view, refreshKey])

  // Everything by day, with the layers and hobbies you've hidden left out.
  const byDay = useMemo(() => {
    const map = {}
    const at = (day) => (map[day] ??= { events: [], happened: [], todos: [], goals: [], holidays: [] })
    if (layers.on('planned')) for (const e of data?.events ?? []) if (layers.hobbyOn(e.hobby)) at(e.day).events.push(e)
    for (const h of data?.happened ?? []) if (layers.hobbyOn(KIND_HOBBY[h.kind])) at(h.day).happened.push(h)
    if (layers.on('moods')) for (const m of data?.moods ?? []) at(m.day).mood = m
    if (layers.on('todos')) for (const t of data?.todos ?? []) if (layers.hobbyOn(t.hobby)) at(t.plan_on ?? t.due_on).todos.push(t)
    if (layers.on('goals')) for (const g of data?.goals ?? []) if (layers.hobbyOn(g.hobby)) at(g.day).goals.push(g)
    if (layers.on('holidays')) for (const h of data?.holidays ?? []) at(h.day).holidays.push(h)
    for (const d of Object.values(map)) d.happened.reverse()     // oldest first within the day
    return map
  }, [data, layers])
  const showHappened = layers.on('happened')

  const set = (next) => setParams((p) => {
    const n = new URLSearchParams(p)
    for (const [k, v] of Object.entries(next)) { if (v == null || (k === 'day' && v === today()) || (k === 'view' && v === 'month')) n.delete(k); else n.set(k, v) }
    return n
  }, { replace: true })
  const pick = (iso) => set({ day: iso })
  const shift = (n) => {
    const d = dayDate(selected)
    if (view === 'month') pick(isoDay(new Date(d.getFullYear(), d.getMonth() + n, 1, 12)))
    else if (view === 'year') pick(`${d.getFullYear() + n}-01-01`)
    else pick(plus(selected, n * (view === 'week' ? 7 : 30)))
  }
  const d0 = dayDate(selected)
  const title = view === 'year' ? String(d0.getFullYear())
    : view === 'week' ? `${dayDate(start).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })} – ${dayDate(end).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}`
      : view === 'agenda' ? `From ${dayDate(selected).toLocaleDateString('en-AU', { day: 'numeric', month: 'long' })}`
        : d0.toLocaleDateString('en-AU', { month: 'long', year: 'numeric' })
  const unit = { month: 'month', week: 'week', agenda: '30 days', year: 'year' }[view]

  return (
    <section className="page calendar">
      {/* the views as tabs on the banner's foot, like Goals' and the Journal's (styles.css .section-tabs) */}
      <nav className="section-tabs segmented" aria-label="Calendar views">
        {VIEWS.map(([id, label]) => {
          const q = new URLSearchParams(params)
          if (id === 'month') q.delete('view'); else q.set('view', id)
          return <Link key={id} to={`/calendar${q.size ? `?${q}` : ''}`} replace aria-current={view === id ? 'page' : undefined}>{label}</Link>
        })}
      </nav>
      <div className="toolbar calendar-head">
        <h2 className="calendar-month">{title}</h2>
        <div className="button-row">
          <button type="button" className="icon-btn" aria-label={`Previous ${unit}`} onClick={() => shift(-1)}>
            <ChevronIcon size={18} style={{ transform: 'scaleX(-1)' }} /></button>
          <button type="button" className="secondary" onClick={() => pick(today())}>Today</button>
          <button type="button" className="icon-btn" aria-label={`Next ${unit}`} onClick={() => shift(1)}><ChevronIcon size={18} /></button>
          <LayersMenu layers={layers} />
          <button type="button" className="primary" onClick={() => openPanel('event', { day: selected })}>+ Add event</button>
        </div>
      </div>
      {/* the same two columns as the calendar below: quick add over the grid, search over the side */}
      <div className={`cal-tools${view === 'week' ? ' week' : ''}${view === 'year' ? ' year' : ''}`}>
        <QuickAdd />
        <EventSearch onPick={(e) => { set({ day: e.day, view: view === 'year' ? 'month' : view }); openPanel('event', { id: e.event_id, day: e.day }) }} />
      </div>
      <Countdowns />
      {error && <p className="alert error">{error}</p>}

      {view === 'year' ? <YearView year={d0.getFullYear()} onPick={(iso) => set({ day: iso, view: 'month' })} />
        : view === 'agenda' ? (
          <div className="calendar-layout">
            <AgendaView start={selected} days={60} byDay={byDay} weather={weather} showHappened={showHappened} />
            <div className="cal-side"><BalanceCard start={isoWeek(today())[0]} end={isoWeek(today())[6]} /><ToPlan /></div>
          </div>
        ) : view === 'week' ? (
          <>
            <div className="calendar-layout week">
              <WeekView days={isoWeek(selected)} byDay={byDay} weather={weather} selected={selected} onPick={pick} />
              <div className="cal-side cal-side-fit">
                <DayDetail day={selected} chosen={byDay[selected]} weather={weather} showHappened={showHappened} />
              </div>
            </div>
            <div className="cal-below">
              <ToPlan />
              <BalanceCard start={start} end={end} label={start === isoWeek(today())[0] ? 'This week' : 'That week'} />
            </div>
          </>
        ) : (
          <>
            {/* the day's card is as tall as the month and scrolls inside (user, 2026-10-21) */}
            <div className="calendar-layout">
              <MonthGrid days={monthDays} month={d0.getMonth()} selected={selected} byDay={byDay} weather={weather}
                showHappened={showHappened} onPick={pick} />
              <div className="cal-side cal-side-fit">
                <DayDetail day={selected} chosen={byDay[selected]} weather={weather} showHappened={showHappened} />
              </div>
            </div>
            <div className="cal-below"><ToPlan /></div>
          </>
        )}
    </section>
  )
}

// The month: each day with its mood, holidays, events (drag one to another day), to-dos and goals, and what happened.
function MonthGrid({ days, month, selected, byDay, weather, showHappened, onPick }) {
  const drop = useDropOnDay()
  const [over, setOver] = useState(null)
  return (
    <div className="month card" role="group" aria-label="Month">
      {WEEKDAYS.map((w) => <span key={w} className="weekday" aria-hidden="true">{w}</span>)}
      {days.map((d) => {
        const iso = isoDay(d)
        const day = byDay[iso]
        const kinds = showHappened ? [...new Set(day?.happened.map((h) => h.kind) ?? [])] : []
        const items = [...(day?.events ?? []).map((e) => ({ e })), ...(day?.todos ?? []).map((t) => ({ t }))]
        return (
          <button key={iso} type="button" aria-pressed={iso === selected}
            className={['day', d.getMonth() !== month && 'other', iso === today() && 'today', over === iso && 'drop-here', day?.holidays.length && 'holiday'].filter(Boolean).join(' ')}
            onClick={() => onPick(iso)}
            onDragOver={(ev) => { if (ev.dataTransfer.types.includes(DRAG_TYPE)) { ev.preventDefault(); setOver(iso) } }}
            onDragLeave={() => setOver((o) => (o === iso ? null : o))}
            onDrop={(ev) => { ev.preventDefault(); setOver(null); drop(JSON.parse(ev.dataTransfer.getData(DRAG_TYPE)), iso) }}
            aria-label={`${d.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}${day?.holidays.length ? `, ${day.holidays[0].name}` : ''}${day?.events.length ? `, ${day.events.length} planned` : ''}`}>
            <span className="day-top">
              <span className="day-num">{d.getDate()}</span>
              {day?.goals.length > 0 && <span className="day-flag" title={day.goals.map((g) => `Goal ends: ${g.title}`).join('\n')}>🏁</span>}
              {day?.mood && <span className="day-mood" title={moodOf(day.mood.mood).label}>{moodOf(day.mood.mood).face}</span>}
            </span>
            {day?.holidays.length > 0 && <span className="day-holiday">{day.holidays[0].name}</span>}
            {items.slice(0, 2).map(({ e, t }) => (e ? (
              <span key={`e${e.event_id}`} className={`day-event ${HOBBY_TONE[e.hobby] ?? 'tint'}${e.start_time ? '' : ' all-day'}`}
                draggable={!e.trip_id} onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'event', id: e.event_id, from: iso, repeats: e.repeats !== 'never' }))}>
                {e.start_time && <span className="day-time">{clock(e.start_time)}</span>} {e.title}
                {weather[`${e.event_id}:${iso}`] && <span className="day-weather"> {weather[`${e.event_id}:${iso}`].icon}</span>}
              </span>
            ) : (
              <span key={`t${t.todo_id}`} className={`day-todo${t.done ? ' done' : ''}`} draggable={!t.done}
                onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'todo', id: t.todo_id, minutes: t.plan_minutes }))}>
                {t.done ? '☑' : '☐'} {t.title}
              </span>
            )))}
            {items.length > 2 && <span className="day-more">+{items.length - 2} more</span>}
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
  )
}

// The chosen day in full: holidays, mood, what's planned (weather, Log it), to-dos, goals ending, what happened.
export function DayDetail({ day: selected, chosen = { events: [], happened: [], todos: [], goals: [], holidays: [] }, weather, showHappened }) {
  const { openPanel, openThing } = useApp()
  const newPage = useNewPage()
  const logIt = useLogIt()
  return (
    <aside className="card day-detail" aria-label="The chosen day">
      <h3 className="home-card-title">{longDay(selected)}</h3>
      {chosen.holidays?.map((h) => <p key={h.name} className="pill teal cal-holiday-pill">🎉 {h.name}</p>)}
      {chosen.mood && (
        <p className={`mood-line ${moodOf(chosen.mood.mood).tone}`}>
          {moodOf(chosen.mood.mood).face} Felt {moodOf(chosen.mood.mood).label.toLowerCase()}
          {chosen.mood.mood_words.length > 0 && <span className="muted"> · {chosen.mood.mood_words.join(', ')}</span>}
        </p>
      )}
      <h4 className="section-title">Planned</h4>
      {chosen.events.length === 0 ? <p className="muted small">Nothing planned.</p> : (
        <ul className="list plain-list">
          {chosen.events.map((e) => {
            const w = weather[`${e.event_id}:${selected}`]
            const logged = e.hobby && isLogged(e, chosen.happened)
            return (
              <li key={`${e.event_id}`} className="cal-planned">
                <button type="button" className="row-button" onClick={() => (e.trip_id ? openPanel('trip', { id: e.trip_id }) : openPanel('event', { id: e.event_id, day: selected }))}>
                  <span className={`time-block ${HOBBY_TONE[e.hobby] ?? 'tint'}`}>{e.start_time ? clock(e.start_time) : 'All day'}</span>
                  <span className="grow">
                    <span className="item-title">{e.title}</span>
                    <span className="item-meta">{[e.end_time && `until ${clock(e.end_time)}`, e.location, hobbyName(e.hobby),
                      e.repeats && e.repeats !== 'never' && repeatText(e), w && weatherLine(w),
                      e.checklist?.length > 0 && `${e.checklist.filter((c) => c.done).length}/${e.checklist.length} packed`].filter(Boolean).join(' · ')}</span>
                  </span>
                </button>
                {e.hobby && !e.trip_id && selected <= today() && (logged
                  ? <span className="pill ok">Logged ✓</span>
                  : <button type="button" className="secondary small" onClick={() => logIt(e, selected)}>Log it</button>)}
              </li>
            )
          })}
        </ul>
      )}
      {chosen.todos?.length > 0 && <>
        <h4 className="section-title">To-dos</h4>
        <ul className="list plain-list">
          {chosen.todos.map((t) => (
            <li key={t.todo_id}>
              <button type="button" className="row-button" onClick={() => openPanel('todo', { id: t.todo_id })}>
                <span className="cal-todo-box" aria-hidden="true">{t.done ? '☑' : '☐'}</span>
                <span className="grow"><span className={`item-title${t.done ? ' muted' : ''}`}>{t.title}</span>
                  <span className="item-meta">{t.plan_on === selected ? `Planned${t.plan_time ? ` ${clock(t.plan_time)}` : ''}` : 'Due'}{t.hobby ? ` · ${hobbyName(t.hobby)}` : ''}</span></span>
              </button>
            </li>
          ))}
        </ul>
      </>}
      {chosen.goals?.length > 0 && <>
        <h4 className="section-title">Goals ending</h4>
        <ul className="list plain-list">
          {chosen.goals.map((g) => <li key={g.goal_id}><Link to={`/goals/${g.goal_id}`}>🏁 {g.title}</Link>{g.status === 'done' && <span className="pill ok"> Reached</span>}</li>)}
        </ul>
      </>}
      {showHappened && <>
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
      </>}
      <div className="button-row day-actions">
        <button type="button" className="secondary" onClick={() => openPanel('event', { day: selected })}>+ Event on this day</button>
        <button type="button" className="plain" onClick={() => newPage({ title: longDay(selected), entry_date: selected })}>Write about this day</button>
      </div>
    </aside>
  )
}

// Home: what you're counting down to, then the next few things on the calendar.
export function ComingUp() {
  const { refreshKey, openPanel } = useApp()
  const [events, setEvents] = useState(null)
  useEffect(() => { api.upcoming(4).then(setEvents).catch(() => setEvents([])) }, [refreshKey])
  return (
    <section className="card home-card" aria-labelledby="home-coming">
      <h2 id="home-coming" className="home-card-title">Coming up
        <Link to="/calendar" className="small">Calendar →</Link></h2>
      <Countdowns compact />
      {!events ? <p className="muted small">Loading...</p> : events.length === 0 ? (
        <p className="muted small">Nothing planned. <button type="button" className="plain small" onClick={() => openPanel('event', {})}>Add an event</button></p>
      ) : (
        <ul className="list plain-list">
          {events.map((e) => {
            const d = dayDate(e.day)
            return (
              <li key={`${e.event_id}-${e.day}`}>
                <button type="button" className="row-button" onClick={() => (e.trip_id ? openPanel('trip', { id: e.trip_id }) : openPanel('event', { id: e.event_id, day: e.day }))}>
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
