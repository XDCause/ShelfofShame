import { useCallback, useEffect, useRef, useState } from 'react'
import { api, timeAgo } from '../../api.js'
import { TimerIcon } from '../../components/icons.jsx'
import { SAVING } from '../../offline/state.js'
import { useApp } from '../app-context.js'
import { clock, minutesText, secondsLeft } from './focusMath.js'

// The focus timer (api/app/focus.py): start 25 minutes (or what you pick) on a to-do or a goal. The start time is kept
// on the server, so a reload, or your phone, shows it still running. When the time is up (and a FocusBar is on the
// page) the session is finished and its minutes are logged against the to-do and the goal.
//   FocusBar     the running timer: the clock, Pause / Resume, Stop. Home's To do card, the To-do page and a goal's page.
//   FocusStart   minutes + "Start focus" for one to-do or goal
//   FocusTime    the time already focused on one to-do or goal

const CHANGED = 'otc-focus-changed'        // every piece on the page listens, so they stay in step
const tell = () => window.dispatchEvent(new Event(CHANGED))

function useFocus(autoFinish = false) {
  const { showToast, changed } = useApp()
  const [state, setState] = useState({ session: null, fetchedAt: 0 })
  const [now, setNow] = useState(0)
  const finishing = useRef(0)
  const load = useCallback(() => api.focusCurrent().then((session) => {
    setState({ session, fetchedAt: Date.now() })
    setNow(Date.now())
  }).catch(() => {}), [])
  useEffect(() => {
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [load])
  const { session, fetchedAt } = state
  const running = session?.status === 'running'
  useEffect(() => {
    if (!running) return undefined
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [running])
  const left = secondsLeft(session, fetchedAt, now)
  const sessionId = session?.session_id
  const label = session?.label
  useEffect(() => {
    if (!autoFinish || SAVING || !running || !now || left > 0 || finishing.current === sessionId) return
    finishing.current = sessionId
    api.finishFocus(sessionId).then((done) => {
      showToast(`Focus finished: ${minutesText(done.focused_seconds / 60)}${label ? ` on ${label}` : ''}. Well done.`)
      changed()
      tell()
    }).catch(() => { finishing.current = 0 })
  }, [autoFinish, running, now, left, sessionId, label, showToast, changed])
  const act = async (call) => {
    try {
      await call()
    } catch (e) {
      showToast(e.message)
    }
    tell()
  }
  return { session, left, act, changed }
}

export function FocusBar() {
  const { session, left, act, changed } = useFocus(true)
  if (!session) return null
  const paused = session.status === 'paused'
  return (
    <section className="focus-bar-box" aria-label="Focus timer">
      <TimerIcon size={22} />
      <span className="focus-bar-what grow">
        <span className="item-title">{session.label ?? 'Focus'}</span>
        <span className="item-meta">{paused ? 'Paused' : 'Focusing'} · {session.minutes} min session</span>
      </span>
      <span className="focus-bar-clock" role="timer" aria-label={`${clock(left)} left`}>{clock(left)}</span>
      <button type="button" className="secondary small" onClick={() => act(() => (paused ? api.resumeFocus(session.session_id) : api.pauseFocus(session.session_id)))}>
        {paused ? 'Resume' : 'Pause'}</button>
      <button type="button" className="plain small" onClick={async () => { await act(() => api.finishFocus(session.session_id)); changed() }}>Stop</button>
    </section>
  )
}

// What goes with the start: { todo_id } or { goal_id } (a to-do's goal comes with it).
export function FocusStart({ target, label = 'Focus on this' }) {
  const { session, act, changed } = useFocus()
  const [minutes, setMinutes] = useState(25)
  if (session) return <p className="hint">A focus session is running{session.label ? ` (${session.label})` : ''}. Stop it to start another.</p>
  const valid = Number.isInteger(minutes) && minutes >= 1 && minutes <= 480
  return (
    <div className="focus-start">
      <label className="field"><span className="field-label">Minutes</span>
        <input type="number" min="1" max="480" step="5" inputMode="numeric" value={minutes}
          onChange={(e) => setMinutes(e.target.value === '' ? 0 : Number(e.target.value))} /></label>
      <button type="button" className="secondary" disabled={!valid}
        onClick={async () => { await act(() => api.startFocus({ ...target, minutes })); changed() }}><TimerIcon size={16} /> {label}</button>
    </div>
  )
}

// kind: 'todo' or 'goal'
export function FocusTime({ kind, id }) {
  const [s, setS] = useState(null)
  const load = useCallback(() => { api.focusSummary(kind, id).then(setS).catch(() => {}) }, [kind, id])
  useEffect(() => {
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [load])
  if (!s || !s.sessions) return null
  return (
    <div className="focus-time">
      <p className="small"><strong>{minutesText(s.minutes)}</strong> focused in {s.sessions} session{s.sessions === 1 ? '' : 's'}
        {s.week_minutes > 0 && <span className="muted"> · {minutesText(s.week_minutes)} this week</span>}</p>
      <ul className="list plain-list compact">
        {s.latest.slice(0, 4).map((x) => (
          <li key={x.session_id}><span className="item-meta">{timeAgo(x.started_at)} · {minutesText(x.minutes)}{x.status === 'stopped' ? ' (stopped early)' : ''}</span></li>
        ))}
      </ul>
    </div>
  )
}
