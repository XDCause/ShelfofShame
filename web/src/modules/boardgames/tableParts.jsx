import { useState } from 'react'
import { api } from '../../api.js'
import PhotoPick from '../../components/PhotoPick.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'

// Board games at the table: the pieces the live play (LivePlay.jsx) and "Log a play" (GamePanel.jsx) share.
// A seat is { player_id, name, is_me, score, parts, adds, team, colour, won } - player_id is missing for someone new
// (the API adds them by name when the play is saved).

export const SCORING = [['highest', 'Highest score wins'], ['lowest', 'Lowest score wins'], ['coop', 'Co-op (win or lose together)'],
  ['none', 'No score']]

export const seatKey = (s) => (s.player_id != null ? `p${s.player_id}` : `n${s.name.trim().toLowerCase()}`)

// What a seat's score adds up to: typed, else its score sheet's parts, else its +/- taps (as the API does).
export function seatTotal(s) {
  if (s.score != null && s.score !== '') return Number(s.score)
  const parts = Object.values(s.parts ?? {}).filter((v) => v !== '' && v != null)
  if (parts.length) return parts.reduce((a, v) => a + Number(v), 0)
  if (s.adds?.length) return s.adds.reduce((a, v) => a + Number(v), 0)
  return null
}

// Places from scores (1, 1, 3 for a tie), for highest / lowest scoring; null where there's no score.
export function places(seats, scoring) {
  if (scoring !== 'highest' && scoring !== 'lowest') return seats.map(() => null)
  const totals = seats.map(seatTotal)
  return totals.map((t) => (t == null ? null : 1 + totals.filter((o) => o != null && (scoring === 'lowest' ? o < t : o > t)).length))
}

// "12:04" or "1:05:22"
export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
}

