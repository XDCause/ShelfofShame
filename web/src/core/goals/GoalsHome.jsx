import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import { dueText, periodShort, ProgressBar, progressText } from './goalParts.jsx'

// Goals on the Home page: the active ones (pinned first, then soonest due), up to four. Phones reach
// the Goals page from here (their tab bar has no room for it).
export default function GoalsHome() {
  const { refreshKey } = useApp()
  const [goals, setGoals] = useState(null)
  useEffect(() => { api.goals('active').then((d) => setGoals(d.goals)).catch(() => setGoals([])) }, [refreshKey])
  if (!goals) return null

  return (
    <section className="card home-card" aria-labelledby="home-goals">
      <h2 id="home-goals" className="home-card-title"><TargetIcon size={20} /> Goals
        <Link to="/goals" className="small">{goals.length ? 'All goals →' : 'Set a goal →'}</Link></h2>
      {goals.length === 0 ? <p className="muted small">Nothing you're aiming for yet.</p> : (
        <ul className="list plain-list home-goals">
          {goals.slice(0, 4).map((g) => (
            <li key={g.goal_id}>
              <Link to={`/goals/${g.goal_id}`} className="row-button">
                <span className="grow">
                  <span className="item-title">{g.title}</span>
                  <span className="item-meta">{[periodShort(g), progressText(g), g.next_step && `Next: ${g.next_step}`, dueText(g)].filter(Boolean).join(' · ')}</span>
                  <ProgressBar goal={g} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
