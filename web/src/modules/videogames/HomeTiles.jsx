import { GamepadIcon, TrophyIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useSteamSummary } from './steam.jsx'

// videogames's parts of Home (VideoGamesTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
// Home: two tiles.
export function VideoGamesTiles() {
  const { data: s } = useSteamSummary()
  if (!s) return <><StatSkeleton /><StatSkeleton /></>
  return (
    <>
      {/* three short lines each (the number, what it is, one detail) so the card lines up with the others; the
          dashboard has the rest (the next game to finish, points to go) */}
      <Stat to="/videogames/dashboard" Icon={TrophyIcon} tone="ok" value={s.perfect} label="Games at 100%"
        sub={s.week?.perfect ? `${s.week.perfect > 0 ? '+' : ''}${s.week.perfect} this week` : 'all platforms'} />
      <Stat to="/videogames/dashboard" Icon={GamepadIcon} tone="purple" value={`${s.goal.percent}%`}
        label="Profile complete" sub={s.goal.reached ? `goal ${s.goal.goal_percent}% reached` : `goal ${s.goal.goal_percent}%`} />
    </>
  )
}
