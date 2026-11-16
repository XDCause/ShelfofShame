import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, dayDate, isoDay } from '../../api.js'
import { useApp } from '../app-context.js'
import { minutesText } from '../focus/focusMath.js'

// The weekly review (api/app/goals_review.py): what you did this week per goal, streaks, what's slipping, and a box
// for a note; saving it makes a journal page (tag "weekly review"). On the Goals page, and on Home on Sundays.
const dayText = (iso) => dayDate(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })

function goalLine(g) {
  const bits = []
  if (g.habit) bits.push(`${g.habit.this} of ${g.habit.times} this ${g.habit.every}${g.habit.this_frozen ? ' (frozen)' : ''}`)
  if (g.counted) bits.push(`${g.counted} ${g.unit ?? ''}`.trim())
  if (g.todos_done) bits.push(`${g.todos_done} to-do${g.todos_done === 1 ? '' : 's'} done`)
  if (g.notes) bits.push(`${g.notes} note${g.notes === 1 ? '' : 's'}`)
  if (g.focus_minutes) bits.push(`${minutesText(g.focus_minutes)} focused`)
  return bits.join(' · ') || 'Quiet this week'
}

export default function WeeklyReview({ compact = false }) {
  const { showToast, changed } = useApp()
  const navigate = useNavigate()
  const [week, setWeek] = useState(null)         // any day in the week asked for; null = this one
  const [r, setR] = useState(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => { api.weeklyReview(week).then(setR).catch((e) => setError(e.message)) }, [week])
  if (!r) return error ? <p className="alert error">{error}</p> : null
  const shift = (days) => {
    const d = dayDate(r.week_start)
    d.setDate(d.getDate() + days)
    setWeek(isoDay(d))
    setNote('')
  }
  const save = async () => {
    setSaving(true)
    try {
      const page = await api.saveWeeklyReview(note, r.week_start)
      changed()
      showToast('Saved to your journal.')
      navigate(`/journal/${page.page_id}`)
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }
  const t = r.totals
  const slipping = r.goals.filter((g) => g.slipping)
  return (
    <section className="card home-card weekly-review" aria-labelledby="weekly-review-title">
      <h2 id="weekly-review-title" className="home-card-title">{r.current ? 'Your week' : 'Weekly review'}
        <span className="muted small">{dayText(r.week_start)} - {dayText(r.week_end)}</span></h2>
      <div className="weekly-review-nav">
        <button type="button" className="plain small" onClick={() => shift(-7)}>‹ Earlier week</button>
        {!r.current && <button type="button" className="plain small" onClick={() => shift(7)}>Later week ›</button>}
      </div>
      {error && <p className="alert error small" role="alert">{error}</p>}
      {t.goals === 0 ? <p className="muted small">No active goals yet. <Link to="/goals">Set one</Link>.</p> : (
        <>
          <p className="weekly-review-sum"><strong>{t.moved} of {t.goals}</strong> goals moved · {t.todos_done} to-do{t.todos_done === 1 ? '' : 's'} done
            {t.focus_minutes > 0 && <> · {minutesText(t.focus_minutes)} focused</>}
            {t.streaks > 0 && <> · {t.streaks} streak{t.streaks === 1 ? '' : 's'} alive</>}</p>
          {!compact && (
            <ul className="list plain-list weekly-review-goals">
              {r.goals.map((g) => (
                <li key={g.goal_id}>
                  <Link to={`/goals/${g.goal_id}`} className="weekly-review-goal">
                    <span className="grow"><span className="item-title">{g.title}</span><span className="item-meta">{goalLine(g)}</span></span>
                    {g.habit?.streak > 0 && <span className="pill ok">{g.habit.streak} in a row</span>}
                    {g.slipping && <span className="pill low">Slipping</span>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {slipping.length > 0 && (
            <p className="small weekly-review-slipping"><strong>Slipping:</strong> {slipping.map((g) => g.title).join(', ')}</p>
          )}
        </>
      )}
      {r.saved_page_id ? (
        <p className="small">Saved: <Link to={`/journal/${r.saved_page_id}`}>open the journal page</Link></p>
      ) : (
        <div className="weekly-review-note">
          <label className="field wide"><span className="field-label">How did the week go?</span>
            <textarea rows={3} value={note} maxLength={20000} onChange={(e) => setNote(e.target.value)}
              placeholder="What worked, what got in the way, what to do next week..." /></label>
          <button type="button" className="secondary" disabled={saving} onClick={save}>Save to the journal</button>
        </div>
      )}
    </section>
  )
}

// Home shows it on Sundays only (and asks nothing the other six days).
export function WeeklyReviewHome() {
  return new Date().getDay() === 0 ? <WeeklyReview compact /> : null
}
