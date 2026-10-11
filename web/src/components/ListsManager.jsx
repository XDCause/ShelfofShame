import { useState } from 'react'
import { api } from '../api.js'

const LISTS = [
  { kind: 'brands', title: 'Brands', placeholder: 'New brand' },
  { kind: 'categories', title: 'Categories', placeholder: 'New category' },
  { kind: 'locations', title: 'Storage locations', placeholder: 'New location' },
]

// Add or remove dropdown entries. Anything still used by a supply can't be removed:
// the database's foreign keys refuse it, and the button is disabled to match.
export default function ListsManager({ lookups, onChanged }) {
  return (
    <section className="card lists">
      <h2>Manage lists</h2>
      <p className="muted">The choices offered in the form. Numbers show how many supplies use each.</p>
      <div className="lists-grid">
        {LISTS.map((l) => (
          <LookupList key={l.kind} {...l} items={lookups[l.kind]} onChanged={onChanged} />
        ))}
      </div>
    </section>
  )
}

function LookupList({ kind, title, placeholder, items, onChanged }) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const add = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    try {
      await api.addLookup(kind, name.trim())
      setName('')
      setError('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (item) => {
    try {
      await api.deleteLookup(kind, item.id)
      setError('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="lookup">
      <h3>{title} <span className="count">{items.length}</span></h3>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <span>{item.name}</span>
            <span className="uses" title={`Used by ${item.uses} supplies`}>{item.uses || ''}</span>
            <button
              className="remove"
              onClick={() => remove(item)}
              disabled={item.uses > 0}
              title={item.uses > 0 ? 'In use - can’t remove' : `Remove ${item.name}`}
              aria-label={`Remove ${item.name}`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={add} className="add-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={placeholder} aria-label={placeholder} />
        <button type="submit" disabled={!name.trim()}>Add</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}
