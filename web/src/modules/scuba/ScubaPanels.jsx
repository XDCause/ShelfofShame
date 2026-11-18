import { useCallback, useEffect, useState } from 'react'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { DiveProfile } from './DiveProfile.jsx'
import { CURRENTS, ENTRIES, SUITS, TAG_IDEAS, diveName, gasName, metres, minutesText, num, stars, tagsFromText, timeText } from './scubaFormat.js'
import { Numbers, useScubaSites, useScubaTrips } from './scubaParts.jsx'

// Scuba's dive panels: one dive (its facts, the profile from the dive computer, what you saw, edit, remove, the
// previous and next) and logging a new one (filled in from your settings and your last dive).

// The form's fields, once (a new dive and editing one). Sites and trips are the pickers' [value, label] pairs.
function diveFields({ sites, trips, editing }) {
  return [
    { name: 'dived_on', label: 'Date', type: 'date', required: true },
    { name: 'time_in', label: 'Time in', type: 'time' },
    { name: 'site_id', label: 'Site', type: 'select', options: sites.map((s) => [String(s.site_id), s.name]), hint: 'Add sites on the Sites page.' },
    { name: 'trip_id', label: 'Trip', type: 'select', options: trips.map((t) => [String(t.trip_id), t.name]) },
    { name: 'max_depth', label: 'Max depth (m)', type: 'number', step: 0.1 },
    { name: 'avg_depth', label: 'Average depth (m)', type: 'number', step: 0.1, hint: 'Better air-use figures with it (else 60% of max).' },
    { name: 'minutes', label: 'Dive time (min)', type: 'number', min: 1 },
    { name: 'gas_o2', label: 'Oxygen in the gas (%)', type: 'number', min: 21, required: true, hint: '21 is air, 32 is EAN32.' },
    { name: 'tank_l', label: 'Tank (litres)', type: 'number', step: 0.5 },
    { name: 'start_bar', label: 'Start (bar)', type: 'number' },
    { name: 'end_bar', label: 'End (bar)', type: 'number' },
    { name: 'weight_kg', label: 'Weight (kg)', type: 'number', step: 0.5 },
    { name: 'suit', label: 'Suit', list: 'scuba-suits', placeholder: 'e.g. 5 mm wetsuit' },
    { name: 'water_temp', label: 'Water (°C)', type: 'number', step: 0.1, min: -3 },
    { name: 'air_temp', label: 'Air (°C)', type: 'number', step: 0.1, min: -30 },
    { name: 'visibility_m', label: 'Visibility (m)', type: 'number' },
    { name: 'current', label: 'Current', type: 'select', options: CURRENTS },
    { name: 'entry', label: 'Entry', type: 'select', options: ENTRIES },
    { name: 'buddy', label: 'Buddy' },
    { name: 'guide', label: 'Guide' },
    { name: 'operator', label: 'Dive operator', placeholder: 'the shop or boat' },
    { name: 'rating', label: 'Rating', type: 'select', options: [1, 2, 3, 4, 5].map((n) => [String(n), `${stars(n)} ${n}`]) },
    { name: 'tags', label: 'Tags', wide: true, list: 'scuba-tags', placeholder: 'night, wreck, drift', hint: 'Separate with commas.' },
    ...(editing ? [{ name: 'dive_no', label: 'Logbook number', type: 'number', min: 1 }] : []),
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
}

// What the form gives -> what the API takes: picker values are text, tags are a list.
function toDive(data) {
  const id = (v) => (v == null ? null : Number(v))
  return { ...data, site_id: id(data.site_id), trip_id: id(data.trip_id), rating: id(data.rating), tags: tagsFromText(data.tags) }
}

const Lists = () => (
  <>
    <datalist id="scuba-suits">{SUITS.map((s) => <option key={s} value={s} />)}</datalist>
    <datalist id="scuba-tags">{TAG_IDEAS.map((s) => <option key={s} value={s} />)}</datalist>
  </>
)

// ---------------------------------------------------------------- a new dive

// day: a calendar event's day (Log it); siteId / tripId: opened from a site or a trip.
export function NewDivePanel({ day = null, siteId = null, tripId = null, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const sites = useScubaSites()
  const trips = useScubaTrips()
  const [start, setStart] = useState(null)        // {settings, last}: the defaults, read once
  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        const [settings, list] = await Promise.all([api.scubaSettings(), api.scubaDives({})])
        const last = list[0] ? await api.scubaDive(list[0].dive_id) : null
        if (live) setStart({ settings, last })
      } catch {
        if (live) setStart({ settings: {}, last: null })
      }
    })()
    return () => { live = false }
  }, [])
  if (!sites || !trips || !start) return <Drawer title="Log a dive" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const { settings: st, last } = start
  const defaults = {
    dived_on: day ?? today(),
    site_id: siteId ?? last?.site_id, trip_id: tripId ?? last?.trip_id,
    gas_o2: last?.gas_o2 ?? st.gas_o2 ?? 21, tank_l: last?.tank_l ?? st.tank_l, start_bar: st.start_bar,
    weight_kg: last?.weight_kg, suit: last?.suit, buddy: last?.buddy, operator: last?.operator, entry: last?.entry,
  }
  return (
    <FormPanel title="Log a dive" fields={diveFields({ sites, trips, editing: false })} defaults={defaults} onClose={onClose} saveLabel="Save dive" wide
      onSave={async (data) => {
        const made = await api.addScubaDive(toDive(data))
        changed()
        onClose()
        openPanel('scubadive', { id: made.dive_id })
        showToast(`${diveName(made)} logged`)
      }}>
      {() => <Lists />}
    </FormPanel>
  )
}

