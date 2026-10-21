import { useEffect, useState } from 'react'
import { api, dayDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'
import { WEEKDAYS, isLogged, useLogIt, weatherLine } from './calendarParts.jsx'

const REPEAT_LABEL = {
  never: "Doesn't repeat", weekly: 'Every week', fortnightly: 'Every two weeks', weekdays: 'On chosen days of the week',
  monthly: 'Monthly, on the same date', monthly_nth: 'Monthly, on the same weekday (e.g. 2nd Saturday)', yearly: 'Every year (birthdays)',
}
const EVERY = { weekly: 'weeks', weekdays: 'weeks', monthly: 'months' }
const longDay = (iso) => dayDate(iso).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })

// A calendar event: add one, or change one. Opened from a day on the calendar (`day` = the day you tapped, which for
// a repeating event is one of many), it also offers what that day needs: Log it in the hobby (or Logged ✓), the
// forecast, "Not on this day" for a repeating event. `prefill`: fields from quick add.
export default function EventPanel({ id = null, day = null, hobby = null, title = '', prefill = null, onClose }) {
  const { lookups, changed, showToast } = useApp()
  const [event, setEvent] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { if (id != null) api.getEvent(id).then(setEvent).catch((e) => setError(e.message)) }, [id])

  if (id != null && !event) {
    return <Drawer title="Event" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  }
  return <EventForm event={event} day={day} defaults={{ starts_on: day ?? today(), hobby: hobby ?? '', title, repeats: 'never', repeat_every: 1, ...(prefill ?? {}) }}
    lookups={lookups} onClose={onClose} prefill={prefill}
    onSaved={(saved, verb) => { changed(); showToast(`${saved.title} ${verb}`); onClose() }} />
}

