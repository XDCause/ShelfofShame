import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { WhistleIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { youtubeId } from './VolleyballPanels.jsx'

// Volleyball Coach (api/app/vbcoach.py): your own notes - drills, things to fix (issues you're
// having, Working on / Sorted) and positions - with web links (YouTube shows a picture) and your
// own uploaded videos. Every note has "Find videos" (a YouTube search for it).
export const KINDS = [['fix', 'Thing to fix'], ['drill', 'Drill'], ['position', 'Position']]
const KIND_NAME = Object.fromEntries(KINDS)
const SHOWS = [['', 'All'], ['working', 'Working on'], ['drill', 'Drills'], ['position', 'Positions'], ['sorted', 'Sorted']]
const shows = (show, n) => !show || (show === 'working' ? n.status === 'working on'
  : show === 'sorted' ? n.status === 'sorted' : n.kind === show)
const youtubeSearch = (n) => `https://www.youtube.com/results?search_query=${encodeURIComponent(
  ['volleyball', n.title, n.kind === 'drill' ? 'drill' : n.kind === 'position' ? 'position tips' : n.skill].filter(Boolean).join(' '))}`

function KindPill({ note }) {
  if (note.kind === 'fix') {
    return <span className={note.status === 'sorted' ? 'pill ok' : 'pill low'}>{note.status === 'sorted' ? 'Sorted' : 'Working on'}</span>
  }
  return <span className={note.kind === 'drill' ? 'pill tint' : 'pill purple'}>{KIND_NAME[note.kind]}</span>
}

export function CoachView() {
  const { refreshKey, openPanel, changed, showToast } = useApp()
  const [data, setData] = useState(null)
  const [show, setShow] = useState('')
  const [skill, setSkill] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api.coachNotes().then(setData).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const starter = async () => {
    try { setData(await api.coachStarter()); changed(); showToast('Added the starter drills and positions') } catch (e) { setError(e.message) }
  }
  const skills = [...new Set(data.notes.map((n) => n.skill).filter(Boolean))]
  const visible = data.notes.filter((n) => shows(show, n) && (!skill || n.skill === skill))
  const working = data.notes.filter((n) => n.status === 'working on').length

  return (
    <section className="page">
      <div className="toolbar">
        <p className="summary grow">{working > 0 ? <><strong>{working}</strong> thing{working > 1 ? 's' : ''} you're working on</>
          : `${data.notes.length} note${data.notes.length === 1 ? '' : 's'}`}</p>
        {!data.has_starter && data.notes.length > 0 && (
          <button type="button" className="secondary" onClick={starter}>+ Starter drills & positions</button>
        )}
        <button type="button" className="primary" onClick={() => openPanel('coachnote', {})}>+ Add note</button>
      </div>
      {data.notes.length === 0 ? (
        <EmptyState Icon={WhistleIcon} title="Your coaching notes" action="+ Add the starter drills & positions" onAction={starter}>
          Drills to practise, things you're working on fixing, and what each position does - with links to videos. Start
          with a set of common drills and the six positions, or add your own with "+ Add note".</EmptyState>
      ) : (
        <>
          <div className="chip-row scroll" role="group" aria-label="Show">
            {SHOWS.map(([k, label]) => (
              <button key={k || 'all'} type="button" className="chip-filter" aria-pressed={show === k} onClick={() => setShow(k)}>{label}</button>
            ))}
          </div>
          {skills.length > 1 && (
            <div className="chip-row scroll" role="group" aria-label="Skill">
              {['', ...skills].map((s) => (
                <button key={s || 'any'} type="button" className="chip-filter" aria-pressed={skill === s} onClick={() => setSkill(s)}>{s || 'Any skill'}</button>
              ))}
            </div>
          )}
          {visible.length === 0 ? <p className="empty card">Nothing here.</p> : (
            <ul className="coach-grid">
              {visible.map((n) => (
                <li key={n.note_id}>
                  <button type="button" className="coach-card card" onClick={() => openPanel('coachnote', { id: n.note_id })}>
                    <span className="coach-top"><KindPill note={n} />{n.pinned && <span className="muted" title="Pinned">★</span>}</span>
                    <span className="item-title">{n.title}</span>
                    <span className="item-meta">{[n.skill, n.position !== n.title && n.position].filter(Boolean).join(' · ')}</span>
                    {n.body && <span className="coach-body">{n.body}</span>}
                    {(n.links.length > 0 || n.videos.length > 0) && (
                      <span className="item-meta">{[n.links.length && `${n.links.length} link${n.links.length > 1 ? 's' : ''}`,
                        n.videos.length && `${n.videos.length} of your videos`].filter(Boolean).join(' · ')}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

// One note: everything editable in place, Save at the bottom.
export function CoachNotePanel({ id = null, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const [note, setNote] = useState(null)
  const [lists, setLists] = useState({ skills: [], positions: [] })
  const [videos, setVideos] = useState([])
  const [f, setF] = useState({ kind: 'fix', title: '', skill: '', position: '', body: '', status: 'working on', links: [], video_ids: [], pinned: false })
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)
  useEffect(() => {
    api.coachNotes().then((d) => {
      setLists({ skills: d.skills, positions: d.positions })
      const n = d.notes.find((x) => x.note_id === id)
      if (n) { setNote(n); setF({ ...n, skill: n.skill ?? '', position: n.position ?? '', body: n.body ?? '', status: n.status ?? 'working on' }) }
    }).catch((e) => setError(e.message))
    api.listVideos().then(setVideos).catch(() => {})
  }, [id])
  if (id != null && !note && !error) return <Drawer title="Note" onClose={onClose}><p className="muted">Loading...</p></Drawer>

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const addLink = () => {
    const l = link.trim()
    if (!/^https?:\/\//i.test(l)) { setError('A link must start with https://'); return }
    setError('')
    setF({ ...f, links: [...f.links.filter((x) => x !== l), l] })
    setLink('')
  }
  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const body = { kind: f.kind, title: f.title, skill: f.skill || null, position: f.position || null, body: f.body || null,
      links: link.trim() && /^https?:\/\//i.test(link.trim()) ? [...f.links, link.trim()] : f.links, video_ids: f.video_ids,
      pinned: f.pinned, ...(f.kind === 'fix' ? { status: f.status } : {}) }
    try {
      const saved = note ? await api.updateCoachNote(note.note_id, body) : await api.addCoachNote(body)
      changed()
      showToast(note ? 'Saved' : `Added ${saved.title}`)
      onClose()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  const linked = f.video_ids.map((vid) => videos.find((v) => v.video_id === vid) ?? note?.videos.find((v) => v.video_id === vid)).filter(Boolean)
  const footer = confirm ? (
    <span className="confirm">Delete this note?
      <button type="button" className="danger" onClick={async () => { await api.deleteCoachNote(note.note_id); changed(); onClose() }}>Delete</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="submit" form="coach-form" className="primary" disabled={busy}>{note ? 'Save' : 'Add note'}</button>
      <button type="button" className="plain" onClick={onClose}>Cancel</button>
      {note && <><span className="spacer" /><button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Delete</button></>}
    </>
  )

  return (
    <Drawer title={note ? note.title : 'Add a coaching note'} onClose={onClose} footer={footer} wide>
      {error && <p className="alert error" role="alert">{error}</p>}
      <form id="coach-form" onSubmit={save} className="coach-form">
        <div className="segmented" role="group" aria-label="Kind of note">
          {KINDS.map(([k, label]) => (
            <button key={k} type="button" aria-pressed={f.kind === k} onClick={() => setF({ ...f, kind: k })}>{label}</button>
          ))}
        </div>
        {f.kind === 'fix' && (
          <div className="segmented" role="group" aria-label="Status">
            {[['working on', 'Working on'], ['sorted', 'Sorted']].map(([k, label]) => (
              <button key={k} type="button" aria-pressed={f.status === k} onClick={() => setF({ ...f, status: k })}>{label}</button>
            ))}
          </div>
        )}
        <label className="field wide"><span className="field-label">{f.kind === 'fix' ? "What's going wrong" : 'Title'} <span className="req" aria-hidden="true"> *</span></span>
          <input value={f.title} onChange={set('title')} required aria-label="Title"
            placeholder={f.kind === 'fix' ? 'e.g. Serves going into the net' : f.kind === 'drill' ? 'e.g. Butterfly passing' : 'e.g. Libero'} /></label>
        <div className="coach-pair">
          <label className="field"><span className="field-label">Skill</span>
            <input value={f.skill} onChange={set('skill')} list="coach-skills" aria-label="Skill" /></label>
          <label className="field"><span className="field-label">Position</span>
            <input value={f.position} onChange={set('position')} list="coach-positions" aria-label="Position" /></label>
        </div>
        <datalist id="coach-skills">{lists.skills.map((s) => <option key={s} value={s} />)}</datalist>
        <datalist id="coach-positions">{lists.positions.map((s) => <option key={s} value={s} />)}</datalist>
        <label className="field wide"><span className="field-label">{f.kind === 'fix' ? 'Tips and what to try' : f.kind === 'drill' ? 'How it works' : 'What they do'}</span>
          <textarea value={f.body} onChange={set('body')} rows={8} aria-label="Notes"
            placeholder={f.kind === 'fix' ? '- Toss lower and a little in front\n- Watch the ball onto the hand' : ''} /></label>

        <section className="coach-links">
          <h4 className="section-title">Links</h4>
          {f.links.length > 0 && (
            <ul className="coach-link-list">
              {f.links.map((l) => {
                const yt = youtubeId(l)
                return (
                  <li key={l}>
                    {yt && <img src={`https://img.youtube.com/vi/${yt}/mqdefault.jpg`} alt="" referrerPolicy="no-referrer"
                      onError={(e) => { e.currentTarget.hidden = true }} />}
                    <a href={l} target="_blank" rel="noreferrer" className="grow">{l.replace(/^https?:\/\/(www\.)?/, '')}</a>
                    <button type="button" className="plain small destructive" aria-label="Remove link"
                      onClick={() => setF({ ...f, links: f.links.filter((x) => x !== l) })}>✕</button>
                  </li>
                )
              })}
            </ul>
          )}
          <div className="paste-row">
            <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="Paste a link (YouTube, an article...)" aria-label="Add a link"
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLink() } }} />
            <button type="button" className="secondary small" onClick={addLink} disabled={!link.trim()}>Add</button>
          </div>
          {f.title.trim() && <a className="small" href={youtubeSearch(f)} target="_blank" rel="noreferrer">Find videos on YouTube ↗</a>}
        </section>

        <section className="coach-links">
          <h4 className="section-title">Your videos</h4>
          {linked.length > 0 && (
            <ul className="coach-link-list">
              {linked.map((v) => (
                <li key={v.video_id}>
                  <button type="button" className="plain grow" onClick={() => { onClose(); openPanel('video', { id: v.video_id }) }}>▶ {v.title}</button>
                  <button type="button" className="plain small destructive" aria-label={`Remove ${v.title}`}
                    onClick={() => setF({ ...f, video_ids: f.video_ids.filter((x) => x !== v.video_id) })}>✕</button>
                </li>
              ))}
            </ul>
          )}
          {videos.filter((v) => !f.video_ids.includes(v.video_id)).length > 0 ? (
            <select value="" aria-label="Add one of your videos"
              onChange={(e) => e.target.value && setF({ ...f, video_ids: [...f.video_ids, Number(e.target.value)] })}>
              <option value="">+ Add one of your videos...</option>
              {videos.filter((v) => !f.video_ids.includes(v.video_id)).map((v) => <option key={v.video_id} value={v.video_id}>{v.title}</option>)}
            </select>
          ) : <p className="muted small">Upload videos in the Videos tab to link them here.</p>}
        </section>

        <label className="all-day-switch">
          <input type="checkbox" role="switch" checked={f.pinned} onChange={(e) => setF({ ...f, pinned: e.target.checked })} />
          <span>Pin to the top</span>
        </label>
      </form>
    </Drawer>
  )
}
