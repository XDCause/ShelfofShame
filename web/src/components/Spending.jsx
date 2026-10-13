import { useEffect, useState } from 'react'
import { api, money, shortDate } from '../api.js'

// Lifetime spend, worked out from the stock history: every purchase remembers the price at the
// time, so removed items still count. Kits are separate: what the kits you've bought cost.
export default function Spending() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api.spending().then(setData).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="alert error small">{error}</p>
  if (!data) return <p className="muted small">Loading...</p>
  return (
    <>
      <div className="stat-grid">
        <div><span>All time</span><strong>{money(data.all_time)}</strong></div>
        <div><span>This year</span><strong>{money(data.this_year)}</strong></div>
        <div><span>This month</span><strong>{money(data.this_month)}</strong></div>
      </div>
      <p className="hint">
        Supplies. Includes {money(data.starting_stock)} of starting stock (what you had when the spreadsheet was
        imported).{data.unpriced > 0 && ` ${data.unpriced} purchase${data.unpriced === 1 ? ' has' : 's have'} no price, so ${data.unpriced === 1 ? "isn't" : "aren't"} counted.`}
        {data.kits_priced > 0 && ` Kits: ${money(data.kits_spent)} on ${data.kits_priced} kit${data.kits_priced === 1 ? '' : 's'}.`}
      </p>
      {data.by_year.length > 1 && (
        <p className="small">{data.by_year.map((y) => `${y.year}: ${money(y.spent)}`).join(' · ')}</p>
      )}
      {data.recent.length > 0 && (
        <>
          <h4 className="section-title">Latest purchases</h4>
          <ul className="list compact">
            {data.recent.map((r, i) => (
              <li key={i}>
                <span className="grow">{r.qty < 0 ? 'Undo: ' : ''}{r.item_name}{Math.abs(r.qty) > 1 ? ` ×${Math.abs(r.qty)}` : ''}</span>
                <span className="muted small">{shortDate(r.created_at)}</span>
                <span className="num">{r.unit_price == null ? '—' : money(r.spent)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}
