import { useState } from 'react'
import { api, dayDate, isoDay } from '../../api.js'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'

// The to-do list's shared pieces (api/app/todos.py): a row you tick off, the quick add, labels for when it's due.

export const BUCKETS = [['overdue', 'Overdue'], ['today', 'Today'], ['week', 'This week'], ['later', 'Later'], ['someday', 'No day']]
export const REPEATS = [['never', "Doesn't repeat"], ['daily', 'Every day'], ['weekly', 'Every week'], ['monthly', 'Every month']]
const hobbyOf = (id) => MODULES.find((m) => m.id === id)

// "Today", "Tomorrow", "Thursday", "3 days late", "12 Nov"
export function dueLabel(t) {
  if (!t.due_on) return null
  const days = Math.round((dayDate(t.due_on) - dayDate(isoDay(new Date()))) / 86400000)
  if (days < 0) return days === -1 ? 'Yesterday' : `${-days} days late`
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  if (days < 7) return dayDate(t.due_on).toLocaleDateString('en-AU', { weekday: 'long' })
  return dayDate(t.due_on).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
}

// Tick it off: it stays on the list struck through until the list reloads (a slip of the finger is easy to undo), and
// the toast offers Undo; a repeating one says when its next is due.
export function useTick(onChanged) {
  const { showToast, changed } = useApp()
  const [ticked, setTicked] = useState(() => new Set())
  const tick = async (t) => {
    if (ticked.has(t.todo_id)) {
      await api.todoUndone(t.todo_id)
      setTicked((s) => { const n = new Set(s); n.delete(t.todo_id); return n })
      return
    }
    setTicked((s) => new Set(s).add(t.todo_id))
    try {
      const r = await api.todoDone(t.todo_id)
      const undo = { label: 'Undo', run: async () => { await api.todoUndone(t.todo_id); setTicked(new Set()); onChanged?.(); changed() } }
      showToast(r.next ? `Done. Next one due ${dueLabel(r.next)?.toLowerCase() ?? 'soon'}.` : `Done: ${t.title}`, undo)
    } catch (e) {
      setTicked((s) => { const n = new Set(s); n.delete(t.todo_id); return n })
      showToast(e.message)
    }
  }
  return [ticked, tick]
}

// grip: something before the tick box (a goal's Next up: the handle to drag an undated one into place).
export function TaskRow({ t, done, onTick, compact = false, grip = null, ...rest }) {
  const { openPanel } = useApp()
  const hobby = hobbyOf(t.hobby)
  const when = dueLabel(t)
  return (
    <li className={`task-row${done ? ' task-done' : ''}${t.bucket === 'overdue' ? ' task-late' : ''}`} {...rest}>
      {grip}
      <input type="checkbox" className="task-check" checked={done} onChange={() => onTick(t)} aria-label={`Done: ${t.title}`} />
      <button type="button" className="task-open" onClick={() => openPanel('todo', { id: t.todo_id })}>
        <span className="item-title">{t.priority === 'high' && <span className="task-high" title="High priority">!</span>}{t.title}</span>
        {(!compact || when) && (
          <span className="item-meta">
            {when && <span className={t.bucket === 'overdue' ? 'task-when late' : 'task-when'}>{when}</span>}
            {t.repeats !== 'never' && <span>{REPEATS.find(([k]) => k === t.repeats)?.[1].toLowerCase()}</span>}
            {!compact && hobby && <span className="task-hobby" style={{ '--hue': hobby.hue }}>{hobby.name}</span>}
            {!compact && t.goal_title && <span>for “{t.goal_title}”</span>}
          </span>
        )}
      </button>
    </li>
  )
}

// One line to add a to-do: its words, and (optionally) a day. More (notes, a hobby, a goal, repeats) in its panel.
// extra: fields every one added here gets (a goal's page: its goal_id and hobby).
export function QuickAdd({ onAdded, placeholder = 'Add a to-do...', withDay = true, extra = null }) {
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [error, setError] = useState('')
  const add = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try {
      const added = await api.addTodo({ ...extra, title: title.trim(), due_on: due || null })
      setTitle('')
      setDue('')
      setError('')
      onAdded?.(added)
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="task-add" onSubmit={add}>
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={placeholder} aria-label="New to-do" maxLength={200} />
      {withDay && <input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Due (optional)" />}
      <button type="submit" className="secondary" disabled={!title.trim()}>Add</button>
      {error && <p className="alert error small" role="alert">{error}</p>}
    </form>
  )
}
