import { useEffect, useState } from 'react'
import { api, money, shortDate, timeAgo } from '../../api.js'
import { LineChart } from '../../components/charts.jsx'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import { RowPhoto } from '../../components/RecordFields.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { FORMATS, GRADES, GradePill, MEDIUMS, RecordCover, SIZES, SLEEVE_GRADES, STATUSES, formatText, yearText } from './vinylParts.jsx'

// One record: the pressing, your copy (grades, paid, shelf, stars, notes), what it's worth (and how that's moved), the
// listening log (play it: which sides, a note, Last.fm), the tracklist, where to listen, journal pages about it.
export default function RecordPanel({ id, onClose }) {
  const { changed, showToast } = useApp()
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [lastfm, setLastfm] = useState(null)
  useEffect(() => {
    api.vinylRecord(id).then(setR).catch((e) => setError(e.message))
    api.vinylSettings().then((s) => setLastfm(s.lastfm)).catch(() => {})
  }, [id])
  if (!r) return <Drawer title="Record" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted loading">Loading...</p>}</Drawer>

  const reload = async (message) => {
    setR(await api.vinylRecord(id))
    changed()
    if (message) showToast(message)
  }
  const update = async (data) => {
    setError('')
    try {
      setR(await api.updateVinylRecord(id, data))
      changed()
    } catch (e) {
      setError(e.message)
    }
  }
  const remove = async () => {
    await api.deleteVinylRecord(id)
    showToast(`Removed ${r.title}`)
    changed()
    onClose()
  }
  const refresh = async () => {
    setError('')
    try {
      setR(await api.refreshVinylRecord(id))
      changed()
      showToast('Read again from Discogs')
    } catch (e) {
      setError(e.message)
    }
  }
  const search = encodeURIComponent([r.artist, r.title].filter(Boolean).join(' '))
  const footer = (
    <>
      {r.discogs_url && <a className="button secondary" href={r.discogs_url} target="_blank" rel="noreferrer">Discogs ↗</a>}
      <span className="spacer" />
      {!editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>}
      <button type="button" className="plain destructive" onClick={remove}>Remove</button>
    </>
  )
  return (
    <Drawer title={r.title} onClose={onClose} footer={footer} wide>
      <section className="panel-section vinyl-head">
        <RecordCover record={r} className="vinyl-cover large" />
        <div className="grow">
          <p className="vinyl-artist">{r.artist ?? 'Unknown artist'}</p>
          <p className="muted small">{[formatText(r), yearText(r), r.country].filter(Boolean).join(' · ')}</p>
          <p className="muted small">{[r.label, r.catno].filter(Boolean).join(' · ')}</p>
          {r.variant && <p className="small">{r.variant}</p>}
          {(r.genres.length > 0 || r.styles.length > 0) && (
            <p className="chips">{[...r.genres, ...r.styles].map((g) => <span key={g} className="chip">{g}</span>)}</p>
          )}
          <p className="vinyl-grades">
            <GradePill grade={r.media_condition} what="Record" /> <GradePill grade={r.sleeve_condition} what="Sleeve" />
            {r.rating && <span className="vinyl-stars" role="img" aria-label={`${r.rating} out of 5 stars`}>{'★'.repeat(r.rating)}</span>}
          </p>
        </div>
      </section>

      <section className="panel-section">
        <div className="segmented" role="group" aria-label="Status">
          {STATUSES.map(([s, label]) => <button key={s} type="button" aria-pressed={r.status === s} onClick={() => update({ status: s })}>{label}</button>)}
        </div>
      </section>

      {editing && <RecordForm record={r} onSaved={(x) => { setR(x); setEditing(false); changed() }} onCancel={() => setEditing(false)} />}

      {r.status !== 'Wanted' && <PlaySection record={r} lastfm={lastfm} onChanged={reload} />}

      <ValueSection record={r} onSet={(value) => update({ value })} />

      {!editing && (
        <section className="panel-section">
          <h3 className="section-title">Your copy</h3>
          <dl className="vinyl-facts">
            <dt>Record</dt><dd>{r.media_condition ? Object.fromEntries(GRADES)[r.media_condition] : 'Not graded'}</dd>
            <dt>Sleeve</dt><dd>{r.sleeve_condition ? Object.fromEntries(SLEEVE_GRADES)[r.sleeve_condition] : 'Not graded'}</dd>
            <dt>Paid</dt><dd>{r.price_paid != null ? money(r.price_paid) : '—'}{r.bought_from && ` at ${r.bought_from}`}{r.purchase_date && `, ${shortDate(r.purchase_date)}`}</dd>
            <dt>Shelf</dt><dd>{r.location ?? '—'}</dd>
            <dt>In the collection</dt><dd>since {shortDate(r.added_on)}</dd>
          </dl>
          {r.notes && <p className="vinyl-notes">{r.notes}</p>}
        </section>
      )}

      {r.tracklist.length > 0 && (
        <section className="panel-section">
          <Fold title="Tracklist" detail={`${r.tracklist.length} tracks`}>
            <ol className="vinyl-tracks">
              {r.tracklist.map((t, i) => (
                <li key={`${t.position}-${i}`}><span className="vinyl-pos">{t.position}</span><span className="grow">{t.title}</span>
                  <span className="muted small">{t.duration}</span></li>
              ))}
            </ol>
          </Fold>
        </section>
      )}

      <section className="panel-section">
        <h3 className="section-title">Listen</h3>
        <div className="button-row">
          <a className="button secondary small" href={`https://open.spotify.com/search/${search}`} target="_blank" rel="noreferrer">Spotify ↗</a>
          <a className="button secondary small" href={`https://music.apple.com/au/search?term=${search}`} target="_blank" rel="noreferrer">Apple Music ↗</a>
          {r.discogs_release_id && <button type="button" className="plain small" onClick={refresh}>Read again from Discogs</button>}
        </div>
      </section>

      <section className="panel-section">
        <h3 className="section-title">Cover</h3>
        <p className="muted small">Discogs' cover, or a photo of your own copy (handy for insurance).</p>
        <RowPhoto path={`/vinyl/records/${r.record_id}`} url={r.photo_url} label="cover" onChanged={reload} />
      </section>

      {error && <p className="alert error small">{error}</p>}
      <JournalMentions kind="record" id={r.record_id} name={r.title} onLeave={onClose} />
    </Drawer>
  )
}

