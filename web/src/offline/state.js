// Is the app answering from the offline copy right now? (offline/sw.js marks a saved answer X-OTC-Saved and its own
// "can't reach it" answers X-OTC-Offline.) api.js tells this after every answer; the banner (OfflineBanner.jsx) listens.
// Kept tiny: api.js is in the main download.
let offline = false
const listeners = new Set()

export const isOffline = () => offline
export const onOfflineChange = (listener) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
export function noteAnswer(res) {
  const now = res.headers.has('X-OTC-Saved') || res.headers.has('X-OTC-Offline')
  if (now === offline) return
  offline = now
  for (const listener of listeners) listener(now)
}

// This copy of the app is the hidden frame "Save everything now" walks through (offline/saveAll.js): App takes its
// directions from the page that opened it.
export const SAVING = window.parent !== window && new URLSearchParams(window.location.search).has('otc-saving')
