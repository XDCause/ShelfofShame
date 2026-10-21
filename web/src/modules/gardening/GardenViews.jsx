import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { BarList, ColumnChart } from '../../components/charts.jsx'
import Fold from '../../components/Fold.jsx'
import { SproutIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { PhotoViewer, StagePill, daysFrom, dueText, isDue, plantEmoji } from './gardenParts.jsx'
import { TaskRow } from './PlantingPanel.jsx'

// The Gardening hobby's pages: Today (what needs doing, weather tips, what to sow), Plants (a list or a
// timeline), Harvests - and the tile on Home.

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`


// ---------------------------------------------------------------------------------------------
// Today
// ---------------------------------------------------------------------------------------------
export function TodayView() {
  const { refreshKey, openPanel, changed, showToast } = useApp()
  const [t, setT] = useState(null)
  const [sow, setSow] = useState(null)
  const [photos, setPhotos] = useState([])
  const [viewing, setViewing] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    api.gardenToday().then(setT).catch((e) => setError(e.message))
    api.gardenSowNow().then(setSow).catch(() => {})
    api.gardenPhotos({ limit: 12 }).then(setPhotos).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!t) return <p className="muted loading">Loading...</p>
  const careAll = async (action) => {
    const r = await api.gardenCare({ action, all_due: true })
    showToast(`${action === 'watered' ? 'Watered' : 'Fed'} ${plural(r.done, 'plant')}`)
    changed()
  }
  const careOne = async (action, p) => {
    await api.gardenCare({ action, planting_ids: [p.planting_id] })
    changed()
  }
  const fresh = t.growing === 0 && t.planned.length === 0
  return (
    <section className="page garden-today">
      {fresh && (
        <section className="card empty-start">
          <h2 className="home-card-title">Start your apartment garden</h2>
          <ol className="garden-steps">
            <li><strong>Where you grow:</strong> add your balcony, windowsill or shelf - its size and which way it faces.
              <button type="button" className="plain small" onClick={() => openPanel('gspace', {})}>+ Add a space</button></li>
            <li><strong>Your pots:</strong> place them on the <Link to="/gardening/layout">layout</Link>.</li>
            <li><strong>Plants:</strong> add what's growing (the guide fills in watering and when to pick).
              <button type="button" className="plain small" onClick={() => openPanel('planting', {})}>+ Add a plant</button></li>
            <li><strong>Where you are</strong> (below) for weather tips, and your climate for what to sow when.</li>
          </ol>
        </section>
      )}
      <div className="home-grid">
        <div className="home-stack">
          <section className="card home-card">
            <div className="section-head">
              <h2 className="home-card-title">💧 Water today</h2>
              {t.water.length > 1 && <button type="button" className="primary small" onClick={() => careAll('watered')}>Watered all {t.water.length}</button>}
            </div>
            {t.water.length === 0 ? <p className="muted small">Nothing needs water today.</p> : (
              <CareList plants={t.water} due="water_due_on" today={t.today} onDone={(p) => careOne('watered', p)} doneLabel="Watered" />
            )}
          </section>
          {t.feed.length > 0 && (
            <section className="card home-card">
              <div className="section-head">
                <h2 className="home-card-title">🧪 Feed today</h2>
                {t.feed.length > 1 && <button type="button" className="secondary small" onClick={() => careAll('fed')}>Fed all {t.feed.length}</button>}
              </div>
              <CareList plants={t.feed} due="feed_due_on" today={t.today} onDone={(p) => careOne('fed', p)} doneLabel="Fed" />
            </section>
          )}
          {t.harvest.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">✂️ Ready to pick</h2>
              <ul className="list plain-list">{t.harvest.map((p) => <PlantRow key={p.planting_id} p={p} today={t.today} />)}</ul>
            </section>
          )}
          <section className="card home-card">
            <h2 className="home-card-title">Reminders</h2>
            {t.tasks.length === 0 ? <p className="muted small">No reminders due. Add them on a plant or container (e.g. "Feed the worms" every 7 days).</p> : (
              <ul className="garden-tasks">{t.tasks.map((x) => <TaskRow key={x.task_id} t={x} onChanged={changed} showWhat />)}</ul>
            )}
          </section>
          {t.planned.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Planned</h2>
              <ul className="list plain-list">{t.planned.map((p) => <PlantRow key={p.planting_id} p={p} today={t.today} />)}</ul>
            </section>
          )}
        </div>
        <div className="home-stack">
          <Weather w={t.weather} />
          {sow && (
            <section className="card home-card">
              <h2 className="home-card-title">Sow in {sow.month}</h2>
              <p className="muted small">For a {sow.climate.toLowerCase()} climate{sow.now.some((g) => g.fits_spaces.length) && ' - the ones that suit your spaces first'}.</p>
              <ul className="garden-sow-chips">
                {sow.now.slice(0, 24).map((g) => (
                  <li key={g.guide_id}><button type="button" className={`chip-filter${g.fits_spaces.length ? ' fits' : ''}`}
                    onClick={() => openPanel('gguide', { id: g.guide_id })}>{plantEmoji({ name: g.name, kind: g.kind })} {g.name}</button></li>
                ))}
              </ul>
              <Link className="button plain small" to="/gardening/guide">The whole guide →</Link>
            </section>
          )}
          {photos.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Latest photos</h2>
              <ul className="garden-photo-strip">
                {photos.map((p, i) => (
                  <li key={p.photo_id}><button type="button" className="garden-thumb" onClick={() => setViewing(i)}
                    aria-label={`Photo of ${p.planting_name ?? 'the garden'}, ${shortDate(p.happened_on)}`}><img src={p.url} alt="" loading="lazy" /></button></li>
                ))}
              </ul>
            </section>
          )}
          <GardenSettings onSaved={load} />
        </div>
      </div>
      {viewing != null && <PhotoViewer photos={photos} index={viewing} onClose={() => setViewing(null)} />}
    </section>
  )
}

function CareList({ plants, due, today, onDone, doneLabel }) {
  const { openPanel } = useApp()
  return (
    <ul className="list plain-list">
      {plants.map((p) => (
        <li key={p.planting_id} className="garden-care-row">
          <button type="button" className="row-button" onClick={() => openPanel('planting', { id: p.planting_id })}>
            <span className="garden-emoji" aria-hidden="true">{plantEmoji(p)}</span>
            <span className="grow">
              <span className="item-title">{p.name}{p.quantity > 1 && <span className="muted"> ×{p.quantity}</span>}</span>
              <span className="item-meta">{[p.space_name && `${p.space_name} › ${p.container_name}`, `due ${dueText(p[due], today)}`].filter(Boolean).join(' · ')}</span>
            </span>
          </button>
          <button type="button" className="secondary small" onClick={() => onDone(p)}>{doneLabel}</button>
        </li>
      ))}
    </ul>
  )
}

function PlantRow({ p, today }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('planting', { id: p.planting_id })}>
        {p.photo_url ? <img className="thumb" src={p.photo_url} alt="" loading="lazy" /> : <span className="garden-emoji" aria-hidden="true">{plantEmoji(p)}</span>}
        <span className="grow">
          <span className="item-title">{p.name}{p.variety && <span className="muted"> · {p.variety}</span>}</span>
          <span className="item-meta">{[p.container_name ? `${p.space_name} › ${p.container_name}` : 'not in a pot',
            p.quantity > 1 && `×${p.quantity}`, `${p.age_days} days`,
            isDue(p.water_due_on, today) && '💧', p.harvest_ready && '✂️ ready'].filter(Boolean).join(' · ')}</span>
        </span>
        <StagePill stage={p.stage} />
      </button>
    </li>
  )
}

// The next 3 days and what they mean for pots (Open-Meteo), or a prompt to say where you are.
function Weather({ w }) {
  if (!w) return null
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Weather{w.place && ` · ${w.place}`}</h2>
      {w.error && <p className="alert error small">{w.error}</p>}
      {w.days.length > 0 && (
        <ul className="garden-weather">
          {w.days.map((d, i) => (
            <li key={d.day}>
              <strong>{i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : new Date(`${d.day}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'short' })}</strong>
              {d.sky && <span className="garden-sky"><span aria-hidden="true">{d.icon}</span> {d.sky}</span>}
              <span>{Math.round(d.max)}° / {Math.round(d.min)}°</span>
              <span className="muted small">{d.rain_mm ? `${d.rain_mm} mm` : 'dry'}{d.gusts != null && ` · gusts ${Math.round(d.gusts)}`}</span>
            </li>
          ))}
        </ul>
      )}
      {w.tips.map((tip, i) => <p key={i} className={`alert small ${tip.kind === 'rain' ? 'ok' : 'low'}`}><strong>{tip.day}:</strong> {tip.text}</p>)}
      {w.days.length > 0 && w.tips.length === 0 && <p className="muted small">Nothing special for your pots in the next two days.</p>}
      <p className="muted small">Forecast by Open-Meteo (CC BY 4.0).</p>
    </section>
  )
}