// The sides on the record ("A", "B"...) from its tracklist.
const sidesOf = (tracks) => [...new Set(tracks.map((t) => (t.position.match(/^[A-Za-z]+/) ?? [''])[0].toUpperCase()).filter(Boolean))]

function PlaySection({ record: r, lastfm, onChanged }) {
  const sides = sidesOf(r.tracklist)
  const [picked, setPicked] = useState([])
  const [note, setNote] = useState('')
  const [scrobble, setScrobble] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { if (lastfm) setScrobble(lastfm.auto) }, [lastfm])
  const play = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const p = await api.logVinylPlay(r.record_id, { sides: picked.join(', ') || null, note: note || null,
        ...(lastfm?.connected && { scrobble }) })
      setPicked([])
      setNote('')
      await onChanged(`Played ${r.title}${p.scrobbling ? ' · sent to Last.fm' : ''}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  const toggle = (s) => setPicked(picked.includes(s) ? picked.filter((x) => x !== s) : [...picked, s])
  return (
    <section className="panel-section">
      <h3 className="section-title">Listening log</h3>
      <form className="vinyl-play-form" onSubmit={play}>
        {sides.length > 1 && (
          <div className="chip-row" role="group" aria-label="Sides played (none = the whole record)">
            {sides.map((s) => <button key={s} type="button" className="chip-filter" aria-pressed={picked.includes(s)} onClick={() => toggle(s)}>Side {s}</button>)}
          </div>
        )}
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="A note (optional)" aria-label="Note about this play" maxLength={2000} />
        {lastfm?.connected && (
          <label className="check small"><input type="checkbox" checked={scrobble} onChange={(e) => setScrobble(e.target.checked)} /> Send to Last.fm</label>
        )}
        <button type="submit" className="primary small" disabled={busy}>▶ {picked.length ? `Played side ${picked.join(' & ')}` : 'Played it'}</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
      {r.plays.length === 0 ? <p className="muted small">Never played here yet.</p> : (
        <ul className="list plain-list vinyl-play-log">
          {r.plays.map((p) => (
            <li key={p.play_id}>
              <span className="grow">
                <strong>{shortDate(p.played_at.slice(0, 10))}</strong>{p.sides && ` · side ${p.sides}`}
                {p.note && <span className="muted"> · {p.note}</span>}
                {p.scrobbled != null && <span className="muted small"> · {p.scrobbled} on Last.fm</span>}
                {p.scrobble_error && <span className="small vinyl-warn"> · {p.scrobble_error}</span>}
              </span>
              {p.scrobble_error && lastfm?.connected && (
                <button type="button" className="plain small" onClick={async () => { await api.scrobbleVinylPlay(p.play_id); onChanged() }}>Send again</button>
              )}
              <button type="button" className="icon-btn" aria-label={`Remove the play on ${shortDate(p.played_at.slice(0, 10))}`}
                onClick={async () => { await api.deleteVinylPlay(p.play_id); onChanged() }}>✕</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function ValueSection({ record: r, onSet }) {
  const [own, setOwn] = useState('')
  const [open, setOpen] = useState(false)
  const rows = r.values.map((v) => ({ x: v.seen_on, y: v.value, tip: v.note }))
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Worth</h3>
        {!open && <button type="button" className="plain small" onClick={() => { setOwn(r.value ?? ''); setOpen(true) }}>Set my own value</button>}
      </div>
      {r.value != null ? (
        <p><strong className="vinyl-value">{money(r.value)}</strong> <span className="muted small">{r.value_note}
          {r.value_checked_at && ` · checked ${timeAgo(r.value_checked_at)}`}</span>
          {r.price_paid != null && <span className={`small ${r.value >= r.price_paid ? 'ok-text' : 'vinyl-warn'}`}> · {r.value >= r.price_paid ? '+' : '−'}{money(Math.abs(r.value - r.price_paid))} on what you paid</span>}
        </p>
      ) : <p className="muted small">{r.discogs_release_id ? 'Not checked yet - values are read from Discogs once a week (or Vinyl → Connect → Check values now).' : 'Link it to Discogs (add it from a Discogs search) or set your own value.'}</p>}
      {(r.lowest_price != null || r.have_count != null) && (
        <p className="muted small">On Discogs: {[r.lowest_price != null && `from ${money(r.lowest_price)} (${r.for_sale ?? 0} for sale)`,
          r.have_count != null && `${r.have_count.toLocaleString()} have it`, r.want_count != null && `${r.want_count.toLocaleString()} want it`,
          r.community_rating && `${r.community_rating}★`].filter(Boolean).join(' · ')}</p>
      )}
      {open && (
        <form className="button-row" onSubmit={(e) => { e.preventDefault(); onSet(own === '' ? null : Number(own)); setOpen(false) }}>
          <label className="small">Value ($) <input type="number" min="0" step="0.01" value={own} onChange={(e) => setOwn(e.target.value)} aria-label="Your value" /></label>
          <button type="submit" className="primary small">Save</button>
          <button type="button" className="plain small" onClick={() => setOpen(false)}>Cancel</button>
        </form>
      )}
      {rows.length > 1 && <LineChart title="Value over time" rows={rows} valueLabel="AUD" height={140} />}
    </section>
  )
}

function RecordForm({ record: r, onSaved, onCancel }) {
  const { lookups } = useApp()
  const places = lookups?.locations ?? []
  const str = (v) => (v == null ? '' : String(v))
  const [f, setF] = useState({
    title: r.title, artist: str(r.artist), medium: r.medium, format: r.format, size: str(r.size), discs: str(r.discs), year: str(r.year),
    original_year: str(r.original_year), label: str(r.label), catno: str(r.catno), country: str(r.country), variant: str(r.variant),
    barcode: str(r.barcode), genres: r.genres.join(', '), styles: r.styles.join(', '), media_condition: str(r.media_condition),
    sleeve_condition: str(r.sleeve_condition), price_paid: str(r.price_paid), purchase_date: str(r.purchase_date), bought_from: str(r.bought_from),
    added_on: str(r.added_on), rating: str(r.rating), location_id: str(r.location_id), notes: str(r.notes),
  })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    setError('')
    const num = (v) => (v === '' ? null : Number(v))
    const list = (v) => v.split(',').map((x) => x.trim()).filter(Boolean)
    try {
      onSaved(await api.updateVinylRecord(r.record_id, {
        ...f, size: f.size || null, discs: num(f.discs) ?? 1, year: num(f.year), original_year: num(f.original_year),
        genres: list(f.genres), styles: list(f.styles), media_condition: f.media_condition || null, sleeve_condition: f.sleeve_condition || null,
        price_paid: f.price_paid === '' ? null : f.price_paid, purchase_date: f.purchase_date || null, added_on: f.added_on || r.added_on,
        rating: num(f.rating), location_id: num(f.location_id),
      }))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <section className="panel-section">
      <form className="vinyl-form" onSubmit={save}>
        <label>Title<input value={f.title} onChange={set('title')} required /></label>
        <label>Artist<input value={f.artist} onChange={set('artist')} /></label>
        <label>Record grade<select value={f.media_condition} onChange={set('media_condition')}>
          <option value="">Not graded</option>{GRADES.map(([g, name]) => <option key={g} value={g}>{g} · {name}</option>)}</select></label>
        <label>Sleeve grade<select value={f.sleeve_condition} onChange={set('sleeve_condition')}>
          <option value="">Not graded</option>{SLEEVE_GRADES.map(([g, name]) => <option key={g} value={g}>{g === name ? g : `${g} · ${name}`}</option>)}</select></label>
        <label>Paid ($)<input type="number" min="0" step="0.01" value={f.price_paid} onChange={set('price_paid')} /></label>
        <label>Bought on<input type="date" value={f.purchase_date} onChange={set('purchase_date')} /></label>
        <label>Bought from<input value={f.bought_from} onChange={set('bought_from')} placeholder="a shop, a market, a friend..." /></label>
        <label>In the collection since<input type="date" value={f.added_on} onChange={set('added_on')} /></label>
        <label>Shelf<select value={f.location_id} onChange={set('location_id')}>
          <option value="">Not set</option>{places.map((p) => <option key={p.location_id} value={p.location_id}>{p.name}</option>)}</select></label>
        <label>Your stars<select value={f.rating} onChange={set('rating')}>
          <option value="">None</option>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{'★'.repeat(n)}</option>)}</select></label>
        <label className="wide">Notes<textarea rows={3} value={f.notes} onChange={set('notes')} /></label>
        <label>Medium<select value={f.medium} onChange={set('medium')}>{MEDIUMS.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>Format<select value={f.format} onChange={set('format')}>{FORMATS.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>Size<select value={f.size} onChange={set('size')}><option value="">—</option>{SIZES.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>Discs<input type="number" min="1" max="100" value={f.discs} onChange={set('discs')} /></label>
        <label>This pressing's year<input type="number" min="1880" max="2200" value={f.year} onChange={set('year')} /></label>
        <label>First released<input type="number" min="1880" max="2200" value={f.original_year} onChange={set('original_year')} /></label>
        <label>Label<input value={f.label} onChange={set('label')} /></label>
        <label>Catalogue number<input value={f.catno} onChange={set('catno')} /></label>
        <label>Country<input value={f.country} onChange={set('country')} /></label>
        <label>Barcode<input value={f.barcode} onChange={set('barcode')} inputMode="numeric" /></label>
        <label className="wide">Variant<input value={f.variant} onChange={set('variant')} placeholder="Red translucent, 180 gram, numbered..." /></label>
        <label>Genres<input value={f.genres} onChange={set('genres')} placeholder="Rock, Jazz" /></label>
        <label>Styles<input value={f.styles} onChange={set('styles')} placeholder="Post-Punk, Hard Bop" /></label>
        <div className="button-row wide">
          <button type="submit" className="primary">Save details</button>
          <button type="button" className="plain" onClick={onCancel}>Cancel</button>
        </div>
        {error && <p className="alert error small wide">{error}</p>}
      </form>
    </section>
  )
}
