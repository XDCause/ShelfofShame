import { useEffect, useState } from 'react'
import { api, duration, imageUrl, money } from '../api.js'

const UNBUILT = ['In stash', 'In progress', 'On hold']
const FILTERS = [
  { id: 'all', label: 'All', test: () => true },
  { id: 'shame', label: 'Shelf of shame', test: (m) => UNBUILT.includes(m.status) },
  { id: 'In progress', label: 'Building', test: (m) => m.status === 'In progress' },
  { id: 'Wanted', label: 'Wanted', test: (m) => m.status === 'Wanted' },
  { id: 'Finished', label: 'Finished', test: (m) => m.status === 'Finished' },
  { id: 'Gone', label: 'Gone', test: (m) => m.status === 'Gone' },
]

export const statusClass = (status) => `status-badge s-${status.replace(' ', '-').toLowerCase()}`

// "HG · 1/144 · Bandai · G5057403", "Ultramarines · Games Workshop", "1/48 · Tamiya · T32595"
export const modelMeta = (m) => [m.grade, m.scale, m.faction, m.brand, m.product_code].filter(Boolean).join(' · ')

// "Panel lined, step 2 of 4" / "3 of 10 minis painted"
function progress(m, stages) {
  const steps = stages?.[m.hobby] ?? []
  const parts = []
  if (m.stage) parts.push(`${m.stage}, step ${steps.indexOf(m.stage) + 1} of ${steps.length}`)
  if (m.hobby === 'Warhammer' && m.figures > 1) parts.push(`${m.figures_done} of ${m.figures} minis painted`)
  return parts.join(' · ')
}

// Your kits: the shelf of shame (owned, not finished) at the top, then cards with photo,
// status, paints and time spent.
export default function ModelsView({ lookups, refreshKey, onOpen }) {
  const [models, setModels] = useState(null)
  const [summary, setSummary] = useState(null)
  const [filter, setFilter] = useState('all')
  const [hobby, setHobby] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.listModels().then(setModels).catch((e) => setError(e.message))
    api.stashSummary().then(setSummary).catch(() => {})
  }, [refreshKey])

  if (error) return <p className="alert error">{error}</p>
  if (!models) return <p className="muted loading">Loading...</p>
  // Hobby chips only appear once you have kits from more than one hobby.
  const hobbies = (lookups?.hobbies ?? []).filter((h) => models.some((m) => m.hobby === h))
  const ofHobby = models.filter((m) => !hobby || m.hobby === hobby)
  const visible = ofHobby.filter(FILTERS.find((f) => f.id === filter).test)
  const shame = summary?.shelf_of_shame

  return (
    <section className="page">
      {shame && (
        <div className="stat-grid card">
          <div><span>Shelf of shame</span><strong>{shame.kits} kit{shame.kits === 1 ? '' : 's'}</strong></div>
          <div><span>Stash value</span><strong>{money(shame.value)}</strong>
            {shame.unpriced > 0 && <small className="muted">{shame.unpriced} without a price</small>}</div>
          <div><span>Time building</span><strong>{duration(summary.total_minutes)}</strong></div>
        </div>
      )}

      {hobbies.length > 1 && (
        <div className="segmented hobby-filter" role="group" aria-label="Hobby">
          {['', ...hobbies].map((h) => (
            <button key={h || 'all'} type="button" aria-pressed={hobby === h} onClick={() => setHobby(h)}>
              {h || 'All'} <span className="chip-count">{h ? models.filter((m) => m.hobby === h).length : models.length}</span>
            </button>
          ))}
        </div>
      )}

      <div className="toolbar">
        <div className="chip-row scroll" role="group" aria-label="Show">
          {FILTERS.filter((f) => f.id === 'all' || ofHobby.some(f.test)).map((f) => (
            <button key={f.id} type="button" className="chip-filter" aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}>
              {f.label} <span className="chip-count">{ofHobby.filter(f.test).length}</span>
            </button>
          ))}
        </div>
        <button type="button" className="primary" onClick={() => onOpen(null)}>+ Add model</button>
      </div>

      {visible.length === 0 ? (
        <p className="empty card">{models.length ? 'Nothing here.' : 'No models yet. Add a kit to plan its paints.'}</p>
      ) : (
        <div className="model-grid">
          {visible.map((m) => <ModelCard key={m.model_id} model={m} stages={lookups?.stages} onOpen={() => onOpen(m.model_id)} />)}
        </div>
      )}
    </section>
  )
}

function ModelCard({ model: m, stages, onOpen }) {
  const missing = m.paints_total - m.paints_have
  const built = progress(m, stages)
  return (
    <button type="button" className="model-card" onClick={onOpen}>
      <span className="model-photo">
        {m.has_image ? <img src={imageUrl(m)} alt="" loading="lazy" /> : <span className="photo-missing">No photo</span>}
        <span className={statusClass(m.status)}>{m.status}</span>
        {m.running_since && <span className="timer-dot" title="Timer running">● Timing</span>}
      </span>
      <span className="model-body">
        <span className="model-name">{m.name}</span>
        <span className="model-meta">{modelMeta(m)}</span>
        {built && <span className="small build-progress">{built}</span>}
        {m.paints_total > 0 ? (
          <span className="paint-progress">
            <span className="progress-bar"><span style={{ width: `${(m.paints_have / m.paints_total) * 100}%` }} /></span>
            <span className={missing ? 'muted small' : 'ok-text small'}>
              {missing ? `Paints ${m.paints_have}/${m.paints_total}, ${missing} to get` : `All ${m.paints_total} paints ✓`}
            </span>
          </span>
        ) : (
          <span className="muted small">No paints listed yet</span>
        )}
        {(m.total_minutes > 0 || m.log_count > 0) && (
          <span className="muted small">
            {[m.total_minutes > 0 && duration(m.total_minutes), m.log_count > 0 && `${m.log_count} log ${m.log_count === 1 ? 'entry' : 'entries'}`]
              .filter(Boolean).join(' · ')}
          </span>
        )}
      </span>
    </button>
  )
}
