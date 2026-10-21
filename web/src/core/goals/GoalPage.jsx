import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useParams } from 'react-router'
import { api, shortDate, timeAgo, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import FitTextarea from '../../components/FitTextarea.jsx'
import Fold from '../../components/Fold.jsx'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'
import { useNewPage } from '../journal/JournalList.jsx'
import { QuickAdd, TaskRow, useTick } from '../todo/todoParts.jsx'
import { Celebrate, dueText, GoalChart, HabitStrip, hobbyName, PaceBadge, paceText, periodChoices, periodLabel, periodValue,
  ProgressBar, progressText, STATUS, timeLeft } from './goalParts.jsx'

const num = (v) => (v == null ? '' : Number(v).toLocaleString('en-AU', { maximumFractionDigits: 2 }))

// One goal, to read first and change second (everything saves as you go):
//   top     where it's at - the big number, on track or not, the chart (or a habit's weeks) - and Mark as reached
//   left    next up (its to-dos), progress notes, why it matters, the details
//   right   the goals inside it (or the bigger goal it's part of), and Set up: when, hobby, what it counts (by
//           itself from a hobby, or a number you give), a habit's how-often, status. Pin and Delete are under ⋯.
export default function GoalPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { changed, showToast } = useApp()
  const [goal, setGoal] = useState(null)
  const [error, setError] = useState('')
  const [cheer, setCheer] = useState(0)
  const menu = useRef(null)
  const load = () => api.getGoal(id).then(setGoal).catch((e) => setError(e.message))
  // eslint-disable-next-line react-hooks/exhaustive-deps -- (load reads only id)
  useEffect(() => { load() }, [id])

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
  const reach = async () => {
    if (await save({ status: 'done' })) {
      setCheer((n) => n + 1)
      showToast('Goal reached - well done!')
    }
  }

  if (!goal) return error ? <p className="alert error">{error} <Link to="/goals">All goals</Link></p> : <p className="muted loading">Loading...</p>
  const fresh = !goal.why && goal.target_value == null && !goal.todos_total && !goal.source && goal.kind === 'target' && !goal.updates.length

  return (
    <section className="page goal-page">
      <div className="goal-page-bar">
        <Link className="button plain small back-link" to="/goals">‹ All goals</Link>
        <details className="goal-more" ref={menu}>
          <summary aria-label="More for this goal">⋯</summary>
          <div className="goal-more-menu">
            <button type="button" onClick={() => { menu.current.open = false; save({ pinned: !goal.pinned }) }}>
              {goal.pinned ? 'Unpin from the top' : 'Pin to the top'}</button>
            <button type="button" className="destructive" onClick={async () => {
              menu.current.open = false
              if (!window.confirm(`Delete "${goal.title}"? Its progress notes go with it; its to-dos stay on your list.`)) return
              try {
                await api.deleteGoal(goal.goal_id)
                changed()
                showToast(`Deleted ${goal.title}`)
                navigate('/goals')
              } catch (e) {
                setError(e.message)
              }
            }}>Delete goal</button>
          </div>
        </details>
      </div>
      {error && <p className="alert error">{error}</p>}
      <Hero goal={goal} save={save} run={run} reach={reach} cheer={cheer} />
      <div className="goal-layout">
        <div className="goal-main">
          <NextUp goal={goal} reload={load} />
          <Notes goal={goal} run={run} />
          <section className="card home-card">
            <h2 className="home-card-title">Details</h2>
            <SavedText className="goal-details" value={goal.details ?? ''} aria-label="Details"
              placeholder="The plan, what you'll need, what might get in the way, ideas..."
              onSave={(details) => save({ details: details || null })} />
          </section>
        </div>
        <div className="goal-side">
          <Family goal={goal} reload={load} />
          <section className="card home-card goal-why-card">
            <h2 className="home-card-title">Why it matters</h2>
            <SavedText value={goal.why ?? ''} placeholder="What it'll mean when you get there..." aria-label="Why it matters"
              onSave={(why) => save({ why: why || null })} />
          </section>
          <SetUp goal={goal} save={save} open={fresh} />
        </div>
      </div>
    </section>
  )
}