// "1 h 05" or "35 min"
export const minutesText = (m) => (m == null ? null : m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}` : `${m} min`)

export const scoreText = (n) => (n == null ? '' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }))

const ordinal = (n) => `${n}${n % 10 === 1 && n % 100 !== 11 ? 'st' : n % 10 === 2 && n % 100 !== 12 ? 'nd' : n % 10 === 3 && n % 100 !== 13 ? 'rd' : 'th'}`
export const placeText = (n) => (n == null ? '' : ordinal(n))

// Who's playing: the people you play with most lately (you first), your groups in one tap, and anyone new by name.
// chosen: seats in order. roster: GET /board-games/players ({players, groups, places}).
export function PlayerPicker({ chosen, onChange, roster, max = null }) {
  const [name, setName] = useState('')
  const [all, setAll] = useState(false)
  const [grouping, setGrouping] = useState(false)
  const [groupName, setGroupName] = useState('')
  const [error, setError] = useState('')
  const [groups, setGroups] = useState(roster?.groups ?? [])
  const players = roster?.players ?? []
  const keys = new Set(chosen.map(seatKey))
  const byId = Object.fromEntries(players.map((p) => [p.player_id, p]))
  const left = players.filter((p) => !keys.has(`p${p.player_id}`))
  const shown = all ? left : left.slice(0, 10)
  const seatOf = (p) => ({ player_id: p.player_id, name: p.name, is_me: p.is_me, adds: [] })
  const add = (...ps) => onChange([...chosen, ...ps.filter((p) => !keys.has(seatKey(p)))])
  const addNew = () => {
    const n = name.trim().replace(/\s+/g, ' ')
    if (!n) return
    const have = players.find((p) => p.name.toLowerCase() === n.toLowerCase())
    add(have ? seatOf(have) : { name: n, adds: [] })
    setName('')
  }
  const saveGroup = async () => {
    setError('')
    try {
      const g = await api.addPlayerGroup({ name: groupName.trim(), player_ids: chosen.map((s) => s.player_id) })
      setGroups([...groups, g])
      setGrouping(false)
      setGroupName('')
    } catch (e) { setError(e.message) }
  }
  const allKnown = chosen.length > 1 && chosen.every((s) => s.player_id != null)
  return (
    <div className="bgt-picker">
      {chosen.length > 0 ? (
        <ol className="bgt-chosen" aria-label="Playing">
          {chosen.map((s, i) => (
            <li key={seatKey(s)} className="bgt-chosen-chip">
              <span>{s.name}{s.is_me && <span className="muted"> (you)</span>}{s.player_id == null && <span className="muted"> · new</span>}</span>
              <button type="button" className="icon-btn small" aria-label={`Move ${s.name} up`} disabled={i === 0}
                onClick={() => onChange(chosen.map((x, j) => (j === i - 1 ? s : j === i ? chosen[i - 1] : x)))}>↑</button>
              <button type="button" className="icon-btn small" aria-label={`Take ${s.name} out`}
                onClick={() => onChange(chosen.filter((x) => seatKey(x) !== seatKey(s)))}>✕</button>
            </li>
          ))}
        </ol>
      ) : <p className="muted small">Who's playing? Tap them below, or add someone new.</p>}
      {max && chosen.length > max && <p className="alert low small">That's more than the {max} this game takes.</p>}
      {groups.length > 0 && (
        <div className="chips bgt-groups" role="group" aria-label="Your groups">
          {groups.map((g) => {
            const members = g.player_ids.map((id) => byId[id]).filter(Boolean)
            return (
              <button key={g.group_id} type="button" className="chip-filter" onClick={() => add(...members.map(seatOf))}
                title={members.map((m) => m.name).join(', ')}>+ {g.name} <span className="chip-count">{members.length}</span></button>
            )
          })}
        </div>
      )}
      {left.length > 0 && (
        <div className="chips bgt-usual" role="group" aria-label="Add a player">
          {shown.map((p) => (
            <button key={p.player_id} type="button" className="chip-filter" onClick={() => add(seatOf(p))}>
              + {p.name}{p.is_me && ' (you)'}</button>
          ))}
          {left.length > 10 && <button type="button" className="plain small" onClick={() => setAll(!all)}>
            {all ? 'Fewer' : `Everyone (${left.length})`}</button>}
        </div>
      )}
      <div className="bgt-new">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Someone new: their name" aria-label="New player's name"
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addNew() } }} maxLength={80} />
        <button type="button" className="secondary" onClick={addNew} disabled={!name.trim()}>Add</button>
      </div>
      {allKnown && !grouping && (
        <button type="button" className="plain small" onClick={() => setGrouping(true)}>Save these {chosen.length} as a group</button>
      )}
      {grouping && (
        <div className="bgt-new">
          <input value={groupName} onChange={(e) => setGroupName(e.target.value)} placeholder="e.g. Thursday crew" aria-label="Group name"
            autoFocus maxLength={60} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (groupName.trim()) saveGroup() } }} />
          <button type="button" className="secondary" onClick={saveGroup} disabled={!groupName.trim()}>Save group</button>
          <button type="button" className="plain" onClick={() => setGrouping(false)}>Cancel</button>
        </div>
      )}
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}

// After the game: each player's score (or their score sheet's parts), colour / faction, and a trophy to say who won
// (a tie-break, or a game without scores). Co-op games ask whether the table won instead.
export function SeatScores({ seats, onChange, scoring, parts = [], coopWon, onCoopWon }) {
  const ranks = places(seats, scoring)
  const set = (i, change) => onChange(seats.map((s, j) => (j === i ? { ...s, ...change } : s)))
  const anyWon = seats.some((s) => s.won)
  if (!seats.length) return null
  if (scoring === 'coop') {
    return (
      <div className="segmented form-segmented" role="group" aria-label="How did it go?">
        <button type="button" aria-pressed={coopWon === true} onClick={() => onCoopWon(true)}>We won</button>
        <button type="button" aria-pressed={coopWon === false} onClick={() => onCoopWon(false)}>The game won</button>
      </div>
    )
  }
  return (
    <ul className="bgt-score-list">
      {seats.map((s, i) => {
        const auto = !anyWon && ranks[i] === 1
        return (
          <li key={seatKey(s)} className="bgt-score-row">
            <span className="bgt-score-name">{s.name}{ranks[i] && <span className="muted small"> · {placeText(ranks[i])}</span>}</span>
            {scoring !== 'none' && (parts.length ? (
              <span className="bgt-parts">
                {parts.map((p) => (
                  <label key={p} className="bgt-part">{p}
                    <input type="number" inputMode="decimal" step="any" value={s.parts?.[p] ?? ''} aria-label={`${s.name}: ${p}`}
                      onChange={(e) => set(i, { score: null, parts: { ...s.parts, [p]: e.target.value } })} />
                  </label>
                ))}
                <strong className="bgt-part-total" aria-label={`${s.name}'s total`}>{scoreText(seatTotal(s)) || '–'}</strong>
              </span>
            ) : (
              <input className="bgt-score-input" type="number" inputMode="decimal" step="any" aria-label={`${s.name}'s score`}
                value={s.score ?? (s.adds?.length ? seatTotal(s) : '')} onChange={(e) => set(i, { score: e.target.value === '' ? null : e.target.value })} />
            ))}
            <input className="bgt-colour-input" value={s.colour ?? ''} placeholder="Colour / faction" aria-label={`${s.name}'s colour or faction`}
              onChange={(e) => set(i, { colour: e.target.value })} maxLength={40} />
            <button type="button" className={`icon-btn bgt-trophy${s.won || auto ? ' on' : ''}`} aria-pressed={!!s.won}
              aria-label={`${s.name} won`} title={auto ? 'Winning on score - tap to pick the winner yourself' : 'Mark as the winner'}
              onClick={() => set(i, { won: !s.won })}>🏆</button>
          </li>
        )
      })}
    </ul>
  )
}

