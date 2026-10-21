import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, clock, dayDate, isoDay, shortDate } from '../../api.js'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'

// The calendar's shared parts (2026-10-21): colours, how a repeat reads, layers (what's shown), the forecast on
// events, "Log it" for each hobby, quick add in plain words, search, countdowns and the hobby-time balance.

export const HOBBY_TONE = { models: 'purple', boardgames: 'teal', volleyball: 'low', videogames: 'purple', chess: 'tint', reading: 'low', car: 'ok', travel: 'teal', shooting: 'out', hiking: 'ok', gardening: 'ok' }
export const KIND_TONE = { model: 'purple', supply: 'ok', page: 'teal', game: 'teal', volleyball: 'low', gear: 'ok', videogame: 'purple',
  chess: 'tint', book: 'low', goal: 'ok', hike: 'ok', planting: 'ok', gcontainer: 'ok', gspace: 'ok' }
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
export const hobbyName = (id) => MODULES.find((m) => m.id === id)?.name
// What each hobby's log is in the activity feed (api/app/calendar_more.py HOBBY_KINDS): a hobby event's day is
// "Logged" once that hobby's log has something on it.
export const HOBBY_KINDS = { models: ['model'], boardgames: ['game'], volleyball: ['volleyball'], videogames: ['videogame'], chess: ['chess'],
  reading: ['book'], travel: ['trip'], shooting: ['shoot'], hiking: ['hike'], gardening: ['planting', 'gcontainer', 'gspace'], car: [] }

const NTH = ['1st', '2nd', '3rd', '4th', 'last']
const ord = (n) => `${n}${['th', 'st', 'nd', 'rd'][(n % 100 > 10 && n % 100 < 14) || n % 10 > 3 ? 0 : n % 10]}`
// "every week", "every 2 weeks on Mon & Thu", "monthly on the 15th", "every 2nd Saturday", "every year"
export function repeatText(e) {
  const first = dayDate(e.starts_on)
  const every = e.repeat_every > 1 ? e.repeat_every : 1
  switch (e.repeats) {
    case 'weekly': return every > 1 ? `every ${every} weeks` : 'every week'
    case 'fortnightly': return 'every two weeks'
    case 'weekdays': return `${every > 1 ? `every ${every} weeks on` : 'every'} ${(e.repeat_days ?? []).map((d) => WEEKDAYS[d]).join(' & ')}`
    case 'monthly': return `${every > 1 ? `every ${every} months` : 'monthly'} on the ${ord(first.getDate())}`
    case 'monthly_nth': return `every ${NTH[Math.min(4, Math.floor((first.getDate() - 1) / 7))]} ${first.toLocaleDateString('en-AU', { weekday: 'long' })}`
    case 'yearly': return `every year on ${first.toLocaleDateString('en-AU', { day: 'numeric', month: 'long' })}`
    default: return ''
  }
}

// ---------------------------------------------------------------- layers
export const LAYERS = [['planned', 'Planned events'], ['happened', 'What happened'], ['moods', 'Moods'], ['todos', 'To-dos'],
  ['goals', 'Goal deadlines'], ['holidays', 'Public holidays'], ['weather', 'Weather']]
const LAYER_KEY = 'offtheclock.calendarLayers'
const readLayers = () => { try { return JSON.parse(localStorage.getItem(LAYER_KEY)) ?? { off: [], hobbies: [] } } catch { return { off: [], hobbies: [] } } }

// What the calendar shows: each layer and each hobby on or off, remembered on this device.
export function useLayers() {
  const [state, setState] = useState(readLayers)
  const save = (next) => { setState(next); try { localStorage.setItem(LAYER_KEY, JSON.stringify(next)) } catch { /* private window */ } }
  const toggle = (list, id) => save({ ...state, [list]: state[list].includes(id) ? state[list].filter((x) => x !== id) : [...state[list], id] })
  return {
    on: (layer) => !state.off.includes(layer),
    hobbyOn: (hobby) => !hobby || !state.hobbies.includes(hobby),
    toggleLayer: (id) => toggle('off', id),
    toggleHobby: (id) => toggle('hobbies', id),
    hidden: state.off.length + state.hobbies.length,
    reset: () => save({ off: [], hobbies: [] }),
  }
}

export function LayersMenu({ layers }) {
  return (
    <details className="cal-menu">
      <summary className="secondary">Show{layers.hidden ? ` · ${layers.hidden} hidden` : ''} ▾</summary>
      <div className="cal-menu-body">
        <p className="cal-menu-head">On the calendar</p>
        {LAYERS.map(([id, label]) => (
          <label key={id} className="cal-check"><input type="checkbox" checked={layers.on(id)} onChange={() => layers.toggleLayer(id)} /> {label}</label>
        ))}
        <p className="cal-menu-head">Hobbies</p>
        {MODULES.map((m) => (
          <label key={m.id} className="cal-check"><input type="checkbox" checked={layers.hobbyOn(m.id)} onChange={() => layers.toggleHobby(m.id)} />
            <i className={`cal-dot ${HOBBY_TONE[m.id] ?? 'tint'}`} aria-hidden="true" /> {m.name}</label>
        ))}
        {layers.hidden > 0 && <button type="button" className="plain small" onClick={layers.reset}>Show everything</button>}
      </div>
    </details>
  )
}