// ---------------------------------------------------------------- a dive

export function DivePanel({ id, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const sites = useScubaSites()
  const trips = useScubaTrips()
  const [cur, setCur] = useState(id)              // the dive shown (previous / next move it)
  const [d, setD] = useState(null)
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState(false)
  useEffect(() => { api.scubaDive(cur).then(setD).catch((e) => setFailed(e.message)) }, [cur])

  if (!d || d.dive_id !== cur) return <Drawer title="Dive" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    if (!sites || !trips) return <Drawer title="Edit dive" onClose={() => setEditing(false)}><p className="muted">Loading...</p></Drawer>
    return (
      <FormPanel title={`Edit ${diveName(d).toLowerCase()}`} fields={diveFields({ sites, trips, editing: true })} record={{ ...d, tags: (d.tags ?? []).join(', ') }}
        onClose={() => setEditing(false)} wide
        onSave={async (data) => {
          setD(await api.updateScubaDive(d.dive_id, toDive(data)))
          setEditing(false)
          changed()
        }}>
        {() => <Lists />}
      </FormPanel>
    )
  }

  const remove = async () => {
    try {
      await api.deleteScubaDive(d.dive_id)
      changed()
      onClose()
    } catch (e) {
      showToast(e.message)
    }
  }
  const footer = confirm ? (
    <span className="confirm">Remove this dive from the logbook?
      <button type="button" className="danger" onClick={remove}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit</button>
      <button type="button" className="plain" disabled={d.prev_id == null} onClick={() => setCur(d.prev_id)}>← Older</button>
      <button type="button" className="plain" disabled={d.next_id == null} onClick={() => setCur(d.next_id)}>Newer →</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Remove</button>
    </>
  )
  const used = d.start_bar != null && d.end_bar != null ? d.start_bar - d.end_bar : null
  const people = [d.buddy && `with ${d.buddy}`, d.guide && `guide ${d.guide}`, d.operator].filter(Boolean)
  return (
    <Drawer title={`${diveName(d)}${d.site_name ? ` · ${d.site_name}` : ''}`} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="section-head">
          <strong>{shortDate(d.dived_on)}{d.time_in && ` · ${timeText(d.time_in)}`}</strong>
          {d.rating != null && <span className="scb-stars" role="img" aria-label={`${d.rating} stars`}>{stars(d.rating)}</span>}
        </div>
        {(people.length > 0 || d.trip_name) && <p className="item-sub">{[d.trip_name, ...people].filter(Boolean).join(' · ')}</p>}
        <Numbers items={[
          { label: 'Max depth', value: metres(d.max_depth) },
          d.avg_depth != null && { label: 'Average depth', value: metres(d.avg_depth) },
          { label: 'Dive time', value: minutesText(d.minutes) },
          { label: 'Gas', value: gasName(d.gas_o2) },
          used != null && { label: 'Air used', value: `${used} bar`, sub: `${d.start_bar} → ${d.end_bar}` },
          d.tank_l != null && { label: 'Tank', value: `${num(d.tank_l)} L` },
          d.sac != null && { label: 'Air use (SAC)', value: `${d.sac} L/min` },
          d.surface_interval_min != null && { label: 'Surface interval', value: minutesText(d.surface_interval_min) },
        ]} />
        <Numbers items={[
          d.water_temp != null && { label: 'Water', value: `${num(d.water_temp)}°C` },
          d.air_temp != null && { label: 'Air', value: `${num(d.air_temp)}°C` },
          d.visibility_m != null && { label: 'Visibility', value: `${d.visibility_m} m` },
          d.current && { label: 'Current', value: d.current[0].toUpperCase() + d.current.slice(1) },
          d.entry && { label: 'Entry', value: d.entry === 'boat' ? 'Boat' : 'Shore' },
          d.weight_kg != null && { label: 'Weight', value: `${num(d.weight_kg)} kg` },
          d.suit && { label: 'Suit', value: d.suit },
        ]} />
        {d.tags?.length > 0 && <p className="scb-tags">{d.tags.map((t) => <span key={t} className="pill tint">{t}</span>)}</p>}
        {d.computer && <p className="muted small">Imported from {d.computer}.</p>}
      </section>
      <DiveProfile diveId={d.dive_id} hasProfile={d.has_profile} />
      <section className="panel-section">
        <h3 className="section-title">What you saw</h3>
        <SightingsEditor key={`${d.dive_id}-${d.sightings.length}`} dive={d} onSaved={(list) => { setD({ ...d, sightings: list }); changed() }} />
      </section>
      {d.notes && (
        <section className="panel-section">
          <h3 className="section-title">Notes</h3>
          <p className="small scb-notes">{d.notes}</p>
        </section>
      )}
      {d.site_id != null && (
        <p className="muted small scb-more">
          <button type="button" className="link-plain" onClick={() => { onClose(); openPanel('scubasite', { id: d.site_id }) }}>{d.site_name}: the site →</button>
        </p>
      )}
    </Drawer>
  )
}

