import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { SproutIcon } from '../../components/icons.jsx'
import { CONTAINER_EMOJI, CareButtons, LogForm, LogTimeline, isDue, localToday, plantEmoji } from './gardenParts.jsx'

// The layout: each space (balcony, windowsill...) drawn to scale from above, with its open side (the
// railing or window - where the sun comes from) and a compass arrow; each container where it sits, with
// what's growing in it and what it needs (💧 water, ✂️ ready to pick, ⚠ worth a look). Drag a container
// to move it, drag its corner to resize it, or use the arrow keys; tap it to open it. Sizes are in cm.

const SNAP = 5
const snap = (v) => Math.round(v / SNAP) * SNAP
const SIDE_ANGLE = { top: 0, right: 90, bottom: 180, left: 270 }
const BEARING = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 }
const FACING_NAME = { N: 'north', NE: 'north-east', E: 'east', SE: 'south-east', S: 'south', SW: 'south-west', W: 'west', NW: 'north-west' }

export function LayoutView() {
  const { refreshKey, openPanel } = useApp()
  const [spaces, setSpaces] = useState(null)
  const [spaceId, setSpaceId] = useState(() => Number(new URLSearchParams(window.location.search).get('space')) || null)
  const [space, setSpace] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.gardenSpaces().then(setSpaces).catch((e) => setError(e.message)) }, [refreshKey])
  const chosen = spaces?.find((s) => s.space_id === spaceId) ?? spaces?.[0]
  const reload = useCallback(() => {
    if (chosen) api.gardenSpace(chosen.space_id).then(setSpace).catch((e) => setError(e.message))
  }, [chosen])
  useEffect(() => { reload() }, [reload, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!spaces) return <p className="muted loading">Loading...</p>
  if (spaces.length === 0) {
    return (
      <section className="page">
        <EmptyState Icon={SproutIcon} title="Map your growing spaces" action="+ Add a space" onAction={() => openPanel('gspace', {})}>
          Start with your balcony, a windowsill or a shelf: its size and which way it faces. Then place your pots on it to scale.</EmptyState>
      </section>
    )
  }
  return (
    <section className="page garden-layout-page">
      <div className="toolbar">
        <div className="chip-row scroll grow" role="group" aria-label="Space">
          {spaces.map((s) => (
            <button key={s.space_id} type="button" className="chip-filter" aria-pressed={s.space_id === chosen?.space_id}
              onClick={() => setSpaceId(s.space_id)}>{s.name} <span className="chip-count">{s.plants}</span></button>
          ))}
        </div>
        <button type="button" className="secondary" onClick={() => openPanel('gspace', {})}>+ Space</button>
        {chosen && <button type="button" className="primary" onClick={() => openPanel('gcontainerform', { spaceId: chosen.space_id })}>+ Container</button>}
      </div>
      {space && space.space_id === chosen?.space_id && (
        <div className="garden-layout">
          <Plan space={space} onChanged={reload} />
          <SpaceSide space={space} onChanged={reload} />
        </div>
      )}
    </section>
  )
}

