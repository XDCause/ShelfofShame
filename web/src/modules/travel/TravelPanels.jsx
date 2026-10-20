import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import TravelMap from './TravelMap.jsx'
import { COUNTRIES, countryName, flag, useTravelLists } from './travelParts.jsx'

// Travel's smaller panels: a booking, and a place (a trip's stop, or one for the bucket list). Opened from a trip,
// they go back to it (at its Bookings / Places) when you save, delete or cancel.

const PLACEHOLDER = { Flight: 'e.g. QF61 Brisbane to Tokyo', Stay: 'e.g. Hotel Gracery Shinjuku', 'Car hire': 'e.g. Hertz, a small SUV',
  Train: 'e.g. Shinkansen to Kyoto', Tour: 'e.g. Mt Fuji day trip', Campsite: 'e.g. Noosa North Shore', Insurance: 'e.g. Cover-More' }
const TIMES = { Stay: ['Check in', 'Check out'], Campsite: ['Check in', 'Check out'], 'Car hire': ['Pick up', 'Return'],
  Flight: ['Departs (local time)', 'Arrives (local time)'] }

export function BookingPanel({ id = null, tripId, kind: startKind = 'Flight', onClose }) {
  const { openPanel, changed } = useApp()
  const lists = useTravelLists()
  const [trip, setTrip] = useState(null)
  const [kind, setKind] = useState(startKind)
  const [error, setError] = useState('')
  useEffect(() => {
    api.trip(tripId).then((t) => { setTrip(t); const b = t.bookings.find((x) => x.booking_id === id); if (b) setKind(b.kind) })
      .catch((e) => setError(e.message))
  }, [tripId, id])
  const back = () => { onClose(); openPanel('trip', { id: tripId, tab: 'bookings' }) }
  const booking = trip?.bookings.find((b) => b.booking_id === id) ?? null
  // (a booking removed since the trip was opened: say so, rather than "Loading..." for ever)
  const problem = error || (trip && id != null && !booking ? "That booking isn't on this trip any more." : '')
  if (problem) return <Drawer title="Booking" onClose={back}><p className="alert error">{problem}</p></Drawer>
  if (!lists || !trip) return <Drawer title="Booking" onClose={back}><p className="muted">Loading...</p></Drawer>
  const [from, to] = TIMES[kind] ?? ['Starts', 'Ends']
  const lastCurrency = trip.bookings.at(-1)?.currency ?? trip.expenses[0]?.currency ?? 'AUD'
  const fields = [
    { name: 'kind', label: 'Kind', type: 'select', options: lists.booking_kinds, required: true },
    { name: 'title', label: 'What', required: true, placeholder: PLACEHOLDER[kind] ?? 'What is it?', wide: true },
    { name: 'starts_at', label: from, type: 'datetime-local' },
    { name: 'ends_at', label: to, type: 'datetime-local' },
    { name: 'from_place', label: 'From', placeholder: 'e.g. BNE' },
    { name: 'to_place', label: 'To', placeholder: 'e.g. NRT' },
    { name: 'address', label: 'Address / where', wide: true },
    { name: 'provider', label: 'Booked with', placeholder: 'e.g. Qantas, Booking.com' },
    { name: 'reference', label: 'Booking reference', placeholder: 'e.g. ABC123' },
    { name: 'cost', label: 'Cost', type: 'money' },
    { name: 'currency', label: 'Currency', type: 'select', options: lists.currencies, required: true },
    { name: 'rate', label: 'Rate (AUD for 1)', type: 'number', step: 'any', hint: 'Blank: today\'s rate (or yours for this trip). AUD is always 1.' },
    { name: 'paid', label: 'Paid?', type: 'select', options: [['false', 'Not yet'], ['true', 'Paid']], required: true },
    { name: 'link', label: 'Link', type: 'url', placeholder: 'https://...', wide: true },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  // Every field is always in the form (so changing the kind keeps what you've typed); ones that don't apply are hidden.
  const moving = ['Flight', 'Train', 'Bus', 'Ferry'].includes(kind)
  const hide = moving ? ['address'] : ['from_place', 'to_place']
  const record = booking && { ...booking, paid: String(booking.paid), rate: booking.currency === 'AUD' ? '' : booking.rate }
  return (
    <FormPanel hide={hide} title={booking ? booking.title : `Add a booking to ${trip.name}`} fields={fields} record={record}
      defaults={{ kind, currency: lastCurrency, paid: 'false' }}
      onField={(name, value) => { if (name === 'kind') setKind(value) }}
      onClose={back} saveLabel={booking ? 'Save' : 'Add booking'}
      onSave={async (data) => {
        const body = { ...data, paid: data.paid === 'true', rate: data.currency === 'AUD' ? null : data.rate }
        if (booking) await api.updateBooking(booking.booking_id, body)
        else await api.addBooking(tripId, Object.fromEntries(Object.entries(body).filter(([, v]) => v != null)))
        changed()
        back()
      }}
      onDelete={booking && (async () => { await api.deleteBooking(booking.booking_id); changed(); back() })} deleteLabel="Remove" />
  )
}

// A place: find a town by name (Open-Meteo's place search), or tap the map where it is.
export function PlacePanel({ id = null, tripId = null, onClose }) {
  const { openPanel, changed } = useApp()
  const lists = useTravelLists()
  const [place, setPlace] = useState(undefined)
  const [trip, setTrip] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const failed = (e) => setError(e.message)
    if (tripId != null) api.trip(tripId).then((t) => { setTrip(t); setPlace(t.places.find((p) => p.place_id === id) ?? null) }).catch(failed)
    else if (id != null) api.travelPlaces().then((all) => setPlace(all.find((p) => p.place_id === id) ?? null)).catch(failed)
    else setPlace(null)
  }, [id, tripId])
  const back = () => { onClose(); if (tripId != null) openPanel('trip', { id: tripId, tab: 'places' }) }
  // (a place removed since: say so - not an empty "new place" form that would add it again)
  const problem = error || (id != null && place === null ? "That place isn't there any more." : '')
  if (problem) return <Drawer title="Place" onClose={back}><p className="alert error">{problem}</p></Drawer>
  if (!lists || place === undefined || (tripId != null && !trip)) return <Drawer title="Place" onClose={back}><p className="muted">Loading...</p></Drawer>
  const fields = [
    { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Kyoto, Fushimi Inari, a great ramen place' },
    { name: 'kind', label: 'Kind', type: 'select', options: lists.place_kinds, required: true },
    { name: 'status', label: tripId ? 'Status' : 'Been or want to go?', type: 'select', required: true,
      options: [['Want', 'Want to go'], ['Planned', 'Going'], ['Been', 'Been']] },
    { name: 'country', label: 'Country', type: 'select', options: COUNTRIES.map((c) => [c.code, `${flag(c.code)} ${c.name}`]) },
    { name: 'region', label: 'Region / state' },
    { name: 'lat', label: 'Latitude', type: 'number', step: 'any', min: -90 },
    { name: 'lon', label: 'Longitude', type: 'number', step: 'any', min: -180 },
    ...(tripId ? [{ name: 'visit_on', label: 'Day there', type: 'date' }] : []),
    { name: 'rating', label: 'Rating', type: 'select', options: [['5', '★★★★★'], ['4', '★★★★'], ['3', '★★★'], ['2', '★★'], ['1', '★']] },
    { name: 'link', label: 'Link', type: 'url', placeholder: 'https://...', wide: true },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const defaults = { kind: 'City', status: trip ? (['past', 'now'].includes(trip.phase) ? 'Been' : 'Planned') : 'Want',
    country: trip?.countries?.length === 1 ? trip.countries[0] : '' }
  const asNumbers = (d) => ({ ...d, rating: d.rating == null ? null : Number(d.rating) })
  return (
    <FormPanel title={place ? place.name : trip ? `Add a place to ${trip.name}` : 'Add a place'} fields={fields} record={place} defaults={defaults}
      onClose={back} saveLabel={place ? 'Save' : 'Add place'} wide
      onSave={async (data) => {
        if (place) await api.updateTravelPlace(place.place_id, asNumbers(data))
        else await api.addTravelPlace(Object.fromEntries(Object.entries({ ...asNumbers(data), trip_id: tripId }).filter(([, v]) => v != null)))
        changed()
        back()
      }}
      onDelete={place && (async () => { await api.deleteTravelPlace(place.place_id); changed(); back() })} deleteLabel="Remove">
      {({ form, set }) => <WhereIsIt form={form} set={set} />}
    </FormPanel>
  )
}

function WhereIsIt({ form, set }) {
  const [q, setQ] = useState('')
  const [found, setFound] = useState(null)
  const [error, setError] = useState('')
  const value = (name, v) => set(name)({ target: { value: v == null ? '' : String(v) } })
  const search = async () => {
    if (q.trim().length < 2) return
    setError('')
    try {
      setFound(await api.findTravelPlace(q.trim()))
    } catch (e) {
      setError(e.message)
    }
  }
  const use = (p) => {
    if (!form.name.trim()) value('name', p.name)
    value('lat', p.lat)
    value('lon', p.lon)
    if (p.country) value('country', p.country)
    if (p.region && !form.region) value('region', p.region.split(', ')[0])
    setFound(null)
  }
  const picked = form.lat !== '' && form.lon !== '' ? { lat: Number(form.lat), lon: Number(form.lon) } : null
  return (
    <section className="panel-section travel-where">
      <h3 className="section-title">Where is it?</h3>
      <div className="travel-find">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a town or city..." aria-label="Find a town or city"
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); search() } }} />
        <button type="button" className="secondary" onClick={search} disabled={q.trim().length < 2}>Find</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
      {found && (found.length === 0 ? <p className="muted small">Nothing by that name - tap the map instead.</p> : (
        <ul className="list plain-list travel-found">{found.map((p) => (
          <li key={`${p.lat},${p.lon}`}><button type="button" className="row-button" onClick={() => use(p)}>
            <span className="grow"><span className="item-title">{flag(p.country)} {p.name}</span>
              <span className="item-meta">{p.region || countryName(p.country)}</span></span>
          </button></li>))}</ul>
      ))}
      <TravelMap picking picked={picked} places={[]} label="Tap where the place is"
        onPick={(p) => { value('lat', p.lat); value('lon', p.lon) }} />
      <p className="hint">Town and city search: Open-Meteo. For a sight or a restaurant, tap the map.</p>
    </section>
  )
}
