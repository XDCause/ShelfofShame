import { useRef, useState } from 'react'
import { api } from '../api.js'
import { shrink } from './PhotoUpload.jsx'
import { Field } from './SupplyFields.jsx'

// Simple forms for the newer parts (calendar events, board games, volleyball): describe the
// fields once and get the form, its state and what to send to the API.
//   { name, label, type: text|number|money|date|time|select|textarea|url, options, required, wide,
//     placeholder, hint }
// The form holds strings (what inputs give); toPayload turns blanks into null and numbers into
// numbers, the way the API wants them.

const formFrom = (fields, record, defaults = {}) => Object.fromEntries(fields.map((f) => {
  const v = record?.[f.name] ?? defaults[f.name]
  return [f.name, v == null ? '' : f.type === 'time' ? String(v).slice(0, 5) : String(v)]
}))

export const toPayload = (fields, form) => Object.fromEntries(fields.map((f) => {
  const v = form[f.name].trim()
  if (v === '') return [f.name, null]
  return [f.name, f.type === 'number' ? Number(v) : v]
}))

export function useRecordForm(fields, record, defaults) {
  const [form, setForm] = useState(() => formFrom(fields, record, defaults))
  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }))
  return { form, setForm, set, payload: () => toPayload(fields, form) }
}

export default function RecordFields({ fields, form, set }) {
  return (
    <fieldset>
      {fields.map((f) => (
        <Field key={f.name} label={f.label} required={f.required} wide={f.wide || f.type === 'textarea'} hint={f.hint}>
          {f.type === 'select' ? (
            <select value={form[f.name]} onChange={set(f.name)} required={f.required}>
              {!f.required && <option value="">—</option>}
              {f.options.map((o) => {
                const [value, label] = Array.isArray(o) ? o : [o, o]
                return <option key={value} value={value}>{label}</option>
              })}
            </select>
          ) : f.type === 'textarea' ? (
            <textarea rows="3" value={form[f.name]} onChange={set(f.name)} placeholder={f.placeholder} />
          ) : (
            <input type={f.type === 'money' ? 'number' : f.type ?? 'text'} value={form[f.name]} onChange={set(f.name)}
              required={f.required} placeholder={f.placeholder} list={f.list}
              {...(f.type === 'number' ? { min: f.min ?? 0, step: 1, inputMode: 'numeric' } : {})}
              {...(f.type === 'money' ? { min: 0, step: '0.01', inputMode: 'decimal' } : {})} />
          )}
        </Field>
      ))}
    </fieldset>
  )
}

// A photo kept on the record itself (a board game's box, a pair of shoes): show it, replace it,
// remove it. `path` is the record's API address ('/board-games/3'); `url` its current photo URL.
export function RowPhoto({ path, url, onChanged, label = 'photo' }) {
  const input = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async (fn, message) => {
    setBusy(true)
    setError('')
    try {
      await fn()
      onChanged(message)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  const pick = (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) run(async () => api.uploadRowPhoto(path, await shrink(file)), 'Photo saved ✓')
  }

  return (
    <div className="row-photo">
      <div className="item-photo">
        {url ? <img src={url} alt="" /> : <span className="photo-missing">No {label}</span>}
      </div>
      <input ref={input} type="file" accept="image/*" onChange={pick} hidden />
      <span className="button-row">
        <button type="button" className="plain small" onClick={() => input.current.click()} disabled={busy}>
          {busy ? 'Saving...' : url ? 'Replace photo' : 'Add a photo'}
        </button>
        {url && <button type="button" className="plain small destructive" disabled={busy}
          onClick={() => run(() => api.deleteRowPhoto(path), 'Photo removed')}>Remove</button>}
      </span>
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}
