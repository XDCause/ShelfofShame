import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { useApp } from '../app-context.js'

const keyOf = (t) => `${t.page_id}:${t.block_id}`

// Every open to-do from every journal page (the editor's check lists), ticked off right here.
// A ticked item stays on the list, struck through, until the list reloads, so a slip of the
// finger can be unticked. `limit` shows only the first few (Home).
export default function TodoList({ limit, card = false }) {
  const { refreshKey } = useApp()
  const [items, setItems] = useState(null)
  const [ticked, setTicked] = useState(() => new Set())
  const [error, setError] = useState('')

  useEffect(() => {
    api.listTodos().then((list) => { setItems(list); setTicked(new Set()) }).catch(() => setItems([]))
  }, [refreshKey])

  if (!items?.length) return null
  const shown = limit ? items.slice(0, limit) : items

  const tick = async (t) => {
    const key = keyOf(t)
    const checked = !ticked.has(key)
    const flip = (on) => setTicked((s) => { const n = new Set(s); if (on) n.add(key); else n.delete(key); return n })
    flip(checked)
    try {
      await api.tickTodo(t.page_id, t.block_id, checked)
      setError('')
    } catch (e) {
      flip(!checked)
      setError(e.message)
    }
  }

  const list = (
    <div className="todos">
      <h3 className="section-title">To do <span className="chip-count">{items.length - ticked.size}</span></h3>
      {error && <p className="alert error small">{error}</p>}
      <ul className="list todo-list">
        {shown.map((t) => {
          const done = ticked.has(keyOf(t))
          return (
            <li key={keyOf(t)}>
              <label className={done ? 'todo done' : 'todo'}>
                <input type="checkbox" checked={done} onChange={() => tick(t)} />
                <span>{t.text}</span>
              </label>
              <Link to={`/journal/${t.page_id}`} className="todo-page">{t.icon} {t.title || 'Untitled'}</Link>
            </li>
          )
        })}
      </ul>
      {limit && items.length > limit && <Link to="/journal" className="small">{items.length - limit} more to do</Link>}
    </div>
  )
  return card ? <section className="card">{list}</section> : list
}
