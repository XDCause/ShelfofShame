import { useEffect, useMemo, useRef, useState } from 'react'
import { api, money, timeAgo } from '../../api.js'
import ScanButton from '../../components/ScanButton.jsx'
import { useApp } from '../../core/app-context.js'
import { KitCard } from './WarhammerRange.jsx'

// Gundam: Bandai's kits at Good Games (api/app/gundam.py, the shop's official interface, like the
// Warhammer tab). Opens on every Gundam kit in stock now; search by name, box code or barcode (or
// scan the box) for the rest, sold-out ones included. Grade chips narrow it down.

const SHOWS = [['all', 'All'], ['stock', 'In stock'], ['missing', "Don't have"]]
const GRADE_ORDER = ['EG', 'HG', 'RG', 'MG', 'PG', 'SD', 'RE/100', 'FM']

export default function GundamRange({ onOpenModel }) {
  const { changed, showToast } = useApp()
  const [query, setQuery] = useState('')            // what's shown (empty = in stock now)
  const [typed, setTyped] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [grade, setGrade] = useState('')
  const [show, setShow] = useState('all')
  const [busy, setBusy] = useState(null)
  const latest = useRef(null)          // the search last asked for: an older, slower answer is ignored

  const load = (q, refresh = false) => {
    latest.current = q
    setError('')
    setData((d) => (d && (d.query ?? '') === q ? { ...d, refreshing: true } : null))
    api.gundamKits(q, refresh)
      .then((r) => { if (latest.current === q) { setData(r); setGrade('') } })
      .catch((e) => { if (latest.current === q) { setError(e.message); setData(null) } })
  }
  useEffect(() => { load(query) }, [query])

  const search = (e) => {
    e?.preventDefault()
    setQuery(typed.trim())
  }
  const want = async (k) => {
    setBusy(k.id)
    try {
      const model = await api.wantGundam(k.id)
      setData((d) => ({ ...d, kits: d.kits.map((x) => (x.id === k.id ? { ...x, my_model: { model_id: model.model_id, status: model.status } } : x)) }))
      changed()
      showToast(`Added to your kits as Wanted: ${model.name}`, { label: 'Open', run: () => onOpenModel(model.model_id) })
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy(null)
    }
  }

  const grades = useMemo(() => {
    const have = new Set((data?.kits ?? []).map((k) => k.grade).filter(Boolean))
    return [...GRADE_ORDER.filter((g) => have.has(g)), ...[...have].filter((g) => !GRADE_ORDER.includes(g))]
  }, [data])
  const kits = (data?.kits ?? []).filter((k) => (!grade || k.grade === grade)
    && (show === 'all' || (show === 'stock' ? k.available : !k.my_model)))

  return (
    <section className="page wh-range gundam-range">
      <form className="toolbar gundam-search" onSubmit={search}>
        <input className="search" type="search" value={typed} onChange={(e) => setTyped(e.target.value)}
          placeholder="Search Gunpla: rx-78-2, aerial, wing zero, G5057403..." aria-label="Search Gunpla" />
        <button type="submit" className="primary">Search</button>
        <ScanButton className="secondary" label="Scan the box" onBarcode={(barcode) => { setTyped(barcode); setQuery(barcode) }} />
        {query && <button type="button" className="plain" onClick={() => { setTyped(''); setQuery('') }}>In stock now</button>}
      </form>

      {error && <p className="alert error">{error}</p>}
      {!data && !error && <p className="muted loading">{query ? `Searching Good Games for “${query}”...` : 'Asking Good Games what Gunpla is in stock...'}</p>}
      {data && (
        <>
          <div className="wh-head">
            <div>
              <h2 className="wh-title">{data.query ? `“${data.query}”` : 'In stock now'}</h2>
              <p className="muted small">
                {data.total} kit{data.total === 1 ? '' : 's'}{data.query && ` · ${data.in_stock} in stock`}
                {' · '}prices and stock from <a href="https://www.goodgames.com.au" target="_blank" rel="noreferrer">Good Games</a>,
                checked {timeAgo(new Date(data.fetched_at * 1000).toISOString())}
              </p>
            </div>
            <div className="wh-tools">
              <div className="segmented" role="group" aria-label="Show">
                {SHOWS.map(([id, label]) => <button key={id} type="button" aria-pressed={show === id} onClick={() => setShow(id)}>{label}</button>)}
              </div>
              <button type="button" className="plain small" onClick={() => load(query, true)} disabled={data.refreshing}>
                {data.refreshing ? 'Checking...' : 'Check again'}
              </button>
            </div>
          </div>
          {grades.length > 1 && (
            <div className="chips wh-grades" role="group" aria-label="Grade">
              <button type="button" className="chip-filter" aria-pressed={!grade} onClick={() => setGrade('')}>All grades</button>
              {grades.map((g) => (
                <button key={g} type="button" className="chip-filter" aria-pressed={grade === g} onClick={() => setGrade(g)}>
                  {g} <span className="chip-count">{data.kits.filter((k) => k.grade === g).length}</span>
                </button>
              ))}
            </div>
          )}
          {data.total === 0 ? (
            <p className="empty card">Good Games has no Gunpla for “{data.query}”. Try fewer words, or the code from the box.</p>
          ) : kits.length === 0 ? <p className="empty card">Nothing here with that filter.</p> : (
            <ul className="model-grid wh-grid">
              {kits.map((k) => (
                <KitCard key={k.id} kit={k} badge={[k.grade, k.scale].filter(Boolean).join(' ')} busy={busy === k.id}
                  onWant={() => want(k)} onOpenModel={onOpenModel} meta={[k.product_code?.startsWith('G50') && k.product_code, k.price != null && money(k.price)]} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