// Your climate (for what to sow when) and where you are (for weather tips).
function GardenSettings({ onSaved }) {
  const { refreshKey } = useApp()
  const [s, setS] = useState(null)
  const [lists, setLists] = useState(null)
  const [q, setQ] = useState('')
  const [found, setFound] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.gardenSettings().then(setS).catch(() => {}) }, [refreshKey])
  useEffect(() => { api.gardenLists().then(setLists).catch(() => {}) }, [])
  if (!s || !lists) return null
  const save = async (data) => { setS(await api.saveGardenSettings(data)); onSaved() }
  const search = async (e) => {
    e.preventDefault()
    setError('')
    try { setFound(await api.gardenPlaces(q)) } catch (err) { setError(err.message) }
  }
  return (
    <section className="card home-card">
      <Fold title="Garden settings" detail={[s.climate, s.place_name].filter(Boolean).join(' · ')} open={!s.place_name}>
        <label className="field">Climate (for what to sow when)
          <select value={s.climate} onChange={(e) => save({ climate: e.target.value })}>
            {lists.climates.map((c) => <option key={c} value={c}>{c}{c === 'Subtropical' ? ' (Brisbane, Gold Coast)' : c === 'Temperate' ? ' (Sydney, Melbourne, Perth, Adelaide)'
              : c === 'Tropical' ? ' (Darwin, Cairns)' : c === 'Cool' ? ' (Hobart, Canberra, the mountains)' : ' (inland)'}</option>)}
          </select>
        </label>
        <form className="garden-place" onSubmit={search}>
          <label className="field grow">Where you are (for weather tips)
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={s.place_name ?? 'Your suburb'} />
          </label>
          <button type="submit" className="secondary small" disabled={q.trim().length < 2}>Find</button>
        </form>
        {error && <p className="alert error small">{error}</p>}
        {found && (found.length === 0 ? <p className="muted small">No place by that name.</p> : (
          <ul className="list plain-list">{found.map((p) => (
            <li key={`${p.lat},${p.lon}`}><button type="button" className="row-button" onClick={async () => {
              await save({ place_name: p.name, lat: p.lat, lon: p.lon })
              setFound(null)
              setQ('')
            }}><span className="grow"><span className="item-title">{p.name}</span><span className="item-meta">{p.region}</span></span></button></li>
          ))}</ul>
        ))}
        <p className="muted small">Only the suburb's position is kept (in your database), to ask Open-Meteo for the forecast.</p>
      </Fold>
    </section>
  )
}

