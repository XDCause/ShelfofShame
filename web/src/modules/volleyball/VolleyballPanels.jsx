import { useCallback, useEffect, useState } from 'react'
import { api, fileSize, money, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import PhotoPick from '../../components/PhotoPick.jsx'
import RecordFields, { RowPhoto, useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { useNewPage } from '../../core/journal/JournalList.jsx'

// The game form: your team is picked from your registered teams; Against and Where suggest what
// you've typed before (datalists vb-opponents / vb-venues).
const gameFields = (teams) => [
  { name: 'played_on', label: 'Day', type: 'date', required: true },
  { name: 'team_id', label: 'Your team', type: 'select', options: teams.map((t) => [String(t.team_id), t.name]) },
  { name: 'opponent', label: 'Against', placeholder: 'the other team', list: 'vb-opponents' },
  { name: 'venue', label: 'Where', list: 'vb-venues' },
  { name: 'sets_won', label: 'Sets you won', type: 'number' },
  { name: 'sets_lost', label: 'Sets you lost', type: 'number' },
  { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'How it went, what to work on' },
]
const BYE_HIDES = ['opponent', 'sets_won', 'sets_lost']   // a bye has no opponent or sets
const TEAM_FIELDS = [
  { name: 'name', label: 'Team name', required: true, wide: true },
  { name: 'location', label: 'Where they play', wide: true, list: 'vb-venues', placeholder: 'e.g. Somerville House Aquatic Centre' },
  { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Competition, night, captain...' },
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
const VIDEO_TOPICS = ['Highlights', 'Full game', 'Serving', 'Passing', 'Setting', 'Attacking', 'Blocking', 'Defence']

// "Won 3-1", "Lost 0-3", "Bye – win", or nothing before the result's in.
export const score = (g) => (g.bye ? BYES[g.bye]
  : g.sets_won == null || g.sets_lost == null ? '' : `${g.result} ${g.sets_won}–${g.sets_lost}`)
const BYES = { win: 'Bye – win', 'no result': 'Bye – no result' }
export const resultTone = (r) => ({ Won: 'ok', Lost: 'out', Drew: 'low' }[r] ?? 'tint')
export const gameTitle = (g) => (g.bye ? 'Bye' : g.kind === 'Training' ? 'Training' : g.opponent ? `vs ${g.opponent}` : g.kind)

// The video's YouTube id, for its thumbnail (other links get an icon).
export const youtubeId = (url) =>
  url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/))([\w-]{11})/)?.[1] ?? null

// A form panel shared by them all: fields + Save, and Delete when editing. onField(name, value,
// setForm) hears every change (the game form fills Where when the team changes).
function FormPanel({ title, fields, record, defaults, before, children, onSave, onDelete, onClose, saveLabel, onField, deleteLabel }) {
  const { form, set: setField, setForm, payload } = useRecordForm(fields, record, defaults)
  const set = (name) => (e) => { setField(name)(e); onField?.(name, e.target.value, setForm) }
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
      {deleteLabel ?? 'Delete'} it?
      <button type="button" className="danger" onClick={() => onDelete().catch((e) => setError(e.message))}>{deleteLabel ?? 'Delete'}</button>
      <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="save" type="submit" form="vb-form" className="primary" disabled={busy}>{saveLabel ?? 'Save'}</button>
      <button key="cancel" type="button" className="plain" onClick={onClose}>Cancel</button>
      {onDelete && <><span className="spacer" />
        <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>{deleteLabel ?? 'Delete'}</button></>}
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
// (eventId + day + its location as venue): the calendar then knows that day's result is in.
// A new one starts filled in: your default team (else your last game's), its location, the kind
// you logged last.
export function VolleyballGamePanel({ id = null, eventId = null, day = null, venue = null, onClose }) {
  const { lookups, changed, showToast, openPanel } = useApp()
  const newPage = useNewPage()
  const [game, setGame] = useState(null)
  const [kind, setKind] = useState('Game')
  const [bye, setBye] = useState(null)        // null = played; 'win' / 'no result' = a bye
  const [teams, setTeams] = useState(null)
  useEffect(() => {
    if (id != null) api.getVolleyball(id).then((g) => { setGame(g); setKind(g.kind); setBye(g.bye) }).catch((e) => showToast(e.message))
  }, [id, showToast])
  useEffect(() => {
    api.volleyballTeams().then((t) => { setTeams(t); if (id == null) setKind(t.defaults.kind) }).catch((e) => showToast(e.message))
  }, [id, showToast])
  if ((id != null && !game) || !teams) return <Drawer title="Volleyball" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  // Current teams, plus this game's own team if it's since been retired.
  const choices = teams.teams.filter((t) => !t.retired || t.team_id === game?.team_id)
  const locationOf = (teamId) => teams.teams.find((t) => String(t.team_id) === String(teamId))?.location ?? ''
  // A new team picked: Where follows it, unless you'd typed somewhere else.
  const onField = (name, value, setForm) => {
    if (name !== 'team_id') return
    setForm((f) => (!f.venue || teams.venues.includes(f.venue) || f.venue === locationOf(f.team_id)
      ? { ...f, venue: locationOf(value) || f.venue } : f))
  }

  const save = async (data) => {
    const body = { ...data, kind, bye: kind === 'Training' ? null : bye }
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
    <FormPanel title={game ? `Volleyball ${gameTitle(game)}` : 'Log volleyball'} fields={gameFields(choices).filter((f) => !(bye && kind !== 'Training' && BYE_HIDES.includes(f.name)))} record={game}
      defaults={{ played_on: day ?? today(), team_id: teams.defaults.team_id, venue: venue || teams.defaults.venue }}
      onField={onField} onClose={onClose} onSave={save} saveLabel={game ? 'Save' : 'Log it'}
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
        <>
          <div className="segmented form-segmented" role="group" aria-label="Kind">
            {lookups.volleyball_kinds.map((k) => (
              <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{k}</button>
            ))}
          </div>
          {kind !== 'Training' && (
            <div className="segmented form-segmented bye-picker" role="group" aria-label="Played or a bye">
              {[[null, 'Played'], ['win', 'Bye – win'], ['no result', 'Bye – no result']].map(([b, label]) => (
                <button key={label} type="button" aria-pressed={bye === b} onClick={() => setBye(b)}>{label}</button>
              ))}
            </div>
          )}
          {bye && kind !== 'Training' && <p className="hint">{bye === 'win'
            ? 'No game this round, counted as a win (as the ladder does).' : 'No game this round, and no result.'}</p>}
          <datalist id="vb-opponents">{teams.opponents.map((o) => <option key={o} value={o} />)}</datalist>
          <datalist id="vb-venues">{teams.venues.map((v) => <option key={v} value={v} />)}</datalist>
          {choices.length === 0 && (
            <p className="hint">Tip: add your team (Volleyball → Games → Teams) with where it plays, and new games start with both filled in.</p>
          )}
        </>
      )}
    </FormPanel>
  )
}

