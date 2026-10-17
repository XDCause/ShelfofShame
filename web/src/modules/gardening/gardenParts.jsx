import { useEffect, useRef, useState } from 'react'
import { api, shortDate } from '../../api.js'
import PhotoPick from '../../components/PhotoPick.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// The Gardening hobby's shared pieces: the choice lists, a plant's picture (an emoji by what it is),
// stages, due dates, the Watered / Fed buttons, notes with photos (form, timeline, viewer).

export const useGardenLists = () => useShared('garden-lists', () => api.gardenLists())
export const useGardenSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`garden-summary-${refreshKey}`, () => api.gardenSummary())
}

// A picture for a plant: by name first (tomato, chilli...), else by its kind.
const BY_NAME = [[/tomato/, '🍅'], [/chill?i/, '🌶️'], [/capsicum|pepper/, '🫑'], [/strawberr/, '🍓'], [/lemon|lime|citrus/, '🍋'],
  [/blueberr/, '🫐'], [/cucumber|zucchini/, '🥒'], [/carrot/, '🥕'], [/lettuce|spinach|silverbeet|chard|bok|kale|rocket/, '🥬'],
  [/onion|chive|leek/, '🧅'], [/garlic/, '🧄'], [/pea\b|peas|snow pea/, '🫛'], [/bean/, '🫘'], [/ginger|turmeric/, '🫚'],
  [/mushroom/, '🍄'], [/beet|radish/, '🥕'], [/basil|mint|parsley|coriander|thyme|oregano|sage|dill|rosemary|herb/, '🌿'],
  [/aloe|jade|cact|succulent/, '🌵'], [/lily|marigold|calendula|nasturtium|flower/, '🌼'], [/monstera|pothos|fern|ivy|zz|snake/, '🪴']]
const BY_KIND = { Herb: '🌿', 'Leafy green': '🥬', Vegetable: '🥕', Fruit: '🍓', Microgreens: '🌱', Flower: '🌼', Houseplant: '🪴',
  Succulent: '🌵', Native: '🌾' }
export function plantEmoji(p) {
  const name = `${p.name ?? ''} ${p.guide_name ?? ''}`.toLowerCase()
  return BY_NAME.find(([re]) => re.test(name))?.[1] ?? BY_KIND[p.plant_kind ?? p.kind] ?? '🌱'
}
export const CONTAINER_EMOJI = { 'Worm farm': '🪱', 'Bokashi bin': '♻️', Compost: '♻️', Hydroponic: '💧', 'Seed tray': '🌱' }

export const STAGE_TONE = { Planned: '', Sown: 'low', Sprouted: 'ok', Seedling: 'ok', Growing: 'ok', Flowering: 'purple',
  Fruiting: 'purple', Harvesting: 'tint', Dormant: '', Done: '', Died: 'out' }
export const StagePill = ({ stage }) => <span className={`pill ${STAGE_TONE[stage] ?? ''}`}>{stage}</span>

const dayMs = 86400000
export const daysFrom = (a, b) => Math.round((new Date(`${b}T12:00:00`) - new Date(`${a}T12:00:00`)) / dayMs)
// "today", "2 days late", "in 3 days" - against the API's "today" (Brisbane), passed in.
export function dueText(due, today) {
  if (!due) return ''
  const d = daysFrom(today, due)
  return d === 0 ? 'today' : d < 0 ? `${-d} day${d === -1 ? '' : 's'} late` : d === 1 ? 'tomorrow' : `in ${d} days`
}
export const isDue = (due, today) => due && due <= today
export const localToday = () => new Date().toLocaleDateString('en-CA')

// Watered / Fed for one plant, a container or a whole space.
export function CareButtons({ planting, containerId, spaceId, onDone, small = true }) {
  const { changed, showToast } = useApp()
  const [busy, setBusy] = useState('')
  const run = async (action) => {
    setBusy(action)
    try {
      const body = planting ? { action, planting_ids: [planting.planting_id] } : containerId ? { action, container_id: containerId }
        : { action, space_id: spaceId }
      const r = await api.gardenCare(body)
      showToast(r.done ? `${action === 'watered' ? 'Watered' : 'Fed'} ${r.done === 1 ? r.names[0] : `${r.done} plants`}` : 'No plants there yet')
      changed()
      onDone?.()
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy('')
    }
  }
  return (
    <span className="button-row garden-care">
      <button type="button" className={`secondary${small ? ' small' : ''}`} disabled={!!busy} onClick={() => run('watered')}>
        {busy === 'watered' ? 'Watering...' : '💧 Watered'}</button>
      <button type="button" className={`secondary${small ? ' small' : ''}`} disabled={!!busy} onClick={() => run('fed')}>
        {busy === 'fed' ? 'Feeding...' : '🧪 Fed'}</button>
    </span>
  )
}

