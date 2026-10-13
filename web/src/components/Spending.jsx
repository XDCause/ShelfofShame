import { useState } from 'react'
import { api, money } from '../api.js'

const day = (iso) => new Date(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })

// Lifetime spend, tucked away in the gear panel and closed until you open it (only then is it
// loaded). Worked out from the stock history: every purchase remembers the price at the time,
// so removed items still count.
export default function Spending() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = (e) => {
    if (e.currentTarget.open && !data) api.spending().then(setData).catch((err) => setError(err.message))
  }

  return (
    <details className="spending" onToggle={load}>
      <summary>Spending</summary>
      {error && <p className="alert error small">{error}</p>}
      {!data && !error && <p className="muted small">Loading...</p>}
      {data && (
        <>
          <div className="spend-totals">
            <div><span className="muted small">All time</span><strong>{money(data.all_time)}</strong></div>
            <div><span className="muted small">This year</span><strong>{money(data.this_year)}</strong></div>
            <div><span className="muted small">This month</span><strong>{money(data.this_month)}</strong></div>
          </div>
          <p className="hint">
            Includes {money(data.starting_stock)} of starting stock (what you had when the spreadsheet was
            imported).{data.unpriced > 0 && ` ${data.unpriced} purchase${data.unpriced === 1 ? ' has' : 's have'} no price, so ${data.unpriced === 1 ? "isn't" : "aren't"} counted.`}
          </p>
          {data.by_year.length > 1 && (
            <p className="small">
              {data.by_year.map((y) => `${y.year}: ${money(y.spent)}`).join(' · ')}
            </p>
          )}
          {data.recent.length > 0 && (
            <>
              <h4 className="section-title">Latest purchases</h4>
              <ul className="spend-recent">
                {data.recent.map((r, i) => (
                  <li key={i}>
                    <span>{r.qty < 0 ? 'Undo: ' : ''}{r.item_name}{Math.abs(r.qty) > 1 ? ` ×${Math.abs(r.qty)}` : ''}</span>
                    <span className="muted small">{day(r.created_at)}</span>
                    <span className="amount">{r.unit_price == null ? '—' : money(r.spent)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </details>
  )
}
