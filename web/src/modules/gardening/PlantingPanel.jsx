import { useCallback, useEffect, useState } from 'react'
import { api, money, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import { CareButtons, LogForm, LogTimeline, StagePill, dueText, isDue, plantEmoji } from './gardenParts.jsx'

// One plant (or a row of seedlings): where it is, its stage, harvest window, watering and feeding (due and
// done), warnings (too little sun, a small pot, out of season), notes and photos, its guide, reminders,
// cuttings taken from it. With no id: add a plant - from the guide (its defaults fill in) or by name.

function useContainers() {
  const [containers, setContainers] = useState([])
  useEffect(() => { api.gardenContainers().then(setContainers).catch(() => {}) }, [])
  return containers
}
const containerOptions = (containers) => containers.map((c) => [String(c.container_id), `${c.space_name} › ${c.name}`])

function plantFields(lists, containers, guides, isNew) {
  return [
    ...(isNew ? [{ name: 'guide_id', label: 'Plant (from the guide)', type: 'select', wide: true,
      options: guides.map((g) => [String(g.guide_id), `${g.name}${g.sow_now ? ' · sow now' : ''}`]) }] : []),
    { name: 'name', label: 'Name', required: !isNew, placeholder: isNew ? 'Leave empty to use the guide\'s name' : '' },
    { name: 'variety', label: 'Variety', placeholder: 'e.g. Tumbling Tom' },
    { name: 'container_id', label: 'In', type: 'select', options: containerOptions(containers) },
    { name: 'source', label: 'Started from', type: 'select', required: true, options: lists?.sources ?? ['Seedling'] },
    { name: 'started_on', label: 'Started on', type: 'date', required: true },
    { name: 'quantity', label: 'How many', type: 'number', min: 1 },
    { name: 'water_every_days', label: 'Water every (days)', type: 'number', min: 1, hint: 'Self-watering pots: half as often.' },
    { name: 'feed_every_days', label: 'Feed every (days)', type: 'number', min: 1 },
    ...(isNew ? [] : [
      { name: 'harvest_from', label: 'Harvest from', type: 'date' },
      { name: 'harvest_to', label: 'Harvest until', type: 'date' },
    ]),
    { name: 'bought_from', label: 'Bought from', placeholder: 'Bunnings, a market...' },
    { name: 'price', label: 'Price', type: 'money' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}

const numbers = (p) => {
  for (const k of ['container_id', 'guide_id', 'quantity', 'water_every_days', 'feed_every_days']) if (p[k] != null) p[k] = Number(p[k])
  if (p.price != null) p.price = Number(p.price)
  return p
}

function PlantForm({ planting, defaults, onSaved, onCancel }) {
  const containers = useContainers()
  const [guides, setGuides] = useState([])
  const [lists, setLists] = useState(null)
  useEffect(() => {
    if (!planting) api.gardenGuides().then((g) => setGuides(g.guides)).catch(() => {})
    api.gardenLists().then(setLists).catch(() => {})
  }, [planting])
  const fields = plantFields(lists, containers, guides, !planting)
  const { form, set, setForm, payload } = useRecordForm(fields, planting, defaults)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // Picking from the guide: its watering / feeding rhythm, unless you've typed your own.
  const onSet = (name) => (e) => {
    set(name)(e)
    if (name !== 'guide_id') return
    const g = guides.find((x) => String(x.guide_id) === e.target.value)
    if (g) setForm((f) => ({ ...f, water_every_days: f.water_every_days || String(g.water_every_days),
      feed_every_days: f.feed_every_days || (g.feed_every_days ? String(g.feed_every_days) : ''),
      source: g.sow_how === 'Seed' ? 'Seed' : g.sow_how === 'Cutting' ? 'Cutting' : f.source }))
  }
  const picked = guides.find((g) => String(g.guide_id) === form.guide_id)
  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const p = numbers(payload())
      onSaved(planting ? await api.updateGardenPlanting(planting.planting_id, p) : await api.addGardenPlanting(p))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <form onSubmit={save} className="garden-plant-form">
      <RecordFields fields={fields} form={form} set={onSet} />
      {picked && (
        <p className="small muted">{picked.sun} ({picked.sun_hours_min}+ h) · water {picked.water.toLowerCase()} · pot {picked.pot_min_l ?? '?'} L+
          {picked.days_min && ` · first harvest in ${picked.days_min}–${picked.days_max} days`}
          {picked.fits_spaces.length > 0 ? ` · suits ${picked.fits_spaces.join(', ')}` : ''}</p>
      )}
      {error && <p className="alert error small">{error}</p>}
      <div className="button-row">
        <button type="submit" className="primary" disabled={busy}>{planting ? 'Save' : 'Add plant'}</button>
        {onCancel && <button type="button" className="plain" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}

export default function PlantingPanel({ id: startId = null, containerId = null, guideId = null, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const [id, setId] = useState(startId)
  const [p, setP] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [lists, setLists] = useState(null)
  const reload = useCallback(() => api.gardenPlanting(id).then(setP).catch((e) => setError(e.message)), [id])
  useEffect(() => { if (id != null) reload() }, [id, reload])
  useEffect(() => { api.gardenLists().then(setLists).catch(() => {}) }, [])
  const today = new Date().toLocaleDateString('en-CA')

  if (id == null) {
    const defaults = { started_on: today, source: 'Seedling', quantity: '1', container_id: containerId ? String(containerId) : '',
      guide_id: guideId ? String(guideId) : '' }
    return (
      <Drawer title="Add a plant" onClose={onClose}>
        <section className="panel-section">
          <PlantForm defaults={defaults} onSaved={(x) => { setP(x); setId(x.planting_id); changed() }} onCancel={onClose} />
        </section>
      </Drawer>
    )
  }
  if (!p) return <Drawer title="Plant" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const after = (x) => { setP(x); changed() }
  const stage = async (s) => after(await api.updateGardenPlanting(p.planting_id, { stage: s }))
  const remove = async () => {
    if (!window.confirm(`Remove ${p.name} and all its notes and photos? (To keep its history, set it to Done or Died instead.)`)) return
    await api.deleteGardenPlanting(p.planting_id)
    changed()
    onClose()
  }
  const propagate = async () => {
    const n = window.prompt(`How many cuttings of ${p.name}?`, '1')
    if (!n) return
    const kid = await api.propagatePlanting(p.planting_id, { quantity: Math.max(1, Number(n) || 1), container_id: null })
    changed()
    showToast(`${kid.quantity} new ${p.name} cutting${kid.quantity > 1 ? 's' : ''} - put them in a pot when they root`)
    setId(kid.planting_id)
  }
  const open = (type, props) => { onClose(); openPanel(type, props) }
  const ended = p.stage === 'Done' || p.stage === 'Died'
  const footer = (
    <>
      {!ended && <button type="button" className="secondary" onClick={propagate}>Take cuttings</button>}
      <span className="spacer" />
      {!editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>}
      <button type="button" className="plain destructive" onClick={remove}>Remove</button>
    </>
  )
  const g = p.guide
  return (
    <Drawer title={`${plantEmoji(p)} ${p.name}`} onClose={onClose} footer={footer} wide>
      <section className="panel-section garden-plant-head">
        {p.photo_url ? <img className="garden-plant-photo" src={p.photo_url} alt="" /> : <span className="garden-plant-photo empty" aria-hidden="true">{plantEmoji(p)}</span>}
        <div className="grow">
          <p className="item-sub">{[p.variety, p.quantity > 1 && `${p.quantity} plants`].filter(Boolean).join(' · ')}</p>
          <p className="garden-where">
            <StagePill stage={p.stage} />{' '}
            {p.container_id ? <button type="button" className="link-title small" onClick={() => open('gcontainer', { id: p.container_id })}>
              {p.space_name} › {p.container_name}</button> : <span className="muted small">Not in a pot yet</span>}
          </p>
          {p.harvest_ready && !ended && <p className="pill ok">{p.plant_kind === 'Flower' ? 'In flower' : 'Ready to pick'}</p>}
        </div>
      </section>
      {p.warnings.length > 0 && (
        <section className="panel-section">
          {p.warnings.map((w) => <p key={w} className="alert low small">{w}</p>)}
        </section>
      )}
      {editing ? (
        <section className="panel-section">
          <PlantForm planting={p} onSaved={(x) => { after(x); setEditing(false) }} onCancel={() => setEditing(false)} />
        </section>
      ) : (
        <section className="panel-section">
          <dl className="garden-facts">
            <dt>Started</dt><dd>{shortDate(p.started_on)} <span className="muted">· {p.source.toLowerCase()} · {p.age_days} days ago</span>
              {p.parent && <> · from <button type="button" className="link-title small" onClick={() => setId(p.parent.planting_id)}>{p.parent.name}</button></>}</dd>
            {p.harvest_from && <><dt>{p.plant_kind === 'Flower' ? 'Flowering' : 'Harvest'}</dt><dd>{shortDate(p.harvest_from)}{p.harvest_to && ` – ${shortDate(p.harvest_to)}`}</dd></>}
            {p.water_every_days && <><dt>Water</dt><dd>every {p.water_every_days} day{p.water_every_days > 1 ? 's' : ''}{p.self_watering && ' (self-watering pot: half as often)'}
              {p.water_due_on && <span className={isDue(p.water_due_on, today) ? 'garden-due' : 'muted'}> · {isDue(p.water_due_on, today) ? 'due' : 'next'} {dueText(p.water_due_on, today)}</span>}</dd></>}
            {p.feed_every_days && <><dt>Feed</dt><dd>every {p.feed_every_days} days
              {p.feed_due_on && <span className={isDue(p.feed_due_on, today) ? 'garden-due' : 'muted'}> · {isDue(p.feed_due_on, today) ? 'due' : 'next'} {dueText(p.feed_due_on, today)}</span>}</dd></>}
            {p.harvested.length > 0 && <><dt>Picked</dt><dd>{p.harvested.map((h) => `${h.amount.toLocaleString()} ${h.unit ?? 'times'}`).join(' + ')}</dd></>}
            {(p.bought_from || p.price != null) && <><dt>Bought</dt><dd>{[p.bought_from, p.price != null && money(p.price)].filter(Boolean).join(' · ')}</dd></>}
            {p.ended_on && <><dt>Ended</dt><dd>{shortDate(p.ended_on)}{p.end_reason && ` · ${p.end_reason.toLowerCase()}`}</dd></>}
            {p.children.length > 0 && <><dt>Cuttings</dt><dd>{p.children.map((c) => (
              <button key={c.planting_id} type="button" className="link-title small" onClick={() => setId(c.planting_id)}>{c.name} ({c.stage.toLowerCase()})</button>
            ))}</dd></>}
          </dl>
          {p.notes && <p className="small garden-notes">{p.notes}</p>}
          {!ended && <CareButtons planting={p} onDone={reload} />}
        </section>
      )}
      <section className="panel-section">
        <p className="field-label">Stage</p>
        <div className="chip-row scroll garden-stages" role="group" aria-label="Stage">
          {(lists?.stages ?? []).map((s) => (
            <button key={s} type="button" className="chip-filter" aria-pressed={p.stage === s} onClick={() => stage(s)}>{s}</button>
          ))}
        </div>
      </section>
      <section className="panel-section">
        <h3 className="section-title">Notes and photos</h3>
        <LogForm about={{ planting_id: p.planting_id }} onSaved={reload} />
        <LogTimeline logs={p.logs} onChanged={reload} />
      </section>
      <PlantTasks p={p} onChanged={reload} />
      {g && (
        <section className="panel-section">
          <Fold title={`Growing ${g.name}`} detail={`${g.sun} · water ${g.water.toLowerCase()}`}>
            <dl className="garden-facts">
              <dt>Light</dt><dd>{g.sun} ({g.sun_hours_min}+ h)</dd>
              {g.pot_min_l && <><dt>Pot</dt><dd>{g.pot_min_l} L or more{g.spacing_cm && ` · ${g.spacing_cm} cm apart`}</dd></>}
              {g.days_min && <><dt>Harvest</dt><dd>{g.days_min}–{g.days_max} days from seed</dd></>}
              {g.companions && <><dt>Good with</dt><dd>{g.companions}</dd></>}
              {g.avoid && <><dt>Keep from</dt><dd>{g.avoid}</dd></>}
              {g.pests && <><dt>Watch for</dt><dd>{g.pests}</dd></>}
            </dl>
            {g.tips && <p className="small">{g.tips}</p>}
            {g.harvest_tips && <p className="small"><strong>Picking:</strong> {g.harvest_tips}</p>}
            {g.apartment_tips && <p className="small"><strong>In an apartment:</strong> {g.apartment_tips}</p>}
            <button type="button" className="plain small" onClick={() => open('gguide', { id: g.guide_id })}>Open the guide →</button>
          </Fold>
        </section>
      )}
    </Drawer>
  )
}

// Reminders for this plant: what's coming, done, and a quick new one (once, or every N days).
export function PlantTasks({ p, about = { planting_id: p?.planting_id }, tasks = p?.tasks ?? [], onChanged }) {
  const [title, setTitle] = useState('')
  const [due, setDue] = useState(new Date().toLocaleDateString('en-CA'))
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState('')
  const add = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try {
      await api.addGardenTask({ ...about, title, due_on: due, repeat_days: repeat ? Number(repeat) : null })
      setTitle('')
      setRepeat('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <section className="panel-section">
      <h3 className="section-title">Reminders</h3>
      {tasks.length > 0 && (
        <ul className="garden-tasks">
          {tasks.map((t) => <TaskRow key={t.task_id} t={t} onChanged={onChanged} />)}
        </ul>
      )}
      <form className="garden-task-form" onSubmit={add}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Pinch out the tips" aria-label="New reminder" />
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Due" />
        <select value={repeat} onChange={(e) => setRepeat(e.target.value)} aria-label="Repeat">
          <option value="">Once</option>
          {[3, 7, 14, 28, 90].map((d) => <option key={d} value={d}>Every {d} days</option>)}
        </select>
        <button type="submit" className="secondary small">Add</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

export function TaskRow({ t, onChanged, showWhat = false }) {
  const today = new Date().toLocaleDateString('en-CA')
  const what = showWhat && (t.planting_name || t.container_name || t.space_name)
  return (
    <li className="garden-task">
      <button type="button" className="garden-tick" aria-label={`Done: ${t.title}`}
        onClick={async () => { await api.gardenTaskDone(t.task_id); onChanged() }}>✓</button>
      <span className="grow">
        <span className="item-title">{t.title}</span>
        <span className="item-meta">{[what, t.due_on <= today ? `due ${dueText(t.due_on, today)}` : `${dueText(t.due_on, today)}`,
          t.repeat_days && `every ${t.repeat_days} days`].filter(Boolean).join(' · ')}</span>
      </span>
      <button type="button" className="plain small destructive" aria-label={`Remove ${t.title}`}
        onClick={async () => { await api.deleteGardenTask(t.task_id); onChanged() }}>×</button>
    </li>
  )
}
