import { useEffect, useState } from 'react'

// Several components wanting the same data (e.g. Home's stat tiles and cards) share one request:
// the first to ask starts it, the others wait for the same answer. `key` names the request; a new
// key (after a change) fetches afresh. Only the latest few answers are kept.
const cache = new Map()

export function useShared(key, load) {
  const [state, setState] = useState({ data: null, error: '' })
  useEffect(() => {
    let current = true
    if (!cache.has(key)) {
      cache.set(key, load())
      while (cache.size > 8) cache.delete(cache.keys().next().value)
    }
    cache.get(key)
      .then((data) => current && setState({ data, error: '' }))
      .catch((e) => { cache.delete(key); if (current) setState({ data: null, error: e.message }) })
    return () => { current = false }
  }, [key])
  return state
}
