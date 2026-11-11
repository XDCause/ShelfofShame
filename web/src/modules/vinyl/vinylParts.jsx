import { useEffect, useRef, useState } from 'react'
import { api, money } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import ScanButton from '../../components/ScanButton.jsx'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'

// Pieces the Vinyl pages share: covers, grades, what a record is ("12" LP"), adding a record (Discogs search, the
// barcode on the back, or typed in), logging a play, the summary.

export const STATUSES = [['Owned', 'In the collection'], ['Wanted', 'Wantlist'], ['Gone', 'Gone']]
// The Goldmine scale (Discogs uses it): best first.
export const GRADES = [['M', 'Mint'], ['NM', 'Near Mint'], ['VG+', 'Very Good Plus'], ['VG', 'Very Good'], ['G+', 'Good Plus'],
  ['G', 'Good'], ['F', 'Fair'], ['P', 'Poor']]
export const SLEEVE_GRADES = [...GRADES, ['Generic', 'Generic sleeve'], ['No cover', 'No cover']]
export const FORMATS = ['LP', 'EP', 'Single', 'Box set', 'Other']
export const MEDIUMS = ['Vinyl', 'CD', 'Cassette', 'Other']
export const SIZES = ['12"', '10"', '7"']
const GRADE_TONE = { M: 'ok', NM: 'ok', 'VG+': 'teal', VG: 'tint', 'G+': 'low', G: 'low', F: 'out', P: 'out' }

export const useVinylSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`vinyl-summary-${refreshKey}`, () => api.vinylSummary())
}

// '12" LP · 2 discs' / 'CD' / '7" Single'
export const formatText = (r) => {
  const kind = r.medium === 'Vinyl' ? [r.size, r.format].filter(Boolean).join(' ') : r.medium
  return [kind, r.discs > 1 && `${r.discs} discs`].filter(Boolean).join(' · ')
}
export const yearText = (r) => (r.original_year && r.year && r.original_year !== r.year ? `${r.original_year} (this pressing ${r.year})` : r.original_year ?? r.year ?? '')

// The cover (Discogs', or your own photo), or a plain record with the title on its label.
export function RecordCover({ record: r, className = 'vinyl-cover' }) {
  const [failed, setFailed] = useState(false)
  const src = r.photo_url ?? r.thumb
  if (src && !failed) return <img className={className} src={src} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
  const hue = [...(r.title ?? '')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 11)
  return (
    <span className={`${className} vinyl-blank`} style={{ '--disc-hue': hue }} aria-hidden="true">
      <span className="vinyl-blank-label"><span>{r.title}</span></span>
    </span>
  )
}

export function GradePill({ grade, what = 'Record' }) {
  if (!grade) return null
  const name = Object.fromEntries(SLEEVE_GRADES)[grade] ?? grade
  return <span className={`pill ${GRADE_TONE[grade] ?? 'tint'}`} title={`${what}: ${name}`}>{what === 'Sleeve' ? `Sleeve ${grade}` : grade}</span>
}

export const StatusPill = ({ status }) => (status === 'Owned' ? null
  : <span className={`pill ${status === 'Wanted' ? 'tint' : 'out'}`}>{status === 'Wanted' ? 'Wanted' : 'Gone'}</span>)

// "Played it": logs a play of the whole record now (the record's panel has sides and a note).
export function PlayedButton({ record, className = 'secondary small', label = 'Played it' }) {
  const { changed, showToast } = useApp()
  const [busy, setBusy] = useState(false)
  const play = async () => {
    setBusy(true)
    try {
      const p = await api.logVinylPlay(record.record_id, {})
      showToast(`Played ${record.title}${p.scrobbling ? ' · sending to Last.fm' : ''}`)
      changed()
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy(false)
    }
  }
  return <button type="button" className={className} disabled={busy} onClick={play} aria-label={`${label}: ${record.title}`}>▶ {label}</button>
}

