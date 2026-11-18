import { useCallback, useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { SPOT_KINDS, WATERS, num, plural } from './fishFormat.js'
import { Numbers, TripRow, useFishingSettings, useFishingSpots } from './fishingParts.jsx'

// Fishing's spots: the list (with "Find boat ramps / fishing spots near..." from OpenStreetMap) and a spot's panel.

// A map link for a spot with a position (OpenStreetMap, opens in a new tab).
export const mapUrl = (s) => `https://www.openstreetmap.org/?mlat=${s.lat}&mlon=${s.lon}#map=15/${s.lat}/${s.lon}`
const waterName = (w) => WATERS.find(([k]) => k === w)?.[1]

export function SpotsView() {
  const { openPanel } = useApp()
  const spots = useFishingSpots()
  const [q, setQ] = useState('')
  const [finding, setFinding] = useState(false)
  const shown = (spots ?? []).filter((s) => !q.trim() || `${s.name} ${s.place ?? ''} ${s.kind ?? ''}`.toLowerCase().includes(q.trim().toLowerCase()))
  return (
    <section className="page fsh">
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search spots..." aria-label="Search spots" className="fsh-search" />
        <span className="grow" />
        <button type="button" className="secondary" aria-pressed={finding} onClick={() => setFinding((f) => !f)}>Find boat ramps and spots near...</button>
        <button type="button" className="primary" onClick={() => openPanel('fishingspot', {})}>+ Add a spot</button>
      </div>
      {finding && <FindSpots onDone={() => setFinding(false)} />}
      {!spots ? <p className="muted loading">Loading...</p> : spots.length === 0 ? (
        <EmptyState Icon={TargetIcon} title="No spots yet" action="+ Add a spot" onAction={() => openPanel('fishingspot', {})}>
          Add the beaches, jetties, creeks and dams you fish - by hand, or find boat ramps and fishing spots near you from OpenStreetMap - and see
          which gives you the most fish an hour.</EmptyState>
      ) : shown.length === 0 ? <p className="empty card">No spot matches that.</p> : (
        <section className="card home-card">
          <p className="muted small fsh-log-note">{plural(shown.length, 'spot')}</p>
          <ul className="list plain-list">
            {shown.map((s) => (
              <li key={s.spot_id} className="fsh-spot-row">
                <button type="button" className="row-button" onClick={() => openPanel('fishingspot', { id: s.spot_id })}>
                  <span className="stat-icon ok" aria-hidden="true"><TargetIcon size={18} /></span>
                  <span className="grow">
                    <span className="item-title">{s.name}</span>
                    <span className="item-meta">{[s.place, s.kind, waterName(s.water), s.sip_needed && 'permit needed'].filter(Boolean).map((t) => <span key={t}>{t}</span>)}</span>
                  </span>
                  <span className="fsh-trip-figures">
                    <strong>{plural(s.trips, 'trip')}</strong>
                    <span className="muted small">{s.fish_per_hour != null ? `${num(s.fish_per_hour, 2)} fish an hour` : s.last_on ? `last ${shortDate(s.last_on)}` : 'not fished yet'}</span>
                  </span>
                </button>
                {s.lat != null && s.lon != null && (
                  <a className="button plain small" href={mapUrl(s)} target="_blank" rel="noreferrer" aria-label={`${s.name} on the map`}>Map ↗</a>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}

// "Find boat ramps and spots near...": OpenStreetMap's boat ramps (leisure=slipway) or fishing spots (leisure=fishing)
// around your home, where you are or a spot you have: one request when you press the button (api/app/fishing_tools.py).
// Add copies one into your spots.
function FindSpots({ onDone }) {
  const { changed, openPanel } = useApp()
  const settings = useFishingSettings()
  const spots = useFishingSpots()
  const [what, setWhat] = useState('ramps')
  const [km, setKm] = useState('20')
  const [found, setFound] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const look = async (lat, lon) => {
    setBusy('look')
    setError('')
    try {
      const r = await api.fishingOsmNear({ lat: Number(lat).toFixed(5), lon: Number(lon).toFixed(5), km, what })
      setFound(Array.isArray(r) ? r : r.places ?? r.spots ?? [])
    } catch (e) {
      setError(e.message)
    }
    setBusy('')
  }
  const here = () => {
    if (!navigator.geolocation) { setError("This browser can't tell where you are: pick a spot or your home instead."); return }
    setBusy('look')
    setError('')
    navigator.geolocation.getCurrentPosition((p) => look(p.coords.latitude, p.coords.longitude),
      () => { setBusy(''); setError("Couldn't get your location (allowed in the browser? on HTTPS?). Pick a spot or your home instead.") },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 })
  }
  const add = async (osm) => {
    setBusy(osm)
    setError('')
    try {
      const s = await api.fishingOsmImport(osm)
      changed()
      setFound((f) => f.map((x) => (x.osm === osm ? { ...x, already: s.spot_id } : x)))
      openPanel('fishingspot', { id: s.spot_id })
    } catch (e) {
      setError(e.message)
    }
    setBusy('')
  }
  const withPlace = (spots ?? []).filter((s) => s.lat != null && s.lon != null)
  const home = settings?.home_lat != null && settings?.home_lon != null
  return (
    <section className="card fsh-find">
      <div className="section-head">
        <h2 className="home-card-title">Find boat ramps and spots near...</h2>
        <button type="button" className="plain small" onClick={onDone}>Close</button>
      </div>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="fsh-find-row">
        <label className="field">Look for
          <select value={what} onChange={(e) => { setWhat(e.target.value); setFound(null) }}>
            <option value="ramps">Boat ramps</option>
            <option value="spots">Fishing spots</option>
          </select></label>
        <label className="field">Within (km)
          <input type="number" min="1" max="100" value={km} onChange={(e) => setKm(e.target.value)} /></label>
        <button type="button" className="secondary" onClick={here} disabled={!!busy}>Where I am</button>
        <button type="button" className="secondary" disabled={!home || !!busy} onClick={() => look(settings.home_lat, settings.home_lon)}
          title={home ? '' : 'Set your home position on the Stats page'}>My home</button>
        {withPlace.length > 0 && (
          <label className="field">A spot I have
            <select value="" disabled={!!busy} onChange={(e) => { const s = withPlace.find((x) => String(x.spot_id) === e.target.value); if (s) look(s.lat, s.lon) }}>
              <option value="">Pick...</option>
              {withPlace.map((s) => <option key={s.spot_id} value={s.spot_id}>{s.name}</option>)}
            </select></label>
        )}
      </div>
      {busy === 'look' && <p className="muted small">Looking...</p>}
      {found && (
        <>
          <p className="muted small">{found.length ? `${plural(found.length, 'place')} on OpenStreetMap` : 'Nothing mapped there.'} Map data from OpenStreetMap contributors.</p>
          <ul className="list plain-list">
            {found.map((x) => (
              <li key={x.osm} className="fsh-found-row">
                <span className="grow">
                  <span className="item-title">{x.name ?? (what === 'ramps' ? 'Unnamed boat ramp' : 'Unnamed fishing spot')}</span>
                  <span className="item-meta">{[x.kind, x.km != null && `${num(x.km)} km away`].filter(Boolean).join(' · ')}</span>
                </span>
                {x.already ? <button type="button" className="plain small" onClick={() => openPanel('fishingspot', { id: x.already })}>Already added</button>
                  : <button type="button" className="primary small" disabled={!!busy} onClick={() => add(x.osm)}>{busy === x.osm ? 'Adding...' : 'Add'}</button>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- a spot

const spotFields = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Wellington Point jetty' },
  { name: 'place', label: 'Area', placeholder: 'e.g. Moreton Bay' },
  { name: 'water', label: 'Water', type: 'select', options: WATERS, hint: 'Salt and estuary spots get a tide forecast.' },
  { name: 'kind', label: 'Kind', list: 'fsh-spot-kinds' },
  { name: 'sip_needed', label: 'Stocked Impoundment Permit', type: 'select', options: [['true', 'Needed (a stocked dam)'], ['false', 'Not needed']], required: true },
  { name: 'lat', label: 'Latitude', type: 'number', step: 'any', min: -90, hint: 'e.g. -27.4698' },
  { name: 'lon', label: 'Longitude', type: 'number', step: 'any', min: -180, hint: 'e.g. 153.0251' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

// id: a spot (null = a new one)
export function SpotPanel({ id = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const [s, setS] = useState(null)
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(id == null)
  const [confirm, setConfirm] = useState(false)
  const reload = useCallback(() => api.fishingSpot(id).then(setS).catch((e) => setFailed(e.message)), [id])
  useEffect(() => { if (id != null) reload() }, [id, reload])

  if (id != null && !s) return <Drawer title="Spot" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    return (
      <FormPanel title={s ? 'Edit spot' : 'Add a spot'} fields={spotFields} record={s} defaults={{ sip_needed: 'false' }} onClose={s ? () => setEditing(false) : onClose}
        onSave={async (data) => {
          const body = { ...data, sip_needed: data.sip_needed === 'true' }
          const saved = s ? await api.updateFishingSpot(s.spot_id, body) : await api.addFishingSpot(body)
          changed()
          if (s) { setS(await api.fishingSpot(s.spot_id)); setEditing(false) } else { onClose(); openPanel('fishingspot', { id: saved.spot_id }) }
        }}>
        {() => <datalist id="fsh-spot-kinds">{SPOT_KINDS.map((k) => <option key={k} value={k} />)}</datalist>}
      </FormPanel>
    )
  }

  const remove = async () => {
    try {
      await api.deleteFishingSpot(s.spot_id)
      changed()
      onClose()
    } catch (e) {
      showToast(e.message)
    }
  }
  const footer = confirm ? (
    <span className="confirm">Remove this spot? Its trips stay in your log.
      <button type="button" className="danger" onClick={remove}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="primary" onClick={() => { onClose(); openPanel('fishingnewtrip', { spotId: s.spot_id }) }}>Log a trip here</button>
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Remove</button>
    </>
  )
  const trips = s.trip_list ?? []
  const caught = s.species_caught ?? []
  return (
    <Drawer title={s.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <p className="item-sub">{[s.place, s.kind, waterName(s.water), s.sip_needed && 'Stocked Impoundment Permit needed'].filter(Boolean).join(' · ') || 'No details yet'}</p>
        <Numbers items={[
          { label: 'Trips', value: s.trips },
          { label: 'Fish', value: s.catches },
          s.last_on && { label: 'Last fished', value: shortDate(s.last_on) },
          s.fish_per_hour != null && { label: 'Fish an hour', value: num(s.fish_per_hour, 2) },
        ]} />
        {s.lat != null && s.lon != null ? (
          <p className="small"><a href={mapUrl(s)} target="_blank" rel="noreferrer">On the map ↗</a> <span className="muted">({num(s.lat, 4)}, {num(s.lon, 4)})</span></p>
        ) : <p className="muted small">No position yet: add the latitude and longitude (Edit) for a map link, the forecast and the conditions saved with each trip.</p>}
        {s.notes && <p className="small fsh-notes">{s.notes}</p>}
      </section>
      {caught.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Caught here</h3>
          <p className="fsh-tags">{caught.map((x) => <span key={x.species} className="pill tint">{x.species}{x.catches > 1 ? ` ×${x.catches}` : ''}</span>)}</p>
        </section>
      )}
      <section className="panel-section">
        <h3 className="section-title">Trips here</h3>
        {trips.length === 0 ? <p className="muted small">None logged yet.</p> : (
          <ul className="list plain-list">{trips.map((t) => <TripRow key={t.trip_id} t={t} before={onClose} />)}</ul>
        )}
      </section>
    </Drawer>
  )
}