const AMOUNT_KINDS = ['Harvested', 'Measured']
const TAG_KINDS = ['Pest', 'Problem', 'Treated']
const KIND_LABEL = { Note: 'Note', Photo: 'Photo', Harvested: 'Harvest', Pest: 'Pest', Problem: 'Problem', Treated: 'Treated',
  Pruned: 'Pruned', Repotted: 'Repotted', Sprouted: 'Sprouted', Flowered: 'Flowered', Measured: 'Measurement', Watered: 'Watered',
  Fed: 'Fed', Moved: 'Moved' }
const KIND_TONE = { Harvested: 'ok', Pest: 'out', Problem: 'out', Treated: 'low', Sprouted: 'ok', Flowered: 'purple', Watered: 'tint',
  Fed: 'tint', Photo: 'teal', Repotted: 'low' }

// A note about a plant / container / space: what kind, when, words, an amount (harvests, measurements),
// problem tags, and photos (shrunk to 1600 px; sent after the note is saved).
export function LogForm({ about, kinds, defaultKind = 'Note', onSaved }) {
  const lists = useGardenLists().data
  const [kind, setKind] = useState(defaultKind)
  const [on, setOn] = useState(localToday())
  const [text, setText] = useState('')
  const [amount, setAmount] = useState('')
  const [unit, setUnit] = useState('g')
  const [tags, setTags] = useState([])
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const previews = useRef([])
  useEffect(() => () => previews.current.forEach(URL.revokeObjectURL), [])
  const addFiles = (picked) => {
    const list = [picked].flat().map((f) => { const url = URL.createObjectURL(f); previews.current.push(url); return { f, url } })
    setFiles((x) => [...x, ...list])
    if (!text && kind === 'Note') setKind('Photo')
  }
  const save = async (e) => {
    e.preventDefault()
    if (!text.trim() && !files.length && !amount && !tags.length && !['Watered', 'Fed', 'Pruned', 'Repotted', 'Sprouted', 'Flowered'].includes(kind)) {
      setError('Write something or add a photo.')
      return
    }
    setBusy('Saving...')
    setError('')
    try {
      const log = await api.addGardenLog({ ...about, kind, happened_on: on, text,
        amount: AMOUNT_KINDS.includes(kind) && amount !== '' ? Number(amount) : null, unit: AMOUNT_KINDS.includes(kind) ? unit : null,
        tags: TAG_KINDS.includes(kind) ? tags : [] })
      for (const [i, { f }] of files.entries()) {
        setBusy(`Adding photo ${i + 1} of ${files.length}...`)
        await api.addGardenPhoto(log.log_id, await shrink(f, 1600))
      }
      setText(''); setAmount(''); setTags([]); setFiles([]); setKind(defaultKind)
      onSaved?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }
  const choices = kinds ?? lists?.log_kinds.filter((k) => !['Watered', 'Fed', 'Moved'].includes(k)) ?? ['Note', 'Photo']
  return (
    <form className="garden-log-form" onSubmit={save}>
      <div className="garden-log-row">
        <label className="field">What
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            {choices.map((k) => <option key={k} value={k}>{KIND_LABEL[k] ?? k}</option>)}
          </select>
        </label>
        <label className="field">When
          <input type="date" value={on} max={localToday()} onChange={(e) => setOn(e.target.value)} required />
        </label>
        {AMOUNT_KINDS.includes(kind) && (
          <>
            <label className="field garden-amount">{kind === 'Harvested' ? 'How much' : 'Reading'}
              <input type="number" min="0" step="any" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="field garden-unit">Unit
              <select value={unit} onChange={(e) => setUnit(e.target.value)}>
                {(lists?.units ?? ['g']).map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </label>
          </>
        )}
      </div>
      {TAG_KINDS.includes(kind) && (
        <div className="chip-row garden-tags" role="group" aria-label="What's wrong">
          {(lists?.problem_tags ?? []).map((t) => (
            <button key={t} type="button" className="chip-filter" aria-pressed={tags.includes(t)}
              onClick={() => setTags((x) => (x.includes(t) ? x.filter((y) => y !== t) : [...x, t]))}>{t}</button>
          ))}
        </div>
      )}
      <label className="field">Notes
        <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)}
          placeholder={kind === 'Harvested' ? 'How it tasted, what you made...' : 'What you noticed, what you did...'} />
      </label>
      {files.length > 0 && (
        <ul className="garden-pending">
          {files.map(({ url }, i) => (
            <li key={url}><img src={url} alt="" />
              <button type="button" className="plain small" aria-label="Don't add this photo"
                onClick={() => setFiles((x) => x.filter((_, j) => j !== i))}>×</button></li>
          ))}
        </ul>
      )}
      {error && <p className="alert error small">{error}</p>}
      <div className="button-row">
        <PhotoPick onFile={addFiles} multiple className="secondary small" label="Add photos" />
        <span className="spacer" />
        <button type="submit" className="primary small" disabled={!!busy}>{busy || 'Save note'}</button>
      </div>
    </form>
  )
}

