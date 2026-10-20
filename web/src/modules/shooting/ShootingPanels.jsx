import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, money, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { RowPhoto } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import LiveBoard from './ShootingLive.jsx'
import { MediaSection, ShotsSection } from './ShootingShots.jsx'
import { KIND_TONE, angle, dist, parseVelocities, plural, sizeAngles, useShootingLists, useShootingThings } from './shootingParts.jsx'

// Precision shooting's panels: a session and its groups, a rifle, ammunition, a range.

const sessionFields = (lists, things) => [
  { name: 'shot_on', label: 'Date', type: 'date', required: true },
  { name: 'kind', label: 'Kind', type: 'select', options: lists?.session_kinds ?? ['Practice'], required: true },
  { name: 'range_id', label: 'Range', type: 'select', options: things.ranges.map((r) => [String(r.range_id), r.name]) },
  { name: 'rifle_id', label: 'Rifle', type: 'select', options: things.rifles.filter((r) => r.status !== 'Wanted').map((r) => [String(r.rifle_id), r.name]) },
  { name: 'ammo_id', label: 'Ammo', type: 'select', options: things.ammo.filter((a) => a.status !== 'Wanted').map((a) => [String(a.ammo_id), a.name]) },
  { name: 'rounds', label: 'Rounds fired', type: 'number', hint: 'Sighters too. Blank = the groups\' shots added up' },
  { name: 'match_name', label: 'Match / event', placeholder: 'e.g. Club 50 m prone' },
  { name: 'finish', label: 'Where you placed', placeholder: 'e.g. 3rd of 24' },
  { name: 'temp_c', label: 'Temperature (°C)', type: 'number', step: 0.1, min: -40 },
  { name: 'wind_kmh', label: 'Wind (km/h)', type: 'number', step: 0.1 },
  { name: 'wind_from', label: 'Wind from', placeholder: "e.g. 3 o'clock, NW" },
  { name: 'light', label: 'Light', placeholder: 'e.g. Bright, overcast' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]
const NUMBER_FIELDS = ['range_id', 'rifle_id', 'ammo_id']
const asNumbers = (data) => Object.fromEntries(Object.entries(data).map(([k, v]) => [k, NUMBER_FIELDS.includes(k) && v != null ? Number(v) : v]))

// A session: a new one starts with what you used last (range, rifle, its ammo); once saved, add its groups.
export function SessionPanel({ id = null, live = false, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const lists = useShootingLists()
  const things = useShootingThings()
  const [s, setS] = useState(null)
  const [editing, setEditing] = useState(false)
  const [last, setLast] = useState(undefined)
  const [plotGroup, setPlotGroup] = useState(null)      // a group just added with "Add and plot shots": its target opens
  const [board, setBoard] = useState(live)              // the live board (hit / miss)
  const [failed, setFailed] = useState('')       // it couldn't be loaded (removed since?): said in the panel
  const reload = useCallback(() => api.shootingSession(id).then(setS).catch((e) => { setFailed(e.message); showToast(e.message) }), [id, showToast])
  useEffect(() => { if (id != null) reload() }, [id, reload])
  useEffect(() => { if (id == null) api.shootingSessions().then((all) => setLast(all[0] ?? null)).catch(() => setLast(null)) }, [id])

  if (id == null || editing) {
    if ((id == null && last === undefined) || !things.loaded || !lists) {
      return <Drawer title={s ? 'Session details' : 'Log a session'} onClose={onClose}><p className="muted">Loading...</p></Drawer>
    }
    const club = things.ranges.find((r) => r.counts_for_club)
    const defaults = { shot_on: today(), kind: 'Practice', range_id: last?.range_id ?? club?.range_id, rifle_id: last?.rifle_id, ammo_id: last?.ammo_id }
    return (
      <FormPanel title={s ? 'Session details' : 'Log a session'} fields={sessionFields(lists, things)} record={s} defaults={defaults}
        onClose={editing ? () => setEditing(false) : onClose} saveLabel={s ? 'Save' : 'Start logging'}
        onSave={async (data) => {
          if (s) {
            setS(await api.updateShootingSession(s.session_id, asNumbers(data)))
            setEditing(false)
          } else {
            const made = await api.addShootingSession(asNumbers(data))
            onClose()
            openPanel('shootsession', { id: made.session_id })
          }
          changed()
        }}
        onDelete={s && (async () => { await api.deleteShootingSession(s.session_id); changed(); onClose() })} deleteLabel="Remove" />
    )
  }
  if (!s) return <Drawer title="Session" onClose={onClose}>{failed ? <p className="alert error">{failed}</p>
    : <p className="muted">Loading...</p>}</Drawer>
  const footer = (
    <>
      <span className="spacer" />
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>
    </>
  )
  const title = s.match_name || s.range_name || 'Range session'
  return (
    <Drawer title={title} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="section-head">
          <strong>{shortDate(s.shot_on)}{s.range_name && s.match_name && ` · ${s.range_name}`}</strong>
          <span className={`pill ${KIND_TONE[s.kind] ?? ''}`}>{s.kind}</span>
        </div>
        <p className="item-sub">{[s.rifle_name, s.ammo_name].filter(Boolean).join(' · ') || 'No rifle or ammo noted'}</p>
        <dl className="shoot-numbers">
          <div><dt>Rounds</dt><dd>{s.rounds}</dd></div>
          <div><dt>Groups</dt><dd>{s.groups}</dd></div>
          {s.best_moa != null && <div><dt>Best group</dt><dd>{s.best_moa} MOA</dd></div>}
          {s.score != null && <div><dt>Score</dt><dd>{s.score}{s.x_count ? `-${s.x_count}X` : ''}</dd></div>}
          {s.hits != null && <div><dt>Hits</dt><dd>{s.hits}/{s.hit_shots}<span className="muted small"> {Math.round((100 * s.hits) / (s.hit_shots || 1))}%</span></dd></div>}
          {s.finish && <div><dt>Placed</dt><dd>{s.finish}</dd></div>}
        </dl>
        {(s.temp_c != null || s.wind_kmh != null || s.light) && (
          <p className="small muted">{[s.temp_c != null && `${s.temp_c}°C`, s.wind_kmh != null && `wind ${s.wind_kmh} km/h${s.wind_from ? ` from ${s.wind_from}` : ''}`,
            s.light].filter(Boolean).join(' · ')}</p>
        )}
        {s.notes && <p className="small shoot-notes">{s.notes}</p>}
      </section>
      <section className="panel-section">
        <div className="section-head">
          <h3 className="section-title">Groups</h3>
          <button type="button" className="primary small" onClick={() => setBoard(true)}>Live board</button>
        </div>
        {s.groups_list.length === 0 && <p className="muted small">No groups yet. Add each group, string or card you shot - then tap
          every shot onto its target ("Add and plot shots"), or just type the group's size.</p>}
        <ul className="shoot-groups">
          {s.groups_list.map((g) => <GroupCard key={g.group_id} g={g} unit={s.scope_unit} lists={lists} autoPlot={plotGroup === g.group_id}
            onChanged={(next) => { if (next) setS(next); else reload(); changed() }} />)}
        </ul>
        <GroupForm lists={lists} unit={s.scope_unit} start={s.groups_list.at(-1)} first={s.groups_list.length === 0}
          onSave={async (data, plot) => {
            const next = await api.addShootingGroup(s.session_id, data)
            setS(next)
            setPlotGroup(plot ? next.groups_list.at(-1)?.group_id : null)
            changed()
          }} />
      </section>
      <MediaSection s={s} onSession={setS} />
      {board && <LiveBoard s={s} lists={lists} onSession={setS} onClose={() => setBoard(false)} />}
    </Drawer>
  )
}

function GroupCard({ g, unit, lists, autoPlot = false, onChanged }) {
  const { showToast } = useApp()
  const [editing, setEditing] = useState(false)
  if (editing) {
    return (
      <li className="card shoot-group">
        <GroupForm lists={lists} unit={unit} start={g} editing
          onCancel={() => setEditing(false)}
          onSave={async (data) => { onChanged(await api.updateShootingGroup(g.group_id, data)); setEditing(false) }} />
      </li>
    )
  }
  const v = g.velocity
  return (
    <li className="card shoot-group">
      <div className="shoot-group-head">
        <strong>{dist(g)}{g.target && ` · ${g.target}`}{g.shots && ` · ${g.shots} shots`}{g.position && ` · ${g.position}`}</strong>
        {g.confirms_dope && <span className="pill ok">DOPE</span>}
      </div>
      <div className="shoot-group-body">
        <dl className="shoot-facts">
          {g.size_mm != null && <><dt>Group</dt><dd>{g.size_mm} mm · <strong>{angle(g.moa, 'MOA')}</strong> · {angle(g.mil, 'MIL')}</dd></>}
          {(g.elevation != null || g.windage != null) && <><dt>Dialled</dt>
            <dd>{[g.elevation != null && `${g.elevation} ${unit} up`, g.windage != null && `${g.windage} ${unit} wind`].filter(Boolean).join(' · ')}</dd></>}
          {g.correction && <><dt>To centre</dt><dd>{g.correction}</dd></>}
          {g.score != null && <><dt>Score</dt><dd>{g.score}{g.x_count ? `-${g.x_count}X` : ''}</dd></>}
          {g.hits != null && <><dt>Hits</dt><dd><strong>{g.hits}/{g.shots}</strong>{g.hit_rate != null && ` (${g.hit_rate}%)`}
            {g.best_streak > 1 && <span className="muted"> · best streak {g.best_streak}</span>}
            {g.shot_list?.some((x) => x.hit != null) && <span className="shoot-board-dots small-dots" aria-hidden="true">
              {g.shot_list.filter((x) => x.hit != null).map((x) => <i key={x.shot_id} className={x.hit ? 'hit' : 'miss'} />)}</span>}</dd></>}
          {v && <><dt>Velocity</dt><dd>{v.avg} m/s ({v.fps} fps) · SD {v.sd} · ES {v.es} <span className="muted">({v.n} shots)</span></dd></>}
        </dl>
        <RowPhoto path={`/shooting/groups/${g.group_id}`} url={g.photo_url} label="target photo"
          onChanged={(msg) => { onChanged(); showToast(msg) }} />
      </div>
      {g.notes && <p className="small shoot-notes">{g.notes}</p>}
      <ShotsSection g={g} autoPlot={autoPlot} onSession={(next) => onChanged(next)} />
      <div className="button-row">
        <button type="button" className="plain small" onClick={() => setEditing(true)}>Edit</button>
        <button type="button" className="plain small destructive" onClick={async () => onChanged(await api.deleteShootingGroup(g.group_id))}>Remove</button>
      </div>
    </li>
  )
}

const blankGroup = (start) => ({
  distance: String(start?.distance ?? 50), unit: start?.unit ?? 'm', shots: String(start?.shots ?? 5), size_mm: '', up_mm: '', right_mm: '',
  elevation: start?.elevation != null ? String(start.elevation) : '', windage: '', position: start?.position ?? '',
  score: '', x_count: '', velocities: '', confirms_dope: false, notes: '', target: start?.target ?? '', hits: '',
})
const fromGroup = (g) => ({
  ...blankGroup(g), size_mm: g.size_mm ?? '', up_mm: g.up_mm ?? '', right_mm: g.right_mm ?? '', windage: g.windage ?? '',
  score: g.score ?? '', x_count: g.x_count ?? '', velocities: (g.velocities ?? []).join(' '), confirms_dope: g.confirms_dope, notes: g.notes ?? '',
  hits: g.hits ?? '',
})

// Add (or edit) a group: distance, shots, size (MOA / MIL shown as you type), where it hit, what you dialled,
// a score, chronograph speeds, and whether it confirms your DOPE at that distance.
function GroupForm({ lists, unit, start, editing = false, first = false, onSave, onCancel }) {
  const [open, setOpen] = useState(editing)
  const [f, setF] = useState(() => (editing ? fromGroup(start) : blankGroup(start)))
  const [error, setError] = useState('')
  useEffect(() => { if (!editing) setF(blankGroup(start)) }, [start, editing])
  if (!open) return <button type="button" className={first ? 'primary' : 'secondary'} onClick={() => setOpen(true)}>+ Add a group</button>
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const num = (v) => (v === '' || v == null ? null : Number(v))
  const a = sizeAngles(num(f.size_mm), num(f.distance), f.unit)
  const speeds = parseVelocities(f.velocities)
  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const plot = e.nativeEvent.submitter?.value === 'plot'      // "Add and plot shots"
    try {
      await onSave({ distance: num(f.distance), unit: f.unit, shots: num(f.shots), size_mm: num(f.size_mm), up_mm: num(f.up_mm),
        right_mm: num(f.right_mm), elevation: num(f.elevation), windage: num(f.windage), position: f.position || null, score: num(f.score),
        x_count: num(f.x_count), velocities: speeds, confirms_dope: f.confirms_dope, notes: f.notes.trim() || null,
        target: f.target.trim() || null, hits: num(f.hits) }, plot)
      if (editing) return
      setOpen(false)
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="shoot-group-form" onSubmit={submit} aria-label={editing ? 'Edit group' : 'New group'}>
      <div className="shoot-form-grid">
        <div className="field">Distance<span className="shoot-dist">
          <input type="number" min="1" max="5000" required value={f.distance} onChange={set('distance')} aria-label="Distance" />
          <select value={f.unit} onChange={set('unit')} aria-label="Unit"><option value="m">m</option><option value="yd">yd</option></select>
        </span></div>
        <label className="field">Shots<input type="number" min="1" value={f.shots} onChange={set('shots')} /></label>
        <label className="field">Group size (mm)<input type="number" min="0" step="0.1" inputMode="decimal" value={f.size_mm} onChange={set('size_mm')} /></label>
        <label className="field">Position<select value={f.position} onChange={set('position')}><option value="">—</option>
          {(lists?.positions ?? []).map((p) => <option key={p}>{p}</option>)}</select></label>
        <label className="field">Hit high by (mm)<input type="number" step="0.1" inputMode="decimal" value={f.up_mm} onChange={set('up_mm')} placeholder="low = minus" /></label>
        <label className="field">Hit right by (mm)<input type="number" step="0.1" inputMode="decimal" value={f.right_mm} onChange={set('right_mm')} placeholder="left = minus" /></label>
        <label className="field">Elevation dialled ({unit})<input type="number" step="0.01" inputMode="decimal" value={f.elevation} onChange={set('elevation')} /></label>
        <label className="field">Windage ({unit})<input type="number" step="0.01" inputMode="decimal" value={f.windage} onChange={set('windage')} /></label>
        <label className="field">Score<input type="number" min="0" step="0.1" inputMode="decimal" value={f.score} onChange={set('score')} /></label>
        <label className="field">X count<input type="number" min="0" value={f.x_count} onChange={set('x_count')} /></label>
        <label className="field">Target<input value={f.target} onChange={set('target')} placeholder="e.g. 2 MOA steel" /></label>
        <label className="field">Hits<input type="number" min="0" value={f.hits} onChange={set('hits')} /></label>
      </div>
      <label className="field">Chronograph speeds (m/s)<input value={f.velocities} onChange={set('velocities')} placeholder="e.g. 325 328 326" /></label>
      <label className="field">Notes<input value={f.notes} onChange={set('notes')} /></label>
      <label className="tick-row"><input type="checkbox" checked={f.confirms_dope} onChange={set('confirms_dope')} />
        This confirms my elevation at this distance (DOPE)</label>
      {editing && start.shot_list?.length > 0 && <p className="hint">This group has its shots plotted: its size, where it hit,
        speeds and score come from them (change a shot to change these).</p>}
      {a && <p className="small shoot-live">{angle(a.moa, 'MOA')} · {angle(a.mil, 'MIL')}{speeds.length > 1 && ` · ${speeds.length} speeds`}</p>}
      {error && <p className="alert error small">{error}</p>}
      <div className="button-row">
        {!editing && <button type="submit" className="primary small" value="plot">Add and plot shots</button>}
        <button type="submit" className={editing ? 'primary small' : 'secondary small'}>{editing ? 'Save group' : 'Add group'}</button>
        <button type="button" className="plain small" onClick={editing ? onCancel : () => setOpen(false)}>Cancel</button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------------------------
const rifleFields = (lists) => [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. CZ 457 Varmint' },
  { name: 'make', label: 'Make' },
  { name: 'model', label: 'Model' },
  { name: 'calibre', label: 'Calibre', placeholder: 'e.g. .22 LR, 6.5 Creedmoor' },
  { name: 'kind', label: 'Kind', type: 'select', options: lists?.rifle_kinds ?? ['Centrefire'], required: true },
  { name: 'action', label: 'Action', type: 'select', options: lists?.actions ?? [] },
  { name: 'barrel_in', label: 'Barrel (inches)', type: 'number', step: 0.1 },
  { name: 'twist', label: 'Twist', placeholder: 'e.g. 1:8' },
  { name: 'scope', label: 'Scope', wide: true, placeholder: 'e.g. Vortex Viper PST 5-25x50' },
  { name: 'scope_unit', label: 'Scope turrets', type: 'select', options: lists?.scope_units ?? ['MOA', 'MIL'], required: true },
  { name: 'click', label: 'One click', type: 'number', step: 0.001, hint: '0.25 MOA or 0.1 MIL, usually' },
  { name: 'zero_m', label: 'Zeroed at (m)', type: 'number' },
  { name: 'sight_height_mm', label: 'Scope height (mm)', type: 'number', step: 0.1 },
  { name: 'rounds_before', label: 'Rounds before logging here', type: 'number', hint: 'Its count when you started using this' },
  { name: 'clean_every', label: 'Clean every (rounds)', type: 'number', hint: 'Blank = your usual (settings)' },
  { name: 'status', label: 'Status', type: 'select', options: lists?.rifle_statuses ?? ['In use'], required: true },
  { name: 'purchase_date', label: 'Bought on', type: 'date' },
  { name: 'price_paid', label: 'Price paid', type: 'money' },
  { name: 'pta_applied', label: 'Permit to Acquire applied', type: 'date', hint: 'Queensland: one per firearm you buy' },
  { name: 'pta_approved', label: 'PTA approved', type: 'date' },
  { name: 'pta_expires', label: 'PTA expires', type: 'date' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

export function RiflePanel({ id = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const navigate = useNavigate()
  const lists = useShootingLists()
  const [r, setR] = useState(null)
  const [editing, setEditing] = useState(false)
  const [logKind, setLogKind] = useState('Cleaned')
  const [logNote, setLogNote] = useState('')
  const [failed, setFailed] = useState('')       // it couldn't be loaded (removed since?): said in the panel
  const reload = useCallback(() => api.rifle(id).then(setR).catch((e) => { setFailed(e.message); showToast(e.message) }), [id, showToast])
  useEffect(() => { if (id != null) reload() }, [id, reload])
  if (!lists) return <Drawer title="Rifle" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  if (id == null || editing) {
    return (
      <FormPanel title={r ? `Edit ${r.name}` : 'Add a rifle'} fields={rifleFields(lists)} record={r}
        defaults={{ kind: 'Centrefire', scope_unit: 'MOA', status: 'In use', rounds_before: 0 }}
        onClose={editing ? () => setEditing(false) : onClose} saveLabel={r ? 'Save' : 'Add rifle'}
        onSave={async (data) => {
          if (r) { await api.updateRifle(r.rifle_id, data); setEditing(false); reload() } else {
            const made = await api.addRifle(data)
            onClose()
            openPanel('rifle', { id: made.rifle_id })
          }
          changed()
        }}
        onDelete={r && (async () => { await api.deleteRifle(r.rifle_id); changed(); onClose() })} deleteLabel="Remove" />
    )
  }
  if (!r) return <Drawer title="Rifle" onClose={onClose}>{failed ? <p className="alert error">{failed}</p>
    : <p className="muted">Loading...</p>}</Drawer>
  const addLog = async () => {
    await api.addRifleLog(r.rifle_id, { kind: logKind, notes: logNote.trim() || null })
    setLogNote('')
    await reload()
    changed()
    showToast(logKind === 'Cleaned' ? 'Cleaned - the count starts again' : 'Noted')
  }
  const footer = (
    <>
      <button type="button" className="secondary" onClick={() => { onClose(); navigate(`/shooting/dope?rifle=${r.rifle_id}`) }}>DOPE card</button>
      <span className="spacer" />
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>
    </>
  )
  return (
    <Drawer title={r.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="item-hero">
          <RowPhoto path={`/shooting/rifles/${r.rifle_id}`} url={r.photo_url} onChanged={(msg) => { reload(); changed(); showToast(msg) }} />
          <div>
            <p className="item-sub">{[r.make, r.model, r.calibre, r.kind, r.action].filter(Boolean).join(' · ')}</p>
            {r.status !== 'In use' && <span className="pill">{r.status}</span>}
            <dl className="shoot-facts">
              {(r.barrel_in || r.twist) && <><dt>Barrel</dt><dd>{[r.barrel_in && `${r.barrel_in}"`, r.twist && `${r.twist} twist`].filter(Boolean).join(' · ')}</dd></>}
              {r.scope && <><dt>Scope</dt><dd>{r.scope}</dd></>}
              <dt>Turrets</dt><dd>{r.scope_unit}{r.click && ` · ${r.click} a click`}</dd>
              {r.zero_m && <><dt>Zero</dt><dd>{r.zero_m} m</dd></>}
              {r.price_paid != null && <><dt>Paid</dt><dd>{money(r.price_paid)}{r.purchase_date && ` · ${shortDate(r.purchase_date)}`}</dd></>}
              {r.pta_applied && <><dt>Permit to Acquire</dt><dd>applied {shortDate(r.pta_applied)}
                {r.pta_approved ? ` · approved ${shortDate(r.pta_approved)}` : <span className="pill low">waiting</span>}
                {r.pta_expires && ` · expires ${shortDate(r.pta_expires)}`}</dd></>}
            </dl>
          </div>
        </div>
        {r.notes && <p className="small shoot-notes">{r.notes}</p>}
      </section>
      <section className="panel-section">
        <dl className="shoot-numbers">
          <div><dt>Round count</dt><dd>{r.round_count.toLocaleString()}</dd></div>
          <div><dt>Since cleaned</dt><dd>{r.since_clean.toLocaleString()}<span className="muted small"> / {r.clean_interval}</span></dd></div>
          <div><dt>Sessions</dt><dd>{r.sessions}</dd></div>
        </dl>
        {r.clean_due && <p className="alert low small">Due for a clean ({r.since_clean} rounds since{r.cleaned_on ? ` ${shortDate(r.cleaned_on)}` : ' you started logging'}).</p>}
      </section>
      <section className="panel-section">
        <h3 className="section-title">How each ammo groups</h3>
        {r.ammo.length === 0 ? <p className="muted small">Log a session with groups to see this.</p> : (
          <table className="shoot-table">
            <thead><tr><th>Ammo</th><th>Groups</th><th>Average</th><th>Best</th><th>Velocity</th><th>SD</th></tr></thead>
            <tbody>{r.ammo.map((a) => (
              <tr key={a.ammo_id ?? 'none'}><td>{a.name}</td><td>{a.groups}</td><td>{angle(a.avg, a.unit)}</td><td>{angle(a.best, a.unit)}</td>
                <td>{a.velocity ? `${a.velocity} m/s` : '—'}</td><td>{a.sd ?? '—'}</td></tr>))}</tbody>
          </table>
        )}
      </section>
      <section className="panel-section">
        <h3 className="section-title">Care log</h3>
        <div className="button-row">
          <select value={logKind} onChange={(e) => setLogKind(e.target.value)} aria-label="What">
            {(lists?.log_kinds ?? ['Cleaned']).map((k) => <option key={k}>{k}</option>)}
          </select>
          <input value={logNote} onChange={(e) => setLogNote(e.target.value)} placeholder="Notes (optional)" aria-label="Care note" />
          <button type="button" className="primary small" onClick={addLog}>Log it</button>
        </div>
        <ul className="list plain-list">{r.logs.map((l) => (
          <li key={l.log_id} className="shoot-log">
            <span className="grow"><strong>{l.kind}</strong> · {shortDate(l.done_on)}{l.at_rounds != null && ` · at ${l.at_rounds.toLocaleString()} rounds`}
              {l.notes && <span className="muted"> · {l.notes}</span>}</span>
            <button type="button" className="plain small destructive" onClick={async () => { await api.deleteRifleLog(l.log_id); reload(); changed() }}>Remove</button>
          </li>))}</ul>
      </section>
      {r.recent.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Latest sessions</h3>
          <ul className="list plain-list">{r.recent.map((x) => (
            <li key={x.session_id}><button type="button" className="row-button" onClick={() => { onClose(); openPanel('shootsession', { id: x.session_id }) }}>
              <span className="grow"><span className="item-title">{shortDate(x.shot_on)} · {x.range_name ?? x.kind}</span>
                <span className="item-meta">{[x.ammo_name, plural(x.rounds, 'round')].filter(Boolean).join(' · ')}</span></span>
            </button></li>))}</ul>
        </section>
      )}
    </Drawer>
  )
}

// ---------------------------------------------------------------------------------------------
const ammoFields = (lists) => [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Lapua Center-X' },
  { name: 'brand', label: 'Brand' },
  { name: 'calibre', label: 'Calibre' },
  { name: 'bullet_gr', label: 'Bullet (grains)', type: 'number', step: 0.1 },
  { name: 'bullet_type', label: 'Bullet type', placeholder: 'e.g. LRN, ELD Match' },
  { name: 'bc', label: 'BC', type: 'number', step: 0.001 },
  { name: 'bc_model', label: 'BC model', type: 'select', options: lists?.bc_models ?? ['G1', 'G7'] },
  { name: 'velocity_ms', label: 'Box velocity (m/s)', type: 'number', step: 0.1 },
  { name: 'lot', label: 'Lot number' },
  { name: 'box_size', label: 'Rounds in a box', type: 'number' },
  { name: 'box_price', label: 'Price a box', type: 'money' },
  { name: 'rounds_bought', label: 'Rounds bought (all up)', type: 'number', hint: 'What\'s left = this less what you\'ve fired' },
  { name: 'bought_from', label: 'Bought from' },
  { name: 'status', label: 'Status', type: 'select', options: lists?.ammo_statuses ?? ['Have'], required: true },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

export function AmmoPanel({ id = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const lists = useShootingLists()
  const [a, setA] = useState(null)
  const [editing, setEditing] = useState(false)
  const [lot, setLot] = useState('')
  const [failed, setFailed] = useState('')       // it couldn't be loaded (removed since?): said in the panel
  const reload = useCallback(() => api.ammo(id).then(setA).catch((e) => { setFailed(e.message); showToast(e.message) }), [id, showToast])
  useEffect(() => { if (id != null) reload() }, [id, reload])
  if (!lists) return <Drawer title="Ammunition" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  if (id == null || editing) {
    return (
      <FormPanel title={a ? `Edit ${a.name}` : 'Add ammunition'} fields={ammoFields(lists)} record={a}
        defaults={{ status: 'Have', rounds_bought: 0 }}
        onClose={editing ? () => setEditing(false) : onClose} saveLabel={a ? 'Save' : 'Add ammo'}
        onSave={async (data) => {
          if (a) { await api.updateAmmo(a.ammo_id, data); setEditing(false); reload() } else {
            const made = await api.addAmmo(data)
            onClose()
            openPanel('ammo', { id: made.ammo_id })
          }
          changed()
        }}
        onDelete={a && (async () => { await api.deleteAmmo(a.ammo_id); changed(); onClose() })} deleteLabel="Remove" />
    )
  }
  if (!a) return <Drawer title="Ammunition" onClose={onClose}>{failed ? <p className="alert error">{failed}</p>
    : <p className="muted">Loading...</p>}</Drawer>
  const box = async () => {
    try {
      await api.ammoBox(a.ammo_id, { lot: lot.trim() || null })
      setLot('')
      await reload()
      changed()
      showToast(`Added ${a.box_size} rounds`)
    } catch (e) {
      showToast(e.message)
    }
  }
  const footer = <><span className="spacer" /><button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button></>
  return (
    <Drawer title={a.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="item-hero">
          <RowPhoto path={`/shooting/ammo/${a.ammo_id}`} url={a.photo_url} onChanged={(msg) => { reload(); changed(); showToast(msg) }} />
          <div>
            <p className="item-sub">{[a.brand, a.calibre, a.bullet_gr && `${a.bullet_gr} gr`, a.bullet_type].filter(Boolean).join(' · ')}</p>
            <dl className="shoot-facts">
              {a.bc && <><dt>BC</dt><dd>{a.bc}{a.bc_model && ` (${a.bc_model})`}</dd></>}
              {a.velocity_ms && <><dt>Box velocity</dt><dd>{a.velocity_ms} m/s ({a.fps} fps)</dd></>}
              {a.lot && <><dt>Lot</dt><dd>{a.lot}</dd></>}
              {a.per_round != null && <><dt>Cost</dt><dd>{money(a.per_round)} a round{a.box_price != null && ` · ${money(a.box_price)} for ${a.box_size}`}</dd></>}
              {a.bought_from && <><dt>From</dt><dd>{a.bought_from}</dd></>}
            </dl>
          </div>
        </div>
        {a.notes && <p className="small shoot-notes">{a.notes}</p>}
      </section>
      <section className="panel-section">
        <dl className="shoot-numbers">
          <div><dt>Left</dt><dd>{a.rounds_left.toLocaleString()}</dd></div>
          <div><dt>Fired</dt><dd>{a.rounds_fired.toLocaleString()}</dd></div>
          <div><dt>Bought</dt><dd>{a.rounds_bought.toLocaleString()}</dd></div>
        </dl>
        {a.low && <p className="alert low small">Running low.</p>}
        {a.box_size && (
          <div className="button-row">
            <input value={lot} onChange={(e) => setLot(e.target.value)} placeholder="New lot number (optional)" aria-label="Lot number" />
            <button type="button" className="secondary small" onClick={box}>Bought a box (+{a.box_size})</button>
          </div>
        )}
      </section>
      <section className="panel-section">
        <h3 className="section-title">How it groups</h3>
        {a.rifles.length === 0 ? <p className="muted small">Log a session with groups to see this.</p> : (
          <table className="shoot-table">
            <thead><tr><th>Rifle</th><th>Groups</th><th>Average</th><th>Best</th><th>Velocity</th><th>SD</th></tr></thead>
            <tbody>{a.rifles.map((x) => (
              <tr key={x.rifle_id ?? 'none'}><td>{x.name}</td><td>{x.groups}</td><td>{angle(x.avg, x.unit)}</td><td>{angle(x.best, x.unit)}</td>
                <td>{x.velocity ? `${x.velocity} m/s` : '—'}</td><td>{x.sd ?? '—'}</td></tr>))}</tbody>
          </table>
        )}
      </section>
    </Drawer>
  )
}

// ---------------------------------------------------------------------------------------------
const rangeFields = (lists) => [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. your club' },
  { name: 'kind', label: 'Kind', type: 'select', options: lists?.range_kinds ?? ['Club range'], required: true },
  { name: 'distances', label: 'Distances', placeholder: 'e.g. 25, 50, 100 m' },
  { name: 'counts_for_club', label: 'Counts as a club shoot?', type: 'select', options: [['true', 'Yes'], ['false', 'No']], required: true },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

export function RangePanel({ id = null, range = null, onClose }) {
  const { changed } = useApp()
  const lists = useShootingLists()
  const record = range && { ...range, counts_for_club: String(range.counts_for_club) }
  if (!lists) return <Drawer title="Range" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  return (
    <FormPanel title={range ? range.name : 'Add a range'} fields={rangeFields(lists)} record={record}
      defaults={{ kind: 'Club range', counts_for_club: 'true' }} onClose={onClose} saveLabel={range ? 'Save' : 'Add range'}
      onSave={async (data) => {
        const body = { ...data, counts_for_club: data.counts_for_club === 'true' }
        if (id != null) await api.updateShootingRange(id, body)
        else await api.addShootingRange(body)
        changed()
        onClose()
      }}
      onDelete={id != null && (async () => { await api.deleteShootingRange(id); changed(); onClose() })} deleteLabel="Remove" />
  )
}
