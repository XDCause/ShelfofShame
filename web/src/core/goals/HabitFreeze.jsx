import { api, dayDate, shortDate } from '../../api.js'

// A habit's freezes (api/app/goals_review.py): a week (or month) you couldn't do it, frozen so it doesn't break the streak.
// A few a month. `run` is the goal page's (it takes the goal the API answers with).
export default function HabitFreeze({ goal: g, run }) {
  const h = g.habit
  const { used, allowed, days } = h.freezes
  const left = allowed - used
  const last = h.periods.length > 1 ? h.periods[h.periods.length - 2] : null
  const label = (iso) => (h.every === 'week' ? `Week of ${shortDate(iso)}` : dayDate(iso).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' }))
  return (
    <div className="habit-freeze" role="group" aria-label="Streak freezes">
      <p className="small"><strong>{left} of {allowed}</strong> freezes left this month. A frozen {h.every} doesn't break your streak.</p>
      <div className="habit-freeze-actions">
        <button type="button" className="secondary small" disabled={h.met || h.this_frozen || left <= 0}
          onClick={() => run(() => api.freezeHabit(g.goal_id))}>Freeze this {h.every}</button>
        {last && !last.met && !last.frozen && (
          <button type="button" className="plain small" disabled={left <= 0} onClick={() => run(() => api.freezeHabit(g.goal_id, last.start))}>
            Freeze last {h.every}</button>
        )}
      </div>
      {days.length > 0 && (
        <ul className="list plain-list compact">
          {days.map((f) => (
            <li key={f.freeze_id}><span className="item-meta">Frozen: {label(f.day)}</span>
              <button type="button" className="plain small" onClick={() => run(() => api.unfreezeHabit(f.freeze_id))}>Undo</button></li>
          ))}
        </ul>
      )}
    </div>
  )
}
