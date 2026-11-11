import { VinylIcon } from '../../components/icons.jsx'
import { money } from '../../api.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useVinylSummary } from './vinylParts.jsx'

// Vinyl's parts of Home (kept apart from its pages, so Home doesn't load them): records and what they're worth, and
// plays this month (or what's spinning now).
export function VinylTiles() {
  const { data: s } = useVinylSummary()
  if (!s) return <StatSkeleton />
  if (!s.owned && !s.wanted) return null
  return (
    <>
      <Stat to="/vinyl/crate" Icon={VinylIcon} tone="tint" value={s.owned} label="Records"
        sub={s.value ? `worth ${money(s.value)}` : `${s.wanted} on the wantlist`} />
      {s.now_spinning ? (
        <Stat to="/vinyl/dashboard" Icon={VinylIcon} tone="teal" value="Spinning" label={s.now_spinning.title} sub={s.now_spinning.artist ?? ''} />
      ) : (
        <Stat to="/vinyl/plays" Icon={VinylIcon} tone="teal" value={s.plays_this_month} label="Plays this month"
          sub={`${s.spun_this_year} of ${s.owned} played this year`} />
      )}
    </>
  )
}
