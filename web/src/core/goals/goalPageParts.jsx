import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import FitTextarea from '../../components/FitTextarea.jsx'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'
import { hobbyName, PaceBadge, periodChoices, periodValue, ProgressBar, STATUS } from './goalParts.jsx'

// A goal's own page, its other parts (split out of GoalPage.jsx, 2026-10-22): the goals inside it, what it counts by
// itself, adding a goal inside it, setting it up, a text that saves itself, and its progress notes.
export const num = (v) => (v == null ? '' : Number(v).toLocaleString('en-AU', { maximumFractionDigits: 2 }))

// A bigger goal's goals inside it (+ Add one: a panel, so you stay on this goal), or the bigger goal this one is part of.
export function Family({ goal: g, reload }) {
  const [adding, setAdding] = useState(false)
  if (!g.goals.length && !g.parent_id && g.timeframe !== 'three_years') return null
  return (
    <section className="card home-card goal-family">
      <h2 className="home-card-title">{g.goals.length || g.timeframe === 'three_years' ? 'Goals inside this' : 'Part of'}
        {!g.parent_id && <button type="button" className="plain small goal-family-add" onClick={() => setAdding(true)}>+ Add one</button>}</h2>
      {/* (on the page itself: inside the sticky side column it would sit under the top bar) */}
      {adding && createPortal(<InsideGoal parent={g} onClose={() => setAdding(false)} onAdded={reload} />, document.body)}
      {g.parent_id && !g.goals.length && <Link to={`/goals/${g.parent_id}`} className="goal-family-link">{g.parent_title} →</Link>}
      {g.goals.length > 0 ? (
        <ul className="goal-family-list">
          {g.goals.map((c) => (
            <li key={c.goal_id}>
              <Link to={`/goals/${c.goal_id}`}>{c.title}</Link>
              <span className="goal-family-meta">
                {c.status !== 'active' ? STATUS[c.status].label : c.progress != null && !c.upcoming ? `${Math.round(c.progress * 100)}%` : ''}
              </span>
              {(c.upcoming || c.pace || c.habit) && <span className="goal-family-pace"><PaceBadge goal={c} /></span>}
              {!c.upcoming && <ProgressBar goal={c} />}
            </li>
          ))}
        </ul>
      ) : g.timeframe === 'three_years' && (
        <p className="muted small">Break it into a goal for each year: + Add one.</p>
      )}
    </section>
  )
}

// What a goal can count by itself (api/app/goal_sources.py), for the pickers.
export function useSources() {
  const [sources, setSources] = useState([])
  useEffect(() => { api.goalSources().then(setSources).catch(() => {}) }, [])
  return sources
}

