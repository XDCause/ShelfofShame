import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { clock, scoreText } from './tableParts.jsx'
import { TURN_LIMITS, addTag, overLimit, roundTotals, tagSuggestions, turnClocks, turnLine } from './turnHelpers.js'

// Turn timer, round-by-round grid, tags and score stats for board games (LivePlay.jsx and GamePanel.jsx use them).

// The chess clock: who's turn it is, how long they've had, tap to pass it on. The server keeps whose turn and since
// when (api/app/boardgames_live.py), so a locked phone loses nothing. `since` = seconds since the live play arrived.
export function TurnTimer({ live, since, onChange, onError }) {
  const turns = live.turns
  const [limit, setLimit] = useState(null)
  const [busy, setBusy] = useState(false)
  const act = async (action, extra) => {
    setBusy(true)
    try { onChange(await api.liveTurns(live.live_id, action, extra)) } catch (e) { onError(e.message) }
    setBusy(false)
  }
  const names = Object.fromEntries(live.seats.map((s) => [s.player_id, s.name]))
  if (!turns?.on) {
    return (
      <section className="panel-section bgx-turns">
        <div className="section-head">
          <h4 className="section-title">Turn timer</h4>
          <span className="button-row">
            <label className="bgx-limit"><span className="visually-hidden">Limit per turn</span>
              <select value={limit ?? ''} onChange={(e) => setLimit(e.target.value ? Number(e.target.value) : null)} aria-label="Limit per turn">
                {TURN_LIMITS.map(([v, label]) => <option key={label} value={v ?? ''}>{label}</option>)}
              </select></label>
            <button type="button" className="secondary small" disabled={busy || live.seats.length === 0} onClick={() => act('start', { limit })}>
              {turns ? 'Start again' : 'Start'}</button>
          </span>
        </div>
        <p className="muted small">Chess-clock style: tap to pass the turn on and each player's thinking time adds up. It runs only while you're playing.</p>
      </section>
    )
  }
  const { totals, current } = turnClocks(turns, live.now, since)
  const over = overLimit(turns, current)
  return (
    <section className="panel-section bgx-turns">
      <div className="section-head">
        <h4 className="section-title">Turn timer</h4>
        <button type="button" className="plain small" disabled={busy} onClick={() => act('stop')}>Stop</button>
      </div>
      <button type="button" className={`bgx-pass${over ? ' over' : ''}`} disabled={busy} onClick={() => act('next')}
        aria-label={`${names[turns.current]}'s turn: pass it on`}>
        <span className="bgx-pass-name">{names[turns.current]}</span>
        <span className="bgx-pass-time" role="timer" aria-live="off">{clock(current)}</span>
        <span className="bgx-pass-hint">{over ? `Over ${clock(turns.limit)}: no rush, but others are waiting` : turns.running ? 'Tap to pass the turn' : 'Paused: the clock runs while playing'}</span>
      </button>
      <ul className="bgx-turn-list">
        {turns.order.map((id) => (
          <li key={id} className={id === turns.current ? 'now' : ''}>
            <button type="button" className="plain small" disabled={busy || id === turns.current} onClick={() => act('to', { player_id: id })}
              aria-label={`Give the turn to ${names[id]}`}>{names[id]}</button>
            <span className="bgx-turn-time">{clock(totals[id] ?? 0)}</span>
            <span className="muted small">{turns.counts[id] ?? 0} turn{(turns.counts[id] ?? 0) === 1 ? '' : 's'}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

// Score by round: a row per round, a column per player, totals at the bottom. `rows`: [{ "<player_id>": score }].
export function RoundGrid({ rows, seats, onChange }) {
  const ids = seats.map((s) => s.player_id)
  const totals = roundTotals(rows, ids)
  const set = (r, id, v) => onChange(rows.map((row, i) => (i === r ? { ...row, [id]: v } : row)))
  return (
    <div className="bgx-grid-wrap">
      <table className="bgx-grid">
        <thead>
          <tr><th scope="col">Round</th>{seats.map((s) => <th key={s.player_id} scope="col">{s.name}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              <th scope="row">{r + 1}</th>
              {seats.map((s) => (
                <td key={s.player_id}><input type="number" inputMode="decimal" step="any" value={row[s.player_id] ?? ''}
                  aria-label={`Round ${r + 1}, ${s.name}`} onChange={(e) => set(r, s.player_id, e.target.value)} /></td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr><th scope="row">Total</th>{seats.map((s) => <td key={s.player_id}>{totals[s.player_id] == null ? '' : scoreText(totals[s.player_id])}</td>)}</tr>
        </tfoot>
      </table>
      <div className="button-row">
        <button type="button" className="secondary small" onClick={() => onChange([...rows, {}])}>+ Add a round</button>
        {rows.length > 0 && <button type="button" className="plain small" onClick={() => onChange(rows.slice(0, -1))}>Remove the last round</button>}
      </div>
    </div>
  )
}

// A saved play's round grid, read only.
export function RoundTable({ rows, seats }) {
  const ids = seats.map((s) => s.player_id)
  const totals = roundTotals(rows, ids)
  return (
    <div className="bgx-grid-wrap">
      <table className="bgx-grid">
        <thead><tr><th scope="col">Round</th>{seats.map((s) => <th key={s.player_id} scope="col">{s.name}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}><th scope="row">{r + 1}</th>{seats.map((s) => <td key={s.player_id}>{row[s.player_id] == null ? '' : scoreText(row[s.player_id])}</td>)}</tr>
          ))}
        </tbody>
        <tfoot><tr><th scope="row">Total</th>{seats.map((s) => <td key={s.player_id}>{totals[s.player_id] == null ? '' : scoreText(totals[s.player_id])}</td>)}</tr></tfoot>
      </table>
    </div>
  )
}

// Tags on a play: chips you can remove, a box to add one (Enter), and the tags you've used before to tap.
export function TagEditor({ tags, onChange }) {
  const [text, setText] = useState('')
  const [known, setKnown] = useState([])
  useEffect(() => { api.boardGameTags().then(setKnown).catch(() => {}) }, [])
  const add = (t) => { onChange(addTag(tags, t)); setText('') }
  const ideas = tagSuggestions(known, tags, text).slice(0, 8)
  return (
    <div className="bgx-tags">
      <span className="field-label">Tags</span>
      <ul className="chip-row bgx-tag-list">
        {tags.map((t) => (
          <li key={t} className="pill tint">{t}
            <button type="button" className="icon-btn small" aria-label={`Remove the tag ${t}`} onClick={() => onChange(tags.filter((x) => x !== t))}>✕</button></li>
        ))}
      </ul>
      <input value={text} maxLength={40} placeholder="e.g. close game, won on the last turn" aria-label="Add a tag"
        onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(text) } }} />
      {text.trim() && <button type="button" className="plain small" onClick={() => add(text)}>Add "{text.trim()}"</button>}
      {ideas.length > 0 && (
        <p className="bgx-ideas">{ideas.map((t) => <button key={t} type="button" className="chip-filter" onClick={() => add(t)}>{t}</button>)}</p>
      )}
    </div>
  )
}

// What each player thought for, on a saved play.
export function TurnTimes({ seats }) {
  const lines = seats.map((s) => [s.name, turnLine(s, clock)]).filter(([, t]) => t)
  if (!lines.length) return null
  return (
    <ul className="bgx-times">
      {lines.map(([name, t]) => <li key={name}><strong>{name}</strong> {t}</li>)}
    </ul>
  )
}

// A game's score stats: per score-sheet category and per round - each player's average, highest and lowest.
export function ScoreStats({ stats }) {
  if (!stats || (!stats.parts.length && !stats.rounds.length)) return null
  const rows = (players) => players.map((p) => (
    <tr key={p.name}><th scope="row">{p.name}</th><td>{scoreText(p.avg)}</td><td>{scoreText(p.high)}</td><td>{scoreText(p.low)}</td><td>{p.n}</td></tr>
  ))
  const head = <thead><tr><th scope="col">Player</th><th scope="col">Avg</th><th scope="col">High</th><th scope="col">Low</th><th scope="col">Times</th></tr></thead>
  return (
    <details className="fold bgx-stats">
      <summary><span className="fold-title">Score stats</span></summary>
      <div className="fold-body">
        {stats.parts.map((p) => (
          <div key={p.part} className="bgx-grid-wrap"><h5 className="bgx-stats-title">{p.part}</h5><table className="bgx-grid">{head}<tbody>{rows(p.players)}</tbody></table></div>
        ))}
        {stats.rounds.length > 0 && (
          <div className="bgx-grid-wrap"><h5 className="bgx-stats-title">Per round</h5><table className="bgx-grid">{head}<tbody>{rows(stats.rounds)}</tbody></table></div>
        )}
      </div>
    </details>
  )
}
