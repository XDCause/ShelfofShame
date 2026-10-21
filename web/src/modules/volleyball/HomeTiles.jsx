import { api, clock, dayDate } from '../../api.js'
import { BallIcon, CalendarIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'

// volleyball's parts of Home (VolleyballTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
export function useVolleyball() {
  const { refreshKey } = useApp()
  return useShared(`volleyball-${refreshKey}`, () => Promise.all([api.volleyballSummary(), api.upcoming(20)])
    .then(([summary, upcoming]) => ({ summary, next: upcoming.filter((e) => e.hobby === 'volleyball') })))
}

// Home: two tiles.
export function VolleyballTiles() {
  const { data } = useVolleyball()
  if (!data) return <><StatSkeleton /><StatSkeleton /></>
  const { summary, next } = data
  const n = next[0]
  return (
    <>
      <Stat to="/volleyball/games" Icon={BallIcon} tone="low" value={`${summary.won}–${summary.lost}`} label="Volleyball"
        sub={`won–lost this year`} />
      <Stat to="/calendar" Icon={CalendarIcon} tone="teal"
        value={n ? dayDate(n.day).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric' }) : '—'}
        label="Next game" sub={n ? [clock(n.start_time), n.location].filter(Boolean).join(' · ') || n.title : 'nothing planned'} />
    </>
  )
}
