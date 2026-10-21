import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api, shortDate, timeAgo } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../app-context.js'
import { useNewPage } from '../journal/JournalList.jsx'
import { QuickAdd, TaskRow, useTick } from '../todo/todoParts.jsx'
import { Family, Notes, SavedText, SetUp, num } from './goalPageParts.jsx'
import { Celebrate, dueText, GoalChart, HabitStrip, hobbyName, PaceBadge, paceText, periodLabel,
  ProgressBar, progressText, STATUS, timeLeft } from './goalParts.jsx'


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
export function NextUp({ goal: g, reload }) {      // (exported for its tests)
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
