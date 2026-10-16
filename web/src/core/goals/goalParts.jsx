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

// Timeframes: a year's goals (New Year's goals) or 3 years, each from a first year (api/app/goals.py).
export const yearsOf = (g) => (g.timeframe === 'three_years' ? [g.period_start, g.period_start + 2] : [g.period_start, g.period_start])
export function periodLabel(timeframe, start) {
  if (timeframe === 'year') return `${start} goals`
  if (timeframe === 'three_years') return `3-year goals · ${start}–${start + 2}`
  return 'No set time'
}
export const periodShort = (g) => (g.timeframe === 'year' ? String(g.period_start)
  : g.timeframe === 'three_years' ? `${g.period_start}–${String(g.period_start + 2).slice(2)}` : '')

// The choices offered: this year, next year (for New Year's goals made in December), 3 years from
// either, no set time - plus whatever the goal already has, if it's none of those.
export function periodChoices(thisYear, goal = null) {
  const choices = [
    ['year', thisYear, `This year (${thisYear})`],
    ['year', thisYear + 1, `Next year (${thisYear + 1})`],
    ['three_years', thisYear, `3 years (${thisYear}–${thisYear + 2})`],
    ['three_years', thisYear + 1, `3 years (${thisYear + 1}–${thisYear + 3})`],
    ['', null, 'No set time'],
  ]
  if (goal?.timeframe && !choices.some(([t, y]) => t === goal.timeframe && y === goal.period_start)) {
    choices.unshift([goal.timeframe, goal.period_start, periodLabel(goal.timeframe, goal.period_start)])
  }
  return choices.map(([t, y, label]) => ({ value: t ? `${t}:${y}` : '', timeframe: t || null, period_start: y, label }))
}
export const periodValue = (g) => (g.timeframe ? `${g.timeframe}:${g.period_start}` : '')

// The Goals page's sections, in this order: this year's, 3-year goals running now, next year's and
// later, no set time, then past years'.
export function groupGoals(goals, thisYear) {
  const groups = new Map()
  for (const g of goals) {
    const key = periodValue(g)
    if (!groups.has(key)) groups.set(key, { key, timeframe: g.timeframe, start: g.period_start, goals: [] })
    groups.get(key).goals.push(g)
  }
  const rank = (s) => {
    if (!s.timeframe) return [3, 0]
    const [from, to] = yearsOf({ timeframe: s.timeframe, period_start: s.start })
    if (to < thisYear) return [4, -to]                        // past: newest first
    if (from <= thisYear) return [s.timeframe === 'year' ? 0 : 1, from]
    return [2, from + (s.timeframe === 'year' ? 0 : 0.5)]
  }
  return [...groups.values()].sort((a, b) => {
    const [x, y] = [rank(a), rank(b)]
    return x[0] - y[0] || x[1] - y[1]
  })
}