function EventForm({ event, day, defaults, lookups, prefill, onClose, onSaved }) {
  const fields = [
    { name: 'title', label: 'What', required: true, wide: true, placeholder: 'e.g. Volleyball comp, Games night' },
    { name: 'hobby', label: 'Hobby', type: 'select', options: MODULES.map((m) => [m.id, m.name]) },
    { name: 'starts_on', label: event?.repeats !== 'never' && event ? 'First day' : 'Day', type: 'date', required: true },
    { name: 'start_time', label: 'From', type: 'time' },
    { name: 'end_time', label: 'Until', type: 'time' },
    { name: 'location', label: 'Where', wide: true },
    { name: 'repeats', label: 'Repeats', type: 'select', required: true, wide: true, options: lookups.repeats.map((r) => [r, REPEAT_LABEL[r] ?? r]) },
    { name: 'repeat_every', label: 'Every how many', type: 'number', min: 1 },
    { name: 'repeat_until', label: 'Until (optional)', type: 'date', hint: 'Empty = keeps going' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const { form, set, payload } = useRecordForm(fields, event, defaults)
  const source = event ?? prefill ?? {}
  const [allDay, setAllDay] = useState(Boolean((event || prefill) && !source.start_time))   // no time = all day
  const [days, setDays] = useState(source.repeat_days ?? [])
  const [place, setPlace] = useState(source.lat != null ? { lat: source.lat, lon: source.lon } : null)
  const [countdown, setCountdown] = useState(Boolean(source.countdown))
  const [checklist, setChecklist] = useState(source.checklist ?? [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const shown = fields.filter((f) => (!['repeat_until', 'repeat_every'].includes(f.name) || form.repeats !== 'never')
    && (f.name !== 'repeat_every' || EVERY[form.repeats])
    && !(allDay && ['start_time', 'end_time'].includes(f.name)))
    .map((f) => (f.name === 'repeat_every' ? { ...f, label: `Every how many ${EVERY[form.repeats] ?? ''}` } : f))
  const when = shown.findIndex((f) => f.name === 'starts_on') + 1     // the All day switch goes after the day
  const repeatsAt = shown.findIndex((f) => f.name === 'repeats') + 1

  const run = async (fn) => {
    setBusy(true)
    setError('')
    try { await fn() } catch (e) { setError(e.message); setBusy(false) }
  }
  const submit = (e) => {
    e.preventDefault()
    if (form.repeats === 'weekdays' && !days.length) { setError('Pick the days it is on.'); return }
    run(async () => {
      const body = { ...payload(), ...(form.repeats === 'never' ? { repeat_until: null } : {}),
        ...(allDay ? { start_time: null, end_time: null } : {}),
        repeat_every: EVERY[form.repeats] ? Math.max(1, Number(form.repeat_every) || 1) : 1,
        repeat_days: form.repeats === 'weekdays' ? days : null,
        lat: place?.lat ?? null, lon: place?.lon ?? null, countdown, checklist }
      onSaved(event ? await api.updateEvent(event.event_id, body) : await api.addEvent(body), event ? 'saved' : 'added to the calendar')
    })
  }
  const repeating = event && event.repeats !== 'never'

  const footer = confirmDelete ? (
    <span className="confirm">
      Delete {repeating ? 'every day of ' : ''}{event.title}?
      <button type="button" className="danger" onClick={() => run(async () => { await api.deleteEvent(event.event_id); onSaved(event, 'deleted') })}>Delete</button>
      <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="save" type="submit" form="event-form" className="primary" disabled={busy}>{event ? 'Save' : 'Add event'}</button>
      <button key="cancel" type="button" className="plain" onClick={onClose}>Cancel</button>
      {event && <><span className="spacer" />
        <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>Delete</button></>}
    </>
  )

  return (
    <Drawer title={event ? event.title : 'Add to the calendar'} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      {event && day && <ThisDay event={event} day={day} onSkipped={() => onSaved(event, `skipped on ${longDay(day)}`)} run={run} busy={busy} />}
      <form id="event-form" onSubmit={submit}>
        <RecordFields fields={shown.slice(0, when)} form={form} set={set} />
        <label className="all-day-switch">
          <input type="checkbox" role="switch" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
          <span>All day</span>
        </label>
        <RecordFields fields={shown.slice(when, repeatsAt)} form={form} set={set} />
        {form.repeats === 'weekdays' && (
          <fieldset className="cal-weekdays">
            <legend className="small">On</legend>
            {WEEKDAYS.map((w, i) => (
              <label key={w} className="cal-weekday"><input type="checkbox" checked={days.includes(i)}
                onChange={(e) => setDays(e.target.checked ? [...days, i].sort() : days.filter((d) => d !== i))} /> {w}</label>
            ))}
          </fieldset>
        )}
        <RecordFields fields={shown.slice(repeatsAt)} form={form} set={set} />
        <PlaceFinder place={place} onPlace={(p, name) => { setPlace(p); if (name && !form.location) set('location')({ target: { value: name } }) }} />
        <label className="all-day-switch">
          <input type="checkbox" role="switch" checked={countdown} onChange={(e) => setCountdown(e.target.checked)} />
          <span>Count down to it (on Home and the calendar)</span>
        </label>
        <Checklist items={checklist} onChange={setChecklist} hobby={form.hobby} />
      </form>
    </Drawer>
  )
}

// The tapped day: how long to go, the forecast, Log it (or Logged ✓), Not on this day.
function ThisDay({ event, day, onSkipped, run, busy }) {
  const logIt = useLogIt()
  const [happened, setHappened] = useState(null)
  const [weather, setWeather] = useState(null)
  useEffect(() => {
    api.calendar(day, day).then((d) => setHappened(d.happened)).catch(() => setHappened([]))
    api.eventWeather().then((r) => setWeather(r.weather.find((w) => w.event_id === event.event_id && w.day === day) ?? null)).catch(() => {})
  }, [day, event.event_id])
  const left = Math.round((dayDate(day) - dayDate(today())) / 86400000)
  const repeating = event.repeats !== 'never'
  const logged = happened && event.hobby && isLogged({ ...event }, happened)
  return (
    <section className="panel-section event-day">
      <p className="item-title">{longDay(day)}
        <span className="muted small"> · {left === 0 ? 'today' : left === 1 ? 'tomorrow' : left > 0 ? `in ${left} days` : `${-left} days ago`}</span></p>
      {weather && <p className="small">{weatherLine(weather)} <span className="muted">({weather.sky}; Open-Meteo)</span></p>}
      <div className="button-row">
        {event.hobby && day <= today() && (logged
          ? <span className="pill ok">Logged ✓</span>
          : <button type="button" className="primary" onClick={() => logIt(event, day)}>{event.hobby === 'volleyball' ? 'Log the result' : 'Log it'}</button>)}
        {repeating && (
          <button type="button" className="secondary" disabled={busy}
            onClick={() => run(async () => { await api.skipEventDay(event.event_id, day); onSkipped() })}>
            Not on this day
          </button>
        )}
      </div>
      {repeating && <p className="hint">Changes below apply to every day it repeats. (Drag it on the calendar to move just this day.)</p>}
    </section>
  )
}

// Where it is on the map (for the weather): search a town, or use home; the Where box keeps its own words.
function PlaceFinder({ place, onPlace }) {
  const [q, setQ] = useState('')
  const [found, setFound] = useState([])
  const [home, setHome] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.homePlace().then(setHome).catch(() => {}) }, [])
  const search = async () => {
    setError('')
    try { setFound(await api.gardenPlaces(q)) } catch (e) { setError(e.message) }
  }
  return (
    <fieldset className="cal-place">
      <legend className="small">On the map (for the weather)</legend>
      {place ? (
        <p className="small">📍 Set ({place.lat.toFixed(2)}, {place.lon.toFixed(2)}) <button type="button" className="plain small" onClick={() => onPlace(null)}>Remove</button></p>
      ) : (
        <>
          <div className="cal-place-row">
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Town or suburb" aria-label="Find the place"
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); search() } }} />
            <button type="button" className="secondary" onClick={search}>Find</button>
            {home && <button type="button" className="plain" onClick={() => onPlace({ lat: home.lat, lon: home.lon }, home.place_name)}>Home</button>}
          </div>
          {error && <p className="alert error small">{error}</p>}
          {found.length > 0 && (
            <ul className="cal-place-list">
              {found.map((p) => (
                <li key={`${p.lat},${p.lon}`}><button type="button" className="plain" onClick={() => { onPlace({ lat: p.lat, lon: p.lon }, p.name); setFound([]) }}>
                  {p.name} <span className="muted small">{p.region}</span></button></li>
              ))}
            </ul>
          )}
          {!home && <p className="hint">No place set: the forecast uses home (Gardening's settings: "Where you are") when that's set.</p>}
        </>
      )}
    </fieldset>
  )
}

