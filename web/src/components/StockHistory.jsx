import { useEffect, useState } from 'react'
import { api } from '../api.js'

const when = (iso) =>
  new Date(iso).toLocaleString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' })

// The last few quantity changes for one supply. `version` changes whenever the quantity does,
// so the list reloads after a +/-.
export default function StockHistory({ supplyId, version }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    api.supplyHistory(supplyId, 8)
      .then((r) => current && setRows(r))
      .catch((e) => current && setError(e.message))
    return () => { current = false }
  }, [supplyId, version])

  if (error) return <p className="alert error small">{error}</p>
  if (!rows) return <p className="muted small">Loading history...</p>
  if (!rows.length) return <p className="muted small">No stock changes recorded yet.</p>

  return (
    <div className="history">
      <h4>Stock history</h4>
      <ul>
        {rows.map((m) => (
          <li key={m.movement_id}>
            <span className={m.change < 0 ? 'chg neg' : 'chg pos'}>{m.change > 0 ? `+${m.change}` : m.change}</span>
            <span className="reason">{m.reason}</span>
            <span className="muted">→ {m.qty_after}</span>
            <span className="muted when">{when(m.created_at)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
