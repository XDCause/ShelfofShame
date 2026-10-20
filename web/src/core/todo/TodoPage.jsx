import { useCallback, useEffect, useState } from 'react'
import { api, timeAgo } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../app-context.js'
import EmptyState from '../EmptyState.jsx'
import TodoList from '../journal/TodoList.jsx'
import { BUCKETS, QuickAdd, TaskRow, useTick } from './todoParts.jsx'
import { CheckIcon } from '../../components/icons.jsx'

// Goals > To-do: the day-to-day under the big goals. A quick add at the top, then everything open, grouped by when
// (overdue, today, this week, later, no day); the tick boxes from journal pages; what's been done lately.
export default function TodoPage() {
  const { refreshKey } = useApp()
  const [todos, setTodos] = useState(null)
  const [done, setDone] = useState([])
  const [error, setError] = useState('')
  const load = useCallback(() => {
    api.todos('open').then((t) => { setTodos(t); setError('') }).catch((e) => setError(e.message))
    api.todos('done', 30).then(setDone).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load, refreshKey])
  const [ticked, tick] = useTick(load)

  if (error) return <p className="alert error">{error}</p>
  if (!todos) return <p className="muted loading">Loading...</p>
  const groups = BUCKETS.map(([key, label]) => [key, label, todos.filter((t) => t.bucket === key)]).filter(([, , list]) => list.length)
  return (
    <section className="page todo-page">
      <section className="card">
        <QuickAdd onAdded={load} placeholder="What needs doing?" />
        <p className="hint">Tap a to-do for more: notes, high priority, a hobby, the goal it helps, and repeats.</p>
      </section>
      {todos.length === 0 ? (
        <EmptyState Icon={CheckIcon} title="Nothing to do">The small steps towards your goals - and everything else - go here.</EmptyState>
      ) : groups.map(([key, label, list]) => (
        <section key={key} className={`card task-group task-group-${key}`} aria-labelledby={`todo-${key}`}>
          <h2 id={`todo-${key}`} className="home-card-title">{label} <span className="chip-count">{list.length}</span></h2>
          <ul className="list plain-list task-list">
            {list.map((t) => <TaskRow key={t.todo_id} t={t} done={ticked.has(t.todo_id)} onTick={tick} />)}
          </ul>
        </section>
      ))}
      <TodoList card />
      {done.length > 0 && (
        <Fold title="Done lately" detail={`${done.length}`}>
          <ul className="list plain-list task-list">
            {done.map((t) => (
              <li key={t.todo_id} className="task-row task-done">
                <span className="grow"><span className="item-title">{t.title}</span>
                  <span className="item-meta">done {timeAgo(t.done_at)}</span></span>
                <button type="button" className="plain small" onClick={async () => { await api.todoUndone(t.todo_id); load() }}>Put back</button>
              </li>
            ))}
          </ul>
        </Fold>
      )}
    </section>
  )
}
