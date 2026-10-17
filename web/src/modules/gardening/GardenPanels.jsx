import { useCallback, useEffect, useState } from 'react'
import { api, money, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import RecordFields, { RowPhoto, useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { CONTAINER_EMOJI, CareButtons, LogForm, LogTimeline, SowMonths, StagePill, isDue, plantEmoji } from './gardenParts.jsx'
import { PlantTasks } from './PlantingPanel.jsx'

// Gardening's other panels: a container (its plants, care, notes, photo), the forms for a space and a
// container, a plant guide entry, and a supply / seed packet (with its Bunnings details).

const YES_NO = [['true', 'Yes'], ['false', 'No']]
const toNumbers = (p, keys) => { for (const k of keys) if (p[k] != null) p[k] = Number(p[k]); return p }
const toBools = (p, keys) => { for (const k of keys) if (p[k] != null) p[k] = p[k] === 'true'; return p }
const asForm = (r, keys) => r && { ...r, ...Object.fromEntries(keys.map((k) => [k, r[k] == null ? '' : String(r[k])])) }

// ---------------------------------------------------------------------------------------------
// A space (balcony, windowsill...)
// ---------------------------------------------------------------------------------------------
const FACING_NAMES = { N: 'North', NE: 'North-east', E: 'East', SE: 'South-east', S: 'South', SW: 'South-west', W: 'West', NW: 'North-west' }
function spaceFields(lists) {
  return [
    { name: 'name', label: 'Name', required: true, placeholder: 'e.g. Balcony' },
    { name: 'kind', label: 'Kind', type: 'select', required: true, options: lists?.space_kinds ?? ['Balcony'] },
    { name: 'width_cm', label: 'Width (cm)', type: 'number', required: true, min: 20, hint: 'Left to right on the plan' },
    { name: 'depth_cm', label: 'Depth (cm)', type: 'number', required: true, min: 20, hint: 'Front to back' },
    { name: 'open_side', label: 'Railing / window side', type: 'select', required: true,
      options: [['top', 'Top of the plan'], ['bottom', 'Bottom of the plan'], ['left', 'Left of the plan'], ['right', 'Right of the plan']] },
    { name: 'facing', label: 'That side faces', type: 'select', options: Object.entries(FACING_NAMES),
      hint: 'In Australia, north gets the most sun; west gets the hot afternoon.' },
    { name: 'sun_hours', label: 'Hours of direct sun', type: 'number', min: 0, step: 0.5, hint: 'Roughly, on a sunny day' },
    { name: 'covered', label: 'Covered (rain doesn\'t reach it)?', type: 'select', required: true, options: YES_NO },
    { name: 'wind', label: 'Wind', type: 'select', required: true, options: lists?.winds ?? ['Some wind'] },
    { name: 'grow_light', label: 'Grow light?', type: 'select', required: true, options: YES_NO },
    { name: 'light_hours', label: 'Grow light hours a day', type: 'number', min: 0, step: 0.5 },
    { name: 'max_load_kg', label: 'Weight limit (kg)', type: 'number', min: 1, hint: 'Ask your building manager / strata: balconies have one' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}

export function SpacePanel({ id = null, onClose }) {
  const { changed, showToast } = useApp()
  const [space, setSpace] = useState(null)
  const [lists, setLists] = useState(null)
  useEffect(() => { api.gardenLists().then(setLists).catch(() => {}) }, [])
  useEffect(() => { if (id != null) api.gardenSpace(id).then(setSpace).catch((e) => showToast(e.message)) }, [id, showToast])
  if ((id != null && !space) || !lists) return <Drawer title="Space" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const save = async (data) => {
    const body = toBools(toNumbers(data, ['width_cm', 'depth_cm', 'sun_hours', 'light_hours', 'max_load_kg']), ['covered', 'grow_light'])
    const s = space ? await api.updateGardenSpace(space.space_id, body) : await api.addGardenSpace(body)
    changed()
    showToast(space ? 'Saved' : `Added ${s.name} - now add its pots on the layout`)
    onClose()
  }
  return (
    <FormPanel title={space ? space.name : 'Add a growing space'} fields={spaceFields(lists)}
      record={asForm(space, ['covered', 'grow_light'])} onClose={onClose} onSave={save} saveLabel={space ? 'Save' : 'Add space'}
      defaults={{ kind: 'Balcony', width_cm: '300', depth_cm: '120', open_side: 'top', covered: 'true', wind: 'Some wind', grow_light: 'false' }}
      onDelete={space && (async () => { await api.deleteGardenSpace(space.space_id); changed(); onClose() })}
      before={<p className="panel-section small muted">The layout draws it to scale. Measure the floor you can use (inside the railing or
        the sill), and pick which edge of the plan is the open side - the sun comes from there.</p>} />
  )
}

// ---------------------------------------------------------------------------------------------
// A container: the form, and its panel
// ---------------------------------------------------------------------------------------------
function containerFields(lists, spaces) {
  return [
    { name: 'name', label: 'Name', required: true, placeholder: 'e.g. Big blue pot' },
    { name: 'space_id', label: 'Where', type: 'select', required: true, options: spaces.map((s) => [String(s.space_id), s.name]) },
    { name: 'kind', label: 'Kind', type: 'select', required: true, options: lists?.container_kinds ?? ['Pot'] },
    { name: 'shape', label: 'Shape (from above)', type: 'select', required: true, options: [['round', 'Round'], ['rect', 'Rectangle']] },
    { name: 'width_cm', label: 'Width (cm)', type: 'number', required: true, min: 5 },
    { name: 'depth_cm', label: 'Depth (cm)', type: 'number', required: true, min: 5, hint: 'Front to back, from above' },
    { name: 'volume_l', label: 'Litres of mix', type: 'number', min: 0, step: 0.5, hint: 'On the pot, or the bags it took' },
    { name: 'level', label: 'Sits', type: 'select', required: true, options: lists?.levels ?? ['Floor'] },
    { name: 'self_watering', label: 'Self-watering?', type: 'select', required: true, options: YES_NO },
    { name: 'soil', label: 'Mix', placeholder: 'Premium potting mix, cactus mix...' },
    { name: 'material', label: 'Material', placeholder: 'Plastic, terracotta, fabric...' },
    { name: 'potted_on', label: 'Potted on', type: 'date' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}
const SHAPE_FOR = { Trough: 'rect', 'Planter box': 'rect', 'Raised planter': 'rect', 'Vertical planter': 'rect', 'Seed tray': 'rect',
  'Worm farm': 'rect', Hydroponic: 'rect' }
const SIZE_FOR = { Trough: [80, 25, 30], 'Planter box': [60, 40, 50], 'Raised planter': [100, 50, 120], 'Grow bag': [40, 40, 40],
  'Hanging basket': [30, 30, 8], 'Seed tray': [35, 25, 3], 'Worm farm': [50, 40, 0], 'Bokashi bin': [30, 30, 0], Pot: [30, 30, 10],
  'Self-watering pot': [30, 30, 10] }

export function ContainerFormPanel({ id = null, spaceId = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const [c, setC] = useState(null)
  const [lists, setLists] = useState(null)
  const [spaces, setSpaces] = useState(null)
  useEffect(() => {
    api.gardenLists().then(setLists).catch(() => {})
    api.gardenSpaces().then(setSpaces).catch(() => {})
  }, [])
  useEffect(() => { if (id != null) api.gardenContainer(id).then(setC).catch((e) => showToast(e.message)) }, [id, showToast])
  if ((id != null && !c) || !lists || !spaces) return <Drawer title="Container" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  // A kind picked for a new container: its usual shape and size.
  const onField = (name, value, setForm) => {
    if (name !== 'kind' || c) return
    const [w, d, l] = SIZE_FOR[value] ?? [30, 30, 10]
    setForm((f) => ({ ...f, shape: SHAPE_FOR[value] ?? 'round', width_cm: String(w), depth_cm: String(d), volume_l: l ? String(l) : '',
      self_watering: value === 'Self-watering pot' ? 'true' : f.self_watering }))
  }
  const save = async (data) => {
    const body = toBools(toNumbers(data, ['space_id', 'width_cm', 'depth_cm', 'volume_l']), ['self_watering'])
    const saved = c ? await api.updateGardenContainer(c.container_id, body) : await api.addGardenContainer(body)
    changed()
    onClose()
    if (!c) openPanel('gcontainer', { id: saved.container_id })
  }
  return (
    <FormPanel title={c ? `Edit ${c.name}` : 'Add a container'} fields={containerFields(lists, spaces)} onField={onField}
      record={asForm(c, ['space_id', 'self_watering'])} onClose={onClose} onSave={save} saveLabel={c ? 'Save' : 'Add container'}
      defaults={{ space_id: spaceId ? String(spaceId) : String(spaces[0]?.space_id ?? ''), kind: 'Pot', shape: 'round', width_cm: '30',
        depth_cm: '30', volume_l: '10', level: 'Floor', self_watering: 'false' }}
      onDelete={c && (async () => { await api.deleteGardenContainer(c.container_id); changed(); onClose() })}
      deleteLabel="Remove container" />
  )
}

export function ContainerPanel({ id, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const [c, setC] = useState(null)
  const [tasks, setTasks] = useState([])
  const reload = useCallback(() => {
    api.gardenContainer(id).then(setC).catch((e) => showToast(e.message))
    api.gardenTasks().then((t) => setTasks(t.filter((x) => x.container_id === id))).catch(() => {})
  }, [id, showToast])
  useEffect(() => { reload() }, [reload])
  if (!c) return <Drawer title="Container" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const open = (type, props) => { onClose(); openPanel(type, props) }
  const today = new Date().toLocaleDateString('en-CA')
  const current = c.plantings.filter((p) => p.stage !== 'Done' && p.stage !== 'Died')
  const past = c.plantings.filter((p) => p.stage === 'Done' || p.stage === 'Died')
  const footer = (
    <>
      <button type="button" className="primary" onClick={() => open('planting', { containerId: c.container_id })}>+ Plant here</button>
      <span className="spacer" />
      <button type="button" className="plain" onClick={() => open('gcontainerform', { id: c.container_id })}>Edit details</button>
    </>
  )
  return (
    <Drawer title={`${CONTAINER_EMOJI[c.kind] ?? ''} ${c.name}`.trim()} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="item-hero">
          <RowPhoto path={`/garden/containers/${c.container_id}`} url={c.photo_url}
            onChanged={(msg) => { reload(); changed(); showToast(msg) }} />
          <div>
            <p className="item-sub">{c.kind} · {c.space_name}{c.level !== 'Floor' && ` · ${c.level.toLowerCase()}`}</p>
            <dl className="garden-facts">
              <dt>Size</dt><dd>{c.width_cm} × {c.depth_cm} cm{c.volume_l && ` · ${c.volume_l} L`}{c.volume_l && <span className="muted"> (about {Math.round(c.volume_l)} kg wet)</span>}</dd>
              {c.soil && <><dt>Mix</dt><dd>{c.soil}</dd></>}
              {c.material && <><dt>Material</dt><dd>{c.material}</dd></>}
              {c.self_watering && <><dt>Watering</dt><dd>Self-watering (water half as often)</dd></>}
              {c.potted_on && <><dt>Potted</dt><dd>{shortDate(c.potted_on)}</dd></>}
            </dl>
          </div>
        </div>
        {c.notes && <p className="small garden-notes">{c.notes}</p>}
      </section>
      <section className="panel-section">
        <div className="section-head">
          <h3 className="section-title">Growing here</h3>
          {current.length > 0 && <CareButtons containerId={c.container_id} onDone={reload} />}
        </div>
        {current.length === 0 ? <p className="muted small">Nothing growing here yet.</p> : (
          <ul className="list plain-list">
            {current.map((p) => (
              <li key={p.planting_id}>
                <button type="button" className="row-button" onClick={() => open('planting', { id: p.planting_id })}>
                  <span className="garden-emoji" aria-hidden="true">{plantEmoji(p)}</span>
                  <span className="grow">
                    <span className="item-title">{p.name}{p.variety && <span className="muted"> · {p.variety}</span>}</span>
                    <span className="item-meta">{[p.quantity > 1 && `${p.quantity} plants`, `${p.age_days} days`,
                      isDue(p.water_due_on, today) && '💧 water due', p.harvest_ready && '✂️ ready to pick'].filter(Boolean).join(' · ')}</span>
                  </span>
                  <StagePill stage={p.stage} />
                </button>
              </li>
            ))}
          </ul>
        )}
        {past.length > 0 && <Fold title="Grown here before" detail={past.length}>
          <ul className="list plain-list">{past.map((p) => (
            <li key={p.planting_id}><button type="button" className="row-button" onClick={() => open('planting', { id: p.planting_id })}>
              <span className="grow"><span className="item-title">{p.name}</span>
                <span className="item-meta">{shortDate(p.started_on)}{p.ended_on && ` – ${shortDate(p.ended_on)}`}</span></span>
              <StagePill stage={p.stage} /></button></li>))}</ul>
        </Fold>}
      </section>
      <section className="panel-section">
        <h3 className="section-title">Notes and photos</h3>
        <LogForm about={{ container_id: c.container_id }} kinds={['Note', 'Photo', 'Repotted', 'Pest', 'Problem', 'Treated', 'Measured']}
          onSaved={reload} />
        <LogTimeline logs={c.logs} onChanged={reload} />
      </section>
      <PlantTasks about={{ container_id: c.container_id }} tasks={tasks} onChanged={reload} />
      {c.plantings.length === 0 && (
        <p className="panel-section small muted">Tip: worm farms and bokashi bins fit here too - add a reminder like "Feed the worms"
          every 7 days.</p>
      )}
    </Drawer>
  )
}

// ---------------------------------------------------------------------------------------------
// A plant guide entry
// ---------------------------------------------------------------------------------------------
const CLIMATE_KEYS = ['tropical', 'subtropical', 'temperate', 'cool', 'arid']

export function GuidePanel({ id, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const [g, setG] = useState(null)
  const [editing, setEditing] = useState(false)
  const reload = useCallback(() => api.gardenGuide(id).then(setG).catch((e) => showToast(e.message)), [id, showToast])
  useEffect(() => { reload() }, [reload])
  if (!g) return <Drawer title="Plant guide" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const open = (type, props) => { onClose(); openPanel(type, props) }
  const copy = async () => {
    const mine = await api.copyGardenGuide(g.guide_id)
    changed()
    onClose()
    openPanel('gguide', { id: mine.guide_id })
  }
  const remove = async () => {
    if (!window.confirm(`Remove your guide entry for ${g.name}?`)) return
    await api.deleteGardenGuide(g.guide_id)
    changed()
    onClose()
  }
  const footer = (
    <>
      <button type="button" className="primary" onClick={() => open('planting', { guideId: g.guide_id })}>+ Plant this</button>
      <span className="spacer" />
      {g.custom ? <>
        {!editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit</button>}
        <button type="button" className="plain destructive" onClick={remove}>Remove</button>
      </> : <button type="button" className="plain" onClick={copy}>Make my own copy</button>}
    </>
  )
  const climate = g.climate.toLowerCase()
  return (
    <Drawer title={`${plantEmoji({ name: g.name, kind: g.kind })} ${g.name}`} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <p className="item-sub">{g.kind}{g.perennial && ' · lasts for years'}{g.custom && ' · your own entry'}</p>
        <p className="field-label">When to {g.sow_how === 'Seed' ? 'sow' : 'plant'} ({climate})</p>
        <SowMonths months={g[`sow_${climate}`]} />
        <p className="small">{g.sow_now ? <span className="pill ok">Sow now</span> : g.sow_next ? <span className="pill low">Next month</span> : null}
          {g.fits_spaces.length > 0 && <span className="muted"> Suits {g.fits_spaces.join(', ')}.</span>}</p>
      </section>
      {editing ? <GuideForm g={g} onSaved={() => { setEditing(false); reload(); changed() }} onCancel={() => setEditing(false)} /> : (
        <>
          <section className="panel-section">
            <dl className="garden-facts">
              <dt>Light</dt><dd>{g.sun} ({g.sun_hours_min}+ h a day)</dd>
              <dt>Water</dt><dd>{g.water} · about every {g.water_every_days} day{g.water_every_days > 1 ? 's' : ''} in a pot</dd>
              {g.feed_every_days && <><dt>Feed</dt><dd>every {g.feed_every_days} days in the growing season</dd></>}
              {g.pot_min_l && <><dt>Pot</dt><dd>{g.pot_min_l} L or more{g.spacing_cm && ` · ${g.spacing_cm} cm apart`}</dd></>}
              {g.days_min && <><dt>Harvest</dt><dd>{g.days_min}–{g.days_max} days from seed</dd></>}
              <dt>Start from</dt><dd>{g.sow_how === 'Either' ? 'Seed or seedling' : g.sow_how}</dd>
              {g.companions && <><dt>Good with</dt><dd>{g.companions}</dd></>}
              {g.avoid && <><dt>Keep from</dt><dd>{g.avoid}</dd></>}
              {g.pests && <><dt>Watch for</dt><dd>{g.pests}</dd></>}
            </dl>
            {g.tips && <p className="small">{g.tips}</p>}
            {g.harvest_tips && <p className="small"><strong>Picking:</strong> {g.harvest_tips}</p>}
            {g.apartment_tips && <p className="small"><strong>In an apartment:</strong> {g.apartment_tips}</p>}
          </section>
          <section className="panel-section">
            <Fold title="Other climates">
              {CLIMATE_KEYS.map((k) => (
                <p key={k} className="garden-climate-row"><span className="small">{k[0].toUpperCase() + k.slice(1)}</span><SowMonths months={g[`sow_${k}`]} label={k} /></p>
              ))}
            </Fold>
          </section>
        </>
      )}
      {g.plantings.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">You've grown it</h3>
          <ul className="list plain-list">{g.plantings.map((p) => (
            <li key={p.planting_id}><button type="button" className="row-button" onClick={() => open('planting', { id: p.planting_id })}>
              <span className="grow"><span className="item-title">{p.name}{p.variety && ` · ${p.variety}`}</span>
                <span className="item-meta">{shortDate(p.started_on)}</span></span><StagePill stage={p.stage} /></button></li>))}</ul>
        </section>
      )}
    </Drawer>
  )
}

const GUIDE_FIELDS = (lists) => [
  { name: 'name', label: 'Name', required: true },
  { name: 'kind', label: 'Kind', type: 'select', required: true, options: lists?.guide_kinds ?? [] },
  { name: 'sun', label: 'Light', type: 'select', required: true, options: lists?.suns ?? [] },
  { name: 'sun_hours_min', label: 'Hours of sun it needs', type: 'number', step: 0.5 },
  { name: 'water', label: 'Water', type: 'select', required: true, options: lists?.waters ?? [] },
  { name: 'water_every_days', label: 'Water every (days)', type: 'number', min: 1 },
  { name: 'feed_every_days', label: 'Feed every (days)', type: 'number', min: 1 },
  { name: 'pot_min_l', label: 'Smallest pot (L)', type: 'number', step: 0.5 },
  { name: 'spacing_cm', label: 'Spacing (cm)', type: 'number' },
  { name: 'days_min', label: 'Days to harvest (from)', type: 'number', min: 1 },
  { name: 'days_max', label: 'Days to harvest (to)', type: 'number', min: 1 },
  { name: 'sow_how', label: 'Start from', type: 'select', required: true, options: lists?.sow_how ?? [] },
  { name: 'companions', label: 'Good with' },
  { name: 'avoid', label: 'Keep from' },
  { name: 'tips', label: 'Growing tips', type: 'textarea' },
  { name: 'harvest_tips', label: 'Picking', type: 'textarea' },
  { name: 'apartment_tips', label: 'In an apartment', type: 'textarea' },
  { name: 'pests', label: 'Watch for', type: 'textarea' },
]

function GuideForm({ g, onSaved, onCancel }) {
  const [lists, setLists] = useState(null)
  useEffect(() => { api.gardenLists().then(setLists).catch(() => {}) }, [])
  const climate = g?.climate?.toLowerCase() ?? 'subtropical'
  const [months, setMonths] = useState(g?.[`sow_${climate}`] ?? [])
  const fields = GUIDE_FIELDS(lists)
  const { form, set, payload } = useRecordForm(fields, g, { kind: 'Herb', sun: 'Part sun', water: 'Medium', sow_how: 'Either' })
  const [error, setError] = useState('')
  const save = async (e) => {
    e.preventDefault()
    try {
      const body = toNumbers(payload(), ['sun_hours_min', 'water_every_days', 'feed_every_days', 'pot_min_l', 'spacing_cm', 'days_min', 'days_max'])
      body[`sow_${climate}`] = months
      if (g) await api.updateGardenGuide(g.guide_id, body)
      else await api.addGardenGuide(body)
      onSaved()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="panel-section" onSubmit={save}>
      <p className="field-label">Sowing months ({climate})</p>
      <div className="chip-row garden-month-pick" role="group" aria-label="Sowing months">
        {'JFMAMJJASOND'.split('').map((l, i) => (
          <button key={i} type="button" className="chip-filter" aria-pressed={months.includes(i + 1)}
            aria-label={new Date(2000, i, 1).toLocaleDateString('en-AU', { month: 'long' })}
            onClick={() => setMonths((m) => (m.includes(i + 1) ? m.filter((x) => x !== i + 1) : [...m, i + 1]))}>{l}</button>
        ))}
      </div>
      <RecordFields fields={fields} form={form} set={set} />
      {error && <p className="alert error small">{error}</p>}
      <div className="button-row">
        <button type="submit" className="primary">Save</button>
        {onCancel && <button type="button" className="plain" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}

export function NewGuidePanel({ onClose }) {
  const { changed } = useApp()
  return (
    <Drawer title="Your own plant" onClose={onClose}>
      <p className="panel-section small muted">For a plant the guide doesn't have. It works like the others: plant from it, see when to sow.</p>
      <GuideForm onSaved={() => { changed(); onClose() }} onCancel={onClose} />
    </Drawer>
  )
}

// ---------------------------------------------------------------------------------------------
// Supplies and seed packets
// ---------------------------------------------------------------------------------------------
const STATUS_TONE = { Have: 'ok', 'Running low': 'low', Wanted: 'tint', 'Used up': '' }
function itemFields(lists, guides, kind) {
  return [
    { name: 'name', label: 'Name', required: true, wide: true },
    { name: 'kind', label: 'Kind', type: 'select', required: true, options: lists?.item_kinds ?? ['Other'] },
    { name: 'status', label: 'Status', type: 'select', required: true, options: lists?.item_statuses ?? ['Have'] },
    { name: 'qty', label: kind === 'Seeds' ? 'Packets' : 'How many', type: 'number', min: 0 },
    { name: 'brand', label: 'Brand' },
    ...(kind === 'Seeds' || kind === 'Seedling' ? [
      { name: 'guide_id', label: 'Which plant', type: 'select', options: guides.map((g) => [String(g.guide_id), g.name]) },
      ...(kind === 'Seeds' ? [{ name: 'sow_by', label: 'Sow by (on the packet)', type: 'date' }] : []),
    ] : []),
    { name: 'price', label: 'Price', type: 'money' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}

function ItemForm({ item, onSaved, onCancel }) {
  const [lists, setLists] = useState(null)
  const [guides, setGuides] = useState([])
  const [kind, setKind] = useState(item?.kind ?? 'Seeds')
  useEffect(() => {
    api.gardenLists().then(setLists).catch(() => {})
    api.gardenGuides().then((g) => setGuides(g.guides)).catch(() => {})
  }, [])
  const fields = itemFields(lists, guides, kind)
  const { form, set, payload } = useRecordForm(itemFields(lists, guides, 'Seeds'), asForm(item, ['guide_id']), { kind: 'Seeds', status: 'Have' })
  const [error, setError] = useState('')
  const onSet = (name) => (e) => { set(name)(e); if (name === 'kind') setKind(e.target.value) }
  const save = async (e) => {
    e.preventDefault()
    try {
      const body = toNumbers(payload(), ['qty', 'guide_id', 'price'])
      if (!['Seeds', 'Seedling'].includes(body.kind)) { body.guide_id = null; body.sow_by = null }
      onSaved(item ? await api.updateGardenItem(item.item_id, body) : await api.addGardenItem(body))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="panel-section" onSubmit={save}>
      <RecordFields fields={fields} form={form} set={onSet} />
      {error && <p className="alert error small">{error}</p>}
      <div className="button-row">
        <button type="submit" className="primary">{item ? 'Save' : 'Add'}</button>
        {onCancel && <button type="button" className="plain" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}

export function ItemPanel({ id = null, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const [item, setItem] = useState(null)
  const [editing, setEditing] = useState(false)
  const [checking, setChecking] = useState(false)
  const [link, setLink] = useState('')
  const [containers, setContainers] = useState([])
  const [sowIn, setSowIn] = useState('')
  const reload = useCallback(() => api.gardenItem(id).then(setItem).catch((e) => showToast(e.message)), [id, showToast])
  useEffect(() => { if (id != null) reload() }, [id, reload])
  useEffect(() => { api.gardenContainers().then(setContainers).catch(() => {}) }, [])
  if (id == null) {
    return (
      <Drawer title="Add a supply or seeds" onClose={onClose}>
        <p className="panel-section small muted">Have a Bunnings link? Paste it on Gardening → Supplies instead: the name, price and photo fill in.</p>
        <ItemForm onSaved={(x) => { changed(); onClose(); openPanel('gitem', { id: x.item_id }) }} onCancel={onClose} />
      </Drawer>
    )
  }
  if (!item) return <Drawer title="Supply" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const update = async (data) => { setItem({ ...(await api.updateGardenItem(item.item_id, data)), plantings: item.plantings }); changed() }
  const check = async () => {
    setChecking(true)
    try {
      const r = await api.refreshGardenItem(item.item_id, link || null)
      setLink('')
      showToast(r.price_before != null && r.price != null && r.price !== r.price_before
        ? `Price ${r.price < r.price_before ? 'down' : 'up'}: ${money(r.price_before)} → ${money(r.price)}` : `Checked: ${r.price != null ? money(r.price) : 'no price shown'}`)
      reload()
      changed()
    } catch (e) {
      showToast(e.message)
    } finally {
      setChecking(false)
    }
  }
  const sow = async () => {
    const p = await api.sowGardenItem(item.item_id, { container_id: sowIn ? Number(sowIn) : null })
    changed()
    onClose()
    openPanel('planting', { id: p.planting_id })
  }
  const remove = async () => {
    if (!window.confirm(`Remove ${item.name}?`)) return
    await api.deleteGardenItem(item.item_id)
    changed()
    onClose()
  }
  const footer = (
    <>
      {item.url && <a className="button secondary" href={item.url} target="_blank" rel="noreferrer">On Bunnings ↗</a>}
      <span className="spacer" />
      {!editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>}
      <button type="button" className="plain destructive" onClick={remove}>Remove</button>
    </>
  )
  return (
    <Drawer title={item.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="item-hero">
          <RowPhoto path={`/garden/items/${item.item_id}`} url={item.photo_url} onChanged={(msg) => { reload(); changed(); showToast(msg) }} />
          <div>
            <p className="item-sub">{[item.kind, item.brand, item.guide_name].filter(Boolean).join(' · ')}</p>
            {item.price != null && <p className="garden-price">{money(item.price)}
              {item.price_checked_at && <span className="muted small"> · checked {shortDate(item.price_checked_at)}</span>}</p>}
            {item.rating && <p className="small">{'★'.repeat(Math.round(item.rating))}<span className="muted"> {item.rating} ({item.reviews} reviews)</span></p>}
            <p className="small muted">{[item.bunnings_item && `I/N ${item.bunnings_item}`, item.weight_kg && `${item.weight_kg} kg`, item.category]
              .filter(Boolean).join(' · ')}</p>
            {item.kind === 'Seeds' && item.sow_by && <p className={`small ${item.expired ? 'garden-due' : 'muted'}`}>
              Sow by {shortDate(item.sow_by)}{item.expired && ' - past it: sow thickly, fewer will come up'}</p>}
          </div>
        </div>
      </section>
      <section className="panel-section">
        <div className="chip-row" role="group" aria-label="Status">
          {['Have', 'Running low', 'Wanted', 'Used up'].map((s) => (
            <button key={s} type="button" className={`chip-filter ${STATUS_TONE[s]}`} aria-pressed={item.status === s} onClick={() => update({ status: s })}>{s}</button>
          ))}
        </div>
        <p className="garden-qty">
          <button type="button" className="secondary small" aria-label="One fewer" disabled={!item.qty} onClick={() => update({ qty: Math.max(0, (item.qty ?? 0) - 1) })}>−</button>
          <span>{item.qty ?? '—'} {item.kind === 'Seeds' ? 'packets' : 'left'}</span>
          <button type="button" className="secondary small" aria-label="One more" onClick={() => update({ qty: (item.qty ?? 0) + 1 })}>+</button>
        </p>
      </section>
      {(item.kind === 'Seeds' || item.kind === 'Seedling') && (
        <section className="panel-section">
          <h3 className="section-title">{item.kind === 'Seeds' ? 'Sow some' : 'Plant it'}</h3>
          <div className="button-row">
            <select value={sowIn} onChange={(e) => setSowIn(e.target.value)} aria-label="Into">
              <option value="">Not in a pot yet (a seed tray, a cup)</option>
              {containers.map((c) => <option key={c.container_id} value={c.container_id}>{c.space_name} › {c.name}</option>)}
            </select>
            <button type="button" className="primary small" onClick={sow}>{item.kind === 'Seeds' ? 'Sow' : 'Plant'}</button>
          </div>
          {item.plantings?.length > 0 && <p className="small muted">Grown from this: {item.plantings.map((p) => p.name).join(', ')}</p>}
        </section>
      )}
      <section className="panel-section">
        <h3 className="section-title">Bunnings</h3>
        {item.url ? (
          <button type="button" className="secondary small" disabled={checking} onClick={check}>{checking ? 'Checking...' : 'Check the price'}</button>
        ) : (
          <div className="button-row">
            <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="Paste its Bunnings link" aria-label="Bunnings link" />
            <button type="button" className="secondary small" disabled={checking || !link} onClick={check}>{checking ? 'Reading...' : 'Connect'}</button>
          </div>
        )}
        {item.description && <Fold title="About it"><p className="small garden-notes">{item.description}</p></Fold>}
        {item.how_to && <Fold title="How to use"><p className="small garden-notes">{item.how_to}</p></Fold>}
      </section>
      {editing && <ItemForm item={item} onSaved={() => { setEditing(false); reload(); changed() }} onCancel={() => setEditing(false)} />}
      {!editing && item.notes && <p className="panel-section small garden-notes">{item.notes}</p>}
    </Drawer>
  )
}
