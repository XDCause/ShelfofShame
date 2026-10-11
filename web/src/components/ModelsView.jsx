import { useEffect, useState } from 'react'
import { api, imageUrl } from '../api.js'

// Your kits as cards: photo, scale, status, and how many of the paints you have.
export default function ModelsView({ refreshKey, onOpen }) {
  const [models, setModels] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listModels().then(setModels).catch((e) => setError(e.message))
  }, [refreshKey])

  if (error) return <p className="alert error">{error}</p>
  if (!models) return <p className="muted">Loading...</p>

  return (
    <section>
      <div className="toolbar">
        <p className="summary grow">
          <strong>{models.length}</strong> model{models.length === 1 ? '' : 's'}
          {models.some((m) => m.status === 'In progress') && <> · {models.filter((m) => m.status === 'In progress').length} in progress</>}
        </p>
        <button type="button" className="primary" onClick={() => onOpen(null)}>+ Add model</button>
      </div>

      {models.length === 0 ? (
        <p className="empty card">No models yet. Add a kit to plan its paints.</p>
      ) : (
        <div className="model-grid">
          {models.map((m) => {
            const missing = m.paints_total - m.paints_have
            return (
              <button type="button" key={m.model_id} className="model-card" onClick={() => onOpen(m.model_id)}>
                <span className="model-photo">
                  {m.has_image ? <img src={imageUrl(m)} alt="" loading="lazy" /> : <span className="photo-missing">No photo</span>}
                  <span className={`status-badge s-${m.status.replace(' ', '-').toLowerCase()}`}>{m.status}</span>
                </span>
                <span className="model-body">
                  <span className="model-name">{m.name}</span>
                  <span className="model-meta">{[m.scale, m.brand, m.product_code].filter(Boolean).join(' · ')}</span>
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
                </span>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
