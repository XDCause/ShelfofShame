import { useCallback, useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { ENTRIES, SITE_KINDS, metres, num, plural } from './scubaFormat.js'
import { DiveRow, Numbers, useScubaSettings, useScubaSites } from './scubaParts.jsx'

// Scuba's dive sites: the list (with "Find dive sites near..." from OpenStreetMap) and a site's panel.

// A map link for a site with a position (OpenStreetMap, opens in a new tab).
export const mapUrl = (s) => `https://www.openstreetmap.org/?mlat=${s.lat}&mlon=${s.lon}#map=14/${s.lat}/${s.lon}`
const depthRange = (s) => (s.depth_min != null && s.depth_max != null ? `${num(s.depth_min)}-${num(s.depth_max)} m`
  : s.depth_max != null ? `to ${num(s.depth_max)} m` : null)

export function SitesView() {
  const { openPanel } = useApp()
  const sites = useScubaSites()
  const [q, setQ] = useState('')
  const [finding, setFinding] = useState(false)
  const shown = (sites ?? []).filter((s) => !q.trim() || `${s.name} ${s.place ?? ''} ${s.kind ?? ''}`.toLowerCase().includes(q.trim().toLowerCase()))
  return (
    <section className="page scb">
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search sites..." aria-label="Search sites" className="scb-search" />
        <span className="grow" />
        <button type="button" className="secondary" aria-pressed={finding} onClick={() => setFinding((f) => !f)}>Find dive sites near...</button>
        <button type="button" className="primary" onClick={() => openPanel('scubasite', {})}>+ Add a site</button>
      </div>
      {finding && <FindSites onDone={() => setFinding(false)} />}
      {!sites ? <p className="muted loading">Loading...</p> : sites.length === 0 ? (
        <EmptyState Icon={TargetIcon} title="No dive sites yet" action="+ Add a site" onAction={() => openPanel('scubasite', {})}>
          Add the reefs, wrecks and walls you dive - by hand, or find them near you from OpenStreetMap - and see how often you have been to each.</EmptyState>
      ) : shown.length === 0 ? <p className="empty card">No site matches that.</p> : (
        <section className="card home-card">
          <p className="muted small scb-log-note">{plural(shown.length, 'site')}</p>
          <ul className="list plain-list">
            {shown.map((s) => (
              <li key={s.site_id} className="scb-site-row">
                <button type="button" className="row-button" onClick={() => openPanel('scubasite', { id: s.site_id })}>
                  <span className="stat-icon ok" aria-hidden="true"><TargetIcon size={18} /></span>
                  <span className="grow">
                    <span className="item-title">{s.name}</span>
                    <span className="item-meta">{[s.place, s.kind, depthRange(s), s.entry === 'boat' ? 'boat' : s.entry === 'shore' ? 'shore' : null]
                      .filter(Boolean).map((t) => <span key={t}>{t}</span>)}</span>
                  </span>
                  <span className="scb-dive-figures">
                    <strong>{plural(s.dives, 'dive')}</strong>
                    <span className="muted small">{s.last_on ? `last ${shortDate(s.last_on)}` : 'not dived yet'}</span>
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

// "Find dive sites near...": OpenStreetMap's dive sites (sport=scuba_diving) around your home, where you are or a
// site you have, one request when you press the button (api/app/scuba_tools.py). Add copies one into your sites.
function FindSites({ onDone }) {
  const { changed, openPanel } = useApp()
  const settings = useScubaSettings()
  const sites = useScubaSites()
  const [km, setKm] = useState('30')
  const [found, setFound] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const look = async (lat, lon) => {
    setBusy('look')
    setError('')
    try {
      const r = await api.scubaOsmNear({ lat: Number(lat).toFixed(5), lon: Number(lon).toFixed(5), km })
      setFound(Array.isArray(r) ? r : r.sites ?? r.places ?? [])
    } catch (e) {
      setError(e.message)
    }
    setBusy('')
  }
  const here = () => {
    if (!navigator.geolocation) { setError("This browser can't tell where you are: pick a site or your home instead."); return }
    setBusy('look')
    setError('')
    navigator.geolocation.getCurrentPosition((p) => look(p.coords.latitude, p.coords.longitude),
      () => { setBusy(''); setError("Couldn't get your location (allowed in the browser? on HTTPS?). Pick a site or your home instead.") },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 })
  }
  const add = async (osm) => {
    setBusy(osm)
    setError('')
    try {
      const s = await api.scubaOsmImport(osm)
      changed()
      setFound((f) => f.map((x) => (x.osm === osm ? { ...x, site_id: s.site_id } : x)))
      openPanel('scubasite', { id: s.site_id })
    } catch (e) {
      setError(e.message)
    }
    setBusy('')
  }
  const withPlace = (sites ?? []).filter((s) => s.lat != null && s.lon != null)
  const home = settings?.home_lat != null && settings?.home_lon != null
  return (
    <section className="card scb-find">
      <div className="section-head">
        <h2 className="home-card-title">Find dive sites near...</h2>
        <button type="button" className="plain small" onClick={onDone}>Close</button>
      </div>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="scb-find-row">
        <label className="field">Within (km)
          <input type="number" min="1" max="100" value={km} onChange={(e) => setKm(e.target.value)} /></label>
        <button type="button" className="secondary" onClick={here} disabled={!!busy}>Where I am</button>
        <button type="button" className="secondary" disabled={!home || !!busy} onClick={() => look(settings.home_lat, settings.home_lon)}
          title={home ? '' : 'Set your home position in the settings (Stats page)'}>My home</button>
        {withPlace.length > 0 && (
          <label className="field">A site I have
            <select value="" disabled={!!busy} onChange={(e) => { const s = withPlace.find((x) => String(x.site_id) === e.target.value); if (s) look(s.lat, s.lon) }}>
              <option value="">Pick...</option>
              {withPlace.map((s) => <option key={s.site_id} value={s.site_id}>{s.name}</option>)}
            </select></label>
        )}
      </div>
      {busy === 'look' && <p className="muted small">Looking...</p>}
      {found && (
        <>
          <p className="muted small">{found.length ? `${plural(found.length, 'site')} on OpenStreetMap` : 'Nothing mapped as a dive site there.'}
            {' '}Map data from OpenStreetMap contributors.</p>
          <ul className="list plain-list">
            {found.map((x) => (
              <li key={x.osm} className="scb-found-row">
                <span className="grow">
                  <span className="item-title">{x.name ?? 'Unnamed dive site'}</span>
                  <span className="item-meta">{[x.place, x.km != null && `${num(x.km)} km away`, x.kind].filter(Boolean).join(' · ')}</span>
                </span>
                {x.site_id ? <button type="button" className="plain small" onClick={() => openPanel('scubasite', { id: x.site_id })}>Already added</button>
                  : <button type="button" className="primary small" disabled={!!busy} onClick={() => add(x.osm)}>{busy === x.osm ? 'Adding...' : 'Add'}</button>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- a site

const siteFields = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Flinders Reef' },
  { name: 'place', label: 'Area', placeholder: 'e.g. Moreton Island' },
  { name: 'country', label: 'Country' },
  { name: 'kind', label: 'Kind', list: 'scuba-site-kinds' },
  { name: 'entry', label: 'Entry', type: 'select', options: ENTRIES },
  { name: 'depth_min', label: 'Shallowest (m)', type: 'number', step: 0.5 },
  { name: 'depth_max', label: 'Deepest (m)', type: 'number', step: 0.5 },
  { name: 'lat', label: 'Latitude', type: 'number', step: 'any', min: -90, hint: 'e.g. -27.0123' },
  { name: 'lon', label: 'Longitude', type: 'number', step: 'any', min: -180, hint: 'e.g. 153.4321' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

// id: a site (null = a new one)
export function SitePanel({ id = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const [s, setS] = useState(null)
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(id == null)
  const [confirm, setConfirm] = useState(false)
  const reload = useCallback(() => api.scubaSite(id).then(setS).catch((e) => setFailed(e.message)), [id])
  useEffect(() => { if (id != null) reload() }, [id, reload])

  if (id != null && !s) return <Drawer title="Site" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    return (
      <FormPanel title={s ? 'Edit site' : 'Add a site'} fields={siteFields} record={s} onClose={s ? () => setEditing(false) : onClose}
        onSave={async (data) => {
          const saved = s ? await api.updateScubaSite(s.site_id, data) : await api.addScubaSite(data)
          changed()
          if (s) { setS(saved); setEditing(false) } else { onClose(); openPanel('scubasite', { id: saved.site_id }) }
        }}>
        {() => <datalist id="scuba-site-kinds">{SITE_KINDS.map((k) => <option key={k} value={k} />)}</datalist>}
      </FormPanel>
    )
  }

  const remove = async () => {
    try {
      await api.deleteScubaSite(s.site_id)
      changed()
      onClose()
    } catch (e) {
      showToast(e.message)
    }
  }
  const footer = confirm ? (
    <span className="confirm">Remove this site? Its dives stay in your logbook.
      <button type="button" className="danger" onClick={remove}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="primary" onClick={() => { onClose(); openPanel('scubanewdive', { siteId: s.site_id }) }}>Log a dive here</button>
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Remove</button>
    </>
  )
  return (
    <Drawer title={s.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <p className="item-sub">{[s.place, s.country, s.kind, s.entry === 'boat' ? 'boat dive' : s.entry === 'shore' ? 'shore dive' : null].filter(Boolean).join(' · ') || 'No details yet'}</p>
        <Numbers items={[
          { label: 'Dives', value: s.dives },
          s.last_on && { label: 'Last dived', value: shortDate(s.last_on) },
          s.deepest != null && { label: 'Your deepest here', value: metres(s.deepest) },
          depthRange(s) && { label: 'Site depth', value: depthRange(s) },
          s.avg_temp != null && { label: 'Water, on average', value: `${num(s.avg_temp)}°C` },
          s.avg_vis != null && { label: 'Visibility, on average', value: `${num(s.avg_vis)} m` },
        ]} />
        {s.lat != null && s.lon != null ? (
          <p className="small"><a href={mapUrl(s)} target="_blank" rel="noreferrer">On the map ↗</a> <span className="muted">({num(s.lat, 4)}, {num(s.lon, 4)})</span></p>
        ) : <p className="muted small">No position yet: add the latitude and longitude (Edit) for a map link and the sea forecast.</p>}
        {s.notes && <p className="small scb-notes">{s.notes}</p>}
      </section>
      {s.species_seen.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Seen here</h3>
          <p className="scb-tags">{s.species_seen.map((x) => <span key={x.species} className="pill tint">{x.species}{x.dives > 1 ? ` ×${x.dives}` : ''}</span>)}</p>
        </section>
      )}
      <section className="panel-section">
        <h3 className="section-title">Dives here</h3>
        {s.recent_dives.length === 0 ? <p className="muted small">None logged yet.</p> : (
          <ul className="list plain-list">{s.recent_dives.map((d) => <DiveRow key={d.dive_id} d={d} before={onClose} />)}</ul>
        )}
      </section>
    </Drawer>
  )
}
