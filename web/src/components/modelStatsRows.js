import { duration } from '../api.js'

// Rows for the Models page's two charts (api/app/models.py: finished_by_year, stage_minutes).

// Kits finished per year, every year from the first to the latest (a year with none shows as 0).
export function yearRows(finishedByYear) {
  if (!finishedByYear?.length) return []
  const byYear = new Map(finishedByYear.map((y) => [y.year, y]))
  const first = Math.min(...byYear.keys())
  const last = Math.max(...byYear.keys())
  const rows = []
  for (let year = first; year <= last; year += 1) {
    const y = byYear.get(year)
    rows.push({ label: String(year), value: y?.kits ?? 0,
      tip: y ? `${y.kits} kit${y.kits === 1 ? '' : 's'}, ${y.minis} mini${y.minis === 1 ? '' : 's'} · ${duration(y.minutes)} timed` : 'none' })
  }
  return rows
}

// Time per build step, biggest first.
export function stepRows(stageMinutes) {
  return [...(stageMinutes ?? [])].filter((s) => s.minutes > 0)
    .sort((a, b) => b.minutes - a.minutes)
    .map((s) => ({ label: s.step, value: s.minutes, text: duration(s.minutes) }))
}