// ---------------------------------------------------------------- weather
// The forecast on events in the next 16 days: {`${event_id}:${day}`: {icon, sky, max, min, rain_chance}}.
export function useEventWeather(enabled = true) {
  const { refreshKey } = useApp()
  const [byEvent, setByEvent] = useState({})
  useEffect(() => {
    if (!enabled) return
    api.eventWeather().then((r) => setByEvent(Object.fromEntries(r.weather.map((w) => [`${w.event_id}:${w.day}`, w])))).catch(() => {})
  }, [refreshKey, enabled])
  return byEvent
}
export const weatherLine = (w) => (w ? `${w.icon ?? ''} ${Math.round(w.max)}°${w.rain_chance != null ? ` · ${w.rain_chance}% rain` : ''}` : '')

// ---------------------------------------------------------------- Log it
// Whether a hobby event's day has been logged in that hobby (its log has something that day; volleyball: from this event).
export const isLogged = (e, happened) => Boolean(e.logged_id) || (HOBBY_KINDS[e.hobby] ?? []).some((k) => happened.some((h) => h.kind === k))

// "Log it": the hobby's own log, opened for the event's day where its panel can take one; else the hobby's page.
export function useLogIt() {
  const { openPanel } = useApp()
  const navigate = useNavigate()
  return (e, day) => {
    if (e.hobby === 'volleyball') openPanel('volleyball', { eventId: e.event_id, day, venue: e.location })
    else if (e.hobby === 'boardgames') openPanel('play', { day })
    else if (e.hobby === 'shooting') openPanel('shootsession', { day })
    else if (e.hobby) navigate(`/${e.hobby}`)
  }
}

// ---------------------------------------------------------------- quick add
const say = (p) => [
  dayDate(p.starts_on).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' }),
  p.start_time ? `${clock(p.start_time)}${p.end_time ? `–${clock(p.end_time)}` : ''}` : 'All day',
  p.repeats !== 'never' && repeatText(p), p.repeat_until && `until ${shortDate(p.repeat_until)}`,
  p.location && `📍 ${p.location}`, p.hobby && hobbyName(p.hobby),
].filter(Boolean)

