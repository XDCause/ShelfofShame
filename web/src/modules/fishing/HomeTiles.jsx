import { shortDate } from '../../api.js'
import { FishIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { hoursText, plural, tripName } from './fishFormat.js'
import { useFishingSummary } from './fishingParts.jsx'

// Fishing's part of Home (FishingTiles): a trip still on the water first (back to it), then the trip count with the
// fish, the last trip, and the biggest fish. Kept apart from its pages so Home doesn't load them. Nothing until the
// first trip is logged.
export function FishingTiles() {
  const { data: s } = useFishingSummary()
  if (!s) return <StatSkeleton />
  if (!s.trips && !s.open_trip) return null
  const last = s.last_trip
  const pb = s.personal_bests?.[0]
  return (
    <>
      {s.open_trip && (
        <Stat to="/fishing/live" Icon={FishIcon} tone="low" value="On the water" label="Back to the water"
          sub={[tripName(s.open_trip), plural(s.open_trip.catches ?? 0, 'fish', 'fish')].join(' · ')} />
      )}
      {s.trips > 0 && (
        <Stat to="/fishing/dashboard" Icon={FishIcon} tone="teal" value={s.trips.toLocaleString()} label="Fishing trips"
          sub={[`${plural(s.catches, 'fish', 'fish')}`, hoursText(s.hours)].join(' · ')} />
      )}
      {last && (
        <Stat to="/fishing/trips" Icon={TargetIcon} tone="ok" value={last.catches ? plural(last.catches, 'fish', 'fish') : 'Blank'} label="Last trip"
          sub={[tripName(last), shortDate(last.started_at)].filter(Boolean).join(' · ')} />
      )}
      {pb && (
        <Stat to="/fishing/stats" Icon={TrophyIcon} tone="low" value={`${pb.length_cm} cm`} label="Biggest fish" sub={pb.species} />
      )}
    </>
  )
}