// The "What it counts" choices, grouped by hobby.
export function SourceOptions({ sources }) {
  const byHobby = MODULES.map((m) => [m.name, sources.filter((s) => s.hobby === m.id)]).filter(([, list]) => list.length)
  const other = sources.filter((s) => !s.hobby || !MODULES.some((m) => m.id === s.hobby))
  return (
    <>
      {byHobby.map(([name, list]) => (
        <optgroup key={name} label={name}>{list.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</optgroup>
      ))}
      {other.length > 0 && <optgroup label="Everything">{other.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</optgroup>}
    </>
  )
}

// A new goal inside this one, in a panel: its name, when, and how it's measured. Add (or close) and you're back here.
export function InsideGoal({ parent, onClose, onAdded }) {
  const { changed, showToast } = useApp()
  const sources = useSources()
  // inside a 3-year goal: each of its years (2026, 2027, 2028); else the usual years ahead
  const thisYear = new Date().getFullYear()
  const choices = parent.timeframe === 'three_years'
    ? [0, 1, 2].map((i) => parent.period_start + i).map((y) => ({ value: `year:${y}`, timeframe: 'year', period_start: y,
      label: y === thisYear ? `${y} (this year)` : String(y) }))
    : periodChoices(thisYear).filter((c) => c.timeframe === 'year' || !c.timeframe)
  const firstYear = choices.find((c) => c.period_start >= thisYear) ?? choices[0]
  const [f, setF] = useState({ title: '', when: firstYear.value, kind: 'target', source: '', target: '', unit: '', times: '1', every: 'week' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const add = async (e) => {
    e.preventDefault()
    if (!f.title.trim()) return
    const when = choices.find((c) => c.value === f.when)
    const measure = f.kind === 'milestone' ? {} : f.kind === 'habit'
      ? { habit_times: Math.max(1, Math.round(Number(f.times) || 1)), habit_every: f.every }
      : { target_value: f.target === '' ? null : Number(f.target), unit: f.source ? null : f.unit || null,
          start_value: f.source || f.target === '' ? null : 0 }
    try {
      await api.addGoal({ title: f.title.trim(), parent_id: parent.goal_id, hobby: parent.hobby, timeframe: when.timeframe,
        period_start: when.period_start, kind: f.kind, source: f.kind === 'milestone' ? null : f.source || null, ...measure })
      changed()
      onAdded()
      showToast(`Added inside ${parent.title}`)
      onClose()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <Drawer title={`A goal inside "${parent.title}"`} onClose={onClose} footer={<>
      <button type="submit" form="inside-goal" className="primary" disabled={!f.title.trim()}>Add goal</button>
      <button type="button" className="plain" onClick={onClose}>Cancel</button>
    </>}>
      <form id="inside-goal" className="panel-section goal-inside-form" onSubmit={add}>
        <label className="field">What's the goal?
          <input autoFocus value={f.title} onChange={set('title')} maxLength={200} placeholder="e.g. Hike 300 km this year" /></label>
        <label className="field">When
          <select value={f.when} onChange={set('when')}>{choices.map((c) => <option key={c.value || 'none'} value={c.value}>{c.label}</option>)}</select></label>
        <div className="segmented goal-kind" role="group" aria-label="Kind">
          <button type="button" aria-pressed={f.kind === 'target'} onClick={() => setF({ ...f, kind: 'target' })}>Reach a target</button>
          <button type="button" aria-pressed={f.kind === 'habit'} onClick={() => setF({ ...f, kind: 'habit' })}>A habit</button>
          <button type="button" aria-pressed={f.kind === 'milestone'} onClick={() => setF({ ...f, kind: 'milestone' })}>Yes or no</button>
        </div>
        {f.kind !== 'milestone' && <>
        <label className="field">{f.kind === 'habit' ? 'What counts as a time' : 'Counting'}
          <select value={f.source} onChange={set('source')} aria-label="What it counts">
            <option value="">{f.kind === 'habit' ? 'I tick it myself' : 'A number I give'}</option>
            <SourceOptions sources={sources} />
          </select></label>
        {f.kind === 'habit' ? (
          <div className="goal-number">
            <label className="field">Times<input type="number" min="1" inputMode="numeric" value={f.times} onChange={set('times')} /></label>
            <label className="field">Every
              <select value={f.every} onChange={set('every')}><option value="week">Week</option><option value="month">Month</option></select></label>
          </div>
        ) : (
          <div className="goal-number">
            <label className="field">Target<input type="number" step="any" inputMode="decimal" value={f.target} onChange={set('target')} /></label>
            {!f.source && <label className="field">Unit<input value={f.unit} onChange={set('unit')} maxLength={40} placeholder="km, books, kg..." /></label>}
          </div>
        )}
        </>}
        <p className="muted small">Its progress feeds into {parent.title}. Why it matters and its to-dos go on its own page, later.</p>
        {error && <p className="alert error small" role="alert">{error}</p>}
      </form>
    </Drawer>
  )
}

// Set up: everything about the goal you'd change now and then.
export function SetUp({ goal: g, save, open }) {
  const [startOpen] = useState(open)      // decided once (a new goal: open); after that it stays as you leave it
  const sources = useSources()
  const [bigger, setBigger] = useState([])
  useEffect(() => {
    api.goals().then((d) => setBigger(d.goals.filter((x) => x.goal_id !== g.goal_id && !x.parent_id && x.status !== 'dropped'))).catch(() => {})
  }, [g.goal_id])
  const choices = periodChoices(new Date().getFullYear(), g)
  const field = (name, label) => (
    <label className="field">{label}
      <SavedText as="input" type="number" step="any" inputMode="decimal" value={g[name] == null ? '' : String(g[name])}
        onSave={(v) => save({ [name]: v === '' ? null : Number(v) })} />
    </label>
  )
  return (
    <details className="card goal-setup" open={startOpen}>
      <summary><h2 className="home-card-title">Set up</h2><span className="muted small">when, what it counts, status</span></summary>
      <div className="goal-setup-body">
        <div className="segmented goal-status" role="group" aria-label="Status">
          {Object.entries(STATUS).map(([k, s]) => (
            <button key={k} type="button" aria-pressed={g.status === k} onClick={() => g.status !== k && save({ status: k })}>{s.label}</button>
          ))}
        </div>
        <div className="goal-fields">
          <label className="field">When
            <select value={periodValue(g)} onChange={(e) => {
              const c = choices.find((x) => x.value === e.target.value)
              save({ timeframe: c.timeframe, period_start: c.period_start })
            }}>
              {choices.map((c) => <option key={c.value || 'none'} value={c.value}>{c.label}</option>)}
            </select>
          </label>
          <label className="field">Hobby
            <select value={g.hobby ?? ''} onChange={(e) => save({ hobby: e.target.value || null })}>
              <option value="">Life in general</option>
              {MODULES.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </label>
          <label className="field">Started
            <input type="date" value={g.started_on ?? ''} onChange={(e) => e.target.value && save({ started_on: e.target.value })} />
          </label>
          <label className="field">Aiming for
            <input type="date" value={g.target_date ?? ''} onChange={(e) => save({ target_date: e.target.value || null })} />
          </label>
          {g.status === 'done' && (
            <label className="field">Reached
              <input type="date" value={g.done_on ?? ''} onChange={(e) => e.target.value && save({ done_on: e.target.value })} />
            </label>
          )}
          <label className="field">Part of
            <select value={g.parent_id ?? ''} onChange={(e) => save({ parent_id: e.target.value ? Number(e.target.value) : null })}
              disabled={g.goals.length > 0} title={g.goals.length ? 'This goal has goals inside it' : undefined}>
              <option value="">Nothing bigger</option>
              {bigger.map((b) => <option key={b.goal_id} value={b.goal_id}>{b.title}</option>)}
            </select>
          </label>
        </div>

        <h3 className="goal-setup-title">How you'll measure it</h3>
        <div className="segmented goal-kind" role="group" aria-label="Kind">
          <button type="button" aria-pressed={g.kind === 'target'} onClick={() => g.kind !== 'target' && save({ kind: 'target' })}>Reach a target</button>
          <button type="button" aria-pressed={g.kind === 'habit'} onClick={() => g.kind !== 'habit' && save({ kind: 'habit' })}>A habit</button>
          <button type="button" aria-pressed={g.kind === 'milestone'} onClick={() => g.kind !== 'milestone' && save({ kind: 'milestone' })}>Yes or no</button>
        </div>
        {g.kind === 'milestone' ? (
          <p className="muted small">Done, or not yet - no number and no pace. Mark it reached when it happens; its to-dos (Next up) show the steps.</p>
        ) : <>
        <label className="field">{g.kind === 'habit' ? 'What counts as a time' : 'Counting'}
          <select value={g.source ?? ''} onChange={(e) => save({ source: e.target.value || null })} aria-label="What it counts">
            <option value="">{g.kind === 'habit' ? 'I\'ll tick it myself ("Did it today")' : 'A number I give'}</option>
            <SourceOptions sources={sources} />
          </select>
        </label>
        {g.kind === 'habit' ? (
          <div className="goal-number">
            <label className="field">Times
              <SavedText as="input" type="number" min="1" inputMode="numeric" value={String(g.habit_times ?? 1)}
                onSave={(v) => Number(v) >= 1 && save({ habit_times: Math.round(Number(v)) })} />
            </label>
            <label className="field">Every
              <select value={g.habit_every ?? 'week'} onChange={(e) => save({ habit_every: e.target.value })}>
                <option value="week">Week</option><option value="month">Month</option>
              </select>
            </label>
          </div>
        ) : (
          <div className="goal-number">
            <label className="field">Unit
              <SavedText as="input" value={g.unit ?? ''} placeholder="books, kg, %..." maxLength={40} aria-label="Unit"
                onSave={(unit) => save({ unit: unit || null })} />
            </label>
            {field('target_value', 'Target')}
            {field('start_value', 'Started at')}
            {g.source
              ? <p className="field"><span>Now</span><span className="goal-now-auto">{num(g.current_value)} <span className="muted small">counted</span></span></p>
              : field('current_value', 'Now')}
            <p className="muted small wide">{g.source ? `Counted from your ${hobbyName(g.hobby) ?? ''} records - no typing needed.`
              : 'A progress note with a number updates "Now" for you. No number? Its to-dos measure it.'}</p>
          </div>
        )}
        </>}
      </div>
    </details>
  )
}

// A box that saves when you leave it (only if it changed). A blank required one goes back. oneLine: a
// text box that wraps (long names on a phone) but Enter finishes it.
export function SavedText({ as = 'textarea', value, onSave, required, oneLine, ...props }) {
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

// Progress notes: what happened, on which day, with a number if you give one (a counted goal counts itself).
export function Notes({ goal, run }) {
  const [note, setNote] = useState({ day: today(), text: '', value: '' })
  const counting = !goal.source && goal.kind === 'target' && (goal.target_value != null || goal.unit)
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
                {u.value != null && <strong>{num(u.value)}{goal.unit ? ` ${goal.unit}` : ''}</strong>}
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
