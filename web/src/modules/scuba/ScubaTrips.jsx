import { useEffect, useState } from 'react'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { SuitcaseIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { hoursText, metres, plural } from './scubaFormat.js'
import { DiveRow, Numbers, useScubaTrips } from './scubaParts.jsx'

// Scuba's trips (a dive weekend, a liveaboard, a holiday of diving): the list and a trip's panel with its dives.

const dates = (t) => (t.end_on && t.end_on !== t.start_on ? `${shortDate(t.start_on)} - ${shortDate(t.end_on)}` : shortDate(t.start_on))

export function TripsView() {
  const { openPanel } = useApp()
  const trips = useScubaTrips()
  return (
    <section className="page scb">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('scubatrip', {})}>+ Add a trip</button>
      </div>
      {!trips ? <p className="muted loading">Loading...</p> : trips.length === 0 ? (
        <EmptyState Icon={SuitcaseIcon} title="No dive trips yet" action="+ Add a trip" onAction={() => openPanel('scubatrip', {})}>
          Group the dives of a weekend away or a liveaboard under one trip, and see its totals.</EmptyState>
      ) : (
        <section className="card home-card">
          <ul className="list plain-list">
            {trips.map((t) => (
              <li key={t.trip_id}>
                <button type="button" className="row-button" onClick={() => openPanel('scubatrip', { id: t.trip_id })}>
                  <span className="stat-icon teal" aria-hidden="true"><SuitcaseIcon size={18} /></span>
                  <span className="grow">
                    <span className="item-title">{t.name}</span>
                    <span className="item-meta">{[dates(t), t.place, t.operator].filter(Boolean).map((x) => <span key={x}>{x}</span>)}</span>
                  </span>
                  <span className="scb-dive-figures">
                    <strong>{plural(t.dives, 'dive')}</strong>
                    <span className="muted small">{t.dives ? `${hoursText(t.minutes)} · to ${metres(t.deepest)}` : 'no dives yet'}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}

const tripFields = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Osprey Reef liveaboard' },
  { name: 'start_on', label: 'From', type: 'date', required: true },
  { name: 'end_on', label: 'To', type: 'date' },
  { name: 'place', label: 'Where' },
  { name: 'operator', label: 'Operator', placeholder: 'the dive centre, boat or liveaboard' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

// id: a trip (null = a new one)
export function TripPanel({ id = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const [t, setT] = useState(null)
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(id == null)
  const [confirm, setConfirm] = useState(false)
  useEffect(() => { if (id != null) api.scubaTrip(id).then(setT).catch((e) => setFailed(e.message)) }, [id])

  if (id != null && !t) return <Drawer title="Trip" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    return (
      <FormPanel title={t ? 'Edit trip' : 'Add a trip'} fields={tripFields} record={t} defaults={{ start_on: today() }} onClose={t ? () => setEditing(false) : onClose}
        onSave={async (data) => {
          const saved = t ? await api.updateScubaTrip(t.trip_id, data) : await api.addScubaTrip(data)
          changed()
          if (t) { setT(saved); setEditing(false) } else { onClose(); openPanel('scubatrip', { id: saved.trip_id }) }
        }} />
    )
  }

  const remove = async () => {
    try {
      await api.deleteScubaTrip(t.trip_id)
      changed()
      onClose()
    } catch (e) {
      showToast(e.message)
    }
  }
  const footer = confirm ? (
    <span className="confirm">Remove this trip? Its dives stay in your logbook.
      <button type="button" className="danger" onClick={remove}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="primary" onClick={() => { onClose(); openPanel('scubanewdive', { tripId: t.trip_id }) }}>Log a dive on it</button>
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Remove</button>
    </>
  )
  return (
    <Drawer title={t.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <p className="item-sub">{[dates(t), t.place, t.operator].filter(Boolean).join(' · ')}</p>
        <Numbers items={[
          { label: 'Dives', value: t.totals.dives },
          { label: 'Underwater', value: hoursText(t.totals.minutes) },
          t.totals.deepest != null && { label: 'Deepest', value: metres(t.totals.deepest) },
          { label: 'Sites', value: t.totals.sites },
        ]} />
        {t.notes && <p className="small scb-notes">{t.notes}</p>}
      </section>
      <section className="panel-section">
        <h3 className="section-title">Dives</h3>
        {t.dive_list.length === 0 ? <p className="muted small">None logged on this trip yet.</p> : (
          <ul className="list plain-list">{t.dive_list.map((d) => <DiveRow key={d.dive_id} d={d} before={onClose} />)}</ul>
        )}
      </section>
    </Drawer>
  )
}