// The space to scale, and its containers.
function Plan({ space, onChanged }) {
  const { openPanel, showToast } = useApp()
  const wrap = useRef(null)
  const [width, setWidth] = useState(600)
  const [pots, setPots] = useState(space.containers)
  const drag = useRef(null)
  useEffect(() => { setPots(space.containers) }, [space])
  useEffect(() => {
    const el = wrap.current
    if (!el) return undefined
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // (the plan has a 26px margin each side for the railing / window label: it fits the space left, not the whole width)
  const scale = Math.max(0.1, Math.min((width - 52) / space.width_cm, 520 / space.depth_cm))
  const px = (cm) => cm * scale
  const today = localToday()

  const save = async (c, data) => {
    try {
      const saved = await api.updateGardenContainer(c.container_id, data)
      setPots((ps) => ps.map((p) => (p.container_id === c.container_id ? { ...p, ...pick(saved) } : p)))
    } catch (e) {
      showToast(e.message)
      onChanged()
    }
  }
  const pick = (c) => ({ x_cm: c.x_cm, y_cm: c.y_cm, width_cm: c.width_cm, depth_cm: c.depth_cm })
  const start = (e, c, mode) => {
    e.stopPropagation()
    e.currentTarget.setPointerCapture?.(e.pointerId)
    drag.current = { id: c.container_id, mode, x: e.clientX, y: e.clientY, from: pick(c), moved: false }
  }
  const move = (e) => {
    const d = drag.current
    if (!d) return
    const dx = (e.clientX - d.x) / scale
    const dy = (e.clientY - d.y) / scale
    if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 4) d.moved = true
    if (!d.moved) return
    setPots((ps) => ps.map((p) => {
      if (p.container_id !== d.id) return p
      if (d.mode === 'move') {
        return { ...p, x_cm: Math.max(0, Math.min(space.width_cm - p.width_cm, snap(d.from.x_cm + dx))),
          y_cm: Math.max(0, Math.min(space.depth_cm - p.depth_cm, snap(d.from.y_cm + dy))) }
      }
      return { ...p, width_cm: Math.max(10, Math.min(space.width_cm - p.x_cm, snap(d.from.width_cm + dx))),
        depth_cm: Math.max(10, Math.min(space.depth_cm - p.y_cm, snap(d.from.depth_cm + dy))) }
    }))
  }
  const end = (c) => {
    const d = drag.current
    drag.current = null
    if (!d || d.id !== c.container_id) return
    if (!d.moved) { if (d.mode === 'move') openPanel('gcontainer', { id: c.container_id }); return }
    const now = pots.find((p) => p.container_id === c.container_id)
    save(c, d.mode === 'move' ? { x_cm: now.x_cm, y_cm: now.y_cm } : { width_cm: now.width_cm, depth_cm: now.depth_cm })
  }
  const keys = (e, c) => {
    const step = e.shiftKey ? 20 : SNAP
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key]
    if (!delta) return
    e.preventDefault()
    const x = Math.max(0, Math.min(space.width_cm - c.width_cm, c.x_cm + delta[0]))
    const y = Math.max(0, Math.min(space.depth_cm - c.depth_cm, c.y_cm + delta[1]))
    setPots((ps) => ps.map((p) => (p.container_id === c.container_id ? { ...p, x_cm: x, y_cm: y } : p)))
    save(c, { x_cm: x, y_cm: y })
  }
  const north = space.facing ? SIDE_ANGLE[space.open_side] - BEARING[space.facing] : null
  const sunText = [space.facing && `faces ${FACING_NAME[space.facing]}`, space.sun_hours != null && `☀ ${space.sun_hours} h sun`].filter(Boolean).join(' · ')
  return (
    <div className="garden-plan-wrap" ref={wrap}>
      <div className={`garden-plan open-${space.open_side}`} style={{ width: px(space.width_cm), height: px(space.depth_cm), '--grid': `${px(50)}px` }}
        onPointerMove={move} aria-label={`${space.name}, ${space.width_cm} by ${space.depth_cm} cm`} role="group">
        <span className={`garden-open-side side-${space.open_side}`}>
          <span>{space.kind === 'Windowsill' || space.kind === 'Indoor' ? 'Window' : 'Railing'}{sunText && ` · ${sunText}`}</span>
        </span>
        {north != null && (
          <span className="garden-compass" style={{ transform: `rotate(${north}deg)` }} title="North" aria-hidden="true"><span>N</span></span>
        )}
        {pots.map((c) => {
          const plants = c.plantings
          const thirsty = plants.some((p) => isDue(p.water_due_on, today))
          const ready = plants.some((p) => p.harvest_ready)
          const warn = plants.some((p) => p.warnings?.length)
          const label = `${c.name}: ${plants.length ? plants.map((p) => p.name).join(', ') : 'empty'}${thirsty ? ', needs water' : ''}${ready ? ', ready to pick' : ''}`
          // a pot drawn to scale on a phone can be tiny: never smaller than a finger's tap (28px), and its level
          // ("Railing") only where there's room for it beside the name
          const [w, h] = [Math.max(px(c.width_cm), 28), Math.max(px(c.depth_cm), 28)]
          return (
            <button key={c.container_id} type="button" aria-label={label}
              className={['garden-pot', c.shape, thirsty && 'thirsty', ready && 'ready'].filter(Boolean).join(' ')}
              style={{ left: px(c.x_cm), top: px(c.y_cm), width: w, height: h }}
              onPointerDown={(e) => start(e, c, 'move')} onPointerUp={() => end(c)} onKeyDown={(e) => keys(e, c)}
              onClick={(e) => { if (e.detail === 0) openPanel('gcontainer', { id: c.container_id }) }}>
              <span className="garden-pot-plants" aria-hidden="true">
                {plants.length ? plants.slice(0, 4).map((p) => <span key={p.planting_id}>{plantEmoji(p)}</span>) : (CONTAINER_EMOJI[c.kind] ?? '')}
                {plants.length > 4 && <small>+{plants.length - 4}</small>}
              </span>
              <span className="garden-pot-name">{c.name}</span>
              <span className="garden-pot-flags" aria-hidden="true">{thirsty && '💧'}{ready && '✂️'}{warn && '⚠️'}</span>
              {c.level !== 'Floor' && h >= 48 && w >= 60 && <span className="garden-pot-level">{c.level}</span>}
              <span className="garden-pot-resize" onPointerDown={(e) => start(e, c, 'size')} onPointerUp={() => end(c)} aria-hidden="true" />
            </button>
          )
        })}
      </div>
      <p className="muted small garden-plan-help">Grid squares are 50 cm. Drag a container to move it, drag its corner to resize it
        (or select it and use the arrow keys); tap it to open it. 💧 needs water · ✂️ ready to pick · ⚠️ worth a look.</p>
    </div>
  )
}

