import { useState } from 'react'
import { api, duration, shortDate, today } from '../api.js'
import Elapsed from './Elapsed.jsx'
import Fold from './Fold.jsx'

// Time spent on a model: start/stop a timer (one runs at a time, across all models), or add
// time you forgot to time. Each change returns the whole model, which `onModel` shows.
export default function TimeTracker({ model, onModel, run }) {
  const [note, setNote] = useState('')
  const [adding, setAdding] = useState(false)
  const [manual, setManual] = useState({ hours: '', minutes: '', day: today(), note: '' })
  const running = !!model.running_since

  const start = () => run(async () => onModel(await api.startTimer(model.model_id), 'Timer started'))
  const stop = () => run(async () => {
    onModel(await api.stopTimer(model.model_id, note.trim() || null), 'Time saved ✓')
    setNote('')
  })
  const addTime = (e) => {
    e.preventDefault()
    const minutes = Number(manual.hours || 0) * 60 + Number(manual.minutes || 0)
    run(async () => {
      onModel(await api.addSession(model.model_id, { minutes, day: manual.day, note: manual.note.trim() || null }), 'Time added ✓')
      setAdding(false)
      setManual({ hours: '', minutes: '', day: today(), note: '' })
    })
  }
  const done = model.sessions.filter((s) => s.ended_at)

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">Time</h4>
        <span className="muted small">{duration(model.total_minutes)} in total</span>
      </div>
      <div className={running ? 'timer running' : 'timer'}>
        {running ? <Elapsed since={model.running_since} /> : <span className="elapsed idle">0:00:00</span>}
        {running ? (
          <>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you do? (optional)"
              aria-label="What did you do" />
            <button type="button" className="primary stop" onClick={stop}>Stop</button>
          </>
        ) : (
          <button type="button" className="primary" onClick={start}>Start timer</button>
        )}
      </div>
      {!adding ? (
        <button type="button" className="plain small" onClick={() => setAdding(true)}>+ Add time by hand</button>
      ) : (
        <form className="inline-form" onSubmit={addTime}>
          <label className="field"><span className="field-label">Hours</span>
            <input type="number" min="0" max="24" inputMode="numeric" value={manual.hours}
              onChange={(e) => setManual((m) => ({ ...m, hours: e.target.value }))} /></label>
          <label className="field"><span className="field-label">Minutes</span>
            <input type="number" min="0" max="59" inputMode="numeric" value={manual.minutes}
              onChange={(e) => setManual((m) => ({ ...m, minutes: e.target.value }))} /></label>
          <label className="field"><span className="field-label">Day</span>
            <input type="date" value={manual.day} onChange={(e) => setManual((m) => ({ ...m, day: e.target.value }))} /></label>
          <label className="field"><span className="field-label">Note</span>
            <input value={manual.note} onChange={(e) => setManual((m) => ({ ...m, note: e.target.value }))} /></label>
          <div className="button-row wide">
            <button type="submit" className="primary" disabled={!(Number(manual.hours) || Number(manual.minutes))}>Add time</button>
            <button type="button" className="plain" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </form>
      )}
      {done.length > 0 && (
        <Fold title="Sessions" detail={done.length} className="inner">
          <ul className="list compact">
            {done.map((s) => (
              <li key={s.session_id}>
                <span className="muted small">{shortDate(s.started_at)}</span>
                <span className="grow">{s.note ?? ''}</span>
                <span className="num">{duration(s.minutes)}</span>
                <button type="button" className="icon-btn small" aria-label="Delete session"
                  onClick={() => run(async () => onModel(await api.deleteSession(s.session_id)))}>✕</button>
              </li>
            ))}
          </ul>
        </Fold>
      )}
    </section>
  )
}
