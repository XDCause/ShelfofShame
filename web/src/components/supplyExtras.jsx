import { useEffect, useRef, useState } from 'react'
import { api, imageUrl, shortDate } from '../api.js'
import { useApp } from '../core/app-context.js'
import Fold from './Fold.jsx'

// More for Supplies (2026-10-21): colours (a swatch, its colour family, guessed from the bottle photo), and the item
// panel's extra sections - shelf life, set aside for a build, the usage forecast, maintenance, warranty and receipts.
// Maintenance, warranty and receipts are shared with gear (volleyball's and hiking's GearPanel).

// ---------------------------------------------------------------- colours
const hsl = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  const d = max - min
  if (!d) return [0, 0, l]
  const s = d / (1 - Math.abs(2 * l - 1))
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  return [(h * 60 + 360) % 360, s, l]
}
export const FAMILIES = ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Purple', 'Pink', 'Brown', 'White', 'Grey', 'Black']
// A swatch's family, for the colour filter: greys by lightness, browns as dark warm colours, the rest by hue.
export function familyOf(hex) {
  if (!hex) return null
  const [h, s, l] = hsl(hex)
  if (l < 0.13) return 'Black'
  if (s < 0.14) return l > 0.85 ? 'White' : 'Grey'
  if (h < 50 && l < 0.42) return 'Brown'
  if (h < 15 || h >= 345) return 'Red'
  if (h < 40) return 'Orange'
  if (h < 68) return 'Yellow'
  if (h < 170) return 'Green'
  if (h < 255) return 'Blue'
  if (h < 300) return 'Purple'
  return 'Pink'
}
// For "sort by colour": by family, then hue, then lightness.
export const colourKey = (hex) => {
  if (!hex) return 999
  const [h, , l] = hsl(hex)
  return FAMILIES.indexOf(familyOf(hex)) * 1000 + Math.round(h) + l
}

// The paint's colour from its bottle photo: the commonest strongly coloured shade, leaving out the white background and
// the label's black and white print (a guess - you can always pick it yourself).
export function swatchFromImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = 48
      c.height = 48
      const g = c.getContext('2d', { willReadFrequently: true })
      g.drawImage(img, 0, 0, 48, 48)
      const px = g.getImageData(0, 0, 48, 48).data
      const bins = new Map()
      for (let i = 0; i < px.length; i += 4) {
        const [r, gg, b, a] = [px[i], px[i + 1], px[i + 2], px[i + 3]]
        if (a < 200 || (r > 225 && gg > 225 && b > 225)) continue          // background
        const key = `${r >> 4},${gg >> 4},${b >> 4}`
        const sat = (Math.max(r, gg, b) - Math.min(r, gg, b)) / 255
        const bin = bins.get(key) ?? { n: 0, w: 0, r: 0, g: 0, b: 0 }
        bin.n += 1
        bin.w += 1 + sat * 2
        bin.r += r
        bin.g += gg
        bin.b += b
        bins.set(key, bin)
      }
      const best = [...bins.values()].sort((x, y) => y.w - x.w)[0]
      if (!best) { reject(new Error('No colour found in the photo.')); return }
      resolve(`#${[best.r, best.g, best.b].map((v) => Math.round(v / best.n).toString(16).padStart(2, '0')).join('')}`)
    }
    img.onerror = () => reject(new Error("Couldn't read the photo."))
    img.src = src
  })
}

export function Swatch({ hex, size = 14 }) {
  if (!hex) return null
  return <span className="sw-dot" style={{ background: hex, width: size, height: size }} title={`${familyOf(hex)} (${hex})`} aria-hidden="true" />
}

const monthsAgo = (iso) => Math.round((Date.now() - new Date(`${iso}T12:00:00`)) / (30.44 * 86400000))

