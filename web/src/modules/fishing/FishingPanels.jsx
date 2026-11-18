import { useEffect, useState } from 'react'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { CatchPhotos } from './CatchPhotos.jsx'
import { FATES, METHODS, PLATFORMS, catchLine, checkedText, clockText, conditionFacts, dateOf, fateName, hoursText, num, platformName, ruleFacts, stars,
  timeOf, toIso, tripName } from './fishFormat.js'
import { CatchRow, Numbers, useFishingLures, useFishingSpecies, useFishingSpots } from './fishingParts.jsx'

// Fishing's panels: one trip (facts, the conditions saved with it, its catches, end / edit / remove, older and newer),
// a past trip's form, and one catch (edit, photos, the rules you typed for that species and what they say about it).

// ---------------------------------------------------------------- a trip's form

function tripFields(spots, ending) {
  return [
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'start_time', label: 'Started', type: 'time', required: true },
    { name: 'end_time', label: 'Finished', type: 'time', required: ending, hint: ending ? '' : 'Leave blank while you are still out.' },
    { name: 'spot_id', label: 'Spot', type: 'select', options: spots.map((s) => [String(s.spot_id), s.name]), hint: 'Add spots on the Spots page. A spot with a position saves the moon, tide and weather with the trip.' },
    { name: 'platform', label: 'Fished from', type: 'select', options: PLATFORMS },
    { name: 'target', label: 'Target', placeholder: 'e.g. flathead, bream' },
    { name: 'companions', label: 'With' },
    { name: 'rating', label: 'Rating', type: 'select', options: [1, 2, 3, 4, 5].map((n) => [String(n), `${stars(n)} ${n}`]) },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}

// What the form gives -> what the API takes: the date and times make the two timestamps (a finish before the start
// means it ran past midnight), picker values are text.
export function toTrip(d) {
  const started = toIso(d.date, d.start_time ?? '00:00')
  let ended = d.end_time ? toIso(d.date, d.end_time) : null
  if (ended && started && ended < started) ended = new Date(new Date(ended).getTime() + 86400000).toISOString()
  const id = (v) => (v == null ? null : Number(v))
  return { started_at: started, ended_at: ended, spot_id: id(d.spot_id), platform: d.platform, target: d.target, companions: d.companions,
    rating: id(d.rating), notes: d.notes }
}

// A trip row as the form's record.
const tripRecord = (t) => ({ ...t, date: dateOf(t.started_at), start_time: timeOf(t.started_at), end_time: timeOf(t.ended_at), spot_id: t.spot_id, rating: t.rating })

// ---------------------------------------------------------------- a past trip

