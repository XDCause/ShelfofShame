// Settings > Offline copy (2026-11-11, user: "if I'm across the world and the laptop does a Windows update I need an
// offline version"). Per device: turning it on registers the service worker (offline/sw.js), which saves the app's
// files and every answer the API gives from then on; turning it off removes the worker and everything it saved.
const SAVED_AT = 'otc-offline-saved-at'      // when "Save everything now" last finished on this device

export const offlinePossible = () =>
  typeof navigator !== 'undefined' && 'serviceWorker' in navigator && window.isSecureContext && 'caches' in window

const registration = () => navigator.serviceWorker.getRegistration('/')

export function lastSaved() {
  try { return localStorage.getItem(SAVED_AT) } catch { return null }
}
export function noteSaved() {
  try { localStorage.setItem(SAVED_AT, new Date().toISOString()) } catch { /* (private window: just not remembered) */ }
}

// {on, savedAt, bytes, kept}: kept = the browser promised not to clear it when space runs low.
export async function offlineStatus() {
  if (!offlinePossible()) return { on: false }
  const on = Boolean(await registration())
  const estimate = await navigator.storage?.estimate?.().catch(() => null)
  const kept = await navigator.storage?.persisted?.().catch(() => false)
  return { on, savedAt: lastSaved(), bytes: estimate?.usage ?? null, kept: Boolean(kept) }
}

export async function turnOfflineOn() {
  await navigator.serviceWorker.register('/sw.js', { scope: '/' })
  await navigator.serviceWorker.ready
  // (the worker takes over open pages as it starts - sw.js claims them; wait for that, briefly)
  if (!navigator.serviceWorker.controller) {
    await new Promise((resolve) => {
      navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true })
      setTimeout(resolve, 5000)
    })
  }
  await navigator.storage?.persist?.().catch(() => false)
}

export async function turnOfflineOff() {
  for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister()
  await forgetSaved({ all: true })
}

// Signing out of this device drops the saved answers (your data); all: the app's files too.
export async function forgetSaved({ all = false } = {}) {
  if (typeof caches === 'undefined') return
  for (const name of await caches.keys()) {
    if (name === 'otc-data' || (all && name.startsWith('otc-'))) await caches.delete(name)
  }
  try { localStorage.removeItem(SAVED_AT) } catch { /* nothing to remove */ }
}