// ---------------------------------------------------------------- the item panel's extra sections
export function SupplyMore({ item, save, onOpenModel }) {
  const { refreshKey } = useApp()
  const [models, setModels] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.listModels().then((all) => setModels(all.filter((m) => !['Wanted', 'Finished', 'Sold', 'Gone'].includes(m.status)))).catch(() => {}) }, [refreshKey])
  const guess = async () => {
    setBusy(true)
    setError('')
    try { await save({ swatch: await swatchFromImage(imageUrl(item)) }) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return (
    <>
      {(item.out_by || item.uses_per_month) && (
        <section className="panel-section">
          <p className="sx-forecast">
            📈 You use about <strong>{item.uses_per_month}</strong> a month
            {item.out_by && <> · {item.qty_on_hand === 1 ? 'your last one' : `your ${item.qty_on_hand}`} should last until about <strong>{shortDate(item.out_by)}</strong></>}
          </p>
        </section>
      )}
      <section className="panel-section quick-grid">
        <label className="field">
          <span className="field-label">Opened on</span>
          <input type="date" value={item.opened_on ?? ''} onChange={(e) => save({ opened_on: e.target.value || null })} />
        </label>
        <label className="field">
          <span className="field-label">Check after (months)</span>
          <input type="number" min="1" max="240" value={item.shelf_months ?? ''} placeholder={item.shelf_life ? `${item.shelf_life} (its category)` : 'never'}
            onChange={(e) => save({ shelf_months: e.target.value ? Number(e.target.value) : null })} />
        </label>
        {item.opened_on && item.check_by && (
          <p className={`field wide small ${item.check_due ? 'sx-warn' : 'muted'}`}>
            {item.check_due ? `⚠️ Opened ${monthsAgo(item.opened_on)} months ago - check it hasn't dried out (or thickened).`
              : `Opened ${shortDate(item.opened_on)}; check it after ${shortDate(item.check_by)}.`}
          </p>
        )}
        <label className="field">
          <span className="field-label">Colour</span>
          <span className="sx-colour">
            <input type="color" value={item.swatch ?? '#888888'} aria-label="Its colour" onChange={(e) => save({ swatch: e.target.value })} />
            {item.has_image && <button type="button" className="plain small" disabled={busy} onClick={guess}>From the photo</button>}
            {item.swatch && <button type="button" className="plain small" onClick={() => save({ swatch: null })}>Clear</button>}
          </span>
        </label>
        <label className="field">
          <span className="field-label">Set aside for</span>
          <select value={item.reserved_model_id ?? ''} onChange={(e) => save({ reserved_model_id: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Nothing in particular</option>
            {models.map((m) => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
          </select>
        </label>
        {item.reserved_model_id && (
          <p className="field wide small">🔖 Kept for <button type="button" className="plain small" onClick={() => onOpenModel(item.reserved_model_id)}>{item.reserved_for}</button> - use it there first.</p>
        )}
        {error && <p className="alert error small field wide">{error}</p>}
      </section>
      <section className="panel-section">
        <Fold title="Maintenance" detail="cleaning, new blades, service">
          <Maintenance kind="supply" id={item.supply_id} hobby="models" name={item.name} />
        </Fold>
      </section>
      <section className="panel-section">
        <Fold title="Warranty and receipts" detail={item.warranty_until ? `warranty until ${shortDate(item.warranty_until)}` : 'receipts, manuals'}>
          <Warranty value={item.warranty_until} soon={item.warranty_soon} onChange={(v) => save({ warranty_until: v })} />
          <Attachments kind="supply" id={item.supply_id} />
        </Fold>
      </section>
    </>
  )
}

export function Warranty({ value, soon, onChange }) {
  return (
    <label className="field sx-warranty">
      <span className="field-label">Warranty until</span>
      <input type="date" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)} />
      {soon && <span className="badge low">Ends soon</span>}
    </label>
  )
}

// Receipts, manuals and warranties: a photo or a PDF each, opened in a new tab.
export function Attachments({ kind, id }) {
  const [files, setFiles] = useState(null)
  const [type, setType] = useState('Receipt')
  const [error, setError] = useState('')
  const input = useRef(null)
  useEffect(() => { api.attachments(kind, id).then(setFiles).catch(() => setFiles([])) }, [kind, id])
  const add = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError('')
    try { const made = await api.addAttachment(kind, id, file, type); setFiles((f) => [...(f ?? []), made]) } catch (err) { setError(err.message) }
  }
  return (
    <div className="sx-files">
      {files?.length > 0 && (
        <ul className="sx-file-list">
          {files.map((f) => (
            <li key={f.attachment_id}>
              <a href={api.attachmentUrl(f.attachment_id)} target="_blank" rel="noreferrer">{f.content_type === 'application/pdf' ? '📄' : '🖼️'} {f.name}</a>
              <span className="muted small"> {f.kind} · {Math.max(1, Math.round(f.size / 1024))} KB</span>
              <button type="button" className="plain small" aria-label={`Delete ${f.name}`}
                onClick={async () => { await api.deleteAttachment(f.attachment_id); setFiles((all) => all.filter((x) => x.attachment_id !== f.attachment_id)) }}>×</button>
            </li>
          ))}
        </ul>
      )}
      <div className="sx-file-add">
        <select value={type} onChange={(e) => setType(e.target.value)} aria-label="What it is">
          {['Receipt', 'Manual', 'Warranty', 'Other'].map((k) => <option key={k}>{k}</option>)}
        </select>
        <input ref={input} type="file" accept="application/pdf,image/*" onChange={add} hidden />
        <button type="button" className="secondary" onClick={() => input.current.click()}>+ Attach a photo or PDF</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}

// Maintenance: to-dos for this tool or piece of gear (repeating ones come back when ticked) - on the to-do list and Home too.
export function Maintenance({ kind, id, hobby, name }) {
  const { refreshKey, changed, showToast } = useApp()
  const [todos, setTodos] = useState(null)
  const [title, setTitle] = useState('')
  const [repeats, setRepeats] = useState('monthly')
  const [due, setDue] = useState('')
  useEffect(() => { api.maintenance(kind, id).then(setTodos).catch(() => setTodos([])) }, [kind, id, refreshKey])
  const add = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try {
      await api.addTodo({ title: title.trim(), repeats, due_on: due || null, hobby, [`${kind}_id`]: id })
      setTitle('')
      changed()
      showToast(`Added: ${title.trim()} (${name})`)
    } catch (err) {
      showToast(err.message)
    }
  }
  return (
    <div className="sx-maint">
      {todos?.length > 0 ? (
        <ul className="sx-maint-list">
          {todos.map((t) => (
            <li key={t.todo_id}>
              <button type="button" className="secondary small" onClick={async () => { await api.todoDone(t.todo_id); changed() }}>Done</button>
              <span><strong>{t.title}</strong><span className="muted small"> {t.repeats !== 'never' ? `· ${t.repeats}` : ''}{t.due_on ? ` · due ${shortDate(t.due_on)}` : ''}</span></span>
            </li>
          ))}
        </ul>
      ) : todos && <p className="muted small">Nothing to look after yet.</p>}
      <form className="sx-maint-add" onSubmit={add}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Clean the airbrush" aria-label="Maintenance task" maxLength={200} />
        <select value={repeats} onChange={(e) => setRepeats(e.target.value)} aria-label="How often">
          <option value="never">Once</option><option value="weekly">Every week</option><option value="monthly">Every month</option><option value="daily">Every day</option>
        </select>
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="First due" />
        <button type="submit" className="secondary">Add</button>
      </form>
    </div>
  )
}
