import { useEffect, useState } from 'react'

// Light or dark: your choice (Settings > Appearance), remembered on this device, or "system" to
// follow the device's own setting. The CSS reads <html data-theme="light|dark">.
const KEY = 'offtheclock.theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')
export const THEMES = [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]

export function readTheme() {
  try { return localStorage.getItem(KEY) || 'system' } catch { return 'system' }
}

export function applyTheme(choice = readTheme()) {
  const theme = choice === 'system' ? (media.matches ? 'dark' : 'light') : choice
  document.documentElement.dataset.theme = theme
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
    m.content = theme === 'dark' ? '#0a0f1c' : '#f3f5fa'
  })
  window.dispatchEvent(new CustomEvent('themechange', { detail: theme }))
}

export function setTheme(choice) {
  try { localStorage.setItem(KEY, choice) } catch { /* private window: just for now */ }
  applyTheme(choice)
}

media.addEventListener('change', () => { if (readTheme() === 'system') applyTheme('system') })

// The theme in use right now ("light" / "dark"), updating when it changes.
export function useTheme() {
  const [theme, setCurrent] = useState(() => document.documentElement.dataset.theme || 'light')
  useEffect(() => {
    const changed = (e) => setCurrent(e.detail)
    window.addEventListener('themechange', changed)
    return () => window.removeEventListener('themechange', changed)
  }, [])
  return theme
}
