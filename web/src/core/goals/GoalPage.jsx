import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api, shortDate, today } from '../../api.js'
import FitTextarea from '../../components/FitTextarea.jsx'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'
import { dueText, ProgressBar, progressText, STATUS } from './goalParts.jsx'

// One goal, in detail. Everything saves as you go: text when you leave the box, buttons and
// pickers straight away.
//   left   the name, status, hobby and dates; why it matters; the details (as long as you like);
//          progress notes (a dated note, with a number if you're tracking one)
//   right  how far along (the number from start to target, else the steps ticked); the steps
export default function GoalPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { changed, showToast } = useApp()
  const [goal, setGoal] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.getGoal(id).then(setGoal).catch((e) => setError(e.message)) }, [id])

  const run = async (fn) => {
    setError('')
    try {
      setGoal(await fn())
      changed()
      return true
    } catch (e) {
      setError(e.message)
      return false
    }
  }
  const save = (changes) => run(() => api.updateGoal(goal.goal_id, changes))

  if (!goal) return error ? <p className="alert error">{error} <Link to="/goals">All goals</Link></p> : <p className="muted loading">Loading...</p>
  const due = dueText(goal)

  return (
    <section className="page goal-page">
      <Link className="button plain small back-link" to="/goals">‹ All goals</Link>
      {error && <p className="alert error">{error}</p>}
      <div className="goal-layout">
        <div className="goal-main">
          <section className="card goal-top">
            <SavedText oneLine className="goal-title-input" value={goal.title} required aria-label="Goal" maxLength={200}
              onSave={(title) => save({ title })} />
            <div className="goal-meta">
              <div className="segmented" role="group" aria-label="Status">
                {Object.entries(STATUS).map(([k, s]) => (
                  <button key={k} type="button" aria-pressed={goal.status === k} onClick={() => goal.status !== k && save({ status: k })}>{s.label}</button>
                ))}
              </div>
              <button type="button" className="chip-filter" aria-pressed={goal.pinned}
                onClick={() => save({ pinned: !goal.pinned })}>{goal.pinned ? 'Pinned' : 'Pin'}</button>
              {due && <span className={`goal-due ${goal.days_left != null && goal.days_left < 0 ? 'late' : ''}`}>{due}</span>}
            </div>
            <div className="goal-fields">
              <label className="field">Hobby
                <select value={goal.hobby ?? ''} onChange={(e) => save({ hobby: e.target.value || null })}>
                  <option value="">Life in general</option>
                  {MODULES.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </label>
              <label className="field">Started
                <input type="date" value={goal.started_on ?? ''} onChange={(e) => e.target.value && save({ started_on: e.target.value })} />
              </label>
              <label className="field">Aiming for
                <input type="date" value={goal.target_date ?? ''} onChange={(e) => save({ target_date: e.target.value || null })} />
              </label>
              {goal.status === 'done' && (
                <label className="field">Reached
                  <input type="date" value={goal.done_on ?? ''} onChange={(e) => e.target.value && save({ done_on: e.target.value })} />
                </label>
              )}
            </div>
          </section>

          <section className="card home-card">
            <h2 className="home-card-title">Why it matters</h2>
            <SavedText value={goal.why ?? ''} placeholder="What it'll mean when you get there..." aria-label="Why it matters"
              onSave={(why) => save({ why: why || null })} />
          </section>

          <section className="card home-card">
            <h2 className="home-card-title">Details</h2>
            <SavedText className="goal-details" value={goal.details ?? ''} aria-label="Details"
              placeholder="The plan, what you'll need, what might get in the way, ideas..."
              onSave={(details) => save({ details: details || null })} />
          </section>

          <Notes goal={goal} run={run} />
        </div>

        <div className="goal-side">
          <NumberCard goal={goal} save={save} />
          <Steps goal={goal} run={run} setGoal={setGoal} />
          <section className="card home-card">
            <h2 className="home-card-title">Remove</h2>
            <p className="muted small">Gone for good, with its steps and notes. To keep it but stop working on it, mark it Dropped.</p>
            <button type="button" className="destructive small" onClick={async () => {
              if (!window.confirm(`Delete "${goal.title}"?`)) return
              try {
                await api.deleteGoal(goal.goal_id)
                changed()
                showToast(`Deleted ${goal.title}`)
                navigate('/goals')
              } catch (e) {
                setError(e.message)
              }
            }}>Delete goal</button>
          </section>
        </div>
      </div>
    </section>
  )
}

// A box that saves when you leave it (only if it changed). A blank required one goes back. oneLine: a
// text box that wraps (long names on a phone) but Enter finishes it.
function SavedText({ as = 'textarea', value, onSave, required, oneLine, ...props }) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  const leave = () => {
    const v = text.trim()
    if (required && !v) { setText(value); return }
    if (v !== (value ?? '').trim()) onSave(v)
  }
  const Box = as === 'input' ? 'input' : FitTextarea
  return <Box {...props} value={text} onChange={(e) => setText(e.target.value)} onBlur={leave}
    onKeyDown={as === 'input' || oneLine ? (e) => { if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur() } } : undefined} />
}

