import { useEffect, useRef, useState } from 'react'
import { api, money, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import RecordFields, { RowPhoto, useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'

export const GAME_FIELDS = [
  { name: 'name', label: 'Name', required: true, wide: true },
  { name: 'publisher', label: 'Publisher' },
  { name: 'year', label: 'Year', type: 'number', min: 1800 },
  { name: 'min_players', label: 'Fewest players', type: 'number', min: 1 },
  { name: 'max_players', label: 'Most players', type: 'number', min: 1 },
  { name: 'play_minutes', label: 'Play time (minutes)', type: 'number', min: 1 },
  { name: 'min_age', label: 'Ages (from)', type: 'number', min: 1 },
  { name: 'designer', label: 'Designer' },
  { name: 'rating', label: 'Your rating (1-10)', type: 'number', min: 1 },
  { name: 'purchase_date', label: 'Bought on', type: 'date' },
  { name: 'price_paid', label: 'Price paid', type: 'money' },
  { name: 'bgg_url', label: 'BoardGameGeek link', type: 'url', wide: true, placeholder: 'https://boardgamegeek.com/...' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

const PLAY_FIELDS = [
  { name: 'played_on', label: 'Day', type: 'date', required: true },
  { name: 'minutes', label: 'How long (minutes)', type: 'number', min: 1 },
  { name: 'players', label: 'Who played', wide: true, placeholder: 'e.g. Sam, Jo, me' },
  { name: 'winner', label: 'Who won' },
  { name: 'notes', label: 'Notes', type: 'textarea' },
]

// "3-4 players · 75 min · 10+ · Klaus Teuber · Kosmos · 1995"
export const gameMeta = (g) => [
  g.min_players && (g.max_players && g.max_players !== g.min_players
    ? `${g.min_players}-${g.max_players} players` : `${g.min_players}+ players`),
  g.play_minutes && `${g.play_minutes} min`, g.min_age && `${g.min_age}+`, g.designer, g.publisher, g.year,
].filter(Boolean).join(' · ')

// Find a game on Wikidata (the open database behind Wikipedia - no account): type a name, pick
// the right one. onPick(result) gets its facts (players, time, age, designer, publisher, year,
// BGG id) and its Wikidata id; the API fetches its photo itself.
function WikidataFind({ start = '', onPick, pickLabel = 'Use' }) {
  const [q, setQ] = useState(start)
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const asked = useRef(0)
  useEffect(() => {
    if (q.trim().length < 2) { setResults(null); return undefined }
    const t = setTimeout(async () => {
      const n = ++asked.current
      setBusy(true)
      setError('')
      try {
        const r = await api.boardGameLookup(q.trim())
        if (n === asked.current) setResults(r)
      } catch (e) {
        if (n === asked.current) setError(e.message)
      } finally {
        if (n === asked.current) setBusy(false)
      }
    }, 450)
    return () => clearTimeout(t)
  }, [q])
  return (
    <section className="panel-section wikidata-find">
      <label className="field">Find it on Wikidata
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Game name, e.g. Ticket to Ride"
          aria-label="Find a board game on Wikidata" autoFocus={!start} /></label>
      {busy && <p className="muted small">Looking on Wikidata...</p>}
      {error && <p className="alert error small">{error}</p>}
      {results && !busy && results.length === 0 && <p className="muted small">Nothing found. Try the full name, or fill it in below.</p>}
      {results?.length > 0 && (
        <ul className="list plain-list wikidata-results">
          {results.map((r) => (
            <li key={r.wikidata_id}>
              <div className="row-button static">
                {r.image_url ? <img className="thumb" src={r.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
                  : <span className="thumb thumb-empty" />}
                <span className="grow">
                  <span className="item-title">{r.name}</span>
                  <span className="item-meta">{gameMeta(r) || r.description}</span>
                </span>
                {r.game_id ? <span className="pill">In your games</span>
                  : <button type="button" className="primary small" onClick={() => onPick(r)}>{pickLabel}</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="muted small">From Wikidata, the free database behind Wikipedia; photos from Wikimedia Commons. BGG's ratings and
        ranks aren't there.</p>
    </section>
  )
}

// One board game: photo, status, plays (log one here), journal pages about it, details.
// Also adds a new game (id = null).
export default function GamePanel({ id, onClose }) {
  const { lookups, changed, openPanel } = useApp()
  const [game, setGame] = useState(null)
  const [editing, setEditing] = useState(id == null)
  const [logging, setLogging] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [finding, setFinding] = useState(false)

  const show = (g, msg) => {
    setGame(g)
    if (msg) { setNote(msg); setTimeout(() => setNote(''), 2500) }
  }
  const run = async (fn) => {
    setError('')
    try { await fn() } catch (e) { setError(e.message) }
  }
  const reload = async (msg) => { show(await api.getBoardGame(game.game_id), msg); changed() }
  useEffect(() => { if (id != null) run(async () => show(await api.getBoardGame(id))) }, [id])

  if (editing) {
    return <GameForm game={game} onClose={onClose} onCancel={() => (game ? setEditing(false) : onClose())}
      onSaved={(g) => { changed(); if (!game) openPanel('boardgame', { id: g.game_id }); else { show(g, 'Saved ✓'); setEditing(false) } }} />
  }
  if (!game) {
    return <Drawer title="Board game" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>
  }

  const footer = confirmDelete ? (
    <span className="confirm">
      Delete {game.name} and its {game.plays} play{game.plays === 1 ? '' : 's'}? (Gone keeps them.)
      <button type="button" className="danger" onClick={() => run(async () => {
        await api.deleteBoardGame(game.game_id); changed(); onClose()
      })}>Delete</button>
      <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button key="edit" type="button" className="secondary" onClick={() => setEditing(true)}>Edit details</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>Delete</button>
    </>
  )

  return (
    <Drawer title="Board game" onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <p className="save-flash" role="status" aria-live="polite">{note}</p>
      <div className="item-hero">
        <RowPhoto path={`/board-games/${game.game_id}`} url={game.photo_url} label="box photo"
          onChanged={(msg) => run(() => reload(msg))} />
        <div>
          <h3 className="item-name">{game.name}</h3>
          <p className="item-sub">{gameMeta(game)}</p>
          <div className="chips">
            {game.rating && <span className="pill low">★ {game.rating}/10</span>}
            {game.price_paid != null && <span className="chip">{money(game.price_paid)}</span>}
            {game.bgg_url && <a className="small" href={game.bgg_url} target="_blank" rel="noreferrer">BoardGameGeek ↗</a>}
            {game.wikidata_id && <a className="small" href={`https://www.wikidata.org/wiki/${game.wikidata_id}`} target="_blank" rel="noreferrer">Wikidata ↗</a>}
            {!game.wikidata_id && !finding && <button type="button" className="plain small" onClick={() => setFinding(true)}>Fill in from Wikidata</button>}
          </div>
        </div>
      </div>
      {finding && (
        <WikidataFind start={game.name} pickLabel="Fill in" onPick={(r) => run(async () => {
          show(await api.boardGameFromWikidata(game.game_id, r.wikidata_id), 'Filled in from Wikidata ✓')
          setFinding(false)
          changed()
          if (r.image_url && !game.has_photo) setTimeout(() => reload().catch(() => {}), 4000)   // the photo comes a moment later
        })} />
      )}

      <section className="panel-section">
        <div className="segmented" role="group" aria-label="Status">
          {lookups.game_statuses.map((s) => (
            <button key={s} type="button" aria-pressed={game.status === s}
              onClick={() => game.status !== s && run(async () => {
                show(await api.updateBoardGame(game.game_id, { status: s }), `${s} ✓`)
                changed()
              })}>{s}</button>
          ))}
        </div>
      </section>

      <section className="panel-section">
        <div className="section-head">
          <h4 className="section-title">Plays <span className="muted">· {game.plays}</span></h4>
          {!logging && <button type="button" className="secondary" onClick={() => setLogging(true)}>+ Log a play</button>}
        </div>
        {logging && (
          <PlayForm gameId={game.game_id} onCancel={() => setLogging(false)}
            onSaved={() => { setLogging(false); run(() => reload('Play logged ✓')) }} />
        )}
        {game.play_log.length === 0 && !logging && <p className="muted small">Not played yet.</p>}
        {game.play_log.length > 0 && (
          <ul className="list compact plays">
            {game.play_log.map((p) => (
              <li key={p.play_id} className="play-row">
                <span className="grow">
                  <span className="item-title">{shortDate(p.played_on)}{p.winner && <span className="pill ok">🏆 {p.winner}</span>}</span>
                  <span className="item-meta">{[p.players, p.minutes && `${p.minutes} min`, p.notes].filter(Boolean).join(' · ')}</span>
                </span>
                <button type="button" className="icon-btn small" aria-label={`Delete the play on ${shortDate(p.played_on)}`}
                  onClick={() => run(async () => { await api.deletePlay(p.play_id); await reload('Play deleted') })}>✕</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {game.notes && <section className="panel-section"><h4 className="section-title">Notes</h4><p className="detail-desc">{game.notes}</p></section>}
      <JournalMentions kind="game" id={game.game_id} name={game.name} onLeave={onClose} />
    </Drawer>
  )
}

function GameForm({ game, onClose, onCancel, onSaved }) {
  const { form, set, setForm, payload } = useRecordForm(GAME_FIELDS, game)
  const [status, setStatus] = useState(game?.status ?? 'Owned')
  const [picked, setPicked] = useState(null)   // the Wikidata game the form was filled from
  // Fill the form from a Wikidata game (your typing after this still wins when you save).
  const pick = (r) => {
    setPicked(r)
    setForm((f) => ({ ...f, ...Object.fromEntries(['name', 'publisher', 'year', 'min_players', 'max_players', 'play_minutes',
      'min_age', 'designer'].filter((k) => r[k] != null).map((k) => [k, String(r[k])])),
    ...(r.bgg_id && { bgg_url: `https://boardgamegeek.com/boardgame/${r.bgg_id}` }) }))
  }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { lookups } = useApp()

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = { ...payload(), status, ...(!game && picked && { wikidata_id: picked.wikidata_id }) }
      onSaved(game ? await api.updateBoardGame(game.game_id, body) : await api.addBoardGame(body))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  const footer = (
    <>
      <button key="save" type="submit" form="game-form" className="primary" disabled={busy}>{game ? 'Save' : 'Add game'}</button>
      <button key="cancel" type="button" className="plain" onClick={onCancel}>Cancel</button>
    </>
  )
  return (
    <Drawer title={game ? `Edit ${game.name}` : 'Add a board game'} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!game && (picked ? (
        <p className="alert ok small">Filled in from Wikidata: {picked.name}{picked.image_url && ' (its photo is added once you save)'}.{' '}
          <button type="button" className="plain small" onClick={() => setPicked(null)}>Pick another</button></p>
      ) : <WikidataFind onPick={pick} />)}
      <form id="game-form" onSubmit={submit}>
        <div className="segmented form-segmented" role="group" aria-label="Status">
          {lookups.game_statuses.map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)}>{s}</button>
          ))}
        </div>
        <RecordFields fields={GAME_FIELDS} form={form} set={set} />
      </form>
    </Drawer>
  )
}

// Log a play: inside a game's panel (gameId given), or on its own with a game picker (PlayPanel).
function PlayForm({ gameId, games, onSaved, onCancel }) {
  const { form, set, payload } = useRecordForm(PLAY_FIELDS, null, { played_on: today() })
  const [pick, setPick] = useState(gameId ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    if (!pick) { setError('Which game?'); return }
    setBusy(true)
    setError('')
    try {
      onSaved(await api.addPlay(pick, payload()))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  // A div, not a form: it sits inside the game panel's own content.
  return (
    <div className="inline-form" onKeyDown={(e) => { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); save() } }}>
      {error && <p className="alert error small">{error}</p>}
      {games && (
        <fieldset>
          <label className="field wide">
            <span className="field-label">Game <span className="req" aria-hidden="true"> *</span></span>
            <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Game">
              <option value="">Choose...</option>
              {games.map((g) => <option key={g.game_id} value={g.game_id}>{g.name}</option>)}
            </select>
          </label>
        </fieldset>
      )}
      <RecordFields fields={PLAY_FIELDS} form={form} set={set} />
      <div className="button-row">
        <button type="button" className="primary" onClick={save} disabled={busy}>{busy ? 'Saving...' : 'Save play'}</button>
        <button type="button" className="plain" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

// "Log a play" from Home or the Plays page: pick the game, then the same form.
export function PlayPanel({ gameId = null, onClose }) {
  const { changed, showToast } = useApp()
  const [games, setGames] = useState(null)
  useEffect(() => { api.listBoardGames().then((gs) => setGames(gs.filter((g) => g.status !== 'Gone'))).catch(() => setGames([])) }, [])
  return (
    <Drawer title="Log a play" onClose={onClose}>
      {!games ? <p className="muted">Loading...</p> : games.length === 0
        ? <p className="empty">Add a game first (Board games, "+ Add game").</p>
        : <PlayForm gameId={gameId} games={games} onCancel={onClose}
            onSaved={(p) => { changed(); showToast(`Logged a play of ${p.game_name}`); onClose() }} />}
    </Drawer>
  )
}
