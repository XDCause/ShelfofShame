import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { CheckIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import TodoList from '../journal/TodoList.jsx'
import { QuickAdd, TaskRow, useTick } from './todoParts.jsx'

// Home's To-do card (beside Recent activity): what's overdue and next, ticked off right here, a quick add, and the
// tick boxes from journal pages. The whole list (and the goals) are under Goals > To-do.
export default function TodoHome() {
  const { refreshKey } = useApp()
  const [s, setS] = useState(null)
  const load = useCallback(() => { api.todoSummary(7).then(setS).catch(() => setS({ open: 0, overdue: 0, today: 0, next: [] })) }, [])
  useEffect(() => { load() }, [load, refreshKey])
  const [ticked, tick] = useTick(load)
  if (!s) return null
  const counts = [s.overdue && `${s.overdue} overdue`, s.today && `${s.today} today`].filter(Boolean).join(' · ')
  return (
    <section className="card home-card todo-home" aria-labelledby="home-todo">
      <h2 id="home-todo" className="home-card-title"><CheckIcon size={20} /> To do
        {counts && <span className={s.overdue ? 'pill out' : 'pill low'}>{counts}</span>}
        <Link to="/goals/todo" className="small">{s.open > s.next.length ? `All ${s.open} →` : 'All to-dos →'}</Link></h2>
      <QuickAdd onAdded={load} withDay={false} />
      {s.next.length > 0
        ? <ul className="list plain-list task-list">{s.next.map((t) => <TaskRow key={t.todo_id} t={t} done={ticked.has(t.todo_id)} onTick={tick} compact />)}</ul>
        : <p className="muted small">Nothing to do. Add the next small step towards something.</p>}
      <TodoList limit={3} />
    </section>
  )
}
