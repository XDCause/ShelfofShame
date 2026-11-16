import { useEffect, useState } from 'react'

// The look: "botanical" (the pine sidebar, parchment and landscape banners; docs/DESIGN.md) or "journal" (a hobby
// notebook: paper and ink, a dot grid, notebook tabs along the top, your banner as a pinned photo; DESIGN.md >
// The journal look). Chosen in Settings > Appearance and remembered on this device, like light / dark.
// The CSS reads <html data-look="journal"> (styles/32-look-journal.css); the shell swaps the sidebar for the
// top bar (App.jsx, core/Navigation.jsx JournalNav).
const KEY = 'offtheclock.look'
export const LOOKS = [['botanical', 'Botanical'], ['journal', 'Journal']]

export function readLook() {
  try {
    const saved = localStorage.getItem(KEY)
    return LOOKS.some(([k]) => k === saved) ? saved : 'botanical'
  } catch { return 'botanical' }
}

export function applyLook(look = readLook()) {
  document.documentElement.dataset.look = look
  window.dispatchEvent(new CustomEvent('lookchange', { detail: look }))
}

export function setLook(look) {
  try { localStorage.setItem(KEY, look) } catch { /* private window: just for now */ }
  applyLook(look)
}

// The look in use right now, updating when it changes.
export function useLook() {
  const [look, setCurrent] = useState(() => document.documentElement.dataset.look || 'botanical')
  useEffect(() => {
    const changed = (e) => setCurrent(e.detail)
    window.addEventListener('lookchange', changed)
    return () => window.removeEventListener('lookchange', changed)
  }, [])
  return look
}
