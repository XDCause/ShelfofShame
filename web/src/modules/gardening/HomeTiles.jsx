import { BoxIcon, SproutIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useGardenSummary } from './gardenParts.jsx'

// gardening's parts of Home (GardenTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
export function GardenTiles() {
  const { data: s } = useGardenSummary()
  if (!s) return <StatSkeleton />
  if (!s.growing && !s.spaces) return null
  return (
    <>
      <Stat to="/gardening/today" Icon={SproutIcon} tone="ok" value={s.growing} label="Plants growing"
        sub={[s.need_water ? `${s.need_water} need water` : 'all watered', s.ready && `${s.ready} ready to pick`].filter(Boolean).join(' · ')} />
      <Stat to="/gardening/harvests" Icon={BoxIcon} tone="low" value={s.harvests_this_year} label={`Harvests in ${new Date().getFullYear()}`}
        sub={s.tasks_due ? `${s.tasks_due} reminder${s.tasks_due === 1 ? '' : 's'} due` : 'no reminders due'} />
    </>
  )
}
