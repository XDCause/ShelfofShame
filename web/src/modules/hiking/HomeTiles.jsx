import { shortDate } from '../../api.js'
import { BootIcon, MountainIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { metres, useHikingSummary } from './hikingParts.jsx'

// hiking's parts of Home (HikingTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
export const plural = (n, one, many = `${one}s`) => `${n.toLocaleString()} ${n === 1 ? one : many}`

export function HikingTiles() {
  const { data: s } = useHikingSummary()
  if (!s) return <StatSkeleton />
  if (!s.all_time.hikes) return null
  const y = s.this_year
  const top = s.bests?.highest?.max_ele_m
  return (
    <>
      <Stat to="/hiking/dashboard" Icon={MountainIcon} tone="ok" value={`${y.km.toFixed(1)} km`} label={`Hiked in ${s.year}`}
        sub={`${plural(y.hikes, 'hike')}${s.recent[0] ? ` · last ${shortDate(s.recent[0].hiked_on)}` : ''}`} />
      <Stat to="/hiking/dashboard" Icon={BootIcon} tone="teal" value={metres(y.ascent_m)} label={`Climbed in ${s.year}`}
        sub={top ? `highest point ${metres(top)}` : 'uphill, all hikes'} />
    </>
  )
}
