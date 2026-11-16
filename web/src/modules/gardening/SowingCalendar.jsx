import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import Fold from '../../components/Fold.jsx'

// The Brisbane sowing calendar (hand-written, api/app/garden_guide.py): every month with what to sow as seed and as
// seedlings. This month starts open. The Guide's per-plant months below it are the detail.
export default function SowingCalendar() {
  const [data, setData] = useState(null)
  useEffect(() => { api.gardenSowingCalendar().then(setData).catch(() => setData(null)) }, [])
  if (!data) return null
  return (
    <section className="card garden-sowcal">
      <h2 className="home-card-title">Sowing calendar · {data.region}</h2>
      <p className="muted small">General guidance written for south-east Queensland: your balcony's sun and wind can shift it a few weeks.</p>
      <ol className="garden-sowcal-list">
        {data.months.map((m) => (
          <li key={m.month} className={m.month === data.this_month ? 'now' : ''}>
            <Fold title={m.name} detail={m.month === data.this_month ? 'this month' : null} open={m.month === data.this_month}>
              <p className="small">{m.note}</p>
              <p className="small"><strong>Seeds:</strong> {m.seeds.join(', ')}.</p>
              <p className="small"><strong>Seedlings:</strong> {m.seedlings.join(', ')}.</p>
            </Fold>
          </li>
        ))}
      </ol>
    </section>
  )
}
