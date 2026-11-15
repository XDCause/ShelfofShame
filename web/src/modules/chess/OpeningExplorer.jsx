import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api.js'
import PlayBoard, { useChessJs } from './PlayBoard.jsx'
import { formatLine, gamesText, mineText } from './openingHelpers.js'

// The Openings tab's "Explore": play moves from the start (or a line you chose) and see, for each position, its name,
// what people play next (Lichess players near your rating, or masters), the theory moves, how you have done from here,
// and - for any reply - "How to meet it" (the answer to play, and why). All answers come from api/app/chess_trainer.py.

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const percent = (n) => (n > 0 && n < 1 ? '<1%' : `${Math.round(n)}%`)
// Lichess's rating buckets ("0,1000" = from 0 up to the next bucket): shown as a range, "rated up to 1199".
const BUCKETS = [0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500, 3200]
export function ratingBand(list) {
  const got = String(list ?? '').split(',').map(Number).filter((n) => !Number.isNaN(n)).sort((a, b) => a - b)
  if (!got.length) return 'all ratings'
  const top = BUCKETS[BUCKETS.indexOf(got.at(-1)) + 1]
  const high = top ? top - 1 : null
  return got[0] === 0 ? (high ? `up to ${high}` : 'all ratings') : high ? `${got[0]}-${high}` : `${got[0]}+`
}