// ---------------------------------------------------------------------------------------------
// Plants: a list by space and container, or a timeline
// ---------------------------------------------------------------------------------------------
export function PlantsView() {
  const { refreshKey, openPanel } = useApp()
  const [status, setStatus] = useState('current')
  const [view, setView] = useState('list')
  const [q, setQ] = useState('')
  const [plants, setPlants] = useState(null)
  const [bought, setBought] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    const t = setTimeout(() => api.gardenPlantings({ status, q }).then(setPlants).catch((e) => setError(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [status, q, refreshKey])
  // Seedlings and plants you have (Supplies) that aren't planted yet: some left (qty), or none planted from it.
  useEffect(() => {
    api.gardenItems().then((items) => setBought(items.filter((i) => ['Seedling', 'Plant'].includes(i.kind)
      && ['Have', 'Running low'].includes(i.status) && (i.qty == null ? i.planted === 0 : i.qty > 0)))).catch(() => {})
  }, [refreshKey])
  const waiting = status === 'past' ? [] : bought.filter((i) => !q || i.name.toLowerCase().includes(q.toLowerCase()))
  if (error) return <p className="alert error">{error}</p>
  const today = new Date().toLocaleDateString('en-CA')
  const groups = []
  for (const p of plants ?? []) {
    const key = p.space_name ?? 'Not in a pot yet'
    if (!groups.length || groups.at(-1).key !== key) groups.push({ key, plants: [] })
    groups.at(-1).plants.push(p)
  }
  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search plants..." aria-label="Search plants" />
        <div className="segmented" role="group" aria-label="View">
          <button type="button" aria-pressed={view === 'list'} onClick={() => setView('list')}>List</button>
          <button type="button" aria-pressed={view === 'timeline'} onClick={() => setView('timeline')}>Timeline</button>
        </div>
        <button type="button" className="primary" onClick={() => openPanel('planting', {})}>+ Add plant</button>
      </div>
      <div className="chip-row" role="group" aria-label="Which plants">
        {[['current', 'Growing'], ['past', 'Past'], ['all', 'All']].map(([v, l]) => (
          <button key={v} type="button" className="chip-filter" aria-pressed={status === v} onClick={() => setStatus(v)}>{l}</button>
        ))}
      </div>
      {waiting.length > 0 && <BoughtPlants items={waiting} />}
      {!plants ? <p className="muted loading">Loading...</p> : plants.length === 0 ? (
        waiting.length > 0 ? null :
        q || status !== 'current' ? <p className="empty card">No plants match that.</p> : (
          <EmptyState Icon={SproutIcon} title="Nothing growing yet" action="+ Add a plant" onAction={() => openPanel('planting', {})}>
            Pick from the guide (watering, feeding and when to pick fill in) or add your own.</EmptyState>
        )
      ) : view === 'timeline' ? <Timeline plants={plants} today={today} /> : groups.map((g) => (
        <section key={g.key} className="card home-card garden-group">
          <h2 className="home-card-title">{g.key}</h2>
          <ul className="list plain-list">{g.plants.map((p) => <PlantRow key={p.planting_id} p={p} today={today} />)}</ul>
        </section>
      ))}
    </section>
  )
}

// Bought, not planted yet: Have items from Supplies. "Add to my plants" makes it a plant now (not in a pot yet -
// choose one later); tapping the row opens the item, where "Plant it" picks the pot.
function BoughtPlants({ items }) {
  const { changed, openPanel, showToast } = useApp()
  const add = async (i) => {
    try {
      const p = await api.sowGardenItem(i.item_id, { container_id: null })
      changed()
      openPanel('planting', { id: p.planting_id })
    } catch (e) {
      showToast(e.message)
    }
  }
  return (
    <section className="card home-card garden-group" aria-label="Bought, not planted yet">
      <h2 className="home-card-title">Bought, not planted yet</h2>
      <ul className="list plain-list">{items.map((i) => (
        <li key={i.item_id} className="garden-bought">
          <button type="button" className="row-button" onClick={() => openPanel('gitem', { id: i.item_id })}>
            {i.photo_url ? <img className="thumb" src={i.photo_url} alt="" loading="lazy" />
              : <span className="garden-emoji" aria-hidden="true">{i.kind === 'Plant' ? '🪴' : '🌱'}</span>}
            <span className="grow">
              <span className="item-title">{i.name}</span>
              <span className="item-meta">{[i.kind, i.qty != null && `${i.qty} to plant`, i.guide_name].filter(Boolean).join(' · ')}</span>
            </span>
          </button>
          <button type="button" className="small" onClick={() => add(i)}>Add to my plants</button>
        </li>
      ))}</ul>
    </section>
  )
}

// The first day of each month from `first` to `last` (YYYY-MM-DD).
function monthStarts(first, last) {
  const out = []
  const m = new Date(`${first}T12:00:00`)
  m.setDate(1)
  for (let iso = m.toLocaleDateString('en-CA'); iso <= last; iso = m.toLocaleDateString('en-CA')) {
    if (iso >= first) out.push(iso)
    m.setMonth(m.getMonth() + 1)
  }
  return out
}

// Each plant as a bar from when it started to when it ended (or its harvest window's end), the harvest
// window shaded, today as a line. Months along the top.
function Timeline({ plants, today }) {
  const { openPanel } = useApp()
  const endOf = (p) => p.ended_on ?? p.harvest_to ?? (p.harvest_from && p.harvest_from > today ? p.harvest_from : null) ?? today
  const first = plants.reduce((m, p) => (p.started_on < m ? p.started_on : m), today)
  const last = plants.reduce((m, p) => (endOf(p) > m ? endOf(p) : m), today)
  const span = Math.max(30, daysFrom(first, last) + 7)
  const X = (d) => `${(100 * daysFrom(first, d)) / span}%`
  const W = (a, b) => `${Math.max(0.8, (100 * daysFrom(a, b)) / span)}%`
  const months = monthStarts(first, last)
  return (
    <section className="card garden-timeline" aria-label="Plants over time">
      <div className="garden-timeline-months" aria-hidden="true">
        {months.map((d) => <span key={d} style={{ left: X(d) }}>{new Date(`${d}T12:00:00`).toLocaleDateString('en-AU', { month: 'short' })}</span>)}
      </div>
      <ul>
        {plants.map((p) => (
          <li key={p.planting_id}>
            <button type="button" className="garden-timeline-name" onClick={() => openPanel('planting', { id: p.planting_id })}>
              {plantEmoji(p)} {p.name}</button>
            <span className="garden-timeline-track">
              <span className={`garden-timeline-bar ${p.stage === 'Died' ? 'died' : ''}`} style={{ left: X(p.started_on), width: W(p.started_on, endOf(p)) }}
                title={`${p.name}: ${shortDate(p.started_on)} – ${shortDate(endOf(p))}`} />
              {p.harvest_from && <span className="garden-timeline-harvest" style={{ left: X(p.harvest_from), width: W(p.harvest_from, p.harvest_to ?? endOf(p)) }}
                title={`Harvest: ${shortDate(p.harvest_from)}${p.harvest_to ? ` – ${shortDate(p.harvest_to)}` : ''}`} />}
              <span className="garden-timeline-today" style={{ left: X(today) }} aria-hidden="true" />
            </span>
          </li>
        ))}
      </ul>
      <p className="muted small">Bars run from planting to the end of the harvest window (or when it ended); the darker part is harvest time; the line is today.</p>
    </section>
  )
}

// ---------------------------------------------------------------------------------------------
// Harvests
// ---------------------------------------------------------------------------------------------
export function HarvestsView() {
  const { refreshKey, openPanel } = useApp()
  const [year, setYear] = useState(null)
  const [h, setH] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.gardenHarvests(year).then(setH).catch((e) => setError(e.message)) }, [year, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!h) return <p className="muted loading">Loading...</p>
  const units = [...new Set(h.by_plant.map((x) => x.unit))]
  const main = units.includes('g') ? 'g' : units[0]
  const monthName = (ym) => new Date(`${ym}-15T12:00:00`).toLocaleDateString('en-AU', { month: 'short' })
  const months = Array.from({ length: 12 }, (_, i) => `${h.year}-${String(i + 1).padStart(2, '0')}`)
  return (
    <section className="page">
      <div className="toolbar">
        <p className="summary grow"><strong>{h.harvests.length}</strong> harvest{h.harvests.length === 1 ? '' : 's'} in {h.year}</p>
        <select value={h.year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Year">
          {h.years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>
      {h.harvests.length === 0 ? (
        <EmptyState Icon={SproutIcon} title="Nothing picked yet">
          When you pick something, add a Harvest note on the plant (with how much) - totals and charts show up here.</EmptyState>
      ) : (
        <div className="home-grid">
          <div className="home-stack">
            {main && (
              <section className="card home-card">
                <h2 className="home-card-title">Per month ({main})</h2>
                <ColumnChart title={`Harvested per month (${main})`} valueLabel={main}
                  rows={months.map((m) => ({ label: monthName(m), value: h.by_month.filter((x) => x.month === m && x.unit === main).reduce((a, x) => a + x.amount, 0) }))} />
              </section>
            )}
            {units.map((u) => (
              <section key={u} className="card home-card">
                <h2 className="home-card-title">By plant ({u})</h2>
                <BarList title={`Harvested by plant (${u})`} valueLabel={u} rows={h.by_plant.filter((x) => x.unit === u).map((x) => ({ label: x.name, value: x.amount }))} />
              </section>
            ))}
          </div>
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Every harvest</h2>
              <ul className="list plain-list">
                {h.harvests.map((x) => (
                  <li key={x.log_id}>
                    <button type="button" className="row-button" onClick={() => openPanel('planting', { id: x.planting_id })}>
                      {x.photos[0] ? <img className="thumb" src={x.photos[0].url} alt="" loading="lazy" /> : <span className="garden-emoji" aria-hidden="true">{plantEmoji({ name: x.planting_name })}</span>}
                      <span className="grow">
                        <span className="item-title">{x.planting_name}{x.amount != null && <span className="muted"> · {x.amount.toLocaleString()} {x.unit}</span>}</span>
                        <span className="item-meta">{[shortDate(x.happened_on), x.text].filter(Boolean).join(' · ')}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      )}
    </section>
  )
}
