import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// A video with its clips (api/app/vbclips.py). While it plays: Mark start and Mark end, a name,
// Save clip - a clip is just a bookmark (start and end), saved straight away. Each clip plays on its
// own (jump to its start, stop at its end) or all of them in a row; tick some and "Make a highlight
// video" cuts them into a new video file (made in the background - it shows in Videos when ready).

// 75.4 -> "1:15.4"; 3725 -> "1:02:05.0"
export function clock(seconds) {
  const s = Math.max(0, seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = (s % 60).toFixed(1).padStart(4, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${rest}` : `${m}:${rest}`
}

export default function ClipEditor({ video }) {
  const { changed, showToast } = useApp()
  const player = useRef(null)
  const stopAt = useRef(null)          // {end, then}: where the clip playing now stops, and what plays next
  const jumping = useRef(false)        // the app moved the video (not you dragging the bar)
  const [clips, setClips] = useState([])
  const [start, setStart] = useState(null)
  const [end, setEnd] = useState(null)
  const [title, setTitle] = useState('')
  const [picked, setPicked] = useState(() => new Set())
  const [playing, setPlaying] = useState(null)       // clip_id playing now
  const [making, setMaking] = useState(null)         // the highlight title box, open
  const [error, setError] = useState('')
  const load = useCallback(() => api.videoClips(video.video_id).then(setClips).catch((e) => setError(e.message)), [video.video_id])
  useEffect(() => { load() }, [load])

  const now = () => Math.round((player.current?.currentTime ?? 0) * 100) / 100   // hundredths of a second
  const run = async (fn) => {
    setError('')
    try { await fn() } catch (e) { setError(e.message) }
  }

  // Play one clip; `rest` = the clips to play after it (Play all).
  const play = (clip, rest = []) => {
    const v = player.current
    if (!v) return
    stopAt.current = { end: clip.end, then: rest }
    setPlaying(clip.clip_id)
    jumping.current = true
    v.currentTime = clip.start
    v.play().catch(() => {})
  }
  const onTime = () => {
    const stop = stopAt.current
    if (!stop || now() < stop.end) return
    const [next, ...rest] = stop.then
    if (next) { play(next, rest); return }
    stopAt.current = null
    setPlaying(null)
    player.current.pause()
  }
  const stopClip = () => { stopAt.current = null; setPlaying(null) }   // the video's own controls take over

  const save = () => run(async () => {
    await api.addClip(video.video_id, { title: title.trim() || null, start, end })
    setStart(null); setEnd(null); setTitle('')
    await load()
    showToast('Clip saved')
  })
  const remove = (clip) => run(async () => {
    await api.deleteClip(clip.clip_id)
    setPicked((p) => { const n = new Set(p); n.delete(clip.clip_id); return n })
    await load()
  })
  const toggle = (id) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const chosen = clips.filter((c) => picked.has(c.clip_id))
  const make = (e) => {
    e.preventDefault()
    run(async () => {
      await api.makeHighlights(making.trim(), chosen.map((c) => c.clip_id))
      setMaking(null)
      changed()
      showToast("Making your highlight video - it'll be in Videos when it's ready")
    })
  }
  const length = start != null && end != null ? end - start : null

  return (
    <>
      <section className="panel-section">
        <video ref={player} className="video-player" src={video.file_url} controls playsInline preload="metadata"
          onTimeUpdate={onTime} onSeeking={() => { if (jumping.current) jumping.current = false; else stopClip() }} />
      </section>
      <section className="panel-section clip-maker">
        <h4 className="section-title">Make a clip</h4>
        <div className="clip-marks">
          <button type="button" className="secondary" onClick={() => setStart(now())}>Mark start</button>
          <button type="button" className="secondary" onClick={() => setEnd(now())}>Mark end</button>
          <span className="small">
            {start != null ? <button type="button" className="plain small inline" onClick={() => { player.current.currentTime = start }}>{clock(start)}</button> : '–'}
            {' → '}
            {end != null ? <button type="button" className="plain small inline" onClick={() => { player.current.currentTime = end }}>{clock(end)}</button> : '–'}
            {length != null && <span className="muted"> · {length > 0 ? `${length.toFixed(1)} s` : 'the end is before the start'}</span>}
          </span>
        </div>
        {start != null && end != null && end > start && (
          <div className="clip-save">
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What happens (e.g. Kill from the 4)"
              aria-label="Clip name" onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); save() } }} />
            <button type="button" className="plain" onClick={() => play({ clip_id: 'new', start, end })}>Preview</button>
            <button type="button" className="primary" onClick={save}>Save clip</button>
          </div>
        )}
        <p className="hint">Play the video, tap Mark start where the moment begins and Mark end where it finishes. Tap a time to jump back to it.</p>
      </section>

      {clips.length > 0 && (
        <section className="panel-section">
          <div className="section-head">
            <h4 className="section-title">Clips</h4>
            <button type="button" className="plain small" onClick={() => {
              const list = chosen.length ? chosen : clips
              play(list[0], list.slice(1))
            }}>▶ Play {chosen.length ? `${chosen.length} ticked` : 'all'}</button>
          </div>
          <ul className="clip-list">
            {clips.map((c, i) => (
              <li key={c.clip_id} className={playing === c.clip_id ? 'playing' : undefined}>
                <input type="checkbox" checked={picked.has(c.clip_id)} onChange={() => toggle(c.clip_id)}
                  aria-label={`Use ${c.title ?? `clip ${i + 1}`} in a highlight video`} />
                <button type="button" className="clip-play plain" onClick={() => play(c)} aria-label={`Play ${c.title ?? `clip ${i + 1}`}`}>▶</button>
                <span className="grow">
                  <span className="item-title">{c.title ?? `Clip ${i + 1}`}</span>
                  <span className="item-meta">{clock(c.start)} – {clock(c.end)} · {c.seconds.toFixed(1)} s</span>
                </span>
                <button type="button" className="plain small destructive" onClick={() => remove(c)} aria-label={`Delete ${c.title ?? `clip ${i + 1}`}`}>✕</button>
              </li>
            ))}
          </ul>
          {making == null ? (
            <button type="button" className="primary" disabled={!chosen.length}
              onClick={() => setMaking(`${video.title} highlights`)}>
              {chosen.length ? `Make a highlight video (${chosen.length} clip${chosen.length > 1 ? 's' : ''}, ${chosen.reduce((n, c) => n + c.seconds, 0).toFixed(0)} s)`
                : 'Tick clips to make a highlight video'}</button>
          ) : (
            <form className="clip-save" onSubmit={make}>
              <input value={making} onChange={(e) => setMaking(e.target.value)} required autoFocus aria-label="Highlight video title" />
              <button type="submit" className="primary">Make it</button>
              <button type="button" className="plain" onClick={() => setMaking(null)}>Cancel</button>
            </form>
          )}
          <p className="hint">A highlight video is a new video file: the ticked clips one after another (in time order). It's
            made on this computer and can take a minute or two; you can keep using the app.</p>
        </section>
      )}
      {error && <p className="alert error small">{error}</p>}
    </>
  )
}

// A highlight video being made: how far it's got (checked every 2 seconds); onDone when it's ready.
export function Making({ video, onDone }) {
  const [state, setState] = useState(video)
  useEffect(() => {
    if (state.processing !== 'making') return undefined
    const timer = setInterval(async () => {
      const now = await api.highlightProgress(video.video_id).catch(() => null)
      if (!now) return
      setState(now)
      if (now.processing !== 'making') { clearInterval(timer); if (!now.processing) onDone() }
    }, 2000)
    return () => clearInterval(timer)
  }, [state.processing, video.video_id, onDone])
  if (state.processing?.startsWith('failed')) {
    return <p className="panel-section alert error">Couldn't make this video ({state.processing.replace(/^failed:\s*/, '')}). Delete it and try again.</p>
  }
  const percent = Math.round((state.progress ?? 0) * 100)
  return (
    <section className="panel-section">
      <p className="small" role="status">Making the video... {percent}%{state.made_from && ` · ${state.made_from}`}</p>
      <span className="fill-bar tint" aria-hidden="true"><span style={{ width: `${percent}%` }} /></span>
    </section>
  )
}
