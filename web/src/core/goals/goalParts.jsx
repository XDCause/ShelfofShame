import { useEffect, useState } from 'react'
import { dayDate, shortDate } from '../../api.js'
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
  if (g.habit) return `${num(g.habit.this)} of ${num(g.habit.times)}${g.unit && g.source ? ` ${g.unit}` : ''} this ${g.habit.every}`
  if (g.todos_total) return `${g.todos_done} of ${g.todos_total} to-do${g.todos_total === 1 ? '' : 's'}`
  if (g.progress_from === 'goals') return 'from the goals inside it'
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
    <span className={`goal-meter ${g.status === 'done' || percent >= 100 ? 'ok' : 'tint'}`} role="meter" aria-valuemin={0}
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

// On track / ahead / behind: an even pace from the start to the day you're aiming for (api/app/goals.py pace).
export const PACE = {
  ahead: { label: 'Ahead', tone: 'ok' },
  on_track: { label: 'On track', tone: 'tint' },
  behind: { label: 'Behind', tone: 'low' },
  done: { label: 'Target reached', tone: 'ok' },
}
export function PaceBadge({ goal: g }) {
  if (g.habit && g.status === 'active') {
    return <span className={`pill ${g.habit.met ? 'ok' : 'tint'}`}>{g.habit.met ? `Done this ${g.habit.every}` : `${num(g.habit.left)} to go this ${g.habit.every}`}</span>
  }
  const p = g.pace && PACE[g.pace.status]
  return p ? <span className={`pill ${p.tone} goal-pace`}>{p.label}</span> : null
}

// "About 3.2 kits a month to finish" (a week, in the last two months); behind: where an even pace would have you.
export function paceText(g) {
  const p = g.pace
  if (!p || p.status === 'done') return ''
  const unit = g.unit ? ` ${g.unit}` : ''
  const parts = []
  const round = (v) => num(Math.abs(v) >= 20 ? Math.round(v) : Math.round(v * 10) / 10)
  if (p.status === 'behind' && p.expected != null) parts.push(`An even pace would have you at ${round(p.expected)}${unit} by now`)
  const weekly = g.days_left != null && g.days_left < 60
  const rate = weekly ? p.per_week : p.per_month
  if (rate != null && rate !== 0) parts.push(`about ${round(Math.abs(rate))}${unit} a ${weekly ? 'week' : 'month'} gets you there`)
  const text = parts.join('; ')
  return text ? text[0].toUpperCase() + text.slice(1) + '.' : ''
}

