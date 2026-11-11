import { useEffect, useState } from 'react'
import { shortDate } from '../api.js'
import { lastSaved } from './offline.js'
import { isOffline, onOfflineChange } from './state.js'

// Under the nav bar while the app is answering from the copy on this device (Settings > Offline copy).
// Try again reloads the pages (App's changed()): the first answer from the server takes this away.
export default function OfflineBanner({ onRetry }) {
  const [offline, setOffline] = useState(isOffline)
  useEffect(() => onOfflineChange(setOffline), [])
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
