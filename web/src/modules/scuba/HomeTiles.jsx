import { shortDate } from '../../api.js'
import { DiveIcon, TargetIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { field, hoursText, metres, noFlyLeft } from './scubaFormat.js'
import { useScubaSummary } from './scubaParts.jsx'

// Scuba's part of Home (ScubaTiles): the dive count with the hours underwater, the last dive, and the no-fly time
// while it runs - kept apart from its pages so Home doesn't load them. Nothing until the first dive is logged.
export function ScubaTiles() {
  const { data: s } = useScubaSummary()
  if (!s) return <StatSkeleton />
  if (!s.dives) return null
  const last = s.last_dive
  const fly = noFlyLeft(s.no_fly_until)
  const year = field(s.this_year, 'dives')
  return (
    <>
      <Stat to="/scuba/dashboard" Icon={DiveIcon} tone="teal" value={s.dives.toLocaleString()} label="Dives"
        sub={[hoursText(s.minutes), year != null && `${year} this year`].filter(Boolean).join(' · ')} />
      {last && (
        <Stat to="/scuba/log" Icon={TargetIcon} tone="ok" value={metres(last.max_depth)} label="Last dive"
          sub={[last.site_name, shortDate(last.dived_on)].filter(Boolean).join(' · ')} />
      )}
      {!fly.clear && (
        <Stat to="/scuba/dashboard" Icon={DiveIcon} tone="low" value={fly.text} label="No-fly time left"
          sub="don't fly until it is over" />
      )}
    </>
  )
}
