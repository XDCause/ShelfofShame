import { shortDate } from '../../api.js'
import { MODULES } from '../../modules/index.js'

// Shared by the Goals list, a goal's own page and the Home card (api/app/goals.py).
export const STATUS = {
  active: { label: 'Active', tone: 'tint' },
  paused: { label: 'Paused', tone: 'low' },
  done: { label: 'Done', tone: 'ok' },
  dropped: { label: 'Dropped', tone: 'out' },
}
export const hobbyName = (id) => MODULES.find((m) => m.id === id)?.name

const num = (v) => (v == null ? '' : Number(v).toLocaleString('en-AU', { maximumFractionDigits: 2 }))

// "6 of 30 books", "77.5 kg (from 80 to 75)", "2 of 5 steps", or nothing to say.
export function progressText(g) {
  if (g.target_value != null) {
    const unit = g.unit ? ` ${g.unit}` : ''
    if (g.current_value == null) return `Target ${num(g.target_value)}${unit}`
    if (g.start_value != null && Number(g.start_value) > Number(g.target_value)) {
      return `${num(g.current_value)}${unit} (from ${num(g.start_value)} to ${num(g.target_value)})`
    }
    return `${num(g.current_value)} of ${num(g.target_value)}${unit}`
  }
  if (g.steps_total) return `${g.steps_done} of ${g.steps_total} step${g.steps_total === 1 ? '' : 's'}`
  return ''
}

// "Due in 12 days", "Due today", "3 days overdue", "Reached 14 Oct"...
export function dueText(g) {
  if (g.status === 'done') return g.done_on ? `Reached ${shortDate(g.done_on)}` : 'Reached'
  if (g.days_left == null) return g.target_date ? `By ${shortDate(g.target_date)}` : ''
  if (g.days_left < 0) return `${-g.days_left} day${g.days_left === -1 ? '' : 's'} overdue`
  if (g.days_left === 0) return 'Due today'
  if (g.days_left < 60) return `Due in ${g.days_left} day${g.days_left === 1 ? '' : 's'}`
  return `By ${shortDate(g.target_date)}`
}

export function ProgressBar({ goal: g }) {
  if (g.progress == null) return null
  const percent = Math.round(g.progress * 100)
  return (
    <span className={`goal-bar ${g.status === 'done' || percent >= 100 ? 'ok' : 'tint'}`} role="meter" aria-valuemin={0}
      aria-valuemax={100} aria-valuenow={percent} aria-label={`${percent}% of the way`}>
      <span style={{ width: `${Math.max(percent, 2)}%` }} />
    </span>
  )
}
