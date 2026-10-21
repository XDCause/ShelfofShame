import { shortDate } from '../../api.js'
import { CalendarIcon, ChevronIcon, SuitcaseIcon, TrophyIcon } from '../../components/icons.jsx'
import Landscape from '../../components/Landscape.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { plural, tripMeta, useTravelSummary, when } from './travelParts.jsx'

// travel's parts of Home (TravelTiles, NextAdventure): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
// Home: two numbers. With a trip on or coming up: the countdown (or where you are), then its packing (once it has a
// list) or the countries you've been to. With none: countries visited and this year's trips.
export function TravelTiles() {
  const { data: s } = useTravelSummary()
  if (!s) return <><StatSkeleton /><StatSkeleton /></>
  const now = s.now[0]
  const next = s.upcoming[0]
  const trip = now ?? next
  const countries = (
    <Stat to="/travel/places" Icon={TrophyIcon} tone="ok" value={s.countries_been} label="Countries visited"
      sub={s.bucket_list ? `${s.bucket_list} on the bucket list` : `${plural(s.places_been, 'place')} been`} />
  )
  if (trip) {
    return (
      <>
        {now ? <Stat to="/travel/dashboard" Icon={SuitcaseIcon} tone="ok" value={when(now)} label={now.name} sub="Travelling now" />
          : <Stat to="/travel/dashboard" Icon={SuitcaseIcon} tone="teal" value={next.starts_in === 1 ? 'Tomorrow' : plural(next.starts_in, 'day')}
            label={`Until ${next.name}`} sub={shortDate(next.start_date)} />}
        {trip.packing_count > 0
          ? <Stat to="/travel/trips" Icon={CalendarIcon} tone="tint" value={`${trip.packed_count}/${trip.packing_count}`} label="Packed"
            sub={trip.packed_count === trip.packing_count ? 'all packed' : `for ${trip.name}`} />
          : countries}
      </>
    )
  }
  if (!s.countries_been) return null
  return (
    <>
      {countries}
      <Stat to="/travel/trips" Icon={CalendarIcon} tone="tint" value={s.this_year.trips} label={`Trips in ${s.year}`}
        sub={`${plural(s.this_year.days, 'day')} away`} />
    </>
  )
}

// Home's feature: the trip you're on, or the next one - its picture (or a drawn coast), dates and a way in.
export function NextAdventure() {
  const { data: s } = useTravelSummary()
  const { openPanel } = useApp()
  const trip = s?.now[0] ?? s?.upcoming[0]
  if (!trip) return null
  return (
    <section className="card home-card next-adventure" aria-labelledby="home-trip">
      {trip.photo_url ? <img className="next-adventure-art" src={trip.photo_url} alt="" loading="lazy" />
        : <span className="next-adventure-art"><Landscape scene="coast" seed={trip.trip_id + 40} hue="#2fa39a" /></span>}
      <div className="next-adventure-text">
        <p className="next-adventure-eyebrow">{s.now[0] ? 'Travelling now' : 'Next adventure'}</p>
        <h2 id="home-trip" className="next-adventure-name">{trip.name}</h2>
        <p className="next-adventure-when">{tripMeta(trip)}</p>
        <button type="button" className="primary" onClick={() => openPanel('trip', { id: trip.trip_id })}>
          View trip <ChevronIcon size={14} /></button>
      </div>
    </section>
  )
}