// Notes newest first, with their photos (tap one to see it big). Watering / feeding are folded into a
// count so the interesting notes stand out.
export function LogTimeline({ logs, onChanged, showRoutine = false }) {
  const [viewing, setViewing] = useState(null)       // {photos, index}
  const [all, setAll] = useState(showRoutine)
  const routine = logs.filter((l) => l.kind === 'Watered' || l.kind === 'Fed')
  const shown = all ? logs : logs.filter((l) => l.kind !== 'Watered' && l.kind !== 'Fed')
  const remove = async (log) => {
    if (!window.confirm('Remove this note and its photos?')) return
    await api.deleteGardenLog(log.log_id)
    onChanged?.()
  }
  return (
    <>
      {logs.length === 0 && <p className="muted small">Nothing written yet.</p>}
      <ul className="garden-logs">
        {shown.map((l) => (
          <li key={l.log_id}>
            <span className="garden-log-head">
              <span className={`pill ${KIND_TONE[l.kind] ?? ''}`}>{KIND_LABEL[l.kind] ?? l.kind}</span>
              <span className="muted small">{shortDate(l.happened_on)}</span>
              {l.amount != null && <strong className="small">{Number(l.amount).toLocaleString()} {l.unit}</strong>}
              <span className="spacer" />
              <button type="button" className="plain small destructive" onClick={() => remove(l)} aria-label="Remove note">×</button>
            </span>
            {l.tags?.length > 0 && <span className="garden-log-tags">{l.tags.map((t) => <span key={t} className="chip">{t}</span>)}</span>}
            {l.text && <p className="garden-log-text">{l.text}</p>}
            {l.photos.length > 0 && (
              <span className="garden-log-photos">
                {l.photos.map((p, i) => (
                  <button key={p.photo_id} type="button" className="garden-thumb" onClick={() => setViewing({ photos: l.photos, index: i, log: l })}
                    aria-label={`Photo ${i + 1} from ${shortDate(l.happened_on)}`}><img src={p.url} alt="" loading="lazy" /></button>
                ))}
              </span>
            )}
          </li>
        ))}
      </ul>
      {routine.length > 0 && (
        <button type="button" className="plain small" onClick={() => setAll(!all)}>
          {all ? 'Hide watering and feeding' : `Show watering and feeding (${routine.length})`}</button>
      )}
      {viewing && <PhotoViewer {...viewing} onClose={() => setViewing(null)}
        onDeleted={() => { setViewing(null); onChanged?.() }} />}
    </>
  )
}

// One photo big, with the note it belongs to; arrows for the others; remove. Escape closes only this.
export function PhotoViewer({ photos, index: start = 0, log, onClose, onDeleted }) {
  const [index, setIndex] = useState(start)
  const box = useRef(null)
  useEffect(() => { box.current?.focus() }, [])
  const p = photos[index]
  if (!p) return null
  const go = (n) => setIndex((index + n + photos.length) % photos.length)
  const keys = (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
    } else if (e.key === 'ArrowRight') {
      go(1)
    } else if (e.key === 'ArrowLeft') {
      go(-1)
    }
  }
  const remove = async () => {
    if (!window.confirm('Remove this photo?')) return
    await api.deleteGardenPhoto(p.photo_id)
    onDeleted?.()
  }
  const when = log?.happened_on ?? p.happened_on
  const words = log?.text ?? p.text
  return (
    <div className="garden-viewer" role="dialog" aria-modal="true" aria-label="Photo" tabIndex={-1} ref={box} onKeyDown={keys}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="garden-viewer-card">
        <img src={p.url} alt={words ?? ''} />
        <p className="small">{[when && shortDate(when), p.planting_name, words].filter(Boolean).join(' · ')}</p>
        <div className="button-row">
          {photos.length > 1 && <button type="button" className="plain" onClick={() => go(-1)} aria-label="Previous photo">‹</button>}
          {photos.length > 1 && <span className="muted small">{index + 1} of {photos.length}</span>}
          {photos.length > 1 && <button type="button" className="plain" onClick={() => go(1)} aria-label="Next photo">›</button>}
          <span className="spacer" />
          {onDeleted && <button type="button" className="plain destructive" onClick={remove}>Remove photo</button>}
          <button type="button" className="secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

// 12 little month boxes, the sowing months filled in (this month outlined).
const MONTH_LETTERS = 'JFMAMJJASOND'
export function SowMonths({ months, label = 'Sowing months' }) {
  const now = new Date().getMonth() + 1
  return (
    <span className="sow-months" role="img" aria-label={`${label}: ${months.length ? months.map((m) => new Date(2000, m - 1, 1)
      .toLocaleDateString('en-AU', { month: 'short' })).join(', ') : 'none'}`}>
      {[...MONTH_LETTERS].map((l, i) => (
        <span key={i} className={[months.includes(i + 1) && 'on', i + 1 === now && 'now'].filter(Boolean).join(' ')}>{l}</span>
      ))}
    </span>
  )
}
