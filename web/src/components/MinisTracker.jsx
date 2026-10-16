import { useState } from 'react'
import { api } from '../api.js'
import Fold from './Fold.jsx'

// Each mini in a Warhammer box with its own build step (api/app/minis.py). The box's own step and
// "minis painted" follow the minis. Minis are grouped by unit; a unit (or the whole box) can be set
// to a step in one go; each mini's step is a row of pills - tap one to say it's got that far, tap
// the last one done again to take it back a step.
// Without minis yet: a way to set them up from what's in the box, or to add them by hand.
export default function MinisTracker({ model, steps, onModel, run }) {
  const minis = model.minis ?? []
  if (!minis.length) return <MinisSetup model={model} onModel={onModel} run={run} />
  const at = (m) => steps.indexOf(m.stage)
  const units = [...new Map(minis.map((m) => [m.unit, null])).keys()]
    .map((unit) => ({ unit, minis: minis.filter((m) => m.unit === unit) }))
  const done = minis.filter((m) => at(m) === steps.length - 1).length
  const counts = [null, ...steps].map((s) => [s, minis.filter((m) => m.stage === s).length]).filter(([, n]) => n)
  const setMany = (list, stage, label) => run(async () => onModel(
    await api.setMinisStage(model.model_id, list.map((m) => m.mini_id), stage), `${label}: ${stage ?? 'not started'}`))

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">Minis</h4>
        <span className={done === minis.length ? 'pill ok' : 'pill tint'}>{done} of {minis.length} complete</span>
      </div>
      <p className="mini-counts small muted">{counts.map(([s, n]) => `${s ?? 'Not started'} ${n}`).join(' · ')}</p>
      <StepPicker label="Whole box" steps={steps} onPick={(s) => setMany(minis, s, 'Whole box')} />
      <div className="mini-units">
        {units.map((u) => (
          <Unit key={u.unit} model={model} unit={u} steps={steps} at={at} onModel={onModel} run={run}
            setAll={(s) => setMany(u.minis, s, u.unit)} />
        ))}
      </div>
      <AddMinis model={model} units={units.map((u) => u.unit)} onModel={onModel} run={run} />
    </section>
  )
}

// "Set every mini to..." for a unit or the box.
function StepPicker({ label, steps, onPick }) {
  return (
    <label className="mini-set small">
      <span className="muted">{label}</span>
      <select value="" onChange={(e) => e.target.value && onPick(e.target.value === '-' ? null : e.target.value)}
        aria-label={`${label}: set every mini to a step`}>
        <option value="">Set all to...</option>
        {steps.map((s) => <option key={s} value={s}>{s}</option>)}
        <option value="-">Not started</option>
      </select>
    </label>
  )
}

// One unit: how far it's got, its minis, and rename / remove.
function Unit({ model, unit, steps, at, onModel, run, setAll }) {
  const [renaming, setRenaming] = useState(null)
  const [confirm, setConfirm] = useState(false)
  const low = Math.min(...unit.minis.map(at))
  const done = unit.minis.filter((m) => at(m) === steps.length - 1).length
  const detail = low === steps.length - 1 ? 'All complete'
    : low >= 0 ? `All ${steps[low].toLowerCase()}${done ? ` · ${done} complete` : ''}`
      : `${unit.minis.filter((m) => at(m) >= 0).length} of ${unit.minis.length} started`
  const rename = (e) => {
    e.preventDefault()
    if (renaming.trim() && renaming.trim() !== unit.unit) {
      run(async () => onModel(await api.renameMiniUnit(model.model_id, unit.unit, renaming.trim()), 'Renamed ✓'))
    }
    setRenaming(null)
  }
  return (
    <Fold className="inner mini-unit" open={unit.minis.length <= 12}
      title={<>{unit.unit} <span className="muted">×{unit.minis.length}</span></>} detail={detail}>
      <div className="mini-unit-tools">
        {unit.minis.length > 1 && <StepPicker label="This unit" steps={steps} onPick={setAll} />}
        <span className="spacer" />
        {renaming == null ? (
          <button type="button" className="plain small" onClick={() => setRenaming(unit.unit)}>Rename</button>
        ) : (
          <form className="mini-rename" onSubmit={rename}>
            <input value={renaming} onChange={(e) => setRenaming(e.target.value)} autoFocus aria-label="Unit name" />
            <button type="submit" className="primary small">Save</button>
          </form>
        )}
        {confirm ? (
          <span className="confirm small">Remove {unit.minis.length === 1 ? 'it' : `all ${unit.minis.length}`}?
            <button type="button" className="danger small" onClick={() => run(async () => {
              await api.deleteMiniUnit(model.model_id, unit.unit)
              onModel(await api.getModel(model.model_id), 'Removed ✓')
            })}>Remove</button>
            <button type="button" className="plain small" onClick={() => setConfirm(false)}>Cancel</button>
          </span>
        ) : <button type="button" className="plain small destructive" onClick={() => setConfirm(true)}>Remove</button>}
      </div>
      <ol className="mini-list">
        {unit.minis.map((m, i) => <Mini key={m.mini_id} mini={m} n={i + 1} steps={steps} reached={at(m)} onModel={onModel} run={run} />)}
      </ol>
    </Fold>
  )
}

