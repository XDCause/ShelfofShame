import { useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import PhotoPick from '../../components/PhotoPick.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'
import { useApp } from '../../core/app-context.js'
import { angle } from './shootingParts.jsx'

// Shot by shot (a target you tap) and a session's photos and videos (api/app/shooting_shots.py).

// mm at this distance for one MOA / MIL
const mmPerUnit = (g) => (g.scope_unit === 'MIL' ? g.metres : g.metres * 0.290888)

// The target: the aim point in the middle, a grid in the scope's unit at this group's distance, each shot numbered
// where it landed (flyers hollow), the group's centre as a +. While plotting, a tap adds a shot there.
export function ShotPlot({ g, plotting, selected, onAdd, onPick }) {
  const svg = useRef(null)
  const unit = g.scope_unit
  const per = mmPerUnit(g)
  const shots = g.shot_list.filter((s) => s.x_mm != null)
  const reach = Math.max(...shots.map((s) => Math.max(Math.abs(s.x_mm), Math.abs(s.y_mm)) / per), 0)
  const minR = unit === 'MIL' ? 0.5 : 2
  const R = Math.max(minR, reach * 1.25)
  const step = unit === 'MIL' ? (R <= 1 ? 0.1 : R <= 3 ? 0.5 : 1) : (R <= 3 ? 0.5 : R <= 8 ? 1 : 2)
  const top = Math.ceil(R / step) * step
  const lines = []
  for (let v = -top; v <= top + 1e-9; v += step) lines.push(Number(v.toFixed(3)))
  const dot = top * 0.045
  const tap = (e) => {
    if (!plotting) return
    const pt = svg.current.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const p = pt.matrixTransform(svg.current.getScreenCTM().inverse())
    onAdd(Math.round(p.x * per * 2) / 2, Math.round(-p.y * per * 2) / 2)     // to the nearest 0.5 mm
  }
  const centre = g.spread ?? (shots.length === 1 ? { right_mm: shots[0].x_mm, up_mm: shots[0].y_mm } : null)
  return (
    <figure className={`shoot-plot${plotting ? ' plotting' : ''}`}>
      <svg ref={svg} viewBox={`${-top} ${-top} ${top * 2} ${top * 2}`} role="img" onClick={tap}
        aria-label={`Target at ${g.distance} ${g.unit}: ${shots.length} shots plotted${plotting ? '. Tap where each shot hit.' : ''}`}>
        <rect x={-top} y={-top} width={top * 2} height={top * 2} className="shoot-plot-bg" />
        {lines.map((v) => <g key={v} className={v === 0 ? 'shoot-plot-axis' : 'shoot-plot-grid'}>
          <line x1={v} y1={-top} x2={v} y2={top} /><line x1={-top} y1={v} x2={top} y2={v} /></g>)}
        <circle cx="0" cy="0" r={dot * 1.6} className="shoot-plot-aim" />
        {centre && (
          <g className="shoot-plot-centre" transform={`translate(${centre.right_mm / per} ${-centre.up_mm / per})`}>
            <line x1={-dot * 2} y1="0" x2={dot * 2} y2="0" /><line x1="0" y1={-dot * 2} x2="0" y2={dot * 2} />
          </g>
        )}
        {shots.map((s) => (
          <g key={s.shot_id} className={`shoot-plot-shot${s.flyer ? ' flyer' : ''}${selected === s.shot_id ? ' picked' : ''}`}
            transform={`translate(${s.x_mm / per} ${-s.y_mm / per})`}
            onClick={(e) => { if (!plotting) { e.stopPropagation(); onPick(s) } }}>
            <circle r={dot} />
            <text y={dot * 0.38} fontSize={dot * 1.1}>{s.n}</text>
          </g>
        ))}
      </svg>
      <figcaption className="muted small">Each square {step} {unit} ({Math.round(step * per * 10) / 10} mm at {g.distance} {g.unit}).
        {centre && ' + is the group\'s centre.'}</figcaption>
    </figure>
  )
}

// Shots for a group: the target, then a row per shot (where it landed, score, X, speed, flyer) - typed or tapped.
export function ShotsSection({ g, onSession }) {
  const { showToast } = useApp()
  const [plotting, setPlotting] = useState(false)
  const [selected, setSelected] = useState(null)
  const has = g.shot_list.length > 0
  const run = async (p) => {
    try { onSession(await p) } catch (e) { showToast(e.message) }
  }
  const add = (x, y) => run(api.addShot(g.group_id, { x_mm: x, y_mm: y }))
  const save = (s, field, raw) => {
    const value = raw === '' ? null : typeof raw === 'boolean' ? raw : Number(raw)
    if ((s[field] ?? null) === value) return
    const body = { [field]: value }
    if (field === 'x_mm' || field === 'y_mm') Object.assign(body, { x_mm: s.x_mm ?? 0, y_mm: s.y_mm ?? 0, [field]: value ?? 0 })
    run(api.updateShot(s.shot_id, body))
  }
  const sp = g.spread
  return (
    <div className="shoot-shots">
      <div className="button-row">
        <button type="button" className={plotting ? 'primary small' : 'secondary small'} aria-pressed={plotting}
          onClick={() => setPlotting(!plotting)}>{plotting ? 'Done plotting' : has ? 'Plot more shots' : 'Plot shots'}</button>
        <button type="button" className="plain small" onClick={() => run(api.addShot(g.group_id, {}))}>+ Shot without a place</button>
      </div>
      {(has || plotting) && <ShotPlot g={g} plotting={plotting} selected={selected} onAdd={add} onPick={(s) => setSelected(s.shot_id)} />}
      {plotting && <p className="hint">Tap where each shot hit, in order. Up and right are as you look at the target.</p>}
      {sp && <p className="small">Mean radius <strong>{angle(sp.mean_radius, g.scope_unit)}</strong> ({sp.mean_radius_mm} mm)
        · {sp.width_mm} mm wide × {sp.height_mm} mm tall{sp.flyers ? ` · ${sp.flyers} flyer${sp.flyers > 1 ? 's' : ''} left out` : ''}</p>}
      {has && (
        <div className="shoot-shot-table-wrap">
          <table className="shoot-table shoot-shot-table">
            <thead><tr><th>#</th><th>Right (mm)</th><th>Up (mm)</th><th>Score</th><th>X</th><th>m/s</th><th>Flyer</th><th /></tr></thead>
            <tbody>{g.shot_list.map((s) => (
              <tr key={`${s.shot_id}-${s.x_mm}-${s.y_mm}-${s.score}-${s.velocity}`} className={selected === s.shot_id ? 'picked' : ''}
                onFocus={() => setSelected(s.shot_id)}>
                <td>{s.n}</td>
                <td><input type="number" step="0.5" inputMode="decimal" defaultValue={s.x_mm ?? ''} aria-label={`Shot ${s.n} right`}
                  onBlur={(e) => save(s, 'x_mm', e.target.value)} /></td>
                <td><input type="number" step="0.5" inputMode="decimal" defaultValue={s.y_mm ?? ''} aria-label={`Shot ${s.n} up`}
                  onBlur={(e) => save(s, 'y_mm', e.target.value)} /></td>
                <td><input type="number" min="0" step="0.1" inputMode="decimal" defaultValue={s.score ?? ''} aria-label={`Shot ${s.n} score`}
                  onBlur={(e) => save(s, 'score', e.target.value)} /></td>
                <td><input type="checkbox" checked={s.is_x} aria-label={`Shot ${s.n} X`} onChange={(e) => save(s, 'is_x', e.target.checked)} /></td>
                <td><input type="number" min="0" step="0.1" inputMode="decimal" defaultValue={s.velocity ?? ''} aria-label={`Shot ${s.n} velocity`}
                  onBlur={(e) => save(s, 'velocity', e.target.value)} /></td>
                <td><input type="checkbox" checked={s.flyer} aria-label={`Shot ${s.n} flyer`} onChange={(e) => save(s, 'flyer', e.target.checked)} /></td>
                <td><button type="button" className="plain small destructive" aria-label={`Remove shot ${s.n}`}
                  onClick={() => run(api.deleteShot(s.shot_id))}>✕</button></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// A session's photos and videos: several at once, each optionally of one group, with a caption.
export function MediaSection({ s, onSession }) {
  const { changed, showToast } = useApp()
  const [ofGroup, setOfGroup] = useState('')
  const [busy, setBusy] = useState('')
  const [viewing, setViewing] = useState(null)
  const videoInput = useRef(null)
  const groupLabel = (id) => {
    const i = s.groups_list.findIndex((x) => x.group_id === id)
    return i < 0 ? null : `Group ${i + 1} · ${s.groups_list[i].distance} ${s.groups_list[i].unit}`
  }
  const params = () => (ofGroup ? { group_id: ofGroup } : {})
  const addPhotos = async (files) => {
    const list = [files].flat()
    try {
      for (const [i, file] of list.entries()) {
        setBusy(`Adding photo ${i + 1} of ${list.length}...`)
        onSession(await api.addShootPhoto(s.session_id, await shrink(file, 1600), params()))
      }
      changed()
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy('')
    }
  }
  const addVideo = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      onSession(await api.addShootVideo(s.session_id, file, params(), (p) => setBusy(`Uploading the video... ${Math.round(p * 100)}%`)))
      changed()
    } catch (err) {
      showToast(err.message)
    } finally {
      setBusy('')
    }
  }
  const media = s.media
  return (
    <section className="panel-section" aria-label="Photos and video">
      <h3 className="section-title">Photos and video</h3>
      <div className="button-row">
        {s.groups_list.length > 0 && (
          <select value={ofGroup} onChange={(e) => setOfGroup(e.target.value)} aria-label="Of which group">
            <option value="">The whole session</option>
            {s.groups_list.map((g) => <option key={g.group_id} value={g.group_id}>{groupLabel(g.group_id)}</option>)}
          </select>
        )}
        <PhotoPick onFile={addPhotos} multiple label="Add photos" className="secondary small" disabled={!!busy} />
        <input ref={videoInput} type="file" accept="video/*" hidden onChange={addVideo} data-source="video" />
        <button type="button" className="secondary small" disabled={!!busy} onClick={() => videoInput.current.click()}>Add a video</button>
      </div>
      {busy && <p className="muted small" role="status">{busy}</p>}
      {media.length === 0 ? <p className="muted small">Targets, your setup, footage from the bench - from your phone.</p> : (
        <ul className="shoot-media">
          {media.map((m, i) => (
            <li key={m.media_id}>
              {m.kind === 'photo'
                ? <button type="button" className="shoot-media-photo" onClick={() => setViewing(i)} aria-label={`Open photo ${m.caption ?? ''}`}>
                  <img src={m.url} alt={m.caption ?? ''} loading="lazy" /></button>
                : <video src={m.url} controls preload="metadata" playsInline />}
              <span className="small">{[m.caption, groupLabel(m.group_id)].filter(Boolean).join(' · ') || (m.kind === 'video' ? m.original_name : '')}</span>
              {m.kind === 'video' && <button type="button" className="plain small" onClick={() => setViewing(i)}>Caption / remove</button>}
            </li>
          ))}
        </ul>
      )}
      {viewing != null && media[viewing] && (
        <MediaViewer m={media[viewing]} groups={s.groups_list} groupLabel={groupLabel} onClose={() => setViewing(null)}
          onSave={async (data) => { onSession(await api.updateShootMedia(media[viewing].media_id, data)) }}
          onDelete={async () => { onSession(await api.deleteShootMedia(media[viewing].media_id)); setViewing(null); changed() }} />
      )}
    </section>
  )
}

function MediaViewer({ m, groups, groupLabel, onSave, onDelete, onClose }) {
  const box = useRef(null)
  const [caption, setCaption] = useState(m.caption ?? '')
  useEffect(() => { box.current?.focus() }, [])
  const keys = (e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
  return (
    <div className="hike-viewer" role="dialog" aria-modal="true" aria-label={m.kind === 'photo' ? 'Photo' : 'Video'} tabIndex={-1} ref={box}
      onKeyDown={keys} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="hike-viewer-card">
        {m.kind === 'photo' ? <img src={m.url} alt={m.caption ?? ''} /> : <video src={m.url} controls playsInline className="shoot-media-big" />}
        <div className="hike-viewer-bar">
          <input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Add a caption" aria-label="Caption"
            onBlur={() => caption !== (m.caption ?? '') && onSave({ caption })} />
          {groups.length > 0 && (
            <select value={m.group_id ?? ''} aria-label="Of which group" onChange={(e) => onSave({ group_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">The whole session</option>
              {groups.map((g) => <option key={g.group_id} value={g.group_id}>{groupLabel(g.group_id)}</option>)}
            </select>
          )}
        </div>
        <div className="button-row">
          <button type="button" className="plain destructive" onClick={onDelete}>Remove</button>
          <span className="spacer" />
          <button type="button" className="secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
