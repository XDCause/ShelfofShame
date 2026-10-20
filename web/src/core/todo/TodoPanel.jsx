import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { MODULES } from '../../modules/index.js'
import { useApp } from '../app-context.js'
import { REPEATS } from './todoParts.jsx'

// A to-do in full: its words and notes, when it's due, how important, a hobby, the goal it helps, and whether it
// repeats. Saves on Save; Delete asks first.
export default function TodoPanel({ id, onClose }) {
  const { changed, showToast } = useApp()
  const [f, setF] = useState(null)
  const [goals, setGoals] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    api.todos('open', 1000).then(async (open) => {
      const t = open.find((x) => x.todo_id === id) ?? (await api.todos('done', 1000)).find((x) => x.todo_id === id)
      if (t) setF({ ...t, notes: t.notes ?? '', due_on: t.due_on ?? '', hobby: t.hobby ?? '', goal_id: t.goal_id ?? '' })
      else setError("That to-do isn't there any more.")
    }).catch((e) => setError(e.message))
    api.goals('active').then((d) => setGoals(d.goals)).catch(() => {})
  }, [id])
  if (!f) return <Drawer title="To-do" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? (e.target.checked ? 'high' : 'normal') : e.target.value })
  const save = async (e) => {
    e.preventDefault()
    try {
      await api.updateTodo(id, { title: f.title, notes: f.notes || null, due_on: f.due_on || null, priority: f.priority,
        hobby: f.hobby || null, goal_id: f.goal_id ? Number(f.goal_id) : null, repeats: f.repeats })
      changed()
      onClose()
    } catch (err) {
      setError(err.message)
    }
  }
  const remove = async () => {
    if (!window.confirm(`Delete "${f.title}"?`)) return
    await api.deleteTodo(id)
    changed()
    showToast(`Deleted: ${f.title}`)
    onClose()
  }
  return (
    <Drawer title="To-do" onClose={onClose} footer={<>
      <button type="submit" form="todo-form" className="primary">Save</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={remove}>Delete</button>
    </>}>
      <form id="todo-form" className="panel-section todo-form" onSubmit={save}>
        <label className="field wide"><span className="field-label">To do</span>
          <input value={f.title} onChange={set('title')} required maxLength={200} /></label>
        <label className="field"><span className="field-label">Due</span>
          <input type="date" value={f.due_on} onChange={set('due_on')} /></label>
        <label className="field"><span className="field-label">Repeats</span>
          <select value={f.repeats} onChange={set('repeats')}>{REPEATS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
        <label className="tick-row field wide"><input type="checkbox" checked={f.priority === 'high'} onChange={set('priority')} /> High priority</label>
        <label className="field"><span className="field-label">Hobby</span>
          <select value={f.hobby} onChange={set('hobby')}>
            <option value="">Life in general</option>
            {MODULES.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select></label>
        <label className="field"><span className="field-label">Helps the goal</span>
          <select value={f.goal_id} onChange={set('goal_id')}>
            <option value="">None</option>
            {goals.map((g) => <option key={g.goal_id} value={g.goal_id}>{g.title}</option>)}
            {f.goal_id && !goals.some((g) => g.goal_id === Number(f.goal_id)) && <option value={f.goal_id}>{f.goal_title}</option>}
          </select></label>
        <label className="field wide"><span className="field-label">Notes</span>
          <textarea value={f.notes} onChange={set('notes')} rows={4} maxLength={2000} /></label>
        {f.repeats !== 'never' && <p className="hint wide">Ticked off, the next one appears, due a step on.</p>}
        {error && <p className="alert error small wide" role="alert">{error}</p>}
      </form>
    </Drawer>
  )
}