// The number over time: where you've been (solid), an even pace from start to target (dashed) and today. For a
// number you give: each progress note's number; for one the app counts: its running total (or each new level).
export function GoalChart({ goal: g }) {
  const series = g.series ?? []
  if (series.length < 1 || g.target_value == null) return null
  const t = (iso) => dayDate(iso).getTime()
  const begin = t(g.start_day)
  const now = Date.now()
  const end = Math.max(g.target_date ? t(g.target_date) : now, now, begin + 86400000)
  const start = g.start_value ?? series[0][1] ?? 0
  const values = [start, g.target_value, ...series.map(([, v]) => v)]
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  if (hi === lo) hi = lo + 1
  const pad = (hi - lo) * 0.08
  lo -= pad
  hi += pad
  const W = 600
  const H = 170
  const x = (ms) => 8 + ((ms - begin) / (end - begin)) * (W - 16)
  const y = (v) => H - 18 - ((v - lo) / (hi - lo)) * (H - 36)
  const steps = series.flatMap(([d, v], i) => (i === 0 ? [[t(d), v]] : [[t(d), series[i - 1][1]], [t(d), v]]))
  steps.push([Math.min(now, end), series[series.length - 1][1]])
  const line = steps.map(([d, v]) => `${x(Math.max(d, begin)).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const last = series[series.length - 1]
  const unit = g.unit ? ` ${g.unit}` : ''
  return (
    <figure className="goal-chart">
      <div className="goal-chart-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" preserveAspectRatio="none"
        aria-label={`${g.title}: from ${num(start)} to ${num(last[1])}${unit} so far, aiming for ${num(g.target_value)}${unit}`}>
        <line className="goal-chart-target" x1="8" x2={W - 8} y1={y(g.target_value)} y2={y(g.target_value)} />
        {g.target_date && <line className="goal-chart-pace" x1={x(begin)} y1={y(start)} x2={x(t(g.target_date))} y2={y(g.target_value)} />}
        {now < end && <line className="goal-chart-today" x1={x(now)} x2={x(now)} y1="6" y2={H - 14} />}
        <polyline className="goal-chart-line" points={line} />
      </svg>
      {/* (the svg stretches to the card's width: a dot drawn in it would squash into an oval) */}
      <span className="goal-chart-dot" style={{ left: `${(x(Math.min(now, end)) / W) * 100}%`, top: `${(y(last[1]) / H) * 100}%` }} />
      </div>
      <figcaption className="goal-chart-key">
        <span>{shortDate(g.start_day)}</span>
        <span><i className="key-line" /> you <i className="key-pace" /> even pace{now < end && <> <i className="key-today" /> today</>}</span>
        <span>{g.target_date ? shortDate(g.target_date) : 'today'}</span>
      </figcaption>
    </figure>
  )
}

// A habit's last weeks / months: one bar each, full when it reached the aim.
export function HabitStrip({ goal: g }) {
  const h = g.habit
  if (!h) return null
  const when = (iso) => (h.every === 'week' ? shortDate(iso) : dayDate(iso).toLocaleDateString('en-AU', { month: 'short' }))
  const reached = h.periods.filter((p) => p.met).length
  return (
    <figure className="habit-chart">
      <div className="habit-strip" role="img" aria-label={`The last ${h.periods.length} ${h.every}s: ${reached} reached ${num(h.times)}`}>
        {h.periods.map((p) => (
          <span key={p.start} className={`habit-bar${p.met ? ' met' : ''}`} title={`${when(p.start)}: ${num(p.count)}`}>
            <span style={{ height: `${Math.max(6, Math.min(100, (p.count / h.times) * 100))}%` }} />
          </span>
        ))}
      </div>
      <figcaption className="goal-chart-key">
        <span>{when(h.periods[0]?.start)}</span>
        <span>The last {h.periods.length} {h.every}s · {reached} reached {num(h.times)}{h.rate != null && ` · ${Math.round(h.rate * 100)}% of all of them`}</span>
        <span>this {h.every}</span>
      </figcaption>
    </figure>
  )
}

// A short burst of leaves and confetti when a goal is reached (none if you've asked your device for less motion).
export function Celebrate({ run }) {
  const [bits, setBits] = useState([])
  useEffect(() => {
    if (!run || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined
    const colours = ['#7da35c', '#e0a35a', '#c9563c', '#4f8f8b', '#e9c79a', '#9b7bb8']
    setBits(Array.from({ length: 36 }, (_, i) => ({
      id: `${run}-${i}`, left: 10 + Math.random() * 80, delay: Math.random() * 0.25, turn: (Math.random() - 0.5) * 720,
      drift: (Math.random() - 0.5) * 160, colour: colours[i % colours.length], leaf: i % 3 === 0,
    })))
    const done = setTimeout(() => setBits([]), 2200)
    return () => clearTimeout(done)
  }, [run])
  if (!bits.length) return null
  return (
    <div className="celebrate" aria-hidden="true">
      {bits.map((b) => (
        <span key={b.id} className={b.leaf ? 'leaf' : 'bit'}
          style={{ left: `${b.left}%`, animationDelay: `${b.delay}s`, background: b.colour, '--turn': `${b.turn}deg`, '--drift': `${b.drift}px` }} />
      ))}
    </div>
  )
}
