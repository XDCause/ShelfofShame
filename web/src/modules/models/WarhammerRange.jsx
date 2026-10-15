import { useEffect, useState } from 'react'
import { api, money, timeAgo } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Warhammer: an army's whole range at Good Games (api/app/warhammer.py, through the shop's official
// interface) - every kit by Games Workshop code, in stock or sold out, its price, how many minis,
// which ones you already have; "+ Wanted" adds one to your kits, "Good Games" opens it to buy.

const ARMY_KEY = 'offtheclock.warhammerArmy'
const SHOWS = [['all', 'All'], ['stock', 'In stock'], ['missing', "Don't have"]]

const readArmy = () => {
  try { return localStorage.getItem(ARMY_KEY) } catch { return null }
}

export default function WarhammerRange({ onOpenModel }) {
  const { changed, showToast } = useApp()
  const [armies, setArmies] = useState(null)
  const [army, setArmy] = useState(readArmy)
  const [typed, setTyped] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [show, setShow] = useState('all')
  const [busy, setBusy] = useState(null)

  useEffect(() => {
    api.warhammerArmies().then((a) => {
      setArmies(a)
      setArmy((now) => now ?? a.yours[0] ?? 'Adeptus Mechanicus')
    }).catch((e) => setError(e.message))
  }, [])

  const load = (name, refresh = false) => {
    setError('')
    setData((d) => (d?.army === name ? { ...d, refreshing: true } : null))
    api.warhammerArmy(name, refresh).then(setData).catch((e) => { setError(e.message); setData(null) })
  }
  useEffect(() => {
    if (!army) return
    try { localStorage.setItem(ARMY_KEY, army) } catch { /* private mode: not remembered */ }
    load(army)
  }, [army])

  const want = async (k) => {
    setBusy(k.id)
    try {
      const model = await api.wantWarhammer(k.id)
      setData((d) => ({ ...d, yours: d.yours + 1, kits: d.kits.map((x) => (x.id === k.id ? { ...x, my_model: { model_id: model.model_id, status: model.status } } : x)) }))
      changed()
      showToast(`Added to your kits as Wanted: ${model.name}`, { label: 'Open', run: () => onOpenModel(model.model_id) })
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy(null)
    }
  }

  const pick = (e) => {
    e.preventDefault()
    if (typed.trim().length >= 2) { setArmy(typed.trim()); setTyped('') }
  }
  const kits = (data?.kits ?? []).filter((k) => show === 'all' || (show === 'stock' ? k.available : !k.my_model))
  const choices = armies ? [...armies.yours, ...armies.others] : []

  return (
    <section className="page wh-range">
      <div className="wh-armies">
        <div className="chips" role="group" aria-label="Army">
          {choices.map((a) => (
            <button key={a} type="button" className="chip-filter" aria-pressed={army === a} onClick={() => setArmy(a)}>
              {a}{armies.yours.includes(a) && <span className="chip-mark" title="You have kits from this army"> ★</span>}
            </button>
          ))}
          {army && !choices.includes(army) && <button type="button" className="chip-filter" aria-pressed>{army}</button>}
        </div>
        <form className="wh-other" onSubmit={pick}>
          <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Another army, e.g. Black Templars" aria-label="Another army" />
          <button type="submit" className="secondary" disabled={typed.trim().length < 2}>Show</button>
        </form>
      </div>

      {error && <p className="alert error">{error}</p>}
      {!data && !error && <p className="muted loading">Asking Good Games for the {army} range...</p>}
      {data && (
        <>
          <div className="wh-head">
            <div>
              <h2 className="wh-title">{data.army}</h2>
              <p className="muted small">
                {data.total} kits · {data.in_stock} in stock · you have {data.yours}
                {' · '}prices and stock from <a href="https://www.goodgames.com.au" target="_blank" rel="noreferrer">Good Games</a>,
                checked {timeAgo(new Date(data.fetched_at * 1000).toISOString())}
              </p>
            </div>
            <div className="wh-tools">
              <div className="segmented" role="group" aria-label="Show">
                {SHOWS.map(([id, label]) => <button key={id} type="button" aria-pressed={show === id} onClick={() => setShow(id)}>{label}</button>)}
              </div>
              <button type="button" className="plain small" onClick={() => load(data.army, true)} disabled={data.refreshing}>
                {data.refreshing ? 'Checking...' : 'Check again'}
              </button>
            </div>
          </div>
          {data.total === 0 ? (
            <p className="empty card">Good Games has no kits for “{data.army}”. Check the army's name (e.g. “T'au Empire”, “Orks”).</p>
          ) : kits.length === 0 ? <p className="empty card">Nothing here with that filter.</p> : (
            <ul className="model-grid wh-grid">
              {kits.map((k) => <KitCard key={k.id} kit={k} busy={busy === k.id} onWant={() => want(k)} onOpenModel={onOpenModel} />)}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

function KitCard({ kit: k, busy, onWant, onOpenModel }) {
  const picture = k.image && `${k.image}${k.image.includes('?') ? '&' : '?'}width=400`
  return (
    <li className={`model-card wh-card${k.my_model ? ' mine' : ''}`}>
      <span className="model-photo">
        {picture ? <img src={picture} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="photo-missing">No photo</span>}
        {k.code && <span className="wh-code">{k.code}</span>}
        <span className={`wh-stock ${k.available ? 'in' : 'out'}`}>{k.available ? 'In stock' : 'Sold out'}</span>
      </span>
      <span className="model-body">
        <span className="model-name">{k.name}</span>
        <span className="model-meta">{[k.figures && `${k.figures} mini${k.figures === 1 ? '' : 's'}`, k.price != null && money(k.price)].filter(Boolean).join(' · ')}</span>
        <span className="wh-actions">
          {k.my_model ? (
            <button type="button" className="secondary small" onClick={() => onOpenModel(k.my_model.model_id)}>Yours · {k.my_model.status}</button>
          ) : (
            <button type="button" className="primary small" onClick={onWant} disabled={busy}>{busy ? 'Adding...' : '+ Wanted'}</button>
          )}
          {k.url && <a className="button plain small" href={k.url} target="_blank" rel="noreferrer">Good Games ↗</a>}
        </span>
      </span>
    </li>
  )
}
