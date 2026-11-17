import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Bits shared by Language learning's pages, panels and Home tiles: the summary, the choice lists, and which language
// you're looking at (remembered on this device; any page can switch it).

export function useLanguageSummary(languageId = null) {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.languageSummary(languageId).then(setData).catch((e) => setError(e.message))
  }, [refreshKey, languageId])
  return { data, error }
}

let listsCache = null
export function useLanguageLists() {
  const [lists, setLists] = useState(listsCache)
  useEffect(() => {
    if (!listsCache) api.languageLists().then((l) => { listsCache = l; setLists(l) }).catch(() => {})
  }, [])
  return lists
}

const KEY = 'otc.language.current'
export const rememberLanguage = (id) => { try { window.localStorage.setItem(KEY, String(id)) } catch { /* (a private window) */ } }
const remembered = () => { try { return Number(window.localStorage.getItem(KEY)) || null } catch { return null } }

// The languages, and the one you're on: the one you picked last (if it's still there), else the first active one.
export function useLanguages() {
  const { refreshKey } = useApp()
  const [languages, setLanguages] = useState(null)
  const [picked, setPicked] = useState(remembered)
  // (a language just added is remembered by its panel: picked up here when the list comes back)
  useEffect(() => { api.languages().then((l) => { setLanguages(l); setPicked(remembered()) }).catch(() => setLanguages([])) }, [refreshKey])
  const pick = useCallback((id) => {
    setPicked(id)
    try { window.localStorage.setItem(KEY, String(id)) } catch { /* (a private window: just for now) */ }
  }, [])
  const current = languages?.find((l) => l.language_id === picked) ?? languages?.find((l) => l.active) ?? languages?.[0] ?? null
  return { languages, current, pick }
}