// Where it's at, at a glance.
function Hero({ goal: g, save, run, reach, cheer }) {
  const newPage = useNewPage()
  const due = dueText(g)
  const text = progressText(g)
  const eyebrow = [g.hobby ? hobbyName(g.hobby) : 'Life in general', g.timeframe && periodLabel(g.timeframe, g.period_start)].filter(Boolean)
  const done = g.status === 'done'
  const there = !done && g.status === 'active' && g.progress != null && g.progress >= 1 && !g.habit && g.kind !== 'milestone'
  const manualHabit = g.habit && !g.source
  const milestone = g.kind === 'milestone'
  const big = milestone ? (done ? 'Done' : 'Not yet') : g.habit ? `${num(g.habit.this)} / ${num(g.habit.times)}`
    : g.target_value != null && g.current_value != null ? `${num(g.current_value)} / ${num(g.target_value)}`
      : g.progress != null ? `${Math.round(g.progress * 100)}%` : null
  const write = () => newPage({
    title: `Reached: ${g.title}`, tags: ['goals'],
    content: [{ type: 'paragraph', content: [{ type: 'text', text: g.why ? `Why it mattered: ${g.why} ` : '', styles: {} }] }],
  })
  return (
    <section className={`card goal-hero${done ? ' reached' : ''}`}>
      <Celebrate run={cheer} />
      <div className="goal-hero-head">
        <div className="grow">
          <p className="goal-eyebrow">{eyebrow.join(' · ')}
            {g.parent_id && <> · part of <Link to={`/goals/${g.parent_id}`}>{g.parent_title}</Link></>}</p>
          <SavedText oneLine className="goal-title-input" value={g.title} required aria-label="Goal" maxLength={200}
            onSave={(title) => save({ title })} />
          <p className="goal-badges">
            {g.status !== 'active' && <span className={`pill ${STATUS[g.status].tone}`}>{STATUS[g.status].label}</span>}
            <PaceBadge goal={g} />
            {g.source_label && <span className="pill goal-auto" title="Counted from your records">Counts itself · {g.source_label}</span>}
            {g.pinned && <span className="pill purple">Pinned</span>}
            {due && <span className={`goal-due ${g.days_left != null && g.days_left < 0 ? 'late' : ''}`}>{due}</span>}
          </p>
        </div>
        {big && (
          <div className="goal-big">
            <span className="goal-big-number">{big}</span>
            <span className="goal-big-unit">{milestone ? (done ? '' : g.target_date ? timeLeft(g.target_date) : 'no set day')
              : g.habit ? `this ${g.habit.every}${g.unit && g.source ? ` · ${g.unit}` : ''}` : g.target_value != null ? g.unit ?? '' : text}</span>
            {!g.habit && !milestone && g.target_value != null && g.current_value != null && g.progress != null && g.progress < 1 && (
              <span className="goal-to-go">{num(Math.abs(g.target_value - g.current_value))}{g.unit ? ` ${g.unit}` : ''} to go</span>
            )}
            {g.habit && g.habit.streak > 0 && <span className="goal-streak">{g.habit.streak} {g.habit.every}{g.habit.streak === 1 ? '' : 's'} in a row</span>}
          </div>
        )}
      </div>
      {g.progress != null && !g.habit && !(milestone && !g.todos_total) && !(milestone && done) && (
        <div className="goal-hero-bar"><ProgressBar goal={g} />
          {milestone ? <span className="goal-big-percent goal-steps-text">{text}</span>
            : big !== `${Math.round(g.progress * 100)}%` && <span className="goal-big-percent">{Math.round(g.progress * 100)}%</span>}</div>
      )}
      {g.upcoming && <p className="goal-pace-text">Its time starts {shortDate(g.start_day)} - until then it's Upcoming: no pace, no nudges. A good time to plan its to-dos.</p>}
      {paceText(g) && <p className="goal-pace-text">{paceText(g)}</p>}
      {g.source && g.kind === 'target' && g.series && new Set(g.series.map(([, v]) => v)).size <= 1 && (
        <p className="goal-pace-text">{g.source_latest
          ? `Nothing new since ${shortDate(g.source_latest)} - the line moves when your ${g.source_label.toLowerCase()} does.`
          : `Nothing counted yet - the line moves when your ${g.source_label.toLowerCase()} does.`}</p>
      )}
      {g.habit ? <HabitStrip goal={g} /> : !milestone && <GoalChart goal={g} />}
      {milestone && !done && g.status === 'active' && !g.upcoming && (
        <p className="goal-pace-text">A yes or no: done, or not yet - mark it reached when it happens.{g.todos_total ? '' : ' Steps towards it can go in Next up.'}</p>
      )}
      {done && (
        <div className="goal-reached">
          <span className="goal-reached-icon" aria-hidden="true">🏆</span>
          <span className="grow"><strong>You did it.</strong> Reached {g.done_on ? shortDate(g.done_on) : ''}
            {g.started_on && g.done_on && <> - {Math.max(1, Math.round((new Date(g.done_on) - new Date(g.start_day)) / 86400000))} days from the start</>}.</span>
          <button type="button" className="secondary small" onClick={write}>Write about it</button>
        </div>
      )}
      {!done && g.status === 'active' && (
        <div className="goal-hero-actions">
          {there && <span className="goal-there">You've hit your target!</span>}
          {manualHabit && <button type="button" className="secondary" onClick={() => run(() => api.addGoalUpdate(g.goal_id, {}))}>Did it today</button>}
          <button type="button" className={there ? 'primary' : 'plain'} onClick={reach}>Mark as reached</button>
        </div>
      )}
    </section>
  )
}

// Next up: the goal's own to-dos - tick them off here; they're on Goals > To-do and Home too. Dated ones come first,
// by day; undated ones in your own order: drag one by its grip (mouse or finger), or focus the grip and use the
// up / down arrow keys.
function NextUp({ goal: g, reload }) {
  const [ticked, tickOff] = useTick(reload)
  const tick = async (t) => { await tickOff(t); reload() }       // (the goal's progress moves with it)
  const open = g.todos.filter((t) => !t.done_at)
  const dated = open.filter((t) => t.due_on)
  const undated = open.filter((t) => !t.due_on)
  const [order, setOrder] = useState(null)                       // the ids while dragging (or just saved)
  const list = useRef(null)
  const drag = useRef(null)
  const [dragging, setDragging] = useState(null)
  const ids = order && order.length === undated.length && undated.every((t) => order.includes(t.todo_id))
    ? order : undated.map((t) => t.todo_id)
  const byId = new Map(undated.map((t) => [t.todo_id, t]))
  const save = async (next) => {
    setOrder(next)
    try { await api.orderTodos(next) } catch { /* the list comes back as saved */ }
    reload()
  }
  const move = (id, to) => {
    const next = ids.filter((x) => x !== id)
    next.splice(Math.max(0, Math.min(next.length, to)), 0, id)
    return next
  }
  // While dragging, the window follows the pointer (the rows move under it, so the grip itself can lose it).
  const follow = (e) => {
    const d = drag.current
    if (!d) return
    const rows = [...list.current.querySelectorAll('[data-undated]')].filter((r) => Number(r.dataset.undated) !== d.id)
    const to = rows.filter((r) => { const b = r.getBoundingClientRect(); return e.clientY > b.top + b.height / 2 }).length
    const next = d.order.filter((x) => x !== d.id)
    next.splice(to, 0, d.id)
    if (next.join() !== d.order.join()) {
      d.order = next
      d.moved = true
      setOrder(next)
    }
  }
  const drop = () => {
    const d = drag.current
    drag.current = null
    setDragging(null)
    if (d?.moved) save(d.order)
  }
  const start = (e, id) => {
    e.preventDefault()
    drag.current = { id, moved: false, order: ids }
    setDragging(id)
    setOrder(ids)
    const up = () => {
      window.removeEventListener('pointermove', follow)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
      drop()
    }
    window.addEventListener('pointermove', follow)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
  }
  const keys = (e, id) => {
    const by = { ArrowUp: -1, ArrowDown: 1 }[e.key]
    if (!by) return
    e.preventDefault()
    save(move(id, ids.indexOf(id) + by))
  }
  const done = g.todos.filter((t) => t.done_at)
  return (
    <section className="card home-card goal-next-up">
      <h2 className="home-card-title">Next up{g.todos_total > 0 && <span className="muted small"> {g.todos_done} of {g.todos_total} done</span>}</h2>
      <QuickAdd onAdded={reload} placeholder="Add a step towards it..." extra={{ goal_id: g.goal_id, hobby: g.hobby }} />
      {open.length > 0
        ? (
          <ul className="list plain-list task-list" ref={list}>
            {dated.map((t) => <TaskRow key={t.todo_id} t={t} done={ticked.has(t.todo_id)} onTick={tick} />)}
            {ids.map((id) => byId.get(id)).filter(Boolean).map((t) => (
              <TaskRow key={t.todo_id} t={t} done={ticked.has(t.todo_id)} onTick={tick} data-undated={t.todo_id}
                data-dragging={dragging === t.todo_id ? 'yes' : undefined}
                grip={undated.length > 1 && (
                  <button type="button" className="task-grip" aria-label={`Move ${t.title} (up / down arrow keys)`} title="Drag to reorder"
                    onPointerDown={(e) => start(e, t.todo_id)}
                    onKeyDown={(e) => keys(e, t.todo_id)}>⠿</button>
                )} />
            ))}
          </ul>
        )
        : <p className="muted small">{done.length ? 'All done - add the next step when you know it.' : 'Break it into small steps: each one goes on your to-do list too.'}</p>}
      {done.length > 0 && (
        <Fold title="Done" detail={String(done.length)}>
          <ul className="list plain-list task-list">
            {done.map((t) => (
              <li key={t.todo_id} className="task-row task-done">
                <span className="grow"><span className="item-title">{t.title}</span><span className="item-meta">done {timeAgo(t.done_at)}</span></span>
                <button type="button" className="plain small" onClick={async () => { await api.todoUndone(t.todo_id); reload() }}>Put back</button>
              </li>
            ))}
          </ul>
        </Fold>
      )}
    </section>
  )
}

// A bigger goal's goals inside it (+ Add one: a panel, so you stay on this goal), or the bigger goal this one is part of.
function Family({ goal: g, reload }) {
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
function useSources() {
  const [sources, setSources] = useState([])
  useEffect(() => { api.goalSources().then(setSources).catch(() => {}) }, [])
  return sources
}

// The "What it counts" choices, grouped by hobby.
function SourceOptions({ sources }) {
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
function InsideGoal({ parent, onClose, onAdded }) {
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
function SetUp({ goal: g, save, open }) {
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

// Progress notes: what happened, on which day, with a number if you give one (a counted goal counts itself).
function Notes({ goal, run }) {
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
