import { useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { FishIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { MONTHS, SPECIES_WATERS, checkedText, cm, hasRules, plural, ruleFacts } from './fishFormat.js'
import { useFishingSettings, useFishingSpecies } from './fishingParts.jsx'

// Fishing's species: the list with YOUR catch counts and biggest fish, and the rules editor. The app ships NO rules
// (they change - Queensland changed them in 2026 - and a wrong number could be a fine): type them from the official
// page, keep them checked, and a kept fish that breaks them is warned about (never blocked).

export function RulesNote({ url }) {
  return (
    <section className="card fsh-rules-note" aria-label="About the rules">
      <p className="small">
        <strong>The app ships no fishing rules.</strong> Size limits, possession limits and closed seasons change, and a wrong number could get you
        fined: type them from the official page for each fish you keep, and keep them checked. A kept fish that breaks the rules you typed gets a
        warning; it is never blocked, and the warning is only as good as what you typed.
      </p>
      <p className="small"><a className="button secondary" href={url} target="_blank" rel="noreferrer">Official fishing rules (Queensland) ↗</a></p>
    </section>
  )
}

export function SpeciesView() {
  const { openPanel } = useApp()
  const rows = useFishingSpecies()
  const settings = useFishingSettings()
  const [q, setQ] = useState('')
  const [only, setOnly] = useState('')               // '' every species, 'caught', 'rules'
  const shown = (rows ?? []).filter((s) => (!q.trim() || `${s.name} ${s.sci_name ?? ''}`.toLowerCase().includes(q.trim().toLowerCase()))
    && (only === 'caught' ? s.caught > 0 : only === 'rules' ? hasRules(s) : true))
  const url = settings?.rules_url ?? 'https://www.qld.gov.au/recreation/activities/boating-fishing/rec-fishing/rules'
  return (
    <section className="page fsh">
      <RulesNote url={url} />
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search species..." aria-label="Search species" className="fsh-search" />
        <div className="chip-row" role="group" aria-label="Show">
          <button type="button" className="chip-filter" aria-pressed={only === ''} onClick={() => setOnly('')}>All</button>
          <button type="button" className="chip-filter" aria-pressed={only === 'caught'} onClick={() => setOnly('caught')}>Caught</button>
          <button type="button" className="chip-filter" aria-pressed={only === 'rules'} onClick={() => setOnly('rules')}>With rules</button>
        </div>
        <span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('fishingspecies', {})}>+ Add a species</button>
      </div>
      {!rows ? <p className="muted loading">Loading...</p> : rows.length === 0 ? (
        <EmptyState Icon={FishIcon} title="No species" action="+ Add a species" onAction={() => openPanel('fishingspecies', {})}>
          The list starts with the common South-East Queensland fish. Add your own, and type the rules for the ones you keep.</EmptyState>
      ) : shown.length === 0 ? <p className="empty card">Nothing matches that.</p> : (
        <section className="card home-card">
          <p className="muted small fsh-log-note">{plural(shown.length, 'species', 'species')}</p>
          <ul className="list plain-list">
            {shown.map((s) => {
              const facts = ruleFacts(s)
              return (
                <li key={s.species_id}>
                  <button type="button" className="row-button" onClick={() => openPanel('fishingspecies', { id: s.species_id })}>
                    <span className="stat-icon teal" aria-hidden="true"><FishIcon size={18} /></span>
                    <span className="grow">
                      <span className="item-title">{s.name}</span>
                      <span className="item-meta">
                        {s.sci_name && <span className="fsh-sci">{s.sci_name}</span>}
                        {facts.length > 0 ? <span>{facts.join(' · ')} ({checkedText(s.rules_checked_on, shortDate)})</span> : <span>no rules typed yet</span>}
                      </span>
                    </span>
                    <span className="fsh-trip-figures">
                      <strong>{s.caught ? plural(s.caught, 'catch', 'catches') : 'Not caught'}</strong>
                      <span className="muted small">{s.best_cm != null ? `best ${cm(s.best_cm)}` : s.last_on ? `last ${shortDate(s.last_on)}` : ''}</span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      )}
      <p className="muted small"><Link to="/fishing/stats#fishing-settings">Change the official rules link in your settings</Link></p>
    </section>
  )
}

// ---------------------------------------------------------------- one species' rules

const mmdd = (m, d) => (m && d ? `${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}` : null)
const MONTH_OPTIONS = MONTHS.map((m, i) => [String(i + 1), m])

const speciesFields = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Dusky flathead' },
  { name: 'sci_name', label: 'Scientific name' },
  { name: 'water', label: 'Water', type: 'select', options: SPECIES_WATERS },
  { name: 'min_cm', label: 'Minimum size (cm)', type: 'number', step: 0.5, hint: 'As you read it on the official page.' },
  { name: 'max_cm', label: 'Maximum size (cm)', type: 'number', step: 0.5 },
  { name: 'bag', label: 'Possession limit (per person)', type: 'number' },
  { name: 'no_take', label: 'Take', type: 'select', required: true, options: [['false', 'Allowed (within the rules)'], ['true', 'No take: release it']] },
  { name: 'from_m', label: 'Closed season from: month', type: 'select', options: MONTH_OPTIONS },
  { name: 'from_d', label: 'day', type: 'number', min: 1 },
  { name: 'to_m', label: 'Closed season to: month', type: 'select', options: MONTH_OPTIONS, hint: 'A season may run over New Year (Nov to Feb).' },
  { name: 'to_d', label: 'day', type: 'number', min: 1 },
  { name: 'rules_checked_on', label: 'Rules checked on', type: 'date', hint: 'When you last read them on the official page.' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

const split = (md) => (md ? md.split('-').map((x) => String(Number(x))) : ['', ''])

// What the form gives -> what the API takes (the closed season's four boxes make 'MM-DD' twice; no_take is a yes / no).
function toSpecies(d) {
  const { from_m: fm, from_d: fd, to_m: tm, to_d: td, ...rest } = d
  const closed_from = mmdd(fm, fd)
  const closed_to = mmdd(tm, td)
  if ((closed_from == null) !== (closed_to == null)) throw new Error('Give both ends of the closed season, or neither.')
  return { ...rest, closed_from, closed_to, no_take: d.no_take === 'true' }
}

// id: a species (null = a new one)
export function SpeciesPanel({ id = null, onClose }) {
  const { changed, showToast } = useApp()
  const rows = useFishingSpecies()
  const settings = useFishingSettings()
  if (!rows || !settings) return <Drawer title="Species" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const s = id != null ? rows.find((x) => x.species_id === id) : null
  if (id != null && !s) return <Drawer title="Species" onClose={onClose}><p className="alert error">That species is gone.</p></Drawer>
  const [fm, fd] = split(s?.closed_from)
  const [tm, td] = split(s?.closed_to)
  const record = s && { ...s, no_take: String(!!s.no_take), from_m: fm, from_d: fd, to_m: tm, to_d: td }
  return (
    <FormPanel title={s ? s.name : 'Add a species'} fields={speciesFields} record={record} defaults={{ no_take: 'false', rules_checked_on: today() }}
      onClose={onClose} saveLabel="Save"
      before={(
        <section className="panel-section">
          <p className="small"><strong>Type the rules from the official page.</strong> The app ships none. A kept fish that breaks what you type here gets a
            warning on its trip.</p>
          <p className="small"><a href={settings.rules_url} target="_blank" rel="noreferrer">Open the official rules ↗</a></p>
          {s && <p className="muted small">{plural(s.caught, 'catch', 'catches')} logged{s.kept ? `, ${s.kept} kept` : ''}{s.best_cm != null ? `, best ${cm(s.best_cm)}` : ''}.</p>}
        </section>
      )}
      onSave={async (data) => {
        const body = toSpecies(data)
        if (s) await api.updateFishingSpecies(s.species_id, body)
        else await api.addFishingSpecies(body)
        changed()
        onClose()
        showToast('Saved')
      }}
      onDelete={s && (async () => { await api.deleteFishingSpecies(s.species_id); changed(); onClose() })} />
  )
}