// day: a calendar event's day; spotId: opened from a spot.
export function NewTripPanel({ day = null, spotId = null, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const spots = useFishingSpots()
  const [last, setLast] = useState(undefined)        // the last trip's spot and platform: the form starts from them
  useEffect(() => { api.fishingSummary().then((s) => setLast(s.last_trip ?? null)).catch(() => setLast(null)) }, [])
  if (!spots || last === undefined) return <Drawer title="Log a past trip" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const defaults = { date: day ?? today(), start_time: '06:00', end_time: '10:00', spot_id: spotId ?? last?.spot_id, platform: last?.platform }
  return (
    <FormPanel title="Log a past trip" fields={tripFields(spots, true)} defaults={defaults} onClose={onClose} saveLabel="Save trip"
      onSave={async (data) => {
        const made = await api.addFishingTrip(toTrip(data))
        changed()
        onClose()
        openPanel('fishingtrip', { id: made.trip_id })
        showToast('Trip saved: add the fish you caught')
      }} />
  )
}

// ---------------------------------------------------------------- a trip

export function TripPanel({ id, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const spots = useFishingSpots()
  const [cur, setCur] = useState(id)                  // the trip shown (older / newer move it)
  const [t, setT] = useState(null)
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState(false)
  useEffect(() => { api.fishingTrip(cur).then(setT).catch((e) => setFailed(e.message)) }, [cur])

  if (!t || t.trip_id !== cur) return <Drawer title="Trip" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    if (!spots) return <Drawer title="Edit trip" onClose={() => setEditing(false)}><p className="muted">Loading...</p></Drawer>
    return (
      <FormPanel title="Edit trip" fields={tripFields(spots, false)} record={tripRecord(t)} onClose={() => setEditing(false)}
        onSave={async (data) => {
          setT(await api.updateFishingTrip(t.trip_id, toTrip(data)))
          setEditing(false)
          changed()
        }} />
    )
  }

  const remove = async () => {
    try {
      await api.deleteFishingTrip(t.trip_id)
      changed()
      onClose()
    } catch (e) {
      showToast(e.message)
    }
  }
  const endNow = async () => {
    try {
      setT(await api.endFishingTrip(t.trip_id))
      changed()
    } catch (e) {
      showToast(e.message)
    }
  }
  const addCatch = () => { onClose(); openPanel('fishingcatch', { tripId: t.trip_id }) }
  const open = !t.ended_at
  const footer = confirm ? (
    <span className="confirm">Remove this trip and its {t.catches.length} fish?
      <button type="button" className="danger" onClick={remove}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="primary" onClick={addCatch}>+ Add a catch</button>
      {open && <button type="button" className="secondary" onClick={endNow}>End trip</button>}
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit</button>
      <button type="button" className="plain" disabled={t.prev_id == null} onClick={() => setCur(t.prev_id)}>← Older</button>
      <button type="button" className="plain" disabled={t.next_id == null} onClick={() => setCur(t.next_id)}>Newer →</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Remove</button>
    </>
  )
  const facts = conditionFacts(t.conditions)
  const kept = t.catches.filter((c) => c.fate === 'kept').length
  const people = [platformName(t.platform) && `from ${platformName(t.platform).toLowerCase()}`, t.target && `after ${t.target}`, t.companions && `with ${t.companions}`].filter(Boolean)
  return (
    <Drawer title={tripName(t)} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="section-head">
          <strong>{shortDate(t.started_at)} · {clockText(t.started_at)}{t.ended_at && ` to ${clockText(t.ended_at)}`}</strong>
          {t.rating != null && <span className="fsh-stars" role="img" aria-label={`${t.rating} stars`}>{stars(t.rating)}</span>}
        </div>
        {open && <p className="item-sub"><span className="pill low">on the water</span> End it when you are done.</p>}
        {people.length > 0 && <p className="item-sub">{people.join(' · ')}</p>}
        <Numbers items={[
          { label: 'Fish', value: t.catches.length, sub: kept ? `${kept} kept` : null },
          t.hours != null && { label: 'Time', value: hoursText(t.hours) },
          t.fish_per_hour != null && { label: 'Fish an hour', value: num(t.fish_per_hour, 2) },
        ]} />
        {t.notes && <p className="small fsh-notes">{t.notes}</p>}
      </section>
      {facts.length > 0 ? (
        <section className="panel-section">
          <h3 className="section-title">Conditions then</h3>
          <Numbers items={facts} />
          <p className="muted small">Saved with the trip from the solunar tables (an old angling theory) and Open-Meteo, so your stats can look for patterns.</p>
        </section>
      ) : (
        <p className="muted small">{t.spot_id == null ? 'Pick a spot with a position to save the moon, tide and weather with a trip.' : 'No conditions were saved for this trip.'}</p>
      )}
      <section className="panel-section">
        <h3 className="section-title">Catches</h3>
        {t.catches.length === 0 ? <p className="muted small">Nothing caught: a blank trip is a result too.</p> : (
          <ul className="list plain-list">
            {t.catches.map((c) => <CatchRow key={c.catch_id} c={c} onOpen={() => { onClose(); openPanel('fishingcatch', { id: c.catch_id, tripId: t.trip_id }) }} />)}
          </ul>
        )}
      </section>
      {t.spot_id != null && (
        <p className="muted small fsh-more">
          <button type="button" className="link-plain" onClick={() => { onClose(); openPanel('fishingspot', { id: t.spot_id }) }}>{t.spot_name}: the spot →</button>
        </p>
      )}
    </Drawer>
  )
}

// ---------------------------------------------------------------- a catch

function catchFields({ species, lures }) {
  return [
    { name: 'species_id', label: 'Species', type: 'select', options: species.map((s) => [String(s.species_id), s.name]), hint: 'Pick from the list, or type it below.' },
    { name: 'species', label: 'Or type the species', placeholder: 'when it is not on the list' },
    { name: 'length_cm', label: 'Length (cm)', type: 'number', step: 0.5 },
    { name: 'weight_kg', label: 'Weight (kg)', type: 'number', step: 0.01 },
    { name: 'fate', label: 'What happened', type: 'select', options: FATES, required: true },
    { name: 'lure_id', label: 'Lure or bait', type: 'select', options: lures.map((l) => [String(l.lure_id), l.name]) },
    { name: 'bait', label: 'Or type the bait', placeholder: 'e.g. live yabby' },
    { name: 'method', label: 'Method', list: 'fsh-methods', placeholder: 'e.g. Casting' },
    { name: 'depth_m', label: 'Depth (m)', type: 'number', step: 0.5 },
    { name: 'caught_time', label: 'Time caught', type: 'time' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}

// The rules you typed for the picked species, shown under the form's species box: what they say, and when you checked.
function RulesHint({ species, form, fmt }) {
  const sp = species.find((s) => String(s.species_id) === form.species_id)
  if (!sp) return null
  const facts = ruleFacts(sp)
  return (
    <p className="small fsh-rules-hint">
      {facts.length ? <>Your rules for {sp.name}: {facts.join(', ')} ({checkedText(sp.rules_checked_on, fmt)}).</> : <>You have typed no rules for {sp.name} yet (Species page).</>}
      {' '}Warnings never stop a catch from being saved.
    </p>
  )
}

// id + tripId: a catch (the trip's answer holds it); tripId alone: a new catch on that trip.
export function CatchPanel({ id = null, tripId = null, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const species = useFishingSpecies()
  const lures = useFishingLures('false')
  const [trip, setTrip] = useState(null)
  const [photos, setPhotos] = useState(null)
  const [failed, setFailed] = useState('')
  const [done, setDone] = useState(null)             // the answer with warnings: shown before going back to the trip
  useEffect(() => {
    if (tripId == null) { setFailed('Open a catch from its trip.'); return }
    api.fishingTrip(tripId).then(setTrip).catch((e) => setFailed(e.message))
  }, [tripId])

  const back = () => { onClose(); if (tripId != null) openPanel('fishingtrip', { id: tripId }) }
  const c = id != null ? trip?.catches.find((x) => x.catch_id === id) : null
  if (!trip || !species || !lures) return <Drawer title="Catch" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>
  if (id != null && !c) return <Drawer title="Catch" onClose={onClose}><p className="alert error">That catch is gone.</p></Drawer>

  if (done) {
    return (
      <Drawer title={catchLine(done)} onClose={back} footer={<button type="button" className="primary" onClick={back}>Back to the trip</button>}>
        <p>Saved: {catchLine(done)}, {fateName(done.fate).toLowerCase()}.</p>
        <ul className="fsh-warnings" aria-label="Rule warnings">
          {done.warnings.map((w) => <li key={w}><span className="pill low">check</span> <span>{w}</span></li>)}
        </ul>
        <p className="muted small">The rules are the ones you typed on the Species page. Check the official page before you keep a fish.</p>
      </Drawer>
    )
  }

  const day = dateOf(c?.caught_at ?? trip.started_at)
  const recent = (key) => [...trip.catches].reverse().find((x) => x[key] != null)?.[key]       // what the last fish was caught on, again
  const defaults = { fate: 'released', caught_time: trip.ended_at ? timeOf(trip.started_at) : timeOf(new Date().toISOString()), method: recent('method'),
    lure_id: recent('lure_id') }
  const record = c && { ...c, caught_time: timeOf(c.caught_at) }
  const toCatch = (d) => {
    const n = (v) => (v == null ? null : Number(v))
    const { caught_time: time, ...rest } = d
    return { ...rest, species_id: n(d.species_id), lure_id: n(d.lure_id), caught_at: time ? toIso(day, time) : null }
  }
  const finish = (answer) => {
    changed()
    if (answer.warnings?.length) setDone(answer)
    else { back(); showToast(c ? 'Saved' : `${catchLine(answer)} logged`) }
  }
  const fmt = shortDate
  return (
    <FormPanel title={c ? catchLine(c) : 'Add a catch'} fields={catchFields({ species, lures })} record={record} defaults={defaults} onClose={back} wide
      saveLabel={c ? 'Save' : 'Log the catch'}
      before={c && (
        <section className="panel-section">
          <CatchPhotos catchId={c.catch_id} photos={photos ?? c.photos ?? []} onChange={(next) => { setPhotos(next); changed() }} />
        </section>
      )}
      onSave={async (data) => finish(c ? await api.updateFishingCatch(c.catch_id, toCatch(data)) : await api.addFishingCatch(trip.trip_id, toCatch(data)))}
      onDelete={c && (async () => { await api.deleteFishingCatch(c.catch_id); changed(); back() })}>
      {({ form }) => (
        <>
          <datalist id="fsh-methods">{METHODS.map((m) => <option key={m} value={m} />)}</datalist>
          <RulesHint species={species} form={form} fmt={fmt} />
          {!c && <p className="muted small">On the water? Use Go fishing: it logs a fish in three taps, with your position, and works without signal.</p>}
        </>
      )}
    </FormPanel>
  )
}