// One piece of gear: photo, condition (tap to change), details, journal pages about it.
export function GearPanel({ id = null, onClose }) {
  const { lookups, changed, showToast } = useApp()
  const [gear, setGear] = useState(null)
  const [condition, setCondition] = useState('Good')
  const reload = useCallback(async () => {
    const g = await api.getGear(id)
    setGear(g)
    setCondition(g.condition)
  }, [id])
  useEffect(() => { if (id != null) reload().catch((e) => showToast(e.message)) }, [id, reload, showToast])
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
  const [file, setFile] = useState(null)          // a video picked to upload (new, or to replace the one there)
  const [asLink, setAsLink] = useState(false)     // add a link instead (YouTube...)
  const [progress, setProgress] = useState(null)  // 0-1 while uploading
  useEffect(() => {
    api.listVolleyball().then(setGames).catch(() => {})
    if (id != null) {
      api.listVideos().then((vs) => { const v = vs.find((x) => x.video_id === id); setVideo(v); setAsLink(Boolean(v?.url)) })
        .catch((e) => showToast(e.message))
    }
  }, [id, showToast])
  if (id != null && !video) return <Drawer title="Video" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  const fields = [
    { name: 'title', label: 'Title', wide: true, placeholder: file ? file.name.replace(/\.[^.]+$/, '') : 'e.g. Float serve drill' },
    ...(asLink ? [{ name: 'url', label: 'Link', type: 'url', required: true, wide: true, placeholder: 'https://youtu.be/...' }] : []),
    { name: 'topic', label: 'Topic', list: 'video-topics' },
    { name: 'game_id', label: 'From the game', type: 'select',
      options: games.filter((g) => g.kind !== 'Training').map((g) => [String(g.game_id), `${shortDate(g.played_on)} ${gameTitle(g)}`]) },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const save = async (data) => {
    if (!video && !asLink && !file) throw new Error('Choose a video to upload first.')
    const body = { ...data, title: data.title || file?.name.replace(/\.[^.]+$/, '') || 'Video' }
    const saved = video ? await api.updateVideo(video.video_id, body) : await api.addVideo(body)
    if (file) {
      setProgress(0)
      try {
        await api.uploadVideo(saved.video_id, file, setProgress)
      } catch (e) {
        setProgress(null)
        if (!video) await api.deleteVideo(saved.video_id).catch(() => {})   // don't leave an empty video behind
        throw e
      }
    }
    changed()
    showToast(video ? 'Saved' : `Added ${body.title}`)
    onClose()
  }
  const picker = (
    <section className="panel-section video-pick">
      {!asLink && (
        <>
          <PhotoPick accept="video/*" label={video?.file_url ? 'Replace the video' : 'Choose a video'} cameraLabel="Record video"
            galleryLabel="Choose video" onFile={setFile} disabled={progress != null} />
          {file && <p className="small">{file.name} · {fileSize(file.size)}</p>}
        </>
      )}
      {progress != null && (
        <p className="small upload-progress" role="status">
          Uploading {Math.round(progress * 100)}% · {fileSize(progress * file.size)} of {fileSize(file.size)}
          <span className="fill-bar tint"><span style={{ width: `${progress * 100}%` }} /></span>
        </p>
      )}
      {!video && progress == null && (
        <button type="button" className="plain small" onClick={() => { setAsLink(!asLink); setFile(null) }}>
          {asLink ? 'Upload a video instead' : 'Or add a link (YouTube...)'}</button>
      )}
    </section>
  )
  return (
    <FormPanel title={video ? video.title : 'Add a video'} fields={fields} record={video}
      defaults={{ game_id: gameId ?? '' }} onClose={onClose} onSave={save}
      saveLabel={progress != null ? 'Uploading...' : video ? 'Save' : 'Add video'}
      onDelete={video && (async () => { await api.deleteVideo(video.video_id); changed(); onClose() })}
      before={<>
        {video?.file_url && (
          <section className="panel-section">
            <video className="video-player" src={video.file_url} controls playsInline preload="metadata" />
            <p className="muted small">{[video.original_name, video.file_size && fileSize(video.file_size)].filter(Boolean).join(' · ')}</p>
          </section>
        )}
        {video?.url && !video.file_url && <p className="panel-section"><a href={video.url} target="_blank" rel="noreferrer">Open the link ↗</a></p>}
        {picker}
      </>}>
      {() => <datalist id="video-topics">{VIDEO_TOPICS.map((t) => <option key={t} value={t} />)}</datalist>}
    </FormPanel>
  )
}

// A team you play in: its name, where it plays, and whether new games start with it. A team with
// games logged is retired rather than deleted, so those games keep its name.
export function TeamPanel({ id = null, onClose }) {
  const { changed, showToast } = useApp()
  const [data, setData] = useState(null)
  const [isDefault, setIsDefault] = useState(false)
  const [retired, setRetired] = useState(false)
  useEffect(() => {
    api.volleyballTeams().then((d) => {
      setData(d)
      const team = d.teams.find((x) => x.team_id === id)
      setIsDefault(team ? team.is_default : d.teams.every((x) => x.retired))   // your first team: the default
      setRetired(team?.retired ?? false)
    }).catch((e) => showToast(e.message))
  }, [id, showToast])
  if (!data) return <Drawer title="Team" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const team = data.teams.find((x) => x.team_id === id) ?? null

  const save = async (form) => {
    const body = { ...form, is_default: isDefault && !retired, ...(team && { retired }) }
    const saved = team ? await api.updateTeam(team.team_id, body) : await api.addTeam(body)
    changed()
    showToast(team ? `${saved.name} saved` : `Added ${saved.name}`)
    onClose()
  }
  const remove = team && (team.games ? async () => {
    await api.updateTeam(team.team_id, { retired: true })
    changed()
    showToast(`${team.name} retired`)
    onClose()
  } : async () => {
    await api.deleteTeam(team.team_id)
    changed()
    onClose()
  })
  return (
    <FormPanel title={team ? team.name : 'Add a team'} fields={TEAM_FIELDS} record={team} onClose={onClose} onSave={save}
      saveLabel={team ? 'Save' : 'Add team'} onDelete={team && !team.retired ? remove : null}
      deleteLabel={team?.games ? 'Retire' : 'Delete'}
      before={team && <p className="muted small panel-section">{team.games ? `${team.games} game${team.games === 1 ? '' : 's'} logged` : 'No games yet'}
        {team.last_played && ` · last played ${shortDate(team.last_played)}`}</p>}>
      {() => (
        <>
          <label className="check-row"><input type="checkbox" checked={isDefault && !retired} disabled={retired}
            onChange={(e) => setIsDefault(e.target.checked)} /> New games start with this team (and where it plays)</label>
          {team?.retired && <label className="check-row"><input type="checkbox" checked={retired}
            onChange={(e) => setRetired(e.target.checked)} /> Retired (not offered for new games)</label>}
          <datalist id="vb-venues">{data.venues.map((v) => <option key={v} value={v} />)}</datalist>
        </>
      )}
    </FormPanel>
  )
}
