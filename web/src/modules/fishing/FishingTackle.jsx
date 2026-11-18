import { useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { FishIcon, RodIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { GearView } from '../volleyball/VolleyballViews.jsx'
import { LURE_KINDS, plural } from './fishFormat.js'
import { useFishingLures } from './fishingParts.jsx'

// Fishing's tackle: the tackle box (lures, soft plastics, baits and flies, with what each one has caught) and, below
// it, rods, reels and the rest on the shared gear pages (gear.hobby 'fishing').

const kindName = (k) => LURE_KINDS.find(([v]) => v === k)?.[1] ?? k

export function TackleView() {
  const { openPanel } = useApp()
  const [showRetired, setShowRetired] = useState(false)
  const lures = useFishingLures('')
  const [q, setQ] = useState('')
  const shown = (lures ?? []).filter((l) => (showRetired || !l.retired)
    && (!q.trim() || `${l.name} ${l.brand ?? ''} ${l.kind} ${l.colour ?? ''}`.toLowerCase().includes(q.trim().toLowerCase())))
  const retired = (lures ?? []).filter((l) => l.retired).length
  return (
    <section className="page fsh">
      <div className="toolbar">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the tackle box..." aria-label="Search the tackle box" className="fsh-search" />
        {retired > 0 && (
          <button type="button" className="chip-filter" aria-pressed={showRetired} onClick={() => setShowRetired((r) => !r)}>Show lost / used up ({retired})</button>
        )}
        <span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('fishinglure', {})}>+ Add a lure or bait</button>
      </div>
      <h2 className="section-title">Tackle box</h2>
      {!lures ? <p className="muted loading">Loading...</p> : lures.length === 0 ? (
        <EmptyState Icon={FishIcon} title="Your tackle box is empty" action="+ Add a lure or bait" onAction={() => openPanel('fishinglure', {})}>
          Add the lures, soft plastics and baits you use, then pick one for each fish: your stats show which ones work.</EmptyState>
      ) : shown.length === 0 ? <p className="empty card">Nothing matches that.</p> : (
        <section className="card home-card">
          <ul className="list plain-list">
            {shown.map((l) => (
              <li key={l.lure_id}>
                <button type="button" className="row-button" onClick={() => openPanel('fishinglure', { id: l.lure_id })}>
                  <span className="stat-icon ok" aria-hidden="true"><FishIcon size={18} /></span>
                  <span className="grow">
                    <span className="item-title">{l.name}{l.retired && <span className="pill tint fsh-open-pill">lost / used up</span>}</span>
                    <span className="item-meta">
                      {[kindName(l.kind), l.brand, l.colour, l.size, l.qty != null && `${l.qty} left`].filter(Boolean).map((x) => <span key={x}>{x}</span>)}
                    </span>
                    {l.species?.length > 0 && <span className="item-meta"><span>caught {l.species.join(', ')}</span></span>}
                  </span>
                  <span className="fsh-trip-figures">
                    <strong>{plural(l.catches, 'fish', 'fish')}</strong>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <h2 className="section-title">Rods, reels and other gear</h2>
      <GearView hobby="fishing" Icon={RodIcon} />
    </section>
  )
}

// ---------------------------------------------------------------- a lure or bait

const lureFields = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Zerek Prawn Shrimp 3.5" or Live yabby' },
  { name: 'kind', label: 'Kind', type: 'select', options: LURE_KINDS, required: true },
  { name: 'brand', label: 'Brand' },
  { name: 'colour', label: 'Colour' },
  { name: 'size', label: 'Size' },
  { name: 'qty', label: 'How many you have', type: 'number' },
  { name: 'retired', label: 'Status', type: 'select', required: true, options: [['false', 'In the box'], ['true', 'Lost or used up (kept for the stats)']] },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

// id: a lure or bait (null = a new one)
export function LurePanel({ id = null, onClose }) {
  const { changed, showToast } = useApp()
  const lures = useFishingLures('')
  if (!lures) return <Drawer title="Lure" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const l = id != null ? lures.find((x) => x.lure_id === id) : null
  if (id != null && !l) return <Drawer title="Lure" onClose={onClose}><p className="alert error">That lure is gone.</p></Drawer>
  return (
    <FormPanel title={l ? l.name : 'Add a lure or bait'} fields={lureFields} record={l && { ...l, retired: String(!!l.retired) }}
      defaults={{ kind: 'lure', retired: 'false' }} onClose={onClose}
      before={l && <p className="muted small">{plural(l.catches, 'fish', 'fish')} caught on it{l.species?.length ? `: ${l.species.join(', ')}` : ''}.</p>}
      onSave={async (data) => {
        const body = { ...data, retired: data.retired === 'true' }
        if (l) await api.updateFishingLure(l.lure_id, body)
        else await api.addFishingLure(body)
        changed()
        onClose()
        showToast('Saved')
      }}
      onDelete={l && (async () => { await api.deleteFishingLure(l.lure_id); changed(); onClose() })} />
  )
}
