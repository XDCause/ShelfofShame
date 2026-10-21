import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import { PaceBadge, ProgressBar, progressText } from './goalParts.jsx'

// A hobby's goals at the top of its first page (Chess > Dashboard...): the active and upcoming ones set to this hobby,
// each with its bar and whether it's on track; tap one for its page. No goals for the hobby: nothing shown.
export default function HobbyGoals({ hobby }) {
  const { refreshKey } = useApp()
  const [goals, setGoals] = useState([])
  useEffect(() => {
    api.goals('active').then((d) => setGoals(d.goals.filter((g) => g.hobby === hobby))).catch(() => setGoals([]))
  }, [hobby, refreshKey])
  if (!goals.length) return null
  const shown = goals.slice(0, 3)
  return (
    <section className="hobby-goals" aria-label="Your goals for this hobby">
      <h2 className="hobby-goals-title"><TargetIcon size={18} /> Your goals
        {goals.length > shown.length && <Link to="/goals" className="small">All {goals.length} →</Link>}</h2>
      <ul className="hobby-goals-list">
        {shown.map((g) => {
          const text = progressText(g)
          return (
            <li key={g.goal_id}>
              <Link to={`/goals/${g.goal_id}`} className="card hobby-goal">
                <span className="hobby-goal-top"><span className="hobby-goal-name">{g.title}</span><PaceBadge goal={g} /></span>
                {!g.upcoming && <ProgressBar goal={g} />}
                {text && <span className="item-meta">{text}{g.progress != null && !g.habit && !g.upcoming && g.kind !== 'milestone' ? ` · ${Math.round(g.progress * 100)}%` : ''}</span>}
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
