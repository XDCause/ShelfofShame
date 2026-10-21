import { shortDate } from '../../api.js'
import { CrosshairIcon, TargetIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { plural, useShootingSummary } from './shootingParts.jsx'

// shooting's parts of Home (ShootingTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
export function ShootingTiles() {
  const { data: s } = useShootingSummary()
  if (!s) return <StatSkeleton />
  if (!s.all_time.sessions) return null
  const last = s.recent[0]
  const lastValue = last?.hit_shots ? `${Math.round((last.hits / last.hit_shots) * 100)}%` : last?.best_moa != null ? `${last.best_moa} MOA`
    : last?.score != null ? last.score : '—'
  const lastLabel = 'Last session'
  const lastSub = last && [last.hit_shots ? `${last.hits} of ${last.hit_shots} hits` : last.best_moa != null ? 'best group'
    : last.score != null ? 'score' : 'no hits or groups logged', shortDate(last.shot_on)].join(' · ')
  return (
    <>
      <Stat to="/shooting/dashboard" Icon={CrosshairIcon} tone="out" value={s.this_year.rounds.toLocaleString()} label={`Rounds in ${s.year}`}
        sub={`${plural(s.this_year.sessions, 'session')}${s.club_needed != null ? ` · ${s.this_year.club_days}/${s.club_needed} club shoots` : ''}`} />
      {last && <Stat to="/shooting/sessions" Icon={TargetIcon} tone="ok" value={lastValue} label={lastLabel} sub={lastSub} />}
    </>
  )
}