// "Add in plain words": what it understood shows as chips; Add makes it, Edit opens the full form with it filled in.
export function QuickAdd() {
  const { openPanel, changed, showToast } = useApp()
  const [text, setText] = useState('')
  const [read, setRead] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!text.trim()) { setRead(null); return undefined }
    const wait = setTimeout(() => api.parseEvent(text).then(setRead).catch(() => setRead(null)), 300)
    return () => clearTimeout(wait)
  }, [text])
  const add = async (e) => {
    e.preventDefault()
    if (!read) return
    setBusy(true)
    try {
      const made = await api.addEvent(read)
      changed()
      showToast(`${made.title} added for ${shortDate(read.starts_on)}`)
      setText('')
    } catch (err) {
      showToast(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="cal-quick" onSubmit={add}>
      <input type="text" value={text} onChange={(e) => setText(e.target.value)} aria-label="Add an event in plain words"
        placeholder="Add in plain words: Volleyball Tue 7-9pm at Sports hall weekly" maxLength={300} />
      {read && (
        <div className="cal-quick-read" aria-live="polite">
          <strong>{read.title}</strong>
          {say(read).map((t) => <span key={t} className="chip">{t}</span>)}
          <span className="grow" />
          <button type="button" className="plain" onClick={() => { openPanel('event', { prefill: read }); setText('') }}>Edit first</button>
          <button type="submit" className="primary" disabled={busy}>Add</button>
        </div>
      )}
    </form>
  )
}

// ---------------------------------------------------------------- search
export function EventSearch({ onPick }) {
  const [q, setQ] = useState('')
  const [found, setFound] = useState(null)
  const box = useRef(null)
  useEffect(() => {
    if (q.trim().length < 2) { setFound(null); return undefined }
    const wait = setTimeout(() => api.searchEvents(q).then(setFound).catch(() => setFound([])), 250)
    return () => clearTimeout(wait)
  }, [q])
  useEffect(() => {
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setFound(null) }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [])
  return (
    <div className="cal-search" ref={box}>
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search events" aria-label="Search events" />
      {found && (
        <ul className="cal-search-list" role="listbox" aria-label="Events found">
          {found.length === 0 && <li className="muted small cal-search-none">No events match.</li>}
          {found.map((e) => (
            <li key={e.event_id}>
              <button type="button" role="option" aria-selected="false" onClick={() => { onPick(e); setQ(''); setFound(null) }}>
                <i className={`cal-dot ${HOBBY_TONE[e.hobby] ?? 'tint'}`} aria-hidden="true" />
                <span className="grow"><strong>{e.title}</strong>
                  <span className="muted small"> {e.upcoming ? 'next' : 'last'} {shortDate(e.day)}{e.location ? ` · ${e.location}` : ''}</span></span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- countdowns
export function Countdowns({ compact = false }) {
  const { refreshKey, openPanel } = useApp()
  const [rows, setRows] = useState([])
  useEffect(() => { api.countdowns().then(setRows).catch(() => setRows([])) }, [refreshKey])
  if (!rows.length) return null
  return (
    <ul className={compact ? 'cal-countdowns compact' : 'cal-countdowns'} aria-label="Counting down">
      {rows.slice(0, compact ? 3 : 8).map((c) => (
        <li key={`${c.event_id}-${c.day}`}>
          <button type="button" className={`cal-countdown ${HOBBY_TONE[c.hobby] ?? 'tint'}`} onClick={() => openPanel('event', { id: c.event_id, day: c.day })}>
            <strong>{c.days_left === 0 ? 'Today' : c.days_left === 1 ? 'Tomorrow' : `${c.days_left} days`}</strong>
            <span>{c.title}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------- balance
const hours = (m) => (m >= 60 ? `${Math.round((m / 60) * 10) / 10} h` : `${m} min`)

// Per hobby this week: time planned (events with times) against done (each hobby's own log; days where it keeps no time).
export function BalanceCard({ start, end, label = 'This week' }) {
  const { refreshKey } = useApp()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.calendarBalance(start, end).then(setRows).catch(() => setRows([])) }, [start, end, refreshKey])
  const most = useMemo(() => Math.max(60, ...(rows ?? []).flatMap((r) => [r.planned_minutes, r.done_minutes ?? 0])), [rows])
  if (!rows) return null
  return (
    <section className="card cal-balance" aria-labelledby="cal-balance-title">
      <h3 id="cal-balance-title" className="home-card-title">Hobby time · {label}</h3>
      {rows.length === 0 ? <p className="muted small">Nothing planned or logged yet. Events with a hobby and times count here.</p> : (
        <ul className="cal-balance-list">
          {rows.map((r) => (
            <li key={r.hobby}>
              <span className="cal-balance-name"><i className={`cal-dot ${HOBBY_TONE[r.hobby] ?? 'tint'}`} aria-hidden="true" /> {hobbyName(r.hobby) ?? r.hobby}</span>
              <span className="cal-balance-bars" aria-hidden="true">
                <i className="planned" style={{ width: `${(r.planned_minutes / most) * 100}%` }} />
                <i className="done" style={{ width: `${((r.done_minutes ?? 0) / most) * 100}%` }} />
              </span>
              <span className="cal-balance-what small">
                Planned {r.planned_minutes ? hours(r.planned_minutes) : `${r.planned_events} event${r.planned_events === 1 ? '' : 's'}`}
                {' · '}did {r.done_minutes ? hours(r.done_minutes) : `${r.done_days} day${r.done_days === 1 ? '' : 's'}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="cal-balance-key muted small"><i className="planned" /> planned <i className="done" /> done (from each hobby's log)</p>
    </section>
  )
}

// The Monday-first week a day is in: [7 Dates].
export const weekOf = (iso) => {
  const d = dayDate(iso)
  const monday = new Date(d)
  monday.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return Array.from({ length: 7 }, (_, i) => { const x = new Date(monday); x.setDate(monday.getDate() + i); return x })
}
export const isoWeek = (iso) => weekOf(iso).map(isoDay)

// Dragging an event (or a to-do) to a day: the data carried, and the drop.
export function useDropOnDay() {
  const { changed, showToast } = useApp()
  return useCallback(async (payload, day, time = null) => {
    try {
      if (payload.kind === 'event') {
        if (payload.from === day && !time) return
        await api.moveEvent(payload.id, { from_day: payload.from, to_day: day,
          ...(time ? { keep_time: false, start_time: time.start, end_time: time.end } : {}) })
        showToast(payload.repeats ? 'Moved that day only (the rest still repeat).' : 'Moved.')
      } else if (payload.kind === 'todo') {
        await api.updateTodo(payload.id, { plan_on: day, plan_time: time?.start ?? null, plan_minutes: time ? (payload.minutes ?? 60) : null })
        showToast(`Planned for ${shortDate(day)}${time ? ` at ${clock(time.start)}` : ''}.`)
      }
      changed()
    } catch (e) {
      showToast(e.message)
    }
  }, [changed, showToast])
}
export const DRAG_TYPE = 'application/x-otc-calendar'
