import { useEffect, useRef, useState } from 'react'
import { api, money, shopRef, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import RecordFields, { RowPhoto, useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'

const GAME_FIELDS = [
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

// What a game is: a game, an expansion for one, or something else (metal coins, sleeves...).
export const KINDS = [['game', 'Game'], ['expansion', 'Expansion'], ['other', 'Other']]

// "3-4 players · 75 min · 10+ · Klaus Teuber · Kosmos · 1995"
export const gameMeta = (g) => [
  g.min_players ? (g.max_players && g.max_players !== g.min_players
    ? `${g.min_players}-${g.max_players} players` : `${g.min_players}+ players`)
    : g.max_players && `up to ${g.max_players} players`,                // Good Games only knows the most
  g.play_minutes && `${g.play_minutes} min`, g.min_age && `${g.min_age}+`, g.designer, g.publisher, g.year,
].filter(Boolean).join(' · ')

// How heavy a game is (BGG's weight, 1-5): "Light" ... "Heavy".
const weightName = (w) => (w == null ? null : w < 1.8 ? 'Light' : w < 2.6 ? 'Medium-light' : w < 3.4 ? 'Medium'
  : w < 4.2 ? 'Medium-heavy' : 'Heavy')

// Find a game: Gameology first (an Australian board game shop whose products carry BoardGameGeek's
// facts), Good Games for what Gameology doesn't have (fewer facts: most players, age, themes,
// mechanics) - asked by the API when Gameology has no match, or with "Search Good Games too".
// Type a name, pick the right one. onPick(result) gets its facts; the API reads the product
// again itself when saving (and fetches its photo).
function ShopFind({ start = '', onPick, pickLabel = 'Use' }) {
  const [q, setQ] = useState(start)
  const [found, setFound] = useState(null)      // {results, asked_good_games, notes}
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const asked = useRef(0)
  const look = async (more = false) => {
    const n = ++asked.current
    setBusy(true)
    setError('')
    try {
      const r = await api.boardGameLookup(q.trim(), more)
      if (n === asked.current) setFound(r)
    } catch (err) {
      if (n === asked.current) setError(err.message)
    } finally {
      if (n === asked.current) setBusy(false)
    }
  }
  useEffect(() => {
    if (q.trim().length < 2) { setFound(null); return undefined }
    const t = setTimeout(() => look(), 450)
    return () => clearTimeout(t)
  }, [q])                                          // eslint-disable-line react-hooks/exhaustive-deps
  const results = found?.results
  return (
    <section className="panel-section shop-find">
      <label className="field">Find it at a shop
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Game name, e.g. Ticket to Ride"
          aria-label="Find a board game" autoFocus={!start} /></label>
      {busy && <p className="muted small">Looking...</p>}
      {found?.notes?.length > 0 && !busy && <p className="muted small">{found.notes.join(' ')}</p>}
      {error && <p className="alert error small">{error}</p>}
      {results && !busy && results.length === 0 && <p className="muted small">Nothing found. Try another name, or fill it in below.</p>}
      {results?.length > 0 && (
        <ul className="list plain-list shop-results">
          {results.map((r) => (
            <li key={`${r.source}-${r.handle}`}>
              <div className="row-button static">
                {r.image_url ? <img className="thumb" src={r.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
                  : <span className="thumb thumb-empty" />}
                <span className="grow">
                  <span className="item-title">{r.title}{r.expansion && <span className="pill">Expansion</span>}
                    {r.source === 'goodgames' && <span className="pill teal">Good Games</span>}
                    {r.available === false && <span className="pill out">Sold out</span>}</span>
                  <span className="item-meta">{[gameMeta(r), r.weight && `weight ${r.weight}`, r.complexity, r.price != null && money(r.price)]
                    .filter(Boolean).join(' · ')}</span>
                </span>
                {r.game_id ? <span className="pill">In your games</span>
                  : <button type="button" className="primary small" onClick={() => onPick(r)}>{pickLabel}</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {found && !busy && !found.asked_good_games && (
        <button type="button" className="plain small" onClick={() => look(true)}>Not here? Search Good Games too</button>
      )}
      <p className="muted small">Gameology first: BoardGameGeek's players, time, age, weight, categories and mechanisms, plus the
        box photo and price. Good Games fills the gaps with what it has (most players, age, themes, mechanics, price, photo).
        BGG's rating and rank aren't included.</p>
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
          <p className="item-sub">
            {game.kind === 'game' ? (game.add_ons > 0 ? `Game · ${game.add_ons} expansion${game.add_ons === 1 ? '' : 's'} / extra${game.add_ons === 1 ? '' : 's'}` : 'Game')
              : <>{game.kind === 'expansion' ? 'Expansion' : 'Extra'}{game.base_game_id && <> for <button type="button" className="link-title inline"
                  onClick={() => openPanel('boardgame', { id: game.base_game_id })}>{game.base_name}</button></>}</>}
          </p>
          <p className="item-sub">{gameMeta(game)}</p>
          <div className="chips">
            {game.rating && <span className="pill low">★ {game.rating}/10</span>}
            {game.price_paid != null && <span className="chip">{money(game.price_paid)}</span>}
            {game.bgg_url && <a className="small" href={game.bgg_url} target="_blank" rel="noreferrer">BoardGameGeek ↗</a>}
            {game.weight && <span className="pill purple" title="BoardGameGeek's weight: how complex it is, 1 to 5">
              {weightName(Number(game.weight))} · {Number(game.weight)}/5</span>}
            {game.shop_url && <a className="small" href={game.shop_url} target="_blank" rel="noreferrer">
              {game.shop_name ?? 'Gameology'}{game.shop_price != null && ` ${money(game.shop_price)}`} ↗</a>}
            {!game.shop_handle && !finding && <button type="button" className="plain small" onClick={() => setFinding(true)}>Fill in from a shop</button>}
          </div>
        </div>
      </div>
      {(game.categories.length > 0 || game.mechanisms.length > 0) && (
        <section className="panel-section game-tags">
          {game.categories.length > 0 && <p className="chips">{game.categories.map((c) => <span key={c} className="chip">{c}</span>)}</p>}
          {game.mechanisms.length > 0 && <p className="muted small">Mechanisms: {game.mechanisms.join(', ')}</p>}
        </section>
      )}
      {finding && (
        <ShopFind start={game.name} pickLabel="Fill in" onPick={(r) => run(async () => {
          show(await api.boardGameFromShop(game.game_id, r), `Filled in from ${r.shop_name} ✓`)
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
                  <span className="item-title">{shortDate(p.played_on)}{!p.finished ? <span className="pill low">Abandoned</span>
                    : p.winner && <span className="pill ok">🏆 {p.winner}</span>}</span>
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
  const [kind, setKind] = useState(game?.kind ?? 'game')
  const [baseId, setBaseId] = useState(game?.base_game_id ? String(game.base_game_id) : '')
  const [bases, setBases] = useState([])       // your games that are games (an expansion's base)
  useEffect(() => {
    api.listBoardGames().then((all) => setBases(all.filter((g) => g.kind === 'game' && g.game_id !== game?.game_id))).catch(() => {})
  }, [game?.game_id])
  const [picked, setPicked] = useState(null)   // the shop product the form was filled from
  // Fill the form from a Gameology product (your typing after this still wins when you save).
  const pick = (r) => {
    setPicked(r)
    if (r.kind) setKind(r.kind)
    setForm((f) => ({ ...f, ...Object.fromEntries(['name', 'publisher', 'min_players', 'max_players', 'play_minutes', 'min_age']
      .filter((k) => r[k] != null).map((k) => [k, String(r[k])])) }))
  }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { lookups } = useApp()

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = { ...payload(), status, kind, base_game_id: kind !== 'game' && baseId ? Number(baseId) : null,
        ...(!game && picked && shopRef(picked)) }
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
        <p className="alert ok small">Filled in from {picked.shop_name}: {picked.title}{picked.weight && ` · weight ${picked.weight}`}
          {picked.image_url && ' (its photo, categories and price are added once you save)'}.{' '}
          <button type="button" className="plain small" onClick={() => setPicked(null)}>Pick another</button></p>
      ) : <ShopFind onPick={pick} />)}
      <form id="game-form" onSubmit={submit}>
        <div className="segmented form-segmented" role="group" aria-label="Status">
          {lookups.game_statuses.map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)}>{s}</button>
          ))}
        </div>
        <div className="game-kind">
          <div className="segmented form-segmented" role="group" aria-label="Type">
            {KINDS.map(([k, label]) => <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{label}</button>)}
          </div>
          {kind !== 'game' && (
            <label className="field">
              <span className="field-label">{kind === 'expansion' ? 'Expansion for' : 'Goes with'}</span>
              <select value={baseId} onChange={(e) => setBaseId(e.target.value)}>
                <option value="">{picked ? 'Found from the shop when you save' : '—'}</option>
                {bases.map((g) => <option key={g.game_id} value={g.game_id}>{g.name}</option>)}
              </select>
            </label>
          )}
        </div>
        <RecordFields fields={GAME_FIELDS} form={form} set={set} />
      </form>
    </Drawer>
  )
}

// Log a play: inside a game's panel (gameId given), or on its own with a game picker (PlayPanel).
// The picker also offers "Someone else's game": type its name (a friend's copy) - it's added to your
// games as Played elsewhere. "Didn't finish" marks an abandoned game (no winner).
const ELSEWHERE = 'elsewhere'
function PlayForm({ gameId, games, onSaved, onCancel, day = null }) {
  const { form, set, payload } = useRecordForm(PLAY_FIELDS, null, { played_on: day ?? today() })
  const [pick, setPick] = useState(gameId ?? '')
  const [otherName, setOtherName] = useState('')
  const [unfinished, setUnfinished] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const elsewhere = pick === ELSEWHERE

  const save = async () => {
    if (!pick || (elsewhere && !otherName.trim())) { setError(elsewhere ? 'Which game was it?' : 'Which game?'); return }
    setBusy(true)
    setError('')
    const play = { ...payload(), finished: !unfinished, ...(unfinished ? { winner: null } : {}) }
    try {
      onSaved(elsewhere ? await api.addPlayElsewhere({ ...play, game_name: otherName.trim() }) : await api.addPlay(pick, play))
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
              {games.filter((g) => g.status !== 'Played elsewhere').map((g) => <option key={g.game_id} value={g.game_id}>{g.name}</option>)}
              {games.some((g) => g.status === 'Played elsewhere') && (
                <optgroup label="Played elsewhere">
                  {games.filter((g) => g.status === 'Played elsewhere').map((g) => <option key={g.game_id} value={g.game_id}>{g.name}</option>)}
                </optgroup>
              )}
              <option value={ELSEWHERE}>Someone else's game (not in my list)...</option>
            </select>
          </label>
          {elsewhere && (
            <label className="field wide">
              <span className="field-label">Their game <span className="req" aria-hidden="true"> *</span></span>
              <input value={otherName} onChange={(e) => setOtherName(e.target.value)} autoFocus placeholder="e.g. Wingspan"
                aria-label="Their game" />
              <span className="hint">Added to your games as "Played elsewhere" - not counted as yours.</span>
            </label>
          )}
        </fieldset>
      )}
      <label className="all-day-switch">
        <input type="checkbox" role="switch" checked={unfinished} onChange={(e) => setUnfinished(e.target.checked)} />
        <span>Didn't finish (abandoned)</span>
      </label>
      <RecordFields fields={unfinished ? PLAY_FIELDS.filter((f) => f.name !== 'winner') : PLAY_FIELDS} form={form} set={set} />
      <div className="button-row">
        <button type="button" className="primary" onClick={save} disabled={busy}>{busy ? 'Saving...' : 'Save play'}</button>
        <button type="button" className="plain" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

// "Log a play" from Home or the Plays page: pick the game, then the same form.
// day: the calendar event's day it was played (Log it).
export function PlayPanel({ gameId = null, day = null, onClose }) {
  const { changed, showToast } = useApp()
  const [games, setGames] = useState(null)
  useEffect(() => { api.listBoardGames().then((gs) => setGames(gs.filter((g) => g.status !== 'Gone'))).catch(() => setGames([])) }, [])
  return (
    <Drawer title="Log a play" onClose={onClose}>
      {!games ? <p className="muted">Loading...</p> : games.length === 0
        ? <p className="empty">Add a game first (Board games, "+ Add game").</p>
        : <PlayForm gameId={gameId} games={games} onCancel={onClose} day={day}
            onSaved={(p) => { changed(); showToast(`Logged a play of ${p.game_name}`); onClose() }} />}
    </Drawer>
  )
}
