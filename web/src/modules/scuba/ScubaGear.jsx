import { useCallback, useEffect, useState } from 'react'
import { api, money, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { DiveIcon, TrophyIcon } from '../../components/icons.jsx'
import RecordFields, { useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { SERVICE_IDEAS, dueText, plural } from './scubaFormat.js'

// Scuba's gear (the shared gear panel with hobby 'scuba', plus when each piece was serviced and is next due), the
// service log panel, and the certification cards.

// How soon a date is: overdue (red), within 60 days (amber), later (green).
const dueTone = (due) => {
  const now = today()
  if (due < now) return 'out'
  return (new Date(`${due}T12:00:00`) - new Date(`${now}T12:00:00`)) / 86400000 <= 60 ? 'low' : 'ok'
}

export function GearView() {
  const { refreshKey, openPanel } = useApp()
  const [gear, setGear] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.scubaGear().then(setGear).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!gear) return <p className="muted loading">Loading...</p>
  const owned = gear.filter((g) => g.condition !== 'Wanted')
  const wanted = gear.filter((g) => g.condition === 'Wanted')
  const soon = owned.filter((g) => g.next_due && dueTone(g.next_due) !== 'ok' && g.condition !== 'Retired')
  const cards = (list) => (
    <ul className="list plain-list scb-gear-list">
      {list.map((g) => (
        <li key={g.gear_id}>
          <button type="button" className="row-button scb-gear-row" onClick={() => openPanel('scubaservice', { gearId: g.gear_id })}>
            <span className="scb-gear-photo" aria-hidden="true">
              {g.photo_url ? <img src={g.photo_url} alt="" loading="lazy" /> : <DiveIcon size={26} />}
            </span>
            <span className="grow">
              <span className="item-title">{g.name}</span>
              <span className="item-meta">{[g.kind, g.brand, g.size].filter(Boolean).map((x) => <span key={x}>{x}</span>)}</span>
              <span className="item-meta">
                <span>{g.last_service ? `${g.last_service.what}: ${shortDate(g.last_service.done_on)}` : g.condition === 'Wanted' ? 'Wanted' : 'Never serviced'}</span>
                {g.condition !== 'Wanted' && <span>{plural(g.dives_since_service, 'dive')} since</span>}
              </span>
            </span>
            {g.next_due && g.condition !== 'Retired' && <span className={`pill ${dueTone(g.next_due)}`}>{dueText(g.next_due)}</span>}
            {g.condition === 'Retired' && <span className="pill tint">Retired</span>}
          </button>
        </li>
      ))}
    </ul>
  )
  return (
    <section className="page scb">
      <div className="toolbar">
        <p className="summary grow"><strong>{owned.filter((g) => g.condition !== 'Retired').length}</strong> in use
          {soon.length > 0 && <span className="muted"> · {soon.length} to service</span>}
          {wanted.length > 0 && <span className="muted"> · {wanted.length} wanted</span>}</p>
        <button type="button" className="secondary" onClick={() => openPanel('gear', { wanted: true, hobby: 'scuba' })}>+ Want</button>
        <button type="button" className="primary" onClick={() => openPanel('gear', { hobby: 'scuba' })}>+ Add gear</button>
      </div>
      {gear.length === 0 ? (
        <EmptyState Icon={DiveIcon} title="No scuba gear yet" action="+ Add gear" onAction={() => openPanel('gear', { hobby: 'scuba' })}>
          Regulator, BCD, tanks, wetsuit, computer: with when each was last serviced and when the next service, tank inspection or hydro test is due.</EmptyState>
      ) : (
        <>
          {owned.length > 0 && <section className="card home-card">{cards(owned)}</section>}
          {wanted.length > 0 && (
            <>
              <h3 className="section-title gear-wanted-title">Wanted</h3>
              <section className="card home-card">{cards(wanted)}</section>
            </>
          )}
        </>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- a piece of gear's service log

const SERVICE_FIELDS = [
  { name: 'what', label: 'What was done', required: true, wide: true, list: 'scuba-service-ideas', placeholder: 'e.g. Annual service' },
  { name: 'done_on', label: 'Done on', type: 'date', required: true },
  { name: 'next_due', label: 'Next due', type: 'date', hint: 'Reminds you on the dashboard 60 days before.' },
  { name: 'done_by', label: 'Done by', placeholder: 'the dive shop or technician' },
  { name: 'cost', label: 'Cost', type: 'money' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

export function ServicePanel({ gearId, onClose }) {
  const { changed, showToast, openPanel, refreshKey } = useApp()
  const [gear, setGear] = useState(null)
  const [rows, setRows] = useState(null)
  const [failed, setFailed] = useState('')
  const [adding, setAdding] = useState(false)
  const reload = useCallback(() => {
    api.scubaGear().then((all) => setGear(all.find((g) => g.gear_id === gearId) ?? null)).catch((e) => setFailed(e.message))
    api.scubaGearService(gearId).then(setRows).catch((e) => setFailed(e.message))
  }, [gearId])
  useEffect(() => { reload() }, [reload, refreshKey])
  const remove = async (id) => {
    try {
      await api.deleteScubaService(id)
      changed()
      reload()
    } catch (e) {
      showToast(e.message)
    }
  }
  if (!rows || !gear) return <Drawer title="Service" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>
  const footer = (
    <>
      <button type="button" className="primary" onClick={() => setAdding(true)} disabled={adding}>+ Log a service</button>
      <button type="button" className="plain" onClick={() => { onClose(); openPanel('gear', { id: gear.gear_id }) }}>The gear's details</button>
    </>
  )
  return (
    <Drawer title={gear.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <p className="item-sub">{[gear.kind, gear.brand, gear.size].filter(Boolean).join(' · ')}</p>
        <p className="small">
          {gear.next_due ? <>Next service <span className={`pill ${dueTone(gear.next_due)}`}>{dueText(gear.next_due)}</span> ({shortDate(gear.next_due)}). </> : 'No next service date set. '}
          {plural(gear.dives_since_service, 'dive')} {gear.last_service ? 'since the last service' : 'logged in all'}.
        </p>
      </section>
      {adding && (
        <section className="panel-section">
          <h3 className="section-title">Log a service</h3>
          <ServiceForm gearId={gearId} onDone={(saved) => { setAdding(false); if (saved) { changed(); reload() } }} />
        </section>
      )}
      <section className="panel-section">
        <h3 className="section-title">Service log</h3>
        {rows.length === 0 ? <p className="muted small">Nothing logged yet. A regulator wants a service every year or so; a tank a visual inspection each year and a hydro test every few.</p> : (
          <ul className="list plain-list">
            {rows.map((s) => (
              <li key={s.service_id} className="scb-service-row">
                <span className="grow">
                  <span className="item-title">{s.what}</span>
                  <span className="item-meta">
                    <span>{shortDate(s.done_on)}</span>
                    {s.done_by && <span>{s.done_by}</span>}
                    {s.cost != null && <span>{money(s.cost)}</span>}
                    {s.next_due && <span>next {shortDate(s.next_due)}</span>}
                  </span>
                  {s.notes && <span className="small muted">{s.notes}</span>}
                </span>
                <button type="button" className="plain small destructive" onClick={() => remove(s.service_id)} aria-label={`Remove ${s.what} on ${shortDate(s.done_on)}`}>Remove</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Drawer>
  )
}

function ServiceForm({ gearId, onDone }) {
  const { form, set, payload } = useRecordForm(SERVICE_FIELDS, null, { done_on: today() })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.addScubaService(gearId, payload())
      onDone(true)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <datalist id="scuba-service-ideas">{SERVICE_IDEAS.map((s) => <option key={s} value={s} />)}</datalist>
      <RecordFields fields={SERVICE_FIELDS} form={form} set={set} />
      <div className="button-row">
        <button type="submit" className="primary" disabled={busy}>Save</button>
        <button type="button" className="plain" onClick={() => onDone(false)}>Cancel</button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------- certifications

const AGENCIES = ['PADI', 'SSI', 'NAUI', 'SDI', 'TDI', 'RAID', 'BSAC', 'CMAS', 'DAN']
const LEVELS = ['Open Water Diver', 'Advanced Open Water', 'Rescue Diver', 'Divemaster', 'Enriched Air (Nitrox)', 'Deep Diver', 'Wreck Diver',
  'Night Diver', 'Emergency First Response', 'DAN Oxygen Provider']

export function CertsView() {
  const { refreshKey, openPanel } = useApp()
  const [certs, setCerts] = useState(null)
  useEffect(() => { api.scubaCerts().then(setCerts).catch(() => setCerts([])) }, [refreshKey])
  return (
    <section className="page scb">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('scubacert', {})}>+ Add a card</button>
      </div>
      {!certs ? <p className="muted loading">Loading...</p> : certs.length === 0 ? (
        <EmptyState Icon={TrophyIcon} title="No certifications yet" action="+ Add a card" onAction={() => openPanel('scubacert', {})}>
          Your Open Water card, advanced and specialty courses, first aid and oxygen provider: with the date, the number and when a card expires.</EmptyState>
      ) : (
        <div className="scb-certs">
          {certs.map((c) => (
            <button key={c.cert_id} type="button" className="card scb-cert" onClick={() => openPanel('scubacert', { id: c.cert_id })}>
              <span className="scb-cert-agency">{c.agency}</span>
              <strong className="scb-cert-name">{c.name}</strong>
              <span className="muted small">{[c.certified_on && shortDate(c.certified_on), c.cert_no && `No. ${c.cert_no}`].filter(Boolean).join(' · ') || 'No date'}</span>
              {c.instructor && <span className="muted small">Instructor {c.instructor}</span>}
              {c.expires_on && <span className={`pill ${dueTone(c.expires_on)}`}>{c.expires_on < today() ? 'Expired' : 'Expires'} {shortDate(c.expires_on)}</span>}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

const certFields = [
  { name: 'agency', label: 'Agency', required: true, list: 'scuba-agencies', placeholder: 'PADI, SSI, NAUI...' },
  { name: 'name', label: 'Certification', required: true, list: 'scuba-levels', placeholder: 'e.g. Open Water Diver' },
  { name: 'certified_on', label: 'Certified on', type: 'date' },
  { name: 'cert_no', label: 'Card number' },
  { name: 'instructor', label: 'Instructor' },
  { name: 'expires_on', label: 'Expires on', type: 'date', hint: 'First aid and oxygen provider cards expire; dive cards do not.' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

// id: a card (null = a new one)
export function CertPanel({ id = null, onClose }) {
  const { changed } = useApp()
  const [c, setC] = useState(id == null ? false : null)
  useEffect(() => {
    if (id != null) api.scubaCerts().then((all) => setC(all.find((x) => x.cert_id === id) ?? false)).catch(() => setC(false))
  }, [id])
  if (c === null) return <Drawer title="Certification" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  if (c === false && id != null) return <Drawer title="Certification" onClose={onClose}><p className="alert error">That card is gone.</p></Drawer>
  return (
    <FormPanel title={c ? `${c.agency} ${c.name}` : 'Add a certification'} fields={certFields} record={c || null} onClose={onClose}
      onSave={async (data) => {
        if (c) await api.updateScubaCert(c.cert_id, data)
        else await api.addScubaCert(data)
        changed()
        onClose()
      }}
      onDelete={c ? async () => { await api.deleteScubaCert(c.cert_id); changed(); onClose() } : undefined}>
      {() => (
        <>
          <datalist id="scuba-agencies">{AGENCIES.map((a) => <option key={a} value={a} />)}</datalist>
          <datalist id="scuba-levels">{LEVELS.map((a) => <option key={a} value={a} />)}</datalist>
        </>
      )}
    </FormPanel>
  )
}
