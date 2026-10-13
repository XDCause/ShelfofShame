import { useEffect, useState } from 'react'
import { api } from '../api.js'
import ColourMatches from './ColourMatches.jsx'

// Colours: find matches for any Tamiya paint, your mixes (recipes), and your own matches
// between paints (any brand).
export default function ColoursView({ refreshKey, onChanged, onOpenItem, onOpenModel }) {
  const [mixes, setMixes] = useState(null)
  const [groups, setGroups] = useState(null)
  const [error, setError] = useState('')

  const load = () => {
    api.listMixes().then(setMixes).catch((e) => setError(e.message))
    api.listColourGroups().then(setGroups).catch((e) => setError(e.message))
  }
  useEffect(load, [refreshKey])
  const changed = () => { load(); onChanged() }

  return (
    <section className="page colours">
      {error && <p className="alert error">{error}</p>}
      <FindMatch onOpenItem={onOpenItem} onChanged={onChanged} />

      <div className="section-head">
        <h2>Mixes</h2>
      </div>
      <p className="hint">Recipes like <span className="mono">XF-62 + XF-2 (3:1)</span>. Put one on a model's paint list and it
        counts as "have it" when you own every part.</p>
      {mixes && <EditableList items={mixes} idKey="mix_id" empty="No mixes yet."
        render={(m) => <MixCard mix={m} onOpenItem={onOpenItem} onOpenModel={onOpenModel} />}
        form={(m) => <MixForm mix={m} />}
        save={(m, body) => (m ? api.updateMix(m.mix_id, body) : api.addMix(body))}
        remove={(m) => api.deleteMix(m.mix_id)} addLabel="+ New mix" onChanged={changed} />}

      <div className="section-head">
        <h2>Your matches</h2>
      </div>
      <p className="hint">Paints you've found are the same colour, from any brand, e.g. from a kit's instructions or
        a conversion chart. They show up on each paint's page and on model paint lists.</p>
      {groups && <EditableList items={groups} idKey="group_id" empty="No matches yet."
        render={(g) => <GroupCard group={g} onOpenItem={onOpenItem} />}
        form={(g) => <GroupForm group={g} />}
        save={(g, body) => (g ? api.updateColourGroup(g.group_id, body) : api.addColourGroup(body))}
        remove={(g) => api.deleteColourGroup(g.group_id)} addLabel="+ New match" onChanged={changed} />}
    </section>
  )
}

