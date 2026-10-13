import { useEffect, useState } from 'react'
import { api, money, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import RecordFields, { RowPhoto, useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { useNewPage } from '../../core/journal/JournalList.jsx'

const GAME_FIELDS = [
  { name: 'played_on', label: 'Day', type: 'date', required: true },
  { name: 'opponent', label: 'Against', placeholder: 'the other team' },
  { name: 'sets_won', label: 'Sets you won', type: 'number' },
  { name: 'sets_lost', label: 'Sets you lost', type: 'number' },
  { name: 'team', label: 'Your team' },
  { name: 'venue', label: 'Where' },
  { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'How it went, what to work on' },
]
const GEAR_FIELDS = [
  { name: 'name', label: 'Name', required: true, wide: true, placeholder: 'e.g. Court shoes' },
  { name: 'kind', label: 'Kind', list: 'gear-kinds', placeholder: 'Shoes, Knee pads, Ball...' },
  { name: 'brand', label: 'Brand' },
  { name: 'size', label: 'Size' },
  { name: 'purchase_date', label: 'Bought on', type: 'date' },
  { name: 'price_paid', label: 'Price paid', type: 'money' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]
const GEAR_KINDS = ['Shoes', 'Knee pads', 'Ball', 'Clothing', 'Bag', 'Ankle brace', 'Water bottle']
export const VIDEO_TOPICS = ['Highlights', 'Full game', 'Serving', 'Passing', 'Setting', 'Attacking', 'Blocking', 'Defence']

// "Won 3-1", "Lost 0-3", or nothing before the result's in.
export const score = (g) => (g.sets_won == null || g.sets_lost == null ? '' : `${g.result} ${g.sets_won}–${g.sets_lost}`)
export const resultTone = (r) => ({ Won: 'ok', Lost: 'out', Drew: 'low' }[r] ?? 'tint')
export const gameTitle = (g) => (g.kind === 'Training' ? 'Training' : g.opponent ? `vs ${g.opponent}` : g.kind)

// The video's YouTube id, for its thumbnail (other links get an icon).
export const youtubeId = (url) =>
  url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/))([\w-]{11})/)?.[1] ?? null

// A form panel shared by the three: fields + Save, and Delete when editing.
function FormPanel({ title, fields, record, defaults, before, children, onSave, onDelete, onClose, saveLabel }) {
  const { form, set, payload } = useRecordForm(fields, record, defaults)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onSave(payload())
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  const footer = confirmDelete ? (
    <span className="confirm">
      Delete it?
      <button type="button" className="danger" onClick={() => onDelete().catch((e) => setError(e.message))}>Delete</button>
      <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="save" type="submit" form="vb-form" className="primary" disabled={busy}>{saveLabel ?? 'Save'}</button>
      <button key="cancel" type="button" className="plain" onClick={onClose}>Cancel</button>
      {onDelete && <><span className="spacer" />
        <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>Delete</button></>}
    </>
  )
  return (
    <Drawer title={title} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      {before}
      <form id="vb-form" onSubmit={submit}>{children?.({ form, set })}<RecordFields fields={fields} form={form} set={set} /></form>
    </Drawer>
  )
}

// A game or training: the result, notes, its videos. New ones can come from a calendar event
// (eventId + day + title): the calendar then knows that day's result is in.
export function VolleyballGamePanel({ id = null, eventId = null, day = null, onClose }) {
  const { lookups, changed, showToast, openPanel } = useApp()
  const newPage = useNewPage()
  const [game, setGame] = useState(null)
  const [kind, setKind] = useState('Game')
  useEffect(() => {
    if (id != null) api.getVolleyball(id).then((g) => { setGame(g); setKind(g.kind) }).catch((e) => showToast(e.message))
  }, [id, showToast])
  if (id != null && !game) return <Drawer title="Volleyball" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  const save = async (data) => {
    const body = { ...data, kind }
    const saved = game ? await api.updateVolleyball(game.game_id, body)
      : await api.addVolleyball({ ...body, event_id: eventId })
    changed()
    showToast(game ? 'Saved' : `Logged: ${kind === 'Training' ? 'training' : gameTitle(saved)}${score(saved) ? ` · ${score(saved)}` : ''}`)
    onClose()
  }
  const write = async () => {
    await newPage({ title: `Volleyball ${gameTitle(game)}`, entry_date: game.played_on })
    onClose()
  }

  return (
    <FormPanel title={game ? `Volleyball ${gameTitle(game)}` : 'Log volleyball'} fields={GAME_FIELDS} record={game}
      defaults={{ played_on: day ?? today() }} onClose={onClose} onSave={save} saveLabel={game ? 'Save' : 'Log it'}
      onDelete={game && (async () => { await api.deleteVolleyball(game.game_id); changed(); onClose() })}
      before={game && (
        <section className="panel-section">
          <div className="button-row">
            {score(game) && <span className={`pill ${resultTone(game.result)}`}>{score(game)}</span>}
            {game.event_title && <span className="muted small">From the calendar: {game.event_title}</span>}
            <span className="spacer" />
            <button type="button" className="plain small" onClick={write}>+ Write about it</button>
          </div>
          {game.video_list.length > 0 && (
            <ul className="list compact">
              {game.video_list.map((v) => (
                <li key={v.video_id}><a className="row-button" href={v.url} target="_blank" rel="noreferrer">
                  <span className="grow item-title">{v.title}</span><span className="muted small">{v.topic} ↗</span></a></li>
              ))}
            </ul>
          )}
          <button type="button" className="plain small" onClick={() => openPanel('video', { gameId: game.game_id })}>+ Add a video of it</button>
        </section>
      )}>
      {() => (
        <div className="segmented form-segmented" role="group" aria-label="Kind">
          {lookups.volleyball_kinds.map((k) => (
            <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{k}</button>
          ))}
        </div>
      )}
    </FormPanel>
  )
}