// What you saw on a dive: species, how many, a note - typed in place, saved together. The species box suggests the
// ones on your life list.
function SightingsEditor({ dive, onSaved }) {
  const { showToast } = useApp()
  const [rows, setRows] = useState(() => dive.sightings.map((s) => ({ species: s.species, how_many: s.how_many ?? '', notes: s.notes ?? '' })))
  const [known, setKnown] = useState([])
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  useEffect(() => { api.scubaSpecies().then(setKnown).catch(() => setKnown([])) }, [])
  const set = (i, k) => (e) => { setRows((r) => r.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x))); setDirty(true) }
  const add = () => { setRows((r) => [...r, { species: '', how_many: '', notes: '' }]); setDirty(true) }
  const drop = (i) => { setRows((r) => r.filter((_, j) => j !== i)); setDirty(true) }
  const save = useCallback(async () => {
    setBusy(true)
    try {
      const list = rows.filter((r) => r.species.trim()).map((r) => ({ species: r.species.trim(), how_many: r.how_many === '' ? null : Number(r.how_many), notes: r.notes.trim() || null }))
      onSaved(await api.saveScubaSightings(dive.dive_id, list))
      setDirty(false)
      showToast('Sightings saved')
    } catch (e) {
      showToast(e.message)
    }
    setBusy(false)
  }, [rows, dive.dive_id, onSaved, showToast])
  return (
    <>
      <datalist id="scuba-species">{known.map((k) => <option key={k.species} value={k.species} />)}</datalist>
      {rows.length === 0 && <p className="muted small">Nothing noted yet: turtles, rays, sharks, the small stuff.</p>}
      <ul className="scb-sightings">
        {rows.map((r, i) => (
          <li key={i}>
            <input value={r.species} onChange={set(i, 'species')} list="scuba-species" placeholder="Species" aria-label={`Species ${i + 1}`} />
            <input type="number" min="1" value={r.how_many} onChange={set(i, 'how_many')} placeholder="How many" aria-label={`How many ${i + 1}`} className="scb-count" />
            <input value={r.notes} onChange={set(i, 'notes')} placeholder="Note" aria-label={`Note ${i + 1}`} />
            <button type="button" className="plain small destructive" onClick={() => drop(i)} aria-label={`Remove sighting ${i + 1}`}>Remove</button>
          </li>
        ))}
      </ul>
      <div className="button-row">
        <button type="button" className="secondary" onClick={add}>+ Add a sighting</button>
        {dirty && <button type="button" className="primary" onClick={save} disabled={busy}>{busy ? 'Saving...' : 'Save sightings'}</button>}
      </div>
    </>
  )
}
