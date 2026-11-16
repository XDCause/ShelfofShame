import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'

// A note above the calendar: what to sow in the month being looked at (the hand-written Brisbane sowing calendar,
// Gardening > Guide). It is a calendar layer ("Sow now (Gardening)"), and hides with the Gardening hobby.
export default function SowNote({ month }) {
  const [data, setData] = useState(null)
  useEffect(() => { api.gardenSowingCalendar().then(setData).catch(() => setData(null)) }, [])
  const m = data?.months.find((x) => x.month === month)
  if (!m) return null
  return (
    <p className="cal-sow-note small">
      <span aria-hidden="true">🌱</span> <strong>Sow in {m.name}:</strong> {m.seeds.slice(0, 8).join(', ')}
      {m.seeds.length > 8 && '…'} · seedlings: {m.seedlings.slice(0, 5).join(', ')}.{' '}
      <Link to="/gardening/guide">Sowing calendar</Link>
    </p>
  )
}
