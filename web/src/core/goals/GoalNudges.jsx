import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../../api.js'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'

// Home's gentle line about goals (api/app/goals.py nudges): the ones that haven't moved in 3 weeks, and in the first
// week of a month, a prompt to check in on them all. Nothing to say: nothing shown.
export default function GoalNudges() {
  const { refreshKey } = useApp()
  const navigate = useNavigate()
  const [n, setN] = useState(null)
  useEffect(() => { api.goalNudges().then(setN).catch(() => setN(null)) }, [refreshKey])
  if (!n || (!n.stale.length && !n.checkin)) return null
  const weeks = (days) => `${Math.round(days / 7)} weeks`
  const seen = async (go) => {
    setN({ ...n, checkin: false })
    await api.goalCheckinSeen().catch(() => {})
    if (go) navigate('/goals')
  }
  return (
    <section className="card goal-nudges" aria-label="Goals that need a look">
      <TargetIcon size={20} />
      <div className="grow">
        {n.checkin && <p><strong>A new month.</strong> A good time to check in on your goals - a line on each keeps them moving.</p>}
        {n.stale.length === 1 && (
          <p><Link to={`/goals/${n.stale[0].goal_id}`}>{n.stale[0].title}</Link> hasn't moved in {weeks(n.stale[0].days)}. A small step today?</p>
        )}
        {n.stale.length > 1 && (
          <p>{n.stale.length} goals haven't moved in a while:{' '}
            {n.stale.slice(0, 3).map((s, i) => (
              <span key={s.goal_id}>{i > 0 && ', '}<Link to={`/goals/${s.goal_id}`}>{s.title}</Link> ({weeks(s.days)})</span>
            ))}{n.stale.length > 3 && ' and more'}.</p>
        )}
      </div>
      {n.checkin && (
        <span className="goal-nudges-actions">
          <button type="button" className="secondary small" onClick={() => seen(true)}>Check in</button>
          <button type="button" className="plain small" onClick={() => seen(false)}>Not now</button>
        </span>
      )}
    </section>
  )
}
