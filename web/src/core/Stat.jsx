import { Link } from 'react-router'

// One stat tile on Home and the Hobbies page: a coloured icon square, the number, what it is,
// and (optionally) how much it changed lately. Tapping it opens the page it's about.
export default function Stat({ to, Icon, tone = 'tint', value, label, sub, change }) {
  return (
    <Link to={to} className="home-stat">
      <span className={`stat-icon ${tone}`}><Icon size={22} /></span>
      <span className="stat-text">
        <strong>{value}{change}</strong>
        <span className="home-stat-label">{label}</span>
        {sub && <span className="muted small">{sub}</span>}
      </span>
    </Link>
  )
}

// "+7" beside a number: how much it changed in the last 7 days (green up, amber down, grey none).
export function Change({ value, unit = '', what = 'in the last 7 days' }) {
  if (value == null) return null
  const n = Number(value)
  const text = `${n < 0 ? '−' : '+'}${Math.abs(n).toLocaleString()}${unit}`
  return <span className={`delta ${n > 0 ? 'up' : n < 0 ? 'down' : 'none'}`} title={`${text} ${what}`}>{text}</span>
}

// While a module's numbers load: an empty tile keeps the grid from jumping.
export const StatSkeleton = () => <span className="home-stat skeleton" aria-hidden="true" />
