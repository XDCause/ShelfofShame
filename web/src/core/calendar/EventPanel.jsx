import { useEffect, useState } from 'react'
import { api, dayDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'

const REPEAT_LABEL = { never: "Doesn't repeat", weekly: 'Every week', fortnightly: 'Every two weeks' }
const longDay = (iso) => dayDate(iso).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })

// A calendar event: add one, or change one. Opened from a day on the calendar (`day` = the day
// you tapped, which for a repeating event is one of many), it also offers what that day needs:
// "Log the result" for a volleyball game, "Not on this day" for a repeating event.
export default function EventPanel({ id = null, day = null, hobby = null, title = '', onClose }) {
  const { lookups, changed, showToast, openPanel } = useApp()
  const [event, setEvent] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { if (id != null) api.getEvent(id).then(setEvent).catch((e) => setError(e.message)) }, [id])

  if (id != null && !event) {
    return <Drawer title="Event" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  }
  return <EventForm event={event} day={day} defaults={{ starts_on: day ?? today(), hobby: hobby ?? '', title, repeats: 'never' }}
    lookups={lookups} onClose={onClose}
    onSaved={(saved, verb) => { changed(); showToast(`${saved.title} ${verb}`); onClose() }}
    onLog={() => openPanel('volleyball', { eventId: event.event_id, day, venue: event.location })} />
}

function EventForm({ event, day, defaults, lookups, onClose, onSaved, onLog }) {
  const fields = [
    { name: 'title', label: 'What', required: true, wide: true, placeholder: 'e.g. Volleyball comp, Games night' },
    { name: 'hobby', label: 'Hobby', type: 'select', options: MODULES.map((m) => [m.id, m.name]) },
    { name: 'starts_on', label: event?.repeats !== 'never' && event ? 'First day' : 'Day', type: 'date', required: true },
    { name: 'start_time', label: 'From', type: 'time' },
    { name: 'end_time', label: 'Until', type: 'time' },
    { name: 'location', label: 'Where', wide: true },
    { name: 'repeats', label: 'Repeats', type: 'select', required: true, options: lookups.repeats.map((r) => [r, REPEAT_LABEL[r]]) },
    { name: 'repeat_until', label: 'Until (optional)', type: 'date', hint: 'Empty = keeps going' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const { form, set, payload } = useRecordForm(fields, event, defaults)
  const [allDay, setAllDay] = useState(Boolean(event && !event.start_time))   // no time = all day
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const shown = fields.filter((f) => (f.name !== 'repeat_until' || form.repeats !== 'never')
    && !(allDay && ['start_time', 'end_time'].includes(f.name)))
  const when = shown.findIndex((f) => f.name === 'starts_on') + 1     // the All day switch goes after the day

  const run = async (fn) => {
    setBusy(true)
    setError('')
    try { await fn() } catch (e) { setError(e.message); setBusy(false) }
  }
  const submit = (e) => {
    e.preventDefault()
    run(async () => {
      const body = { ...payload(), ...(form.repeats === 'never' ? { repeat_until: null } : {}),
        ...(allDay ? { start_time: null, end_time: null } : {}) }
      onSaved(event ? await api.updateEvent(event.event_id, body) : await api.addEvent(body), event ? 'saved' : 'added to the calendar')
    })
  }
  const repeating = event && event.repeats !== 'never'
  const past = day && day <= today()

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
      {event && day && (
        <section className="panel-section event-day">
          <p className="item-title">{longDay(day)}</p>
          <div className="button-row">
            {event.hobby === 'volleyball' && (
              <button type="button" className={past ? 'primary' : 'secondary'} onClick={onLog}>Log the result</button>
            )}
            {repeating && (
              <button type="button" className="secondary" disabled={busy}
                onClick={() => run(async () => { await api.skipEventDay(event.event_id, day); onSaved(event, `skipped on ${longDay(day)}`) })}>
                Not on this day
              </button>
            )}
          </div>
          {repeating && <p className="hint">Changes below apply to every day it repeats.</p>}
        </section>
      )}
      <form id="event-form" onSubmit={submit}>
        <RecordFields fields={shown.slice(0, when)} form={form} set={set} />
        <label className="all-day-switch">
          <input type="checkbox" role="switch" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
          <span>All day</span>
        </label>
        <RecordFields fields={shown.slice(when)} form={form} set={set} />
      </form>
    </Drawer>
  )
}
