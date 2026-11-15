import { useEffect, useRef, useState } from 'react'
import { api, money, shopRef, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import RecordFields, { RowPhoto, useRecordForm } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { FunPicker, PlayPhotos, PlayerPicker, SCORING, SeatScores, minutesText, placeText, scoreText, seatsOut } from './tableParts.jsx'

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
  { name: 'teach_notes', label: 'Teach notes', type: 'textarea', placeholder: 'What to cover when you teach it: the goal, a turn, how it ends, tips' },
]

const PLAY_FIELDS = [
  { name: 'played_on', label: 'Day', type: 'date', required: true },
  { name: 'location', label: 'Where', list: 'bgt-log-places', placeholder: 'e.g. Home, an event' },
  { name: 'setup_minutes', label: 'Setup (minutes)', type: 'number' },
  { name: 'teach_minutes', label: 'Teach (minutes)', type: 'number' },
  { name: 'minutes', label: 'Playing (minutes)', type: 'number', min: 1 },
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
          {!logging && (
            <span className="button-row">
              {game.status !== 'Wanted' && game.kind === 'game' && (
                <button type="button" className="primary" onClick={() => { onClose(); openPanel('liveplay', { gameId: game.game_id }) }}>▶ Start a play</button>
              )}
              <button type="button" className="secondary" onClick={() => setLogging(true)}>+ Log a play</button>
            </span>
          )}
        </div>
        {game.stats && <GameStats stats={game.stats} scoring={game.scoring} />}
        {logging && (
          <PlayForm gameId={game.game_id} onCancel={() => setLogging(false)}
            onSaved={(p) => { setLogging(false); run(() => reload(p.highlights?.[0] ?? 'Play logged ✓')) }} />
        )}
        {game.play_log.length === 0 && !logging && <p className="muted small">Not played yet.</p>}
        {game.play_log.length > 0 && (
          <ul className="list compact plays">
            {game.play_log.map((p) => <PlayRow key={p.play_id} play={p} onChanged={(msg) => run(() => reload(msg))} />)}
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
  const [scoring, setScoring] = useState(game?.scoring ?? 'highest')
  const [parts, setParts] = useState((game?.score_parts ?? []).join(', '))
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
      const body = { ...payload(), status, kind, base_game_id: kind !== 'game' && baseId ? Number(baseId) : null, scoring,
        score_parts: parts.split(',').map((x) => x.trim()).filter(Boolean),
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
        {kind === 'game' && (
          <fieldset className="bgt-scoring">
            <label className="field">
              <span className="field-label">Scoring</span>
              <select value={scoring} onChange={(e) => setScoring(e.target.value)} aria-label="Scoring">
                {SCORING.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>
            </label>
            {(scoring === 'highest' || scoring === 'lowest') && (
              <label className="field wide">
                <span className="field-label">Score sheet (optional)</span>
                <input value={parts} onChange={(e) => setParts(e.target.value)} placeholder="e.g. Birds, Bonus cards, Goals, Eggs, Food, Tucked"
                  aria-label="Score sheet" />
                <span className="hint">The parts a score is made of, separated by commas: each player fills them in and they're added up.
                  Leave it empty to keep one total with +/- buttons.</span>
              </label>
            )}
          </fieldset>
        )}
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
  const [roster, setRoster] = useState(null)
  const [game, setGame] = useState(null)        // the picked game in full: how it's scored, its expansions
  const [seats, setSeats] = useState([])
  const [coopWon, setCoopWon] = useState(null)
  const [expansions, setExpansions] = useState([])
  const [fun, setFun] = useState(null)
  const [firstId, setFirstId] = useState('')
  const elsewhere = pick === ELSEWHERE
  useEffect(() => {
    api.boardGamePlayers().then((r) => {
      setRoster(r)
      const me = r.players.find((p) => p.is_me)
      if (me) setSeats((s) => (s.length ? s : [{ player_id: me.player_id, name: me.name, is_me: true, adds: [] }]))
    }).catch(() => setRoster({ players: [], groups: [], places: [] }))
  }, [])
  useEffect(() => {
    setExpansions([])
    if (!pick || pick === ELSEWHERE) { setGame(null); return }
    api.getBoardGame(pick).then(setGame).catch(() => setGame(null))
  }, [pick])
  const scoring = game?.scoring ?? 'highest'

  const save = async () => {
    if (!pick || (elsewhere && !otherName.trim())) { setError(elsewhere ? 'Which game was it?' : 'Which game?'); return }
    setBusy(true)
    setError('')
    const first = seats.find((s) => (s.player_id != null ? `p${s.player_id}` : `n${s.name}`) === firstId)
    const play = { ...payload(), finished: !unfinished, seats: seatsOut(unfinished ? seats.map((s) => ({ ...s, won: null })) : seats),
      coop_won: scoring === 'coop' && !unfinished ? coopWon : null, expansions, fun, first_player_id: first?.player_id ?? null }
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
      <div className="bgt-log-section">
        <span className="field-label">Who played</span>
        {roster ? <PlayerPicker chosen={seats} onChange={setSeats} roster={roster} max={game?.max_players} /> : <p className="muted small">Loading...</p>}
      </div>
      {!unfinished && seats.length > 0 && (
        <div className="bgt-log-section">
          <span className="field-label">{scoring === 'coop' ? 'How did it go?' : scoring === 'none' ? 'Who won' : 'Scores'}</span>
          <SeatScores seats={seats} onChange={setSeats} scoring={scoring} parts={game?.score_parts ?? []} coopWon={coopWon} onCoopWon={setCoopWon} />
        </div>
      )}
      {seats.length > 1 && (
        <label className="field">
          <span className="field-label">Who went first</span>
          <select value={firstId} onChange={(e) => setFirstId(e.target.value)} aria-label="Who went first">
            <option value="">—</option>
            {seats.map((s) => { const k = s.player_id != null ? `p${s.player_id}` : `n${s.name}`; return <option key={k} value={k} disabled={s.player_id == null}>{s.name}</option> })}
          </select>
        </label>
      )}
      {game?.add_on_list?.length > 0 && (
        <fieldset className="bgt-expansions">
          <legend className="field-label">Expansions in</legend>
          {game.add_on_list.map((e) => (
            <label key={e.game_id} className="check-row">
              <input type="checkbox" checked={expansions.includes(e.game_id)}
                onChange={(ev) => setExpansions(ev.target.checked ? [...expansions, e.game_id] : expansions.filter((x) => x !== e.game_id))} />
              {e.name}
            </label>
          ))}
        </fieldset>
      )}
      <RecordFields fields={PLAY_FIELDS} form={form} set={set} />
      <datalist id="bgt-log-places">{(roster?.places ?? []).map((pl) => <option key={pl} value={pl} />)}</datalist>
      <FunPicker value={fun} onChange={setFun} />
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
            onSaved={(p) => { changed(); showToast(p.highlights?.[0] ? `⭐ ${p.highlights[0]}` : `Logged a play of ${p.game_name}`); onClose() }} />}
    </Drawer>
  )
}

// A game's numbers so far: how long it takes to teach and play, how fun it is, your best and the record.
function GameStats({ stats, scoring }) {
  const bits = [
    stats.avg_teach != null && `teach ${minutesText(stats.avg_teach)}`,
    stats.avg_minutes != null && `play ${minutesText(stats.avg_minutes)}`,
    stats.my_plays > 0 && `you've won ${stats.my_wins} of ${stats.my_plays}${scoring === 'coop' ? ' (co-op)' : ''}`,
    stats.my_best != null && `your best ${scoreText(stats.my_best)}`,
    stats.record && `record ${scoreText(stats.record.score)} (${stats.record.is_me ? 'you' : stats.record.name})`,
    stats.avg_fun != null && `fun ★ ${Number(stats.avg_fun)}`,
  ].filter(Boolean)
  return bits.length ? <p className="muted small bgt-game-stats">{bits.join(' · ')}</p> : null
}

// One play: when, who won, the scores (place by place), times, where, expansions, photos. Tap for photos and more.
function PlayRow({ play: p, onChanged }) {
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [error, setError] = useState('')
  const scores = p.seats.filter((s) => s.score != null)
  const meta = [
    !scores.length && p.players,
    p.location,
    [p.setup_minutes != null && `setup ${p.setup_minutes}`, p.teach_minutes != null && `teach ${p.teach_minutes}`,
      p.minutes != null && `${p.teach_minutes != null || p.setup_minutes != null ? 'play ' : ''}${p.minutes} min`].filter(Boolean).join(' / '),
    p.first_player && `${p.first_player} went first`,
    p.expansion_names?.length > 0 && `with ${p.expansion_names.join(', ')}`,
    p.rounds && `${p.rounds} rounds`,
    p.fun && '★'.repeat(p.fun),
  ].filter(Boolean)
  const run = async (fn, msg) => {
    setError('')
    try { await fn(); onChanged(msg) } catch (e) { setError(e.message) }
  }
  return (
    <li className="play-row bgt-play">
      <div className="bgt-play-main">
        <button type="button" className="bgt-play-open" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="item-title">{shortDate(p.played_on)}{!p.finished ? <span className="pill low">Abandoned</span>
            : p.scoring === 'coop' ? (p.coop_won ? <span className="pill ok">Won together</span> : p.coop_won === false && <span className="pill low">The game won</span>)
              : p.winner && <span className="pill ok">🏆 {p.winner}</span>}
            {p.photos.length > 0 && <span className="pill">📷 {p.photos.length}</span>}</span>
          {scores.length > 0 && (
            <span className="bgt-play-scores">{p.seats.map((s) => (
              <span key={s.player_id} className={s.won ? 'bgt-won' : ''}>{s.name} {scoreText(s.score)}{s.first_time && <span className="muted"> (new)</span>}</span>
            ))}</span>
          )}
          {meta.length > 0 && <span className="item-meta">{meta.join(' · ')}</span>}
        </button>
        <button type="button" className="icon-btn small" aria-label={`Delete the play on ${shortDate(p.played_on)}`}
          onClick={() => setConfirm(!confirm)}>✕</button>
      </div>
      {confirm && (
        <span className="confirm small">Delete this play?
          <button type="button" className="danger small" onClick={() => run(() => api.deletePlay(p.play_id), 'Play deleted')}>Delete</button>
          <button type="button" className="plain small" onClick={() => setConfirm(false)}>Cancel</button>
        </span>
      )}
      {error && <p className="alert error small">{error}</p>}
      {open && (
        <div className="bgt-play-more">
          {p.seats.some((s) => s.place != null || s.colour) && (
            <ol className="bgt-standings">
              {p.seats.map((s) => (
                <li key={s.player_id}>{s.place ? <strong>{placeText(s.place)}</strong> : <span />}<span>{s.name}{s.colour && <span className="muted"> · {s.colour}</span>}</span>
                  <span>{scoreText(s.score)}{s.parts && <span className="muted small"> ({Object.entries(s.parts).map(([k, v]) => `${k} ${scoreText(v)}`).join(', ')})</span>}</span></li>
              ))}
            </ol>
          )}
          {p.notes && <p className="detail-desc">{p.notes}</p>}
          <PlayPhotos photos={p.photos} onAdd={(blob) => api.addPlayPhoto(p.play_id, blob).then(() => onChanged('Photo added ✓'))}
            onRemove={(ph) => run(() => api.deletePlayPhoto(ph.photo_id), 'Photo removed')} />
          <FunPicker value={p.fun} onChange={(n) => run(() => api.updatePlay(p.play_id, { fun: n }), 'Saved ✓')} />
        </div>
      )}
    </li>
  )
}
