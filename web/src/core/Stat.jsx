import { Link } from 'react-router'

// One stat tile on Home and the Hobbies page: a coloured icon square, the number, what it is.
// Tapping it opens the page it's about.
export default function Stat({ to, Icon, tone = 'tint', value, label, sub }) {
  return (
    <Link to={to} className="home-stat">
      <span className={`stat-icon ${tone}`}><Icon size={22} /></span>
      <span className="stat-text">
        <strong>{value}</strong>
        <span className="home-stat-label">{label}</span>
        {sub && <span className="muted small">{sub}</span>}
      </span>
    </Link>
  )
}

// While a module's numbers load: an empty tile keeps the grid from jumping.
export const StatSkeleton = () => <span className="home-stat skeleton" aria-hidden="true" />
