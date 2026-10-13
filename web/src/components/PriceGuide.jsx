import { useEffect, useState } from 'react'
import { api, money } from '../api.js'

const blank = { label: '', title_contains: '', paint_type: '', size: '', price: '' }

// Your usual prices. A product gets the price of the first rule it fits: every condition a rule
// has must match (name contains / paint type / size). Used for the wishlist's expected price and
// pre-filled when adding.
export default function PriceGuide({ lookups }) {
  const [rules, setRules] = useState(null)
  const [form, setForm] = useState(blank)
  const [editing, setEditing] = useState(null) // rule_id being edited, or 'new'
  const [error, setError] = useState('')

  const load = () => api.priceGuide().then(setRules).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const set = (f) => (e) => setForm((x) => ({ ...x, [f]: e.target.value }))
  const start = (rule) => {
    setError('')
    setEditing(rule ? rule.rule_id : 'new')
    setForm(rule ? Object.fromEntries(Object.keys(blank).map((k) => [k, rule[k] == null ? '' : String(rule[k])])) : blank)
  }
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      if (editing === 'new') await api.addPriceRule({ ...form, sort_order: (rules.at(-1)?.sort_order ?? 0) + 1 })
      else await api.updatePriceRule(editing, form)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }
  const remove = async (rule) => {
    try {
      await api.deletePriceRule(rule.rule_id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (!rules) return <p className="muted small">{error || 'Loading...'}</p>
  const describe = (r) => [r.title_contains && `name has "${r.title_contains}"`, r.paint_type, r.size]
    .filter(Boolean).join(' · ')

  return (
    <>
      <ul className="list">
        {rules.map((r) => (
          <li key={r.rule_id}>
            <button type="button" className="row-button" onClick={() => start(r)}>
              <span className="grow"><strong>{r.label}</strong><span className="muted small block">{describe(r)}</span></span>
              <span className="num">{money(r.price)}</span>
            </button>
          </li>
        ))}
      </ul>
      {editing ? (
        <form className="inline-form" onSubmit={save}>
          <label className="field wide"><span className="field-label">Name</span>
            <input value={form.label} onChange={set('label')} required placeholder="e.g. LP lacquer" /></label>
          <label className="field wide"><span className="field-label">Product name contains</span>
            <input value={form.title_contains} onChange={set('title_contains')} placeholder="e.g. PANEL LINE ACCENT" /></label>
          <label className="field"><span className="field-label">Paint type</span>
            <select value={form.paint_type} onChange={set('paint_type')}>
              <option value="">Any</option>
              {lookups.paint_types.map((t) => <option key={t}>{t}</option>)}
            </select></label>
          <label className="field"><span className="field-label">Size</span>
            <input value={form.size} onChange={set('size')} placeholder="e.g. 10ml" /></label>
          <label className="field"><span className="field-label">Price ($)</span>
            <input type="number" min="0" step="0.01" inputMode="decimal" value={form.price} onChange={set('price')} required /></label>
          <div className="button-row wide">
            <button type="submit" className="primary">Save</button>
            <button type="button" className="plain" onClick={() => setEditing(null)}>Cancel</button>
            {editing !== 'new' && (
              <button type="button" className="plain destructive"
                onClick={() => { remove(rules.find((r) => r.rule_id === editing)); setEditing(null) }}>Delete rule</button>
            )}
          </div>
        </form>
      ) : (
        <button type="button" className="plain" onClick={() => start(null)}>+ Add a price</button>
      )}
      {error && <p className="alert error small">{error}</p>}
      <p className="hint">The first rule that fits wins. Blank conditions match anything.</p>
    </>
  )
}