// One mini: its name (tap to give it one: "Alpha", "Plasma caliver") and a pill per step.
function Mini({ mini, n, steps, reached, onModel, run }) {
  const [naming, setNaming] = useState(null)
  const save = (data, msg) => run(async () => onModel(await api.updateMini(mini.mini_id, data), msg))
  const pick = (i) => (i === reached
    ? save({ stage: i > 0 ? steps[i - 1] : null }, 'Step unticked')
    : save({ stage: steps[i] }, `${mini.name ?? `#${n}`}: ${steps[i]} ✓`))
  return (
    <li className={reached === steps.length - 1 ? 'mini done' : 'mini'}>
      {naming == null ? (
        <button type="button" className="mini-name plain" onClick={() => setNaming(mini.name ?? '')} title="Give it a name">
          <span className="mini-n">#{n}</span>{mini.name && ` ${mini.name}`}
        </button>
      ) : (
        <form className="mini-rename" onSubmit={(e) => { e.preventDefault(); save({ name: naming }, 'Saved ✓'); setNaming(null) }}>
          <input value={naming} onChange={(e) => setNaming(e.target.value)} autoFocus placeholder="e.g. Alpha" aria-label={`Name for mini ${n}`} />
          <button type="submit" className="primary small">Save</button>
        </form>
      )}
      <span className="mini-steps" role="group" aria-label={`Mini ${n}${mini.name ? ` ${mini.name}` : ''} steps`}>
        {steps.map((s, i) => (
          <button key={s} type="button" aria-pressed={i <= reached} onClick={() => pick(i)}
            title={i === reached ? `${s}. Tap to take it back a step.` : `Tap when it's ${s.toLowerCase()}`}>{s}</button>
        ))}
      </span>
    </li>
  )
}

// "+ 10 Skitarii Rangers": count and unit (an existing unit adds to it).
function AddMinis({ model, units, onModel, run, first = false }) {
  const [open, setOpen] = useState(first)
  const [count, setCount] = useState('1')
  const [unit, setUnit] = useState('')
  const add = (e) => {
    e.preventDefault()
    run(async () => {
      onModel(await api.addMinis(model.model_id, unit.trim(), Number(count) || 1), `Added ${count} × ${unit.trim()}`)
      setUnit('')
      setCount('1')
    })
  }
  if (!open) return <button type="button" className="plain small" onClick={() => setOpen(true)}>+ Add minis</button>
  return (
    <form className="mini-add" onSubmit={add}>
      <input type="number" min="1" max="100" value={count} onChange={(e) => setCount(e.target.value)} aria-label="How many" />
      <input value={unit} onChange={(e) => setUnit(e.target.value)} required placeholder="Unit, e.g. Skitarii Rangers"
        aria-label="Unit" list={`units-${model.model_id}`} />
      <datalist id={`units-${model.model_id}`}>{units.map((u) => <option key={u} value={u} />)}</datalist>
      <button type="submit" className="primary" disabled={!unit.trim()}>Add</button>
    </form>
  )
}

// No minis yet: set them up from the box's contents, or by hand.
function MinisSetup({ model, onModel, run }) {
  const [byHand, setByHand] = useState(false)
  const box = model.box_units ?? []
  const total = box.reduce((n, u) => n + u.count, 0)
  const fromBox = () => run(async () => onModel(await api.minisFromBox(model.model_id), 'Minis set up ✓'))
  return (
    <section className="panel-section">
      <h4 className="section-title">Track each mini</h4>
      <p className="small muted">Give every mini in the box its own step - built, primed, painted, based - instead of one step for the whole box.</p>
      <div className="mini-setup">
        {(box.length > 0 || model.product_code) && (
          <button type="button" className="secondary" onClick={fromBox}>
            {box.length ? `Set up ${total} mini${total === 1 ? '' : 's'} from the box` : 'Set up from the box'}</button>
        )}
        {!byHand && <button type="button" className="plain" onClick={() => setByHand(true)}>Add them by hand</button>}
      </div>
      {box.length > 0 && <p className="hint">{box.map((u) => `${u.count} × ${u.unit}`).join(', ')} (from the shop's description)</p>}
      {byHand && <AddMinis model={model} units={[]} onModel={onModel} run={run} first />}
    </section>
  )
}
