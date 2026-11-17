import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Bits shared by golf's pages and panels: the summary (Home's tiles and the dashboard), the choice lists, the
// courses for pickers. Kept small: Home loads this file up front (HomeTiles.jsx). The plain formatters are in
// golfFormat.js.

export function useGolfSummary() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.golfSummary().then(setData).catch((e) => setError(e.message)) }, [refreshKey])
  return { data, error }
}

let listsCache = null
export function useGolfLists() {
  const [lists, setLists] = useState(listsCache)
  useEffect(() => {
    if (!listsCache) api.golfLists().then((l) => { listsCache = l; setLists(l) }).catch(() => {})
  }, [])
  return lists
}

// The settings (official handicap, target, allowance, home course), refreshed with the app.
export function useGolfSettings() {
  const { refreshKey } = useApp()
  const [settings, setSettings] = useState(null)
  useEffect(() => { api.golfSettings().then(setSettings).catch(() => setSettings({})) }, [refreshKey])
  return settings
}

// Courses (last played first) for the pickers and the list; null until loaded.
export function useGolfCourses() {
  const { refreshKey } = useApp()
  const [courses, setCourses] = useState(null)
  useEffect(() => { api.golfCourses().then(setCourses).catch(() => setCourses([])) }, [refreshKey])
  return courses
}
