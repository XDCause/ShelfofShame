import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { RowPhoto } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { MODULES } from '../index.js'
import { Stars } from '../reading/readingParts.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { JournalTab, PlacesTab } from './TripMemories.jsx'
import { BookingsTab, MoneyTab, PackingTab, PlanTab } from './TripSections.jsx'
import { codeFor, COUNTRIES, countryName, dates, flag, PHASE_NAME, PHASE_TONE, useTravelLists, when } from './travelParts.jsx'

// A trip: when and where, what needs doing, the weather there (while it's on), then its parts as tabs - the day
// plan, bookings, money, packing, places (its stops and route) and the journal with photos. New trips start here
// too; "Edit details" changes the dates, budget, countries, rating and what you'll remember.

const TABS = [['plan', 'Plan'], ['bookings', 'Bookings'], ['money', 'Money'], ['packing', 'Packing'], ['places', 'Places'], ['journal', 'Journal']]
const firstTab = (t) => (t.phase === 'past' ? 'journal' : t.phase === 'idea' ? 'places' : 'plan')

const tripFields = (lists, past) => [
  { name: 'name', label: 'Name', required: true, placeholder: 'e.g. Japan 2026, Noosa long weekend', wide: true },
  { name: 'kind', label: 'Kind', type: 'select', options: lists.kinds, required: true },
  { name: 'status', label: 'Status', type: 'select', required: true, options: [['Planned', 'Going (or been)'], ['Idea', 'Just an idea'], ['Cancelled', 'Cancelled']] },
  { name: 'start_date', label: 'From', type: 'date' },
  { name: 'end_date', label: 'To', type: 'date' },
  { name: 'destination', label: 'Where', placeholder: 'e.g. Tokyo, Kyoto, Osaka' },
  { name: 'countries', label: 'Countries', placeholder: 'e.g. Japan, South Korea', list: 'travel-country-names',
    hint: 'Names or codes, with commas. Overseas trips get a passport check.' },
  { name: 'hobby', label: 'For a hobby?', type: 'select', options: lists.hobbies.map((h) => [h, MODULES.find((m) => m.id === h)?.name ?? h]),
    hint: 'A hiking trip, a shooting comp, a volleyball tournament - its gear can go on the packing list' },
  { name: 'budget', label: 'Budget (AUD)', type: 'money' },
  ...(past ? [
    { name: 'rating', label: 'How was it?', type: 'select', options: [['5', '★★★★★'], ['4', '★★★★'], ['3', '★★★'], ['2', '★★'], ['1', '★']] },
    { name: 'highlights', label: 'What you\'ll remember', type: 'textarea' }] : []),
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

function TripForm({ t, onClose, onSaved }) {
  const { changed, openPanel } = useApp()
  const lists = useTravelLists()
  if (!lists) return <Drawer title="Trip" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const record = t && { ...t, countries: (t.countries ?? []).map(countryName).join(', '), rating: t.rating ?? '' }
  return (
    <FormPanel title={t ? 'Trip details' : 'Plan a trip'} fields={tripFields(lists, t?.phase === 'past')} record={record}
      defaults={{ kind: 'Domestic', status: 'Planned' }} onClose={onClose} saveLabel={t ? 'Save' : 'Plan it'}
      before={<datalist id="travel-country-names">{COUNTRIES.map((c) => <option key={c.code} value={c.name} />)}</datalist>}
      onSave={async (data) => {
        const words = (data.countries ?? '').split(',').map((w) => w.trim()).filter(Boolean)
        const unknown = words.filter((w) => !codeFor(w))
        if (unknown.length) throw new Error(`Which country is "${unknown[0]}"? Use its name (Japan) or code (JP).`)
        const body = { ...data, countries: words.map(codeFor), rating: data.rating == null ? null : Number(data.rating) }
        if (!t) {
          const made = await api.addTrip(Object.fromEntries(Object.entries(body).filter(([, v]) => v != null)))
          changed()
          onClose()
          openPanel('trip', { id: made.trip_id })
          return
        }
        onSaved(await api.updateTrip(t.trip_id, body))
        changed()
      }}
      onDelete={t && (async () => { await api.deleteTrip(t.trip_id); changed(); onClose() })}
      deleteLabel="Delete trip" />
  )
}

export default function TripPanel({ id = null, tab: askedTab = null, onClose }) {
  const { changed, showToast } = useApp()
  const [t, setT] = useState(null)
  const [editing, setEditing] = useState(false)
  const [tab, setTab] = useState(askedTab)
  const [failed, setFailed] = useState('')       // it couldn't be loaded (removed since?): said in the panel
  const reload = useCallback(() => api.trip(id).then(setT).catch((e) => { setFailed(e.message); showToast(e.message) }), [id, showToast])
  useEffect(() => { if (id != null) reload() }, [id, reload])

  if (id == null) return <TripForm onClose={onClose} />
  if (!t) return <Drawer title="Trip" onClose={onClose}>{failed ? <p className="alert error">{failed}</p>
    : <p className="muted">Loading...</p>}</Drawer>
  if (editing) return <TripForm t={t} onClose={() => setEditing(false)} onSaved={(next) => { setT(next); setEditing(false) }} />

  const update = (next) => { setT(next); changed() }
  const shown = tab ?? firstTab(t)
  const hobby = t.hobby && MODULES.find((m) => m.id === t.hobby)
  const footer = (
    <>
      <span className="spacer" />
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>
    </>
  )
  return (
    <Drawer title={t.name} onClose={onClose} footer={footer} wide>
      {t.photo_url && <img className="trip-cover" src={t.photo_url} alt="" />}
      <section className="panel-section">
        <div className="section-head">
          <strong>{dates(t)}</strong>
          <span className={`pill ${PHASE_TONE[t.phase]}`}>{t.phase === 'past' ? PHASE_NAME.past : when(t)}</span>
          <span className="pill">{t.kind}</span>
          {hobby && <span className="pill teal">{hobby.name}</span>}
        </div>
        {(t.destination || t.countries.length > 0) && (
          <p className="item-sub">{[t.destination, t.countries.map((c) => `${flag(c)} ${countryName(c)}`).join(', ')].filter(Boolean).join(' · ')}</p>
        )}
        {t.rating && <p className="trip-rating"><Stars value={t.rating} size="small" /></p>}
        {t.highlights && <p className="small trip-highlights">{t.highlights}</p>}
        {t.notes && <p className="small muted">{t.notes}</p>}
        {t.warnings.length > 0 && (
          <ul className="trip-warnings" aria-label="Needs doing">{t.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        )}
        {t.weather && (
          <div className="trip-weather" role="group" aria-label={`Weather in ${t.weather.place}`}>
            <span className="muted small">{t.weather.place}</span>
            {t.weather.days.map((d, i) => (
              <span key={d.day} className="trip-weather-day" title={d.sky ?? ''}>
                <span className="small">{i === 0 ? 'Today' : new Date(`${d.day}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short' })}</span>
                <span aria-hidden="true">{d.icon}</span>
                <span className="small">{d.max != null ? `${Math.round(d.max)}°` : ''}{d.min != null ? <span className="muted"> {Math.round(d.min)}°</span> : null}</span>
              </span>
            ))}
            <span className="hint">Open-Meteo</span>
          </div>
        )}
      </section>
      <div className="segmented trip-tabs" role="tablist" aria-label="Trip">
        {TABS.map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={shown === k} onClick={() => setTab(k)}>
            {label}{k === 'packing' && t.packing_count > 0 ? ` ${t.packed_count}/${t.packing_count}` : ''}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={TABS.find(([k]) => k === shown)[1]}>
        {shown === 'plan' && <PlanTab t={t} onTrip={update} />}
        {shown === 'bookings' && <BookingsTab t={t} onClose={onClose} />}
        {shown === 'money' && <MoneyTab t={t} onTrip={update} />}
        {shown === 'packing' && <PackingTab t={t} onTrip={update} />}
        {shown === 'places' && <PlacesTab t={t} onClose={onClose} onTrip={update} />}
        {shown === 'journal' && <JournalTab t={t} onTrip={update} />}
      </div>
      <section className="panel-section">
        <h3 className="section-title">Cover photo</h3>
        <RowPhoto path={`/travel/trips/${t.trip_id}`} url={t.has_cover ? t.photo_url : null} label="cover photo"
          onChanged={() => { reload(); changed() }} />
      </section>
      <JournalMentions kind="trip" id={t.trip_id} name={t.name} onLeave={onClose} />
    </Drawer>
  )
}