// Beside the plan: the space's facts, weight on it, and what to do for all of it at once.
function SpaceSide({ space: s, onChanged }) {
  const { openPanel } = useApp()
  const load = s.max_load_kg ? Math.min(100, Math.round((100 * s.load_kg) / s.max_load_kg)) : null
  return (
    <aside className="garden-layout-side card">
      <h2 className="home-card-title">{s.name}</h2>
      <dl className="garden-facts">
        <dt>Size</dt><dd>{(s.width_cm / 100).toFixed(1)} × {(s.depth_cm / 100).toFixed(1)} m</dd>
        {s.facing && <><dt>Faces</dt><dd>{FACING_NAME[s.facing]}{s.sun_hours != null && ` · about ${s.sun_hours} h of sun`}</dd></>}
        {s.grow_light && <><dt>Grow light</dt><dd>{s.light_hours ?? '?'} h a day</dd></>}
        <dt>Rain</dt><dd>{s.covered ? 'Covered' : 'Open to the rain'} · {s.wind.toLowerCase()}</dd>
        <dt>Growing</dt><dd>{s.plants} plant{s.plants === 1 ? '' : 's'} in {s.containers.length} container{s.containers.length === 1 ? '' : 's'}</dd>
        <dt>Weight</dt><dd>about {s.load_kg} kg of wet mix{s.max_load_kg ? ` of ${s.max_load_kg} kg` : ''}</dd>
      </dl>
      {load != null && (
        <span className={`garden-load${load >= 80 ? ' heavy' : ''}`} role="img" aria-label={`${load}% of the weight limit`}><span style={{ width: `${load}%` }} /></span>
      )}
      {load >= 80 && <p className="alert low small">Getting heavy for this space: check with your building before adding more big pots.</p>}
      {s.plants > 0 && <CareButtons spaceId={s.space_id} onDone={onChanged} />}
      <div className="button-row">
        <button type="button" className="plain small" onClick={() => openPanel('gspace', { id: s.space_id })}>Edit space</button>
      </div>
      {s.notes && <p className="small garden-notes">{s.notes}</p>}
      <Fold title="Notes and photos" detail={s.logs.length || null}>
        <LogForm about={{ space_id: s.space_id }} kinds={['Note', 'Photo', 'Pest', 'Problem', 'Measured']} onSaved={onChanged} />
        <LogTimeline logs={s.logs} onChanged={onChanged} />
      </Fold>
    </aside>
  )
}
