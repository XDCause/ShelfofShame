import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useShared } from './useShared.js'

// Your banner pictures ({area: {photo_url, focus_y}}), shared by every banner on screen. After a change,
// bannersChanged() makes them all ask again.
let version = 0
const listeners = new Set()

export function bannersChanged() {
  version += 1
  listeners.forEach((f) => f(version))
}

export function useBanners() {
  const [v, setV] = useState(version)
  useEffect(() => {
    listeners.add(setV)
    return () => listeners.delete(setV)
  }, [])
  return useShared(`banners-${v}`, api.banners).data ?? {}
}
