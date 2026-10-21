import { useEffect, useMemo, useState } from 'react'
import { api, clock, dayDate, isoDay, today } from '../../api.js'
import { useApp } from '../app-context.js'
import { moodOf } from '../journal/moods.js'
import { DRAG_TYPE, HOBBY_TONE, WEEKDAYS, hobbyName, isLogged, repeatText, useDropOnDay, useLogIt, weatherLine } from './calendarParts.jsx'

const FIRST_HOUR = 6
const LAST_HOUR = 23
const HOUR_PX = 44
const mins = (t) => { if (!t) return null; const [h, m] = t.split(':').map(Number); return h * 60 + m }
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
const dayLabel = (iso) => (iso === today() ? 'Today' : dayDate(iso).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' }))

// Timed things in a day, each given a lane so ones that overlap sit side by side.
function lanes(items) {
  const sorted = [...items].sort((a, b) => a.start - b.start)
  const ends = []
  for (const it of sorted) {
    let lane = ends.findIndex((end) => end <= it.start)
    if (lane < 0) { lane = ends.length; ends.push(0) }
    ends[lane] = it.end
    it.lane = lane
  }
  return { items: sorted, count: Math.max(1, ends.length) }
}

// The week: seven days of hours (6 am - 11 pm). Drag an event to another day or time (its length stays), or a to-do
// from "To plan" onto a time to block it out. All-day things, holidays, goals and undated to-dos sit along the top.
export function WeekView({ days, byDay, weather, selected, onPick }) {
  const { openPanel } = useApp()
  const drop = useDropOnDay()
  const [now, setNow] = useState(() => new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 60000); return () => clearInterval(t) }, [])
  const hours = Array.from({ length: LAST_HOUR - FIRST_HOUR + 1 }, (_, i) => FIRST_HOUR + i)
  const at = (ev) => {
    const box = ev.currentTarget.getBoundingClientRect()
    const m = FIRST_HOUR * 60 + Math.round(((ev.clientY - box.top) / HOUR_PX) * 4) * 15
    return Math.max(0, Math.min(23 * 60 + 45, m))
  }
  const onDrop = (ev, day) => {
    ev.preventDefault()
    const payload = JSON.parse(ev.dataTransfer.getData(DRAG_TYPE))
    const start = at(ev)
    const end = payload.minutes ? Math.min(23 * 60 + 59, start + payload.minutes) : null
    drop(payload, day, { start: hhmm(start), end: payload.kind === 'event' && end ? hhmm(end) : null })
  }
  return (
    <div className="card cal-week" role="group" aria-label="Week">
      <div className="cal-week-head">
        <span />
        {days.map((iso, i) => (
          <button key={iso} type="button" className={`cal-week-day${iso === selected ? ' on' : ''}${iso === today() ? ' today' : ''}`} onClick={() => onPick(iso)}
            aria-pressed={iso === selected}>
            <small>{WEEKDAYS[i]}</small><strong>{dayDate(iso).getDate()}</strong>
            {byDay[iso]?.mood && <span aria-hidden="true">{moodOf(byDay[iso].mood.mood).face}</span>}
          </button>
        ))}
      </div>
      <div className="cal-week-allday">
        <span className="cal-week-hour muted small">All day</span>
        {days.map((iso) => {
          const d = byDay[iso] ?? {}
          return (
            <div key={iso} className="cal-week-allday-cell" onDragOver={(ev) => ev.dataTransfer.types.includes(DRAG_TYPE) && ev.preventDefault()}
              onDrop={(ev) => { ev.preventDefault(); drop(JSON.parse(ev.dataTransfer.getData(DRAG_TYPE)), iso) }}>
              {d.holidays?.map((h) => <span key={h.name} className="cal-chip teal">🎉 {h.name}</span>)}
              {d.goals?.map((g) => <span key={g.goal_id} className="cal-chip ok">🏁 {g.title}</span>)}
              {d.events?.filter((e) => !e.start_time).map((e) => (
                <button key={e.event_id} type="button" className={`cal-chip ${HOBBY_TONE[e.hobby] ?? 'tint'}`} draggable={!e.trip_id}
                  onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'event', id: e.event_id, from: iso, repeats: e.repeats !== 'never' }))}
                  onClick={() => (e.trip_id ? openPanel('trip', { id: e.trip_id }) : openPanel('event', { id: e.event_id, day: iso }))}>{e.title}</button>
              ))}
              {d.todos?.filter((t) => !t.plan_time).map((t) => (
                <button key={t.todo_id} type="button" className={`cal-chip todo${t.done ? ' done' : ''}`} draggable={!t.done}
                  onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'todo', id: t.todo_id, minutes: t.plan_minutes ?? 60 }))}
                  onClick={() => openPanel('todo', { id: t.todo_id })}>{t.done ? '☑' : '☐'} {t.title}</button>
              ))}
            </div>
          )
        })}
      </div>
      <div className="cal-week-body" style={{ '--hour': `${HOUR_PX}px` }}>
        <div className="cal-week-hours" aria-hidden="true">
          {hours.map((h) => <span key={h}>{clock(`${h}:00`)}</span>)}
        </div>
        {days.map((iso) => {
          const d = byDay[iso] ?? {}
          const timed = [
            ...(d.events ?? []).filter((e) => e.start_time).map((e) => ({ e, start: mins(e.start_time), end: mins(e.end_time) ?? mins(e.start_time) + 60 })),
            ...(d.todos ?? []).filter((t) => t.plan_time).map((t) => ({ t, start: mins(t.plan_time), end: mins(t.plan_time) + (t.plan_minutes ?? 60) })),
          ]
          const { items, count } = lanes(timed)
          const nowMin = now.getHours() * 60 + now.getMinutes()
          return (
            <div key={iso} className={`cal-week-col${iso === today() ? ' today' : ''}`} onDragOver={(ev) => ev.dataTransfer.types.includes(DRAG_TYPE) && ev.preventDefault()}
              onDrop={(ev) => onDrop(ev, iso)} aria-label={dayLabel(iso)} role="group">
              {iso === isoDay(now) && nowMin >= FIRST_HOUR * 60 && (
                <span className="cal-week-now" style={{ top: `${((nowMin - FIRST_HOUR * 60) / 60) * HOUR_PX}px` }} aria-hidden="true" />
              )}
              {items.map(({ e, t, start, end, lane }) => {
                const top = (Math.max(start, FIRST_HOUR * 60) - FIRST_HOUR * 60) / 60 * HOUR_PX
                const height = Math.max(22, ((end - Math.max(start, FIRST_HOUR * 60)) / 60) * HOUR_PX - 2)
                const style = { top: `${top}px`, height: `${height}px`, left: `${(lane / count) * 100}%`, width: `calc(${100 / count}% - 3px)` }
                if (t) {
                  return (
                    <button key={`t${t.todo_id}`} type="button" className={`cal-block todo${t.done ? ' done' : ''}`} style={style} draggable={!t.done}
                      onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'todo', id: t.todo_id, minutes: t.plan_minutes ?? 60 }))}
                      onClick={() => openPanel('todo', { id: t.todo_id })}>
                      <strong>{t.done ? '☑' : '☐'} {t.title}</strong><span>{clock(t.plan_time)}</span>
                    </button>
                  )
                }
                const w = weather[`${e.event_id}:${iso}`]
                return (
                  <button key={`e${e.event_id}`} type="button" className={`cal-block ${HOBBY_TONE[e.hobby] ?? 'tint'}`} style={style} draggable={!e.trip_id}
                    onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'event', id: e.event_id, from: iso,
                      repeats: e.repeats !== 'never', minutes: end - start }))}
                    onClick={() => (e.trip_id ? openPanel('trip', { id: e.trip_id }) : openPanel('event', { id: e.event_id, day: iso }))}>
                    <strong>{e.title}</strong>
                    <span>{clock(e.start_time)}{e.end_time ? `–${clock(e.end_time)}` : ''}{w ? ` ${w.icon}` : ''}</span>
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Agenda: the days ahead that have something on, as a list (a phone's best view).
export function AgendaView({ start, days, byDay, weather }) {
  const { openPanel } = useApp()
  const logIt = useLogIt()
  const list = useMemo(() => Array.from({ length: days }, (_, i) => { const d = dayDate(start); d.setDate(d.getDate() + i); return isoDay(d) })
    .filter((iso) => { const d = byDay[iso]; return d && (d.events.length || d.todos.length || d.goals.length || d.holidays.length) }), [start, days, byDay])
  return (
    <div className="cal-agenda">
      {list.length === 0 && <p className="empty card">Nothing on in the next {days} days.</p>}
      {list.map((iso) => {
        const d = byDay[iso]
        return (
          <section key={iso} className="card cal-agenda-day" aria-label={dayLabel(iso)}>
            <h3 className={`cal-agenda-date${iso === today() ? ' today' : ''}`}>{dayLabel(iso)}
              {d.holidays.map((h) => <span key={h.name} className="pill teal">🎉 {h.name}</span>)}</h3>
            <ul className="list plain-list">
              {d.events.map((e) => {
                const w = weather[`${e.event_id}:${iso}`]
                return (
                  <li key={`e${e.event_id}`} className="cal-planned">
                    <button type="button" className="row-button" onClick={() => (e.trip_id ? openPanel('trip', { id: e.trip_id }) : openPanel('event', { id: e.event_id, day: iso }))}>
                      <span className={`time-block ${HOBBY_TONE[e.hobby] ?? 'tint'}`}>{e.start_time ? clock(e.start_time) : 'All day'}</span>
                      <span className="grow">
                        <span className="item-title">{e.title}</span>
                        <span className="item-meta">{[e.end_time && `until ${clock(e.end_time)}`, e.location, hobbyName(e.hobby),
                          e.repeats && e.repeats !== 'never' && repeatText(e), w && weatherLine(w)].filter(Boolean).join(' · ')}</span>
                      </span>
                    </button>
                    {e.hobby && !e.trip_id && iso <= today() && (isLogged(e, d.happened)
                      ? <span className="pill ok">Logged ✓</span>
                      : <button type="button" className="secondary small" onClick={() => logIt(e, iso)}>Log it</button>)}
                  </li>
                )
              })}
              {d.todos.map((t) => (
                <li key={`t${t.todo_id}`}>
                  <button type="button" className="row-button" onClick={() => openPanel('todo', { id: t.todo_id })}>
                    <span className="time-block">{t.plan_time ? clock(t.plan_time) : '☐'}</span>
                    <span className="grow"><span className="item-title">{t.title}</span>
                      <span className="item-meta">{t.plan_on === iso ? 'Planned' : 'Due'}{t.hobby ? ` · ${hobbyName(t.hobby)}` : ''}</span></span>
                  </button>
                </li>
              ))}
              {d.goals.map((g) => <li key={`g${g.goal_id}`} className="cal-goal-line">🏁 Goal ends: <strong>{g.title}</strong></li>)}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

// "To plan": open to-dos without a planned day - drag one onto a day (or a time in the week) to block it out.
export function ToPlan() {
  const { refreshKey, openPanel } = useApp()
  const [todos, setTodos] = useState(null)
  useEffect(() => { api.todos('open').then((all) => setTodos(all.filter((t) => !t.plan_on))).catch(() => setTodos([])) }, [refreshKey])
  if (!todos?.length) return null
  return (
    <section className="card cal-toplan" aria-labelledby="cal-toplan-title">
      <h3 id="cal-toplan-title" className="home-card-title">To plan</h3>
      <p className="muted small">Drag a to-do onto a day (or a time in Week) to plan when you'll do it.</p>
      <ul className="cal-toplan-list">
        {todos.slice(0, 12).map((t) => (
          <li key={t.todo_id}>
            <button type="button" className="cal-chip todo" draggable
              onDragStart={(ev) => ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ kind: 'todo', id: t.todo_id, minutes: 60 }))}
              onClick={() => openPanel('todo', { id: t.todo_id })}>
              ☐ {t.title}{t.due_on && <span className="muted"> · due {dayDate(t.due_on).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

// The year: twelve small months, each day shaded by how much you did (or coloured by its mood); holidays ringed.
export function YearView({ year, onPick }) {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [mode, setMode] = useState('activity')
  useEffect(() => { setData(null); api.calendarYear(year).then(setData).catch(() => setData({ days: [], holidays: [] })) }, [year, refreshKey])
  const byDay = useMemo(() => Object.fromEntries((data?.days ?? []).map((d) => [d.day, d])), [data])
  const holidays = useMemo(() => Object.fromEntries((data?.holidays ?? []).map((h) => [h.day, h.name])), [data])
  const level = (n) => (n === 0 ? 0 : n === 1 ? 1 : n <= 3 ? 2 : n <= 5 ? 3 : 4)
  const busiest = useMemo(() => [...(data?.days ?? [])].sort((a, b) => b.count - a.count)[0], [data])
  return (
    <section className="cal-year">
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Colour days by">
          <button type="button" aria-pressed={mode === 'activity'} onClick={() => setMode('activity')}>What you did</button>
          <button type="button" aria-pressed={mode === 'mood'} onClick={() => setMode('mood')}>Mood</button>
        </div>
        {data && <span className="muted small">{data.days.filter((d) => d.count).length} active days{busiest?.count ? ` · busiest ${dayDate(busiest.day).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })} (${busiest.count})` : ''}</span>}
      </div>
      {!data ? <p className="muted loading">Loading...</p> : (
        <div className="cal-year-grid">
          {Array.from({ length: 12 }, (_, m) => {
            const first = new Date(year, m, 1, 12)
            const lead = (first.getDay() + 6) % 7
            const length = new Date(year, m + 1, 0).getDate()
            return (
              <div key={m} className="card cal-year-month">
                <h3>{first.toLocaleDateString('en-AU', { month: 'long' })}</h3>
                <div className="cal-year-days">
                  {WEEKDAYS.map((w) => <span key={w} className="cal-year-name" aria-hidden="true">{w[0]}</span>)}
                  {Array.from({ length: lead }, (_, i) => <span key={`x${i}`} aria-hidden="true" />)}
                  {Array.from({ length }, (_, i) => {
                    const iso = `${year}-${String(m + 1).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`
                    const d = byDay[iso]
                    const mood = moodOf(d?.mood)
                    const cls = mode === 'mood' ? (mood ? `mood ${mood.tone}` : '') : `lv${level(d?.count ?? 0)}`
                    const label = `${dayDate(iso).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })}: ${d?.count ?? 0} thing${d?.count === 1 ? '' : 's'}${d?.hobbies?.length ? ` (${d.hobbies.map(hobbyName).join(', ')})` : ''}${mood ? `, ${mood.label}` : ''}${holidays[iso] ? `, ${holidays[iso]}` : ''}`
                    return (
                      <button key={iso} type="button" className={`cal-year-day ${cls}${holidays[iso] ? ' holiday' : ''}${iso === today() ? ' today' : ''}`}
                        title={label} aria-label={label} onClick={() => onPick(iso)}>{mode === 'mood' && mood ? mood.face : ''}</button>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
      <p className="cal-year-key muted small">
        {mode === 'activity' ? <>Less <i className="lv0" /><i className="lv1" /><i className="lv2" /><i className="lv3" /><i className="lv4" /> more · </> : 'A face is that day\'s mood · '}
        a ring is a public holiday. Tap a day to open it.
      </p>
    </section>
  )
}
