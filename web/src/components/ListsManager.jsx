import { useState } from 'react'
import { api } from '../api.js'

// One of Settings > Lists (brands, categories, storage locations): the choices offered when adding or editing.
// Anything still in use can't be removed: the database's foreign keys refuse it, and the button is disabled to match.
export function LookupList({ kind, placeholder, items, onChanged }) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const run = async (fn) => {
    try {
      await fn()
      setError('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }
  const add = (e) => {
    e.preventDefault()
    if (name.trim()) run(async () => { await api.addLookup(kind, name.trim()); setName('') })
  }

  return (
    <>
      <ul className="list">
        {items.map((item) => (
          <li key={item.id}>
            <span className="grow">{item.name}</span>
            <span className="muted small num" title={`Used ${item.uses} times`}>{item.uses || ''}</span>
            <button type="button" className="icon-btn small" onClick={() => run(() => api.deleteLookup(kind, item.id))}
              disabled={item.uses > 0} title={item.uses > 0 ? 'In use - can’t remove' : `Remove ${item.name}`}
              aria-label={`Remove ${item.name}`}>✕</button>
          </li>
        ))}
      </ul>
      <form onSubmit={add} className="add-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={placeholder} aria-label={placeholder} />
        <button type="submit" className="secondary" disabled={!name.trim()}>Add</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
    </>
  )
}