export default function OpeningExplorer({ start = [], onLearn }) {
  const Chess = useChessJs()
  const [sans, setSans] = useState(start)
  const [cursor, setCursor] = useState(start.length)
  const [flipped, setFlipped] = useState(false)
  const [source, setSource] = useState('lichess')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [engine, setEngine] = useState(null)        // { key, lines } for the position it was asked about
  const [advice, setAdvice] = useState(null)        // { key, move, error } likewise
  const [busy, setBusy] = useState(null)
  const shown = useMemo(() => sans.slice(0, cursor), [sans, cursor])
  const key = shown.join(' ')

  const position = useMemo(() => {
    if (!Chess) return { fen: START, last: null }
    const game = new Chess()
    let last = null
    try { for (const san of shown) last = game.move(san) } catch { last = null }
    return { fen: game.fen(), last: last && { from: last.from, to: last.to } }
  }, [Chess, shown])

  useEffect(() => {
    let stale = false
    setData(null)
    api.trainerExplore({ moves: key })
      .then((d) => { if (!stale) { setData(d); setError(null) } })
      .catch((e) => { if (!stale) setError(e.message) })
    return () => { stale = true }
  }, [key])

  const play = (san) => { setSans([...shown, san]); setCursor(shown.length + 1) }
  const askEngine = () => {
    setBusy('engine')
    api.trainerExplore({ moves: key }, true)
      .then((d) => setEngine({ key, lines: d.engine ?? [] }))
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null))
  }
  // "How to meet it": play their reply on the board, then ask for the answer to it.
  const meet = (san) => {
    const next = [...shown, san]
    const nextKey = next.join(' ')
    setSans(next)
    setCursor(next.length)
    setBusy('meet')
    api.trainerRecommend({ moves: nextKey })
      .then((r) => setAdvice({ key: nextKey, move: r.move, error: r.explorer_error }))
      .catch((e) => setAdvice({ key: nextKey, move: null, error: e.message }))
      .finally(() => setBusy(null))
  }

  const table = source === 'lichess' ? data?.lichess : data?.masters
  const note = advice?.key === key ? advice : null
  const lines = engine?.key === key ? engine.lines : null
  const arrows = note?.move ? [{ from: note.move.from, to: note.move.to, colour: 'best' }] : []
  const marks = position.last ? { [position.last.from]: 'from', [position.last.to]: 'to' } : {}
  const mineMoves = data?.mine.moves.filter((m) => m.mine).slice(0, 3) ?? []
  const theirMoves = data?.mine.moves.filter((m) => !m.mine).slice(0, 3) ?? []
  const named = data?.name

  return (
    <div className="ot-explore">
      <div className="ot-boardside">
        <PlayBoard fen={position.fen} orientation={flipped ? 'black' : 'white'} onMove={(m) => play(m.san)} arrows={arrows} marks={marks}
          label={`Opening board${key ? `: ${formatLine(shown)}` : ''}`} />
        <div className="ot-controls">
          <button type="button" className="secondary small" onClick={() => setCursor(0)} disabled={cursor === 0} aria-label="Back to the start">«</button>
          <button type="button" className="secondary small" onClick={() => setCursor(cursor - 1)} disabled={cursor === 0} aria-label="Back one move">‹</button>
          <button type="button" className="secondary small" onClick={() => setCursor(cursor + 1)} disabled={cursor >= sans.length} aria-label="Forward one move">›</button>
          <button type="button" className="secondary small" onClick={() => setCursor(sans.length)} disabled={cursor >= sans.length} aria-label="Forward to the end">»</button>
          <button type="button" className="secondary small" onClick={() => setFlipped(!flipped)}>Flip board</button>
        </div>
        {sans.length > 0 && (
          <p className="ot-movelist" aria-label="Moves played">
            {sans.map((san, i) => (
              <span key={`${i}-${san}`} className="ot-ply-wrap">
                {i % 2 === 0 && <span className="ot-num">{i / 2 + 1}.</span>}
                <button type="button" className={`ot-ply${i + 1 === cursor ? ' now' : ''}`} onClick={() => setCursor(i + 1)}>{san}</button>
              </span>
            ))}
          </p>
        )}
      </div>

      <div className="ot-side">
        <div className="ot-name">
          <strong>{named ? named.name : shown.length ? 'Not a named opening (yet)' : 'The starting position'}</strong>
          {named && <span className="muted small"> {named.eco}</span>}
          {data && <span className="muted small"> · {data.turn === 'white' ? 'White' : 'Black'} to move</span>}
        </div>
        {error && <p className="alert error small">{error}</p>}
        {!data && !error && <p className="muted loading">Loading...</p>}
        {data?.explorer_error && <p className="alert low small">{data.explorer_error}</p>}

        {note && (
          <div className="ot-advice" role="status">
            {note.move ? (
              <>
                <strong>Meet it with {note.move.san}.</strong>{' '}
                <span>{note.move.note}</span>
              </>
            ) : <span>No answer found{note.error ? `: ${note.error}` : '.'}</span>}
          </div>
        )}
        {busy === 'meet' && <p className="muted small loading">Finding the answer...</p>}

        {data && !data.game_over && (
          <>
            {data.lichess || data.masters ? (
              <div className="ot-tablehead">
                <div className="segmented" role="group" aria-label="Where the moves come from">
                  <button type="button" aria-pressed={source === 'lichess'} onClick={() => setSource('lichess')}>Players</button>
                  <button type="button" aria-pressed={source === 'masters'} onClick={() => setSource('masters')}>Masters</button>
                </div>
                <span className="muted small">
                  {source === 'lichess' ? `Lichess games rated ${ratingBand(data.ratings)}` : 'Master games'}
                  {table ? ` · ${gamesText(table.total)} games` : ''}
                </span>
              </div>
            ) : null}
            {table && table.moves.length > 0 && (
              <ul className="ot-moves">
                {table.moves.map((m) => (
                  <li key={m.uci} className="ot-move">
                    <button type="button" className="ot-move-main" onClick={() => play(m.san)}
                      aria-label={`${m.san}: played in ${percent(m.share)} of games. White ${m.white}%, draws ${m.draws}%, Black ${m.black}%`}>
                      <span className="ot-san">{m.san}{m.theory && <span className="ot-book" title={m.name ?? 'Known theory'}> ●</span>}</span>
                      <span className="ot-share">{percent(m.share)}</span>
                      <span className="ot-wdl" aria-hidden="true">
                        <span className="ot-wdl-w" style={{ flexGrow: m.white }} />
                        <span className="ot-wdl-d" style={{ flexGrow: m.draws }} />
                        <span className="ot-wdl-b" style={{ flexGrow: m.black }} />
                      </span>
                      <span className="ot-rating muted small">{m.avg_rating ?? ''}</span>
                    </button>
                    <button type="button" className="plain small ot-meet" onClick={() => meet(m.san)} disabled={busy === 'meet'}>How to meet it</button>
                  </li>
                ))}
              </ul>
            )}
            {table && table.moves.length === 0 && <p className="muted small">Nobody has played on from here{source === 'lichess' ? ' at this rating' : ''}.</p>}

            {data.theory.length > 0 && (
              <div className="ot-theory">
                <span className="muted small">Theory moves:</span>
                {data.theory.map((t) => (
                  <button key={t.san} type="button" className="chip ot-theory-move" onClick={() => play(t.san)} title={t.name ?? ''}>
                    {t.san}{t.name ? ` - ${t.name}` : ''}
                  </button>
                ))}
              </div>
            )}
            {data.theory.length === 0 && data.in_book === false && shown.length > 0 && <p className="muted small">Out of book: no named opening goes on from here.</p>}

            <div className="ot-mine">
              {mineText(data.mine) ? (
                <>
                  <p className="small">{mineText(data.mine)}</p>
                  {mineMoves.length > 0 && <p className="muted small">You usually play {mineMoves.map((m) => `${m.san} (${m.games}: +${m.wins} =${m.draws} -${m.losses})`).join(', ')}</p>}
                  {theirMoves.length > 0 && <p className="muted small">Your opponents usually play {theirMoves.map((m) => `${m.san} (${m.games})`).join(', ')}</p>}
                </>
              ) : <p className="muted small">None of your games has been here yet.</p>}
            </div>

            <div className="ot-actions">
              <button type="button" className="secondary small" onClick={askEngine} disabled={busy === 'engine'}>
                {busy === 'engine' ? 'Thinking...' : 'Ask the engine'}</button>
              {onLearn && shown.length > 0 && (
                <button type="button" className="primary small" onClick={() => onLearn({ moves: shown, name: named?.name })}>Learn this line...</button>
              )}
            </div>
            {lines && (lines.length > 0 ? (
              <ul className="ot-engine">
                {lines.map((l) => <li key={l.uci}><strong>{l.san}</strong> <span className="muted small">{l.text} for the side to move</span>
                  <button type="button" className="plain small" onClick={() => play(l.san)}>Play it</button></li>)}
              </ul>
            ) : <p className="muted small">The engine isn't available just now.</p>)}
          </>
        )}
        {data?.game_over && <p className="muted small">The game is over here.</p>}
      </div>
    </div>
  )
}
