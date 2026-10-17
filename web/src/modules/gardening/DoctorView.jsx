import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { api } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../../core/app-context.js'

// The plant doctor (api/app/garden_doctor.py): tap what you see and the problems that match most come first;
// each says what it looks like, why it happens, what to do (in order) and how to stop it next time. With a plant
// chosen (?plant=id, from a plant's "Something wrong?"), the problems that plant usually gets come first, and
// "I've got this" notes it on the plant and sets a reminder to look again.
const ICON = { Pest: '🐛', Disease: '🍄', Feeding: '🧪', Watering: '💧', Conditions: '☀️' }
const URGENCY = { 'Act now': 'out', 'This week': 'low', 'Keep an eye': '' }

export default function DoctorView() {
  const { refreshKey } = useApp()
  const [params, setParams] = useSearchParams()
  const plantId = params.get('plant') || ''
  const [data, setData] = useState(null)
  const [plants, setPlants] = useState([])
  const [seen, setSeen] = useState([])
  const [kind, setKind] = useState('')
  const [q, setQ] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    api.gardenProblems(plantId ? { planting_id: plantId } : {}).then(setData).catch((e) => setError(e.message))
  }, [plantId, refreshKey])
  useEffect(() => { api.gardenPlantings().then(setPlants).catch(() => {}) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const toggle = (key) => setSeen((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]))
  const words = q.trim().toLowerCase()
  const shown = data.problems
    .map((p) => ({ ...p, score: p.signs.filter((s) => seen.includes(s)).length }))
    .filter((p) => (!seen.length || p.score > 0) && (!kind || p.kind === kind)
      && (!words || `${p.name} ${p.looks} ${p.plants}`.toLowerCase().includes(words)))
    .sort((a, b) => b.score - a.score || b.common - a.common)
  const labels = Object.fromEntries(data.signs.flatMap((g) => g.signs.map((s) => [s.key, s.label])))
  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search problems..."
          aria-label="Search problems" />
        <label className="field">Which plant
          <select value={plantId} onChange={(e) => setParams(e.target.value ? { plant: e.target.value } : {})}>
            <option value="">Any plant</option>
            {plants.map((p) => <option key={p.planting_id} value={p.planting_id}>{p.name}{p.container_name ? ` (${p.container_name})` : ''}</option>)}
          </select>
        </label>
      </div>
      <section className="card home-card garden-doc-signs">
        <Fold title="What do you see?" detail={seen.length ? `${seen.length} picked` : 'tap all that fit'} open>
          {data.signs.map((g) => (
            <div key={g.group}>
              <h3>{g.group}</h3>
              <div className="chip-row" role="group" aria-label={g.group}>
                {g.signs.map((s) => (
                  <button key={s.key} type="button" className="chip-filter" aria-pressed={seen.includes(s.key)} onClick={() => toggle(s.key)}>
                    {s.label}</button>
                ))}
              </div>
            </div>
          ))}
          {seen.length > 0 && <button type="button" className="plain small" onClick={() => setSeen([])}>Clear</button>}
        </Fold>
      </section>
      <div className="chip-row" role="group" aria-label="Kind of problem">
        {[{ key: '', label: 'All' }, ...data.kinds].map((k) => (
          <button key={k.key} type="button" className="chip-filter" aria-pressed={kind === k.key} onClick={() => setKind(k.key)}>
            {k.key && <span aria-hidden="true">{ICON[k.key]} </span>}{k.label}</button>
        ))}
      </div>
      {shown.length === 0 ? <p className="empty card">Nothing matches all of that - try fewer signs.</p> : (
        <ul className="garden-doc-list">
          {shown.map((p) => <Problem key={p.problem_id} p={p} plant={data.plant} labels={labels} seen={seen} />)}
        </ul>
      )}
      <p className="muted small">General advice for home gardens. Read and follow the label of any spray, and keep sprays off
        plants you're about to pick.</p>
    </section>
  )
}

function Problem({ p, plant, labels, seen }) {
  const { changed, showToast } = useApp()
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [noted, setNoted] = useState(null)
  const found = async () => {
    try {
      const r = await api.gardenProblemFound(p.problem_id, { planting_id: plant.planting_id, note: note || null })
      setNoted(r)
      changed()
      showToast(`Noted on ${plant.name}; a reminder to check again in ${r.recheck_days} days`)
    } catch (e) {
      showToast(e.message)
    }
  }
  return (
    <li className="card">
      <button type="button" className="garden-doc-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="garden-doc-icon" aria-hidden="true">{ICON[p.kind]}</span>
        <span className="grow">
          <span className="item-title">{p.name}</span>
          <span className="item-meta">{p.looks}</span>
          <span className="garden-doc-pills">
            {p.urgency && <span className={`pill ${URGENCY[p.urgency]}`}>{p.urgency}</span>}
            {p.spreads && <span className="pill">Spreads</span>}
            {p.common && <span className="pill ok">Common for {plant?.name}</span>}
            {p.score > 0 && <span className="pill">{p.score} of your signs</span>}
          </span>
        </span>
      </button>
      {open && (
        <div className="garden-doc-body">
          <p className="small">Signs: {p.signs.map((s) => (
            <span key={s} className={seen.includes(s) ? 'garden-doc-seen' : ''}>{labels[s]}</span>)).reduce((a, b) => [a, ', ', b])}</p>
          {p.why && <><h4>Why</h4><p className="small">{p.why}</p></>}
          <h4>What to do</h4>
          <ol className="small">{p.fix.map((step) => <li key={step}>{step}</li>)}</ol>
          {p.spreads && <p className="alert low small">It spreads: move it away from your other plants until it's clear, and check them too.</p>}
          {p.prevent && <><h4>Next time</h4><p className="small">{p.prevent}</p></>}
          {p.plants && <p className="muted small">Usually on: {p.plants}</p>}
          <div className="button-row">
            {p.buy && <button type="button" className="secondary small" onClick={() => window.open(
              `https://www.bunnings.com.au/search/products?q=${encodeURIComponent(p.buy)}`, '_blank', 'noopener,noreferrer')}>
              Search Bunnings: {p.buy} ↗</button>}
          </div>
          {plant && (noted ? <p className="alert ok small">Noted on {plant.name}, with a reminder to check again on {noted.due_on}.</p> : (
            <div className="button-row">
              <input type="text" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Where / how bad (optional)"
                aria-label="Note" maxLength={2000} />
              <button type="button" className="primary small" onClick={found}>I've got this on {plant.name}</button>
            </div>
          ))}
        </div>
      )}
    </li>
  )
}