// How good a play it was, 1-5.
export function FunPicker({ value, onChange }) {
  return (
    <div className="bgt-fun" role="group" aria-label="How good was it?">
      <span className="field-label">How good was it?</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" className={`icon-btn bgt-star${value >= n ? ' on' : ''}`} aria-pressed={value === n}
          aria-label={`${n} out of 5`} onClick={() => onChange(value === n ? null : n)}>★</button>
      ))}
    </div>
  )
}

// A play's photos (the final board, the table): thumbnails, add more, remove one.
export function PlayPhotos({ photos, onAdd, onRemove, busy = false }) {
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')
  const add = async (files) => {
    setAdding(true)
    setError('')
    try {
      for (const f of files) await onAdd(await shrink(f, 1600))
    } catch (e) { setError(e.message) } finally { setAdding(false) }
  }
  return (
    <div className="bgt-photos">
      {photos.length > 0 && (
        <ul className="bgt-photo-row">
          {photos.map((p) => (
            <li key={p.photo_id}>
              <a href={p.url} target="_blank" rel="noreferrer"><img src={p.url} alt={p.caption || 'A photo of the play'} loading="lazy" /></a>
              {onRemove && <button type="button" className="icon-btn small" aria-label="Remove this photo" onClick={() => onRemove(p)}>✕</button>}
            </li>
          ))}
        </ul>
      )}
      <PhotoPick multiple onFile={add} disabled={adding || busy} label="Add a photo of the play" />
      {adding && <span className="muted small"> Adding...</span>}
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}

// Seats for the API: who (an id, or a new name) and how they scored.
export const seatsOut = (seats) => seats.map((s) => ({
  ...(s.player_id != null ? { player_id: s.player_id } : { name: s.name }),
  score: s.score === '' || s.score == null ? null : Number(s.score),
  parts: s.parts ? Object.fromEntries(Object.entries(s.parts).filter(([, v]) => v !== '' && v != null).map(([k, v]) => [k, Number(v)])) : null,
  adds: s.adds ?? [], team: s.team || null, colour: s.colour || null, won: s.won || null,
}))
