import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { pickGames, shelfHtml, thumb } from './shelfFile.js'

// "Share my shelf": choose what goes in, make the file (shelfFile.js), then download it or - on a phone - hand it
// to Messages / WhatsApp / email with the share sheet. Nothing is sent anywhere by the app: you send the file.
const today = () => new Date().toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })
const fileDay = () => new Date().toISOString().slice(0, 10)

async function withLimit(items, limit, work) {
  const out = []
  let next = 0
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next++
      out[i] = await work(items[i])
    }
  }))
  return out
}

export function ShelfSharePanel({ onClose }) {
  const [games, setGames] = useState(null)
  const [error, setError] = useState('')
  const [o, setO] = useState({ list: 'owned', title: '', note: '', photos: true, expansions: true, borrowed: false,
    plays: false, rating: false, links: true })
  const [busy, setBusy] = useState('')
  const [made, setMade] = useState(null)                 // {file, url, size}
  useEffect(() => {
    api.listBoardGames().then(setGames, (e) => setError(e.message))
  }, [])
  useEffect(() => () => { if (made) URL.revokeObjectURL(made.url) }, [made])
  const set = (k, v) => { setO((x) => ({ ...x, [k]: v })); setMade(null) }
  const count = games ? pickGames(games, o).length : 0

  const make = async () => {
    setError('')
    const cards = pickGames(games, o)
    let photos = {}
    if (o.photos) {
      const withPhoto = cards.filter((g) => g.photo_url)
      let done = 0
      setBusy(`Shrinking photos... 0 of ${withPhoto.length}`)
      const urls = await withLimit(withPhoto, 4, async (g) => {
        const u = await thumb(g.photo_url)
        setBusy(`Shrinking photos... ${++done} of ${withPhoto.length}`)
        return u
      })
      photos = Object.fromEntries(withPhoto.map((g, i) => [g.game_id, urls[i]]).filter(([, u]) => u))
    }
    const html = shelfHtml(games, { ...o, photos, made: today() })
    const name = `${o.list === 'wanted' ? 'games-i-would-like' : 'board-games'}-${fileDay()}.html`
    const file = new File([html], name, { type: 'text/html' })
    setMade({ file, url: URL.createObjectURL(file), size: file.size })
    setBusy('')
  }
  const share = async () => {
    try {
      await navigator.share({ files: [made.file], title: made.file.name })
    } catch (e) {
      if (e?.name !== 'AbortError') setError("This device couldn't share the file: download it and send it instead.")
    }
  }
  const canShare = made && typeof navigator !== 'undefined' && navigator.canShare?.({ files: [made.file] })
  const check = (k, label, hint) => (
    <label className="shs-check"><input type="checkbox" checked={o[k]} onChange={(e) => set(k, e.target.checked)} />
      <span>{label}{hint && <span className="muted small"> · {hint}</span>}</span></label>)

  return (
    <Drawer title="Share my shelf" onClose={onClose}>
      <p className="muted">Makes one web page file of your games to send to someone - by message, email or a Drive link. It
        opens in any browser, no sign-in, with search and &quot;how many players / how long&quot; filters. It&apos;s a
        snapshot: make a new one after you buy games. Prices, notes and where you bought them never go in.</p>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!games ? <p className="muted loading">Loading...</p> : (
        <div className="shs-form">
          <div className="field" role="group" aria-label="Which list">
            <span>Which list</span>
            <div className="shs-choice">
              <button type="button" className="chip-filter" aria-pressed={o.list === 'owned'} onClick={() => set('list', 'owned')}>Games I own</button>
              <button type="button" className="chip-filter" aria-pressed={o.list === 'wanted'} onClick={() => set('list', 'wanted')}>Games I&apos;d like</button>
            </div>
          </div>
          <label className="field">Title
            <input value={o.title} onChange={(e) => set('title', e.target.value)} placeholder={o.list === 'wanted' ? "Games I'd like" : 'My board games'} /></label>
          <label className="field">A note at the top (optional)
            <textarea rows={2} value={o.note} onChange={(e) => set('note', e.target.value)} placeholder="e.g. Pick one for Friday night!" /></label>
          <fieldset className="shs-checks">
            <legend>Put in</legend>
            {check('photos', 'Photos', 'small copies, so the file stays a few MB')}
            {check('expansions', 'Expansions on their game')}
            {o.list === 'owned' && check('borrowed', 'Games I have on loan')}
            {check('plays', 'How often I\'ve played each')}
            {check('rating', 'My ratings')}
            {check('links', 'Links to BoardGameGeek')}
          </fieldset>
          <p className="muted small">{count} game{count === 1 ? '' : 's'} on {o.list === 'wanted' ? 'the list' : 'the shelf'}.</p>
          <div className="button-row">
            <button type="button" className="primary" disabled={!!busy || !count} onClick={make}>{busy ? 'Making...' : made ? 'Make it again' : 'Make the file'}</button>
          </div>
          {busy && <p className="muted small" role="status">{busy}</p>}
          {made && (
            <div className="card shs-done" role="status">
              <p><strong>{made.file.name}</strong> · {Math.max(1, Math.round(made.size / 1024)).toLocaleString()} KB</p>
              <div className="button-row">
                <a className="button primary" href={made.url} download={made.file.name}>Download</a>
                {canShare && <button type="button" className="secondary" onClick={share}>Share...</button>}
              </div>
              <p className="muted small">Send the file itself (attach it, or put it on Google Drive and share the link). The person opens
                it in their browser. Open the downloaded file yourself to see what they'll see.</p>
            </div>
          )}
        </div>
      )}
    </Drawer>
  )
}
