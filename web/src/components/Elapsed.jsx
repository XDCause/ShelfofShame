import { useEffect, useState } from 'react'
import { duration } from '../api.js'

// Time since `since`, ticking every second: "0:45:12".
export default function Elapsed({ since }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const s = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000))
  const text = `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  return <span className="elapsed" title={duration(s / 60)}>{text}</span>
}