// Search the Tamiya catalogue, pick a paint, see its matches.
function FindMatch({ onOpenItem, onChanged }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [picked, setPicked] = useState(null)

  useEffect(() => {
    if (!q.trim()) { setResults([]); return }
    let current = true
    const t = setTimeout(() => {
      api.searchCatalog(q.trim()).then((r) => current && setResults(r.filter((p) => p.genre === 'Paints'))).catch(() => {})
    }, 250)
    return () => { current = false; clearTimeout(t) }
  }, [q])

  return (
    <div className="card find-match">
      <h2>Find a match</h2>
      <input type="search" value={q} onChange={(e) => { setQ(e.target.value); setPicked(null) }}
        placeholder="A Tamiya paint: XF-62, LP-28, olive drab..." aria-label="Find a colour match" />
      {!picked && results.length > 0 && (
        <ul className="list compact pick-list">
          {results.slice(0, 12).map((p) => (
            <li key={p.product_code}>
              <button type="button" className="row-button" onClick={() => setPicked(p)}>
                <span className="grow">{p.name}<span className="muted small block">{p.product_code}</span></span>
                {p.owned_qty > 0 && <span className="tag ok">You have {p.owned_qty}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {picked && (
        <>
          <p className="small">Matches for <strong>{picked.name}</strong></p>
          <ColourMatches brandId={picked.brand_id} productCode={picked.product_code} name={picked.name}
            onOpenItem={onOpenItem} onChanged={onChanged} />
        </>
      )}
    </div>
  )
}

// A list where each card can be edited or deleted in place, with an "add" form at the end.
// `form(item)` returns form fields with `name` attributes; their values become the request body.
function EditableList({ items, idKey, empty, render, form, save, remove, addLabel, onChanged }) {
  const [editing, setEditing] = useState(null) // an item, or 'new'
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const body = Object.fromEntries(new FormData(e.currentTarget))
    try {
      await save(editing === 'new' ? null : editing, body)
      setEditing(null)
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }
  const del = async (item) => {
    try {
      await remove(item)
      setEditing(null)
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }
  const editor = (item) => (
    <form className="card inline-form" onSubmit={submit}>
      {form(item)}
      <div className="button-row wide">
        <button type="submit" className="primary">Save</button>
        <button type="button" className="plain" onClick={() => setEditing(null)}>Cancel</button>
        {item && <button type="button" className="plain destructive" onClick={() => del(item)}>Delete</button>}
      </div>
      {error && <p className="alert error small wide">{error}</p>}
    </form>
  )

  return (
    <div className="card-list">
      {items.length === 0 && editing !== 'new' && <p className="empty">{empty}</p>}
      {items.map((item) => (editing !== 'new' && editing?.[idKey] === item[idKey] ? (
        <div key={item[idKey]}>{editor(item)}</div>
      ) : (
        <div key={item[idKey]} className="card">
          {render(item)}
          <button type="button" className="plain small" onClick={() => { setError(''); setEditing(item) }}>Edit</button>
        </div>
      )))}
      {editing === 'new' ? editor(null)
        : <button type="button" className="secondary" onClick={() => { setError(''); setEditing('new') }}>{addLabel}</button>}
    </div>
  )
}

function Owned({ part, onOpenItem }) {
  return part.owned_qty > 0
    ? <button type="button" className="tag ok as-button" onClick={() => onOpenItem(part.owned_supply_id)}>Have</button>
    : <span className="tag warn">Need</span>
}

function MixCard({ mix, onOpenItem, onOpenModel }) {
  return (
    <>
      <h3>{mix.name} {mix.have_all ? <span className="tag ok">You have everything</span> : null}</h3>
      <ul className="list compact">
        {mix.parts.map((p) => (
          <li key={p.part_id}>
            <span className="num parts">{Number(p.parts)}×</span>
            <span className="grow">{p.paint_name}</span>
            {p.product_code && <Owned part={p} onOpenItem={onOpenItem} />}
          </li>
        ))}
      </ul>
      {mix.notes && <p className="small muted">{mix.notes}</p>}
      {mix.used_on.length > 0 && (
        <p className="small">Used on {mix.used_on.map((m, i) => (
          <span key={m.model_id}>{i > 0 && ', '}<button type="button" className="plain inline" onClick={() => onOpenModel(m.model_id)}>{m.name}</button></span>
        ))}</p>
      )}
    </>
  )
}

function MixForm({ mix }) {
  return (
    <>
      <label className="field wide"><span className="field-label">Recipe</span>
        <input name="recipe" defaultValue={mix?.short ?? ''} required placeholder="XF-62 + XF-2 (3:1)" autoFocus /></label>
      <label className="field wide"><span className="field-label">Name (optional)</span>
        <input name="name" defaultValue={mix?.name ?? ''} placeholder="e.g. Faded olive drab" /></label>
      <label className="field wide"><span className="field-label">Notes</span>
        <input name="notes" defaultValue={mix?.notes ?? ''} placeholder="Where it's from, how it looks" /></label>
    </>
  )
}

function GroupCard({ group, onOpenItem }) {
  return (
    <>
      <h3>{group.name}</h3>
      {group.note && <p className="small muted">{group.note}</p>}
      <ul className="list compact">
        {group.members.map((m) => (
          <li key={m.member_id}>
            <span className="grow">{m.paint_name}{m.brand && <span className="muted small block">{m.brand} {m.product_code}</span>}</span>
            {m.product_code && <Owned part={m} onOpenItem={onOpenItem} />}
          </li>
        ))}
      </ul>
    </>
  )
}

function GroupForm({ group }) {
  return (
    <>
      <label className="field wide"><span className="field-label">Name</span>
        <input name="name" defaultValue={group?.name ?? ''} required placeholder="e.g. US Olive Drab" autoFocus /></label>
      <label className="field wide"><span className="field-label">Paints, one per line</span>
        <textarea name="paints" rows="4" required placeholder={'XF-62\nMr. Color C38\nVallejo 70.887'}
          defaultValue={group?.members.map((m) => m.paint_name).join('\n') ?? ''} /></label>
      <label className="field wide"><span className="field-label">Where the match comes from</span>
        <input name="note" defaultValue={group?.note ?? ''} placeholder="e.g. Sherman instructions" /></label>
    </>
  )
}