// Adding a record: search Discogs (artist, title, catalogue number), scan or type the barcode on the back, or type it in.
export function AddRecordPanel({ onClose, status: startStatus = 'Owned' }) {
  const { changed, openPanel, showToast } = useApp()
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(startStatus)
  const [manual, setManual] = useState(false)
  const [token, setToken] = useState(true)
  const asked = useRef(0)
  useEffect(() => { api.vinylSettings().then((s) => setToken(s.discogs.token)).catch(() => {}) }, [])

  const search = async (params) => {
    const n = ++asked.current
    setBusy(true)
    setError('')
    try {
      const r = await api.vinylLookup(params)
      if (n === asked.current) setResults(r.results)
      return r
    } catch (e) {
      if (n === asked.current) setError(e.message)
      throw e
    } finally {
      if (n === asked.current) setBusy(false)
    }
  }
  useEffect(() => {
    if (!token || q.trim().length < 3) return undefined
    const t = setTimeout(() => search({ q: q.trim() }).catch(() => {}), 500)
    return () => clearTimeout(t)
  }, [q, token])

  const scanned = async (barcode) => {
    setQ('')
    const r = await search({ barcode })
    if (!r.results.length) {
      setManual(true)
      throw new Error("Discogs doesn't know that barcode - search by name, or type the record in below.")
    }
  }
  const add = async (data) => {
    setAdding(data.discogs_release_id ?? 'manual')
    setError('')
    try {
      const saved = await api.addVinylRecord({ ...data, status })
      changed()
      showToast(`Added ${saved.title}`)
      onClose()
      openPanel('record', { id: saved.record_id })
    } catch (e) {
      setError(e.message)
    } finally {
      setAdding(null)
    }
  }
  return (
    <Drawer title="Add a record" onClose={onClose} wide>
      <section className="panel-section">
        <div className="segmented" role="group" aria-label="Add to">
          {STATUSES.slice(0, 2).map(([id, label]) => <button key={id} type="button" aria-pressed={status === id} onClick={() => setStatus(id)}>{label}</button>)}
        </div>
        {token ? (
          <div className="lookup-row">
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} autoFocus
              placeholder="Artist, title or catalogue number" aria-label="Find a record on Discogs" />
            <ScanButton onBarcode={scanned} label="Scan barcode" />
          </div>
        ) : (
          <p className="muted small">Finding records on Discogs needs your Discogs token (Vinyl → Connect). You can still type one in.</p>
        )}
        {error && <p className="alert error small">{error}</p>}
        {busy && <p className="muted small">Looking on Discogs...</p>}
      </section>
      {results && (
        <ul className="list plain-list vinyl-results">
          {results.length === 0 && !busy && <li className="muted small">Nothing found. Try fewer words, or type it in.</li>}
          {results.map((r) => (
            <li key={r.discogs_release_id}>
              <div className="row-button static">
                <RecordCover record={r} className="vinyl-cover small" />
                <span className="grow">
                  <span className="item-title">{r.title}</span>
                  <span className="item-meta">{[r.artist, r.year, r.country].filter(Boolean).join(' · ')}</span>
                  <span className="item-meta">{[r.label, r.catno, r.formats.slice(0, 4).join(', ')].filter(Boolean).join(' · ')}</span>
                </span>
                {r.record_id ? (
                  <button type="button" className="secondary small" onClick={() => { onClose(); openPanel('record', { id: r.record_id }) }}>
                    {r.my_status === 'Owned' ? 'Yours' : r.my_status} ›</button>
                ) : <button type="button" className="primary small" disabled={adding != null}
                  onClick={() => add({ discogs_release_id: r.discogs_release_id })}>{adding === r.discogs_release_id ? 'Adding...' : 'Add'}</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <section className="panel-section">
        {manual || !token ? <ManualRecord onAdd={add} busy={adding === 'manual'} /> : (
          <button type="button" className="plain small" onClick={() => setManual(true)}>Not on Discogs? Type it in</button>
        )}
      </section>
    </Drawer>
  )
}

function ManualRecord({ onAdd, busy }) {
  const [f, setF] = useState({ title: '', artist: '', year: '', format: 'LP', label: '', catno: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <form className="vinyl-form" onSubmit={(e) => { e.preventDefault(); onAdd({ ...f, year: f.year ? Number(f.year) : null }) }}>
      <label>Title<input value={f.title} onChange={set('title')} required /></label>
      <label>Artist<input value={f.artist} onChange={set('artist')} /></label>
      <label>Year<input type="number" min="1880" max="2200" value={f.year} onChange={set('year')} /></label>
      <label>Format<select value={f.format} onChange={set('format')}>{FORMATS.map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>Label<input value={f.label} onChange={set('label')} /></label>
      <label>Catalogue number<input value={f.catno} onChange={set('catno')} /></label>
      <button type="submit" className="primary" disabled={busy}>{busy ? 'Adding...' : 'Add record'}</button>
    </form>
  )
}

// "$1,234 paid · worth $1,890": the collection's money in one line.
export const moneyLine = (s) => [s.paid ? `${money(s.paid)} paid` : null, s.value ? `worth ${money(s.value)}` : null].filter(Boolean).join(' · ')