// One piece of gear: photo, condition (tap to change), details, journal pages about it.
export function GearPanel({ id = null, onClose }) {
  const { lookups, changed, showToast } = useApp()
  const [gear, setGear] = useState(null)
  const [condition, setCondition] = useState('Good')
  const reload = async () => { const g = await api.getGear(id); setGear(g); setCondition(g.condition) }
  useEffect(() => { if (id != null) reload().catch((e) => showToast(e.message)) }, [id])
  if (id != null && !gear) return <Drawer title="Gear" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  const save = async (data) => {
    const body = { ...data, condition }
    if (gear) await api.updateGear(gear.gear_id, body)
    else await api.addGear(body)
    changed()
    showToast(gear ? 'Saved' : `Added ${body.name} to your gear`)
    onClose()
  }
  return (
    <FormPanel title={gear ? gear.name : 'Add gear'} fields={GEAR_FIELDS} record={gear} onClose={onClose} onSave={save}
      saveLabel={gear ? 'Save' : 'Add gear'}
      onDelete={gear && (async () => { await api.deleteGear(gear.gear_id); changed(); onClose() })}
      before={gear && (
        <div className="item-hero">
          <RowPhoto path={`/gear/${gear.gear_id}`} url={gear.photo_url}
            onChanged={(msg) => { reload(); changed(); showToast(msg) }} />
          <div>
            <h3 className="item-name">{gear.name}</h3>
            <p className="item-sub">{[gear.kind, gear.brand, gear.size].filter(Boolean).join(' · ')}</p>
            {gear.price_paid != null && <span className="chip">{money(gear.price_paid)}</span>}
            {gear.purchase_date && <span className="muted small"> Bought {shortDate(gear.purchase_date)}</span>}
          </div>
        </div>
      )}>
      {() => (
        <>
          <datalist id="gear-kinds">{GEAR_KINDS.map((k) => <option key={k} value={k} />)}</datalist>
          <p className="field-label">Condition</p>
          <div className="condition-picker" role="group" aria-label="Condition">
            {lookups.gear_conditions.map((c) => (
              <button key={c} type="button" aria-pressed={condition === c} className={c === 'Needs replacing' ? 'warn' : ''}
                onClick={() => setCondition(c)}>{c}</button>
            ))}
          </div>
          {gear && <JournalMentions kind="gear" id={gear.gear_id} name={gear.name} onLeave={onClose} />}
        </>
      )}
    </FormPanel>
  )
}

// A video link: a game's footage or a drill to learn from.
export function VideoPanel({ id = null, gameId = null, onClose }) {
  const { changed, showToast } = useApp()
  const [video, setVideo] = useState(null)
  const [games, setGames] = useState([])
  useEffect(() => {
    api.listVolleyball().then(setGames).catch(() => {})
    if (id != null) api.listVideos().then((vs) => setVideo(vs.find((v) => v.video_id === id))).catch((e) => showToast(e.message))
  }, [id, showToast])
  if (id != null && !video) return <Drawer title="Video" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  const fields = [
    { name: 'title', label: 'Title', required: true, wide: true, placeholder: 'e.g. Float serve drill' },
    { name: 'url', label: 'Link', type: 'url', required: true, wide: true, placeholder: 'https://youtu.be/...' },
    { name: 'topic', label: 'Topic', list: 'video-topics' },
    { name: 'game_id', label: 'From the game', type: 'select',
      options: games.filter((g) => g.kind !== 'Training').map((g) => [String(g.game_id), `${shortDate(g.played_on)} ${gameTitle(g)}`]) },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const save = async (data) => {
    if (video) await api.updateVideo(video.video_id, data)
    else await api.addVideo(data)
    changed()
    showToast(video ? 'Saved' : `Added ${data.title}`)
    onClose()
  }
  return (
    <FormPanel key={games.length} title={video ? video.title : 'Add a video'} fields={fields} record={video}
      defaults={{ game_id: gameId ?? '' }} onClose={onClose} onSave={save} saveLabel={video ? 'Save' : 'Add video'}
      onDelete={video && (async () => { await api.deleteVideo(video.video_id); changed(); onClose() })}>
      {() => <datalist id="video-topics">{VIDEO_TOPICS.map((t) => <option key={t} value={t} />)}</datalist>}
    </FormPanel>
  )
}
