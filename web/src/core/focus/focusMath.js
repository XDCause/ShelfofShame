// The focus timer's small sums (kept apart so they can be tested).

// 1500 -> "25:00", 3725 -> "1:02:05"
export function clock(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`
}

// Seconds left now. The server said `session.remaining_seconds` when it answered (at `fetchedAt`, in ms); a running
// timer counts down from there, a paused one stands still.
export function secondsLeft(session, fetchedAt, nowMs) {
  if (!session) return 0
  if (session.status !== 'running') return session.remaining_seconds
  return Math.max(0, session.remaining_seconds - Math.floor((nowMs - fetchedAt) / 1000))
}

// 95 -> "1 h 35 min", 45 -> "45 min", 0 -> "0 min"
export function minutesText(minutes) {
  const m = Math.round(minutes)
  return m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ''}` : `${m} min`
}
