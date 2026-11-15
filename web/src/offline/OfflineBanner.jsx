import { useEffect, useRef, useState } from 'react'
import { shortDate } from '../api.js'
import { lastSaved } from './offline.js'
import { isOffline, onOfflineChange } from './state.js'

// Under the nav bar while the app is answering from the copy on this device (Settings > Offline copy).
// Try again reloads the pages (App's changed()): the first answer from the server takes this away. It also happens by
// itself: when the service worker hears from the server again (sw.js BACK), and when the phone wakes or the page is
// looked at again while it says Offline (2026-11-15: it used to sit on Offline until you tapped Try again).
export default function OfflineBanner({ onRetry }) {
  const [offline, setOffline] = useState(isOffline)
  useEffect(() => onOfflineChange(setOffline), [])
  const retry = useRef(onRetry)
  retry.current = onRetry
  useEffect(() => {
    const sw = navigator.serviceWorker
    const back = (e) => { if (e.data === 'otc-server-back' && isOffline()) retry.current() }
    const looked = () => { if (document.visibilityState === 'visible' && isOffline()) retry.current() }
    sw?.addEventListener('message', back)
    document.addEventListener('visibilitychange', looked)
    window.addEventListener('online', looked)
    return () => {
      sw?.removeEventListener('message', back)
      document.removeEventListener('visibilitychange', looked)
      window.removeEventListener('online', looked)
    }
  }, [])
  if (!offline) return null
  const saved = lastSaved()
  return (
    <div className="offline-banner" role="status">
      <span><strong>Offline.</strong> The app at home can't be reached: this is the copy saved on this device
        {saved ? ` (everything saved ${shortDate(saved)})` : ''}. Changes are off until it's back.</span>
      <button type="button" className="secondary small" onClick={onRetry}>Try again</button>
    </div>
  )
}
