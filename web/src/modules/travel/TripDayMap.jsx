import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api.js'
import { dayLabel } from './TripSections.jsx'
import TravelMap from './TravelMap.jsx'

// A trip's day-by-day map (api/app/travel_extras.py): pick a day and see its planned places in order on the map, with the
// distance from each stop to the next. Distances are straight lines; the road and time figures are rough estimates (no
// routing service is asked). A plan item shows here once it's linked to a place that has a position.
export default function DayMapTab({ t }) {
  const [m, setM] = useState(null)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)
  useEffect(() => { api.tripDayMap(t.trip_id).then(setM).catch((e) => setError(e.message)) }, [t.trip_id])
  const day = m && (m.days.find((d) => d.day === picked) ?? m.days[0])
  const places = useMemo(() => (day ? day.stops.map((s) => ({ place_id: s.place_id, name: s.name, lat: s.lat, lon: s.lon, status: 'Planned' })) : []), [day])
  if (!m) return <section className="panel-section">{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</section>
  if (!day) {
    return (
      <section className="panel-section">
        <h3 className="section-title">Day by day</h3>
        <p className="muted small">Nothing to map yet. On the Plan tab, link a day's items to places that have a spot on the map (or give a
          place a visit day): each day's stops then show here in order, with the distance between them.</p>
        {m.without_position > 0 && <p className="hint">{m.without_position} plan item{m.without_position === 1 ? ' has' : 's have'} no place with a position yet.</p>}
      </section>
    )
  }
  return (
    <section className="panel-section">
      <h3 className="section-title">Day by day</h3>
      <div className="segmented daymap-days" role="group" aria-label="Day">
        {m.days.map((d) => (
          <button key={d.day} type="button" aria-pressed={d.day === day.day} onClick={() => setPicked(d.day)}>Day {d.number}</button>
        ))}
      </div>
      <p className="item-sub">{dayLabel(day.day, t)}{day.legs.length > 0 && ` · ${day.km} km between stops (about ${day.road_km} km by road, ${day.drive_min} min driving)`}</p>
      <TravelMap places={places} route={places.length > 1} label={`Map of day ${day.number}`} />
      <ol className="list plain-list daymap-stops">
        {day.stops.map((s, i) => {
          const leg = day.legs.find((l) => l.to === s.name && l.from === day.stops[i - 1]?.name)
          return (
            <li key={`${s.place_id}-${i}`}>
              {leg && (
                <p className="daymap-leg muted small">↓ {leg.km} km straight line · about {leg.road_km} km by road ·
                  {' '}{leg.drive_min} min driving{leg.road_km <= 3 ? `, ${leg.walk_min} min walking` : ''}</p>
              )}
              <p className="daymap-stop"><span className="trip-stop-n" aria-hidden="true">{i + 1}</span>
                <span className="grow"><span className="item-title">{s.name}</span>
                  <span className="item-meta">{[s.at && s.at.slice(0, 5), s.title !== s.name && s.title].filter(Boolean).join(' · ')}</span></span></p>
            </li>
          )
        })}
      </ol>
      {m.without_position > 0 && <p className="hint">{m.without_position} plan item{m.without_position === 1 ? ' has' : 's have'} no place with a position, so
        {m.without_position === 1 ? " it isn't" : " they aren't"} on the map.</p>}
      <p className="hint">{m.note}</p>
    </section>
  )
}