// What to bring: tick items off; add your own, the hobby's gear, or a packing list's items; untick all for next time.
function Checklist({ items, onChange, hobby }) {
  const [text, setText] = useState('')
  const [offer, setOffer] = useState(null)
  useEffect(() => { api.bringOptions(hobby || '').then(setOffer).catch(() => setOffer(null)) }, [hobby])
  const add = (names) => {
    const have = new Set(items.map((i) => i.text.toLowerCase()))
    onChange([...items, ...names.filter((n) => n && !have.has(n.toLowerCase())).slice(0, 60 - items.length).map((n) => ({ text: n.slice(0, 120), done: false }))])
  }
  return (
    <fieldset className="cal-checklist">
      <legend className="small">What to bring{items.length ? ` · ${items.filter((i) => i.done).length}/${items.length} packed` : ''}</legend>
      {items.length > 0 && (
        <ul className="cal-checklist-items">
          {items.map((it, i) => (
            <li key={`${it.text}-${i}`}>
              <label><input type="checkbox" checked={it.done} onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, done: e.target.checked } : x)))} /> {it.text}</label>
              <button type="button" className="plain small" aria-label={`Remove ${it.text}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>×</button>
            </li>
          ))}
        </ul>
      )}
      <div className="cal-place-row">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Add an item" aria-label="Add an item to bring" maxLength={120}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add([text.trim()]); setText('') } }} />
        <button type="button" className="secondary" onClick={() => { add([text.trim()]); setText('') }}>Add</button>
      </div>
      <div className="button-row">
        {offer?.gear.length > 0 && <button type="button" className="plain small" onClick={() => add(offer.gear)}>+ My {MODULES.find((m) => m.id === hobby)?.name.toLowerCase()} gear</button>}
        {offer?.packing_lists.length > 0 && (
          <select className="cal-pack-pick" value="" aria-label="Add a packing list's items" onChange={(e) => { const l = offer.packing_lists.find((p) => p.name === e.target.value); if (l) add(l.items) }}>
            <option value="">+ A packing list…</option>
            {offer.packing_lists.map((p) => <option key={p.name} value={p.name}>{p.name} ({p.items.length})</option>)}
          </select>
        )}
        {items.some((i) => i.done) && <button type="button" className="plain small" onClick={() => onChange(items.map((i) => ({ ...i, done: false })))}>Untick all</button>}
      </div>
    </fieldset>
  )
}