// How far along: the bar, then the number to track (unit, start, target, where you are now).
function NumberCard({ goal, save }) {
  const [open, setOpen] = useState(goal.target_value != null)
  const text = progressText(goal)
  const field = (name, label) => (
    <label className="field">{label}
      <SavedText as="input" type="number" step="any" inputMode="decimal" value={goal[name] == null ? '' : String(goal[name])}
        onSave={(v) => save({ [name]: v === '' ? null : Number(v) })} />
    </label>
  )
  return (
    <section className="card home-card goal-progress">
      <h2 className="home-card-title">How far along</h2>
      {goal.progress != null ? (
        <>
          <p className="goal-percent">{Math.round(goal.progress * 100)}%</p>
          <ProgressBar goal={goal} />
          {text && <p className="muted small">{text}</p>}
        </>
      ) : <p className="muted small">Add steps or a number to track, and your progress shows here.</p>}
      {open ? (
        <div className="goal-number">
          <label className="field">Counting
            <SavedText as="input" value={goal.unit ?? ''} placeholder="books, kg, %, games..." maxLength={40}
              onSave={(unit) => save({ unit: unit || null })} />
          </label>
          {field('start_value', 'Started at')}
          {field('target_value', 'Target')}
          {field('current_value', 'Now')}
          <p className="muted small wide">A progress note with a number updates "Now" for you.</p>
        </div>
      ) : <button type="button" className="secondary small" onClick={() => setOpen(true)}>Track a number</button>}
    </section>
  )
}

function Steps({ goal, run, setGoal }) {
  const [text, setText] = useState('')
  const steps = goal.steps
  const move = (i, by) => {
    const ids = steps.map((s) => s.step_id)
    ;[ids[i], ids[i + by]] = [ids[i + by], ids[i]]
    run(() => api.orderGoalSteps(goal.goal_id, ids))
  }
  const add = (e) => {
    e.preventDefault()
    if (!text.trim()) return
    run(() => api.addGoalStep(goal.goal_id, text)).then((ok) => ok && setText(''))
  }
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Steps{steps.length > 0 && <span className="muted small"> {goal.steps_done} of {steps.length}</span>}</h2>
      {steps.length > 0 && (
        <ul className="goal-steps">
          {steps.map((s, i) => (
            <li key={s.step_id} className={s.done ? 'done' : ''}>
              <input type="checkbox" checked={s.done} aria-label={`Done: ${s.text}`}
                onChange={() => {      // ticks straight away; the reply brings the new progress
                  setGoal((g) => ({ ...g, steps: g.steps.map((x) => (x.step_id === s.step_id ? { ...x, done: !s.done } : x)) }))
                  run(() => api.updateGoalStep(s.step_id, { done: !s.done }))
                    .then((ok) => ok || api.getGoal(goal.goal_id).then(setGoal).catch(() => {}))   // failed: as it really is
                }} />
              <SavedText as="input" className="goal-step-text" value={s.text} required aria-label="Step"
                onSave={(t) => run(() => api.updateGoalStep(s.step_id, { text: t }))} />
              {s.done && s.done_on && <span className="muted small">{shortDate(s.done_on)}</span>}
              <span className="goal-step-tools">
                <button type="button" className="icon-btn small" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move ${s.text} up`}>↑</button>
                <button type="button" className="icon-btn small" disabled={i === steps.length - 1} onClick={() => move(i, 1)} aria-label={`Move ${s.text} down`}>↓</button>
                <button type="button" className="icon-btn small" onClick={() => run(() => api.deleteGoalStep(s.step_id))} aria-label={`Remove ${s.text}`}>✕</button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <form className="goal-add-step" onSubmit={add}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Add a step" aria-label="New step" maxLength={500} />
        <button type="submit" className="secondary small" disabled={!text.trim()}>Add</button>
      </form>
    </section>
  )
}

// Progress notes: what happened, on which day, with a number if you're counting one.
function Notes({ goal, run }) {
  const [note, setNote] = useState({ day: today(), text: '', value: '' })
  const counting = goal.target_value != null || goal.unit
  const add = (e) => {
    e.preventDefault()
    if (!note.text.trim() && note.value === '') return
    run(() => api.addGoalUpdate(goal.goal_id, { day: note.day || null, text: note.text, value: note.value === '' ? null : Number(note.value) }))
      .then((ok) => ok && setNote({ day: today(), text: '', value: '' }))
  }
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Progress notes</h2>
      <form className="goal-note-form" onSubmit={add}>
        <FitTextarea value={note.text} onChange={(e) => setNote({ ...note, text: e.target.value })} placeholder="How's it going?"
          aria-label="Progress note" />
        <div className="goal-note-row">
          <input type="date" value={note.day} onChange={(e) => setNote({ ...note, day: e.target.value })} aria-label="Day" />
          {counting && <input type="number" step="any" inputMode="decimal" value={note.value} placeholder={goal.unit ? `Now (${goal.unit})` : 'Now'}
            onChange={(e) => setNote({ ...note, value: e.target.value })} aria-label="Number now" />}
          <button type="submit" className="primary small" disabled={!note.text.trim() && note.value === ''}>Add note</button>
        </div>
      </form>
      {goal.updates.length === 0 ? <p className="muted small">Nothing yet.</p> : (
        <ul className="goal-notes">
          {goal.updates.map((u) => (
            <li key={u.update_id}>
              <span className="goal-note-day">{shortDate(u.day)}</span>
              <span className="grow">
                {u.value != null && <strong>{Number(u.value).toLocaleString('en-AU')}{goal.unit ? ` ${goal.unit}` : ''}</strong>}
                {u.value != null && u.text && ' · '}
                {u.text && <span className="goal-note-text">{u.text}</span>}
              </span>
              <button type="button" className="icon-btn small" onClick={() => run(() => api.deleteGoalUpdate(u.update_id))}
                aria-label={`Remove the note from ${shortDate(u.day)}`}>✕</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
