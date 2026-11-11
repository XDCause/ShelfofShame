import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, money, shortDate, timeAgo, vinylExportUrl } from '../../api.js'
import { BarList, ColumnChart, LineChart } from '../../components/charts.jsx'
import { VinylIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { GradePill, PlayedButton, RecordCover, StatusPill, formatText, moneyLine, useVinylSummary } from './vinylParts.jsx'

// The Vinyl hobby's pages: a dashboard (now spinning, what to play next, recently played and added, gathering dust),
// the crate (every record as covers, filtered), the listening log, stats, and Connect (Discogs, Last.fm, export).

const plural = (n, one, many = `${one}s`) => `${n.toLocaleString()} ${n === 1 ? one : many}`
const monthName = (ym, long = false) => new Date(`${ym}-15T12:00:00`)
  .toLocaleDateString('en-AU', long ? { month: 'long', year: 'numeric' } : { month: 'short', year: '2-digit' })

export function Dashboard() {
  const { data: s, error } = useVinylSummary()
  const { openPanel } = useApp()
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  if (!s.owned && !s.wanted && !s.gone) {
    return (
      <section className="page vinyl">
        <section className="card empty-start">
          <h2 className="home-card-title">Start your crate</h2>
          <p className="muted small">Bring your collection across from Discogs, or add a record by searching or scanning its barcode.</p>
          <div className="button-row">
            <Link className="button primary" to="/vinyl/connect">Sync with Discogs</Link>
            <button type="button" className="secondary" onClick={() => openPanel('addrecord', {})}>+ Add a record</button>
          </div>
        </section>
      </section>
    )
  }
  const spunPct = s.owned ? Math.round((100 * s.spun_this_year) / s.owned) : 0
  return (
    <section className="page vinyl">
      {s.now_spinning && <NowSpinning play={s.now_spinning} />}
      <div className="home-stats">
        <Stat to="/vinyl/crate" Icon={VinylIcon} tone="tint" value={s.owned} label="Records" sub={`${s.wanted} on the wantlist`} />
        <Stat to="/vinyl/plays" Icon={VinylIcon} tone="teal" value={s.plays_this_month} label="Plays this month" sub={`${plural(s.plays_this_year, 'play')} this year`} />
        <Stat to="/vinyl/crate?sort=dusty" Icon={VinylIcon} tone="ok" value={`${spunPct}%`} label={`Played in ${s.year}`}
          sub={`${s.spun_this_year} of ${s.owned} records`} />
        <Stat to="/vinyl/stats" Icon={VinylIcon} tone="purple" value={s.value ? money(s.value) : money(s.paid)} label={s.value ? 'Worth today' : 'Paid'}
          sub={s.value ? `${s.valued} of ${s.owned} valued${s.paid ? ` · ${money(s.paid)} paid` : ''}` : 'values come from Discogs weekly'} />
      </div>
      <div className="home-grid">
        <div className="home-stack">
          <PickCard />
          <section className="card home-card">
            <h2 className="home-card-title">Recently played</h2>
            {s.recent_plays.length === 0 ? <p className="muted small">Press ▶ Played it on a record and it shows here.</p> : (
              <ul className="list plain-list">{s.recent_plays.map((p) => <PlayRow key={p.play_id} play={p} />)}</ul>
            )}
            <Link className="button plain small" to="/vinyl/plays">The listening log →</Link>
          </section>
        </div>
        <div className="home-stack">
          <section className="card home-card">
            <div className="section-head">
              <h2 className="home-card-title">Recently added</h2>
              <button type="button" className="plain small" onClick={() => openPanel('addrecord', {})}>+ Add a record</button>
            </div>
            <div className="vinyl-shelf">{s.recently_added.map((r) => <CoverButton key={r.record_id} record={r} />)}</div>
            <Link className="button plain small" to="/vinyl/crate?sort=added">The whole crate →</Link>
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Gathering dust</h2>
            <p className="muted small chart-sub">{s.dusty_count === 0 ? 'Every record has had a spin in the last year.'
              : `${plural(s.dusty_count, 'record')} not played in a year (or never played here).`}</p>
            {s.dusty.length > 0 && <div className="vinyl-shelf">{s.dusty.map((r) => <CoverButton key={r.record_id} record={r} />)}</div>}
          </section>
        </div>
      </div>
    </section>
  )
}

function NowSpinning({ play: p }) {
  const { openPanel } = useApp()
  return (
    <section className="card vinyl-now" aria-label="Now spinning">
      <button type="button" className="cover-button" onClick={() => openPanel('record', { id: p.record_id })} aria-label={`Open ${p.title}`}>
        <RecordCover record={p} className="vinyl-cover" />
      </button>
      <span className="grow">
        <span className="vinyl-now-label">Now spinning</span>
        <strong>{p.title}</strong>
        <span className="item-meta">{[p.artist, p.sides && `side ${p.sides}`, timeAgo(p.played_at)].filter(Boolean).join(' · ')}</span>
      </span>
    </section>
  )
}

// "What should I play?": one you've never played, else one you've gone longest without. "Another" skips it.
function PickCard() {
  const { refreshKey, openPanel } = useApp()
  const [pick, setPick] = useState(undefined)
  const [skip, setSkip] = useState([])
  useEffect(() => { api.vinylPick(skip).then(setPick).catch(() => setPick(null)) }, [skip, refreshKey])
  if (pick === null) return null
  return (
    <section className="card home-card vinyl-pick">
      <h2 className="home-card-title">What should I play?</h2>
      {!pick ? <p className="muted small loading">Picking...</p> : (
        <div className="vinyl-pick-row">
          <button type="button" className="cover-button" onClick={() => openPanel('record', { id: pick.record_id })} aria-label={`Open ${pick.title}`}>
            <RecordCover record={pick} className="vinyl-cover" />
          </button>
          <span className="grow">
            <span className="item-title">{pick.title}</span>
            <span className="item-meta">{pick.artist}</span>
            <span className="item-meta">{pick.last_played ? `Last played ${timeAgo(pick.last_played)}` : 'Never played here'}</span>
            <span className="button-row">
              <PlayedButton record={pick} className="primary small" />
              <button type="button" className="plain small" onClick={() => setSkip([...skip, pick.record_id].slice(-50))}>Another</button>
            </span>
          </span>
        </div>
      )}
    </section>
  )
}

function CoverButton({ record: r }) {
  const { openPanel } = useApp()
  return (
    <button type="button" className="cover-card" onClick={() => openPanel('record', { id: r.record_id })}>
      <RecordCover record={r} className="vinyl-cover" />
      <span className="cover-card-title">{r.title}</span>
      <span className="item-meta vinyl-card-artist">{r.artist}</span>
    </button>
  )
}

function PlayRow({ play: p, onRemove }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('record', { id: p.record_id })}>
        <RecordCover record={p} className="vinyl-cover small" />
        <span className="grow">
          <span className="item-title">{p.title}</span>
          <span className="item-meta">{[p.artist, p.sides && `side ${p.sides}`, p.note].filter(Boolean).join(' · ')}</span>
        </span>
        <span className="muted small">{timeAgo(p.played_at)}{p.scrobbled != null && ' · Last.fm ✓'}</span>
      </button>
      {onRemove && <button type="button" className="icon-btn" aria-label={`Remove this play of ${p.title}`} onClick={() => onRemove(p)}>✕</button>}
    </li>
  )
}

const SORTS = [['artist', 'Artist'], ['title', 'Title'], ['added', 'Recently added'], ['year', 'Year'], ['played', 'Recently played'],
  ['dusty', 'Gathering dust'], ['plays', 'Most played'], ['value', 'Most valuable'], ['rating', 'Your stars']]
const STATUS_CHIPS = [['Owned', 'Collection'], ['Wanted', 'Wantlist'], ['Gone', 'Gone']]

// The crate: every record as a cover, a status at a time; search, genre / decade / format, sort.
export function CrateView() {
  const { refreshKey, openPanel } = useApp()
  const params = new URLSearchParams(window.location.search)
  const [status, setStatus] = useState(params.get('status') ?? 'Owned')
  const [q, setQ] = useState('')
  const [genre, setGenre] = useState('')
  const [decade, setDecade] = useState('')
  const [format, setFormat] = useState('')
  const [sort, setSort] = useState(params.get('sort') ?? 'artist')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const t = setTimeout(() => api.vinylRecords({ status, q, genre, decade, format, sort }).then(setData).catch((e) => setError(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [status, q, genre, decade, format, sort, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  const counts = data?.counts ?? {}
  const facets = data?.facets ?? { genres: [], decades: [], formats: [] }
  const all = Object.values(counts).reduce((a, b) => a + b, 0)
  return (
    <section className="page vinyl">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search artists, titles, labels..." aria-label="Search your records" />
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
          {SORTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <button type="button" className="primary" onClick={() => openPanel('addrecord', { status: status === 'Wanted' ? 'Wanted' : 'Owned' })}>+ Add a record</button>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Status">
        {STATUS_CHIPS.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={status === id} onClick={() => setStatus(id)}>
            {label} <span className="chip-count">{counts[id] ?? 0}</span></button>
        ))}
      </div>
      <div className="vinyl-filters">
        <select value={genre} onChange={(e) => setGenre(e.target.value)} aria-label="Genre">
          <option value="">Every genre</option>{facets.genres.map((g) => <option key={g}>{g}</option>)}</select>
        <select value={decade} onChange={(e) => setDecade(e.target.value)} aria-label="Decade">
          <option value="">Every decade</option>{facets.decades.map((d) => <option key={d} value={d}>{d}s</option>)}</select>
        <select value={format} onChange={(e) => setFormat(e.target.value)} aria-label="Format">
          <option value="">Every format</option>{facets.formats.map((f) => <option key={f}>{f}</option>)}</select>
        {data && <span className="muted small">{plural(data.records.length, 'record')}</span>}
      </div>
      {!data ? <p className="muted loading">Loading...</p> : data.records.length === 0 ? (
        all ? <p className="empty card">{q || genre || decade || format ? 'No records match that.' : 'None here yet.'}</p> : (
          <EmptyState Icon={VinylIcon} title="No records yet" action="+ Add a record" onAction={() => openPanel('addrecord', {})}>
            Search Discogs, scan the barcode on the back, or sync your Discogs collection (Connect).</EmptyState>
        )
      ) : (
        <ul className="vinyl-grid">
          {data.records.map((r) => (
            <li key={r.record_id}>
              <button type="button" className="vinyl-card" onClick={() => openPanel('record', { id: r.record_id })}>
                <RecordCover record={r} className="vinyl-cover" />
                <span className="vinyl-card-text">
                  <span className="item-title">{r.title}</span>
                  <span className="item-meta">{r.artist}</span>
                  <span className="item-meta">{[formatText(r), r.original_year ?? r.year].filter(Boolean).join(' · ')}</span>
                  <span className="vinyl-card-pills">
                    <StatusPill status={r.status} /><GradePill grade={r.media_condition} />
                    {sort === 'value' && r.value != null && <span className="pill purple">{money(r.value)}</span>}
                    {(sort === 'plays' || sort === 'played' || sort === 'dusty') && <span className="muted small">
                      {r.plays ? `${plural(r.plays, 'play')}${r.last_played ? ` · ${timeAgo(r.last_played)}` : ''}` : 'never played'}</span>}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// The listening log: every play, newest first, by day.
export function PlaysView() {
  const { refreshKey, changed } = useApp()
  const [plays, setPlays] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.vinylPlays(500).then(setPlays).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!plays) return <p className="muted loading">Loading...</p>
  if (!plays.length) {
    return (
      <section className="page vinyl">
        <EmptyState Icon={VinylIcon} title="Nothing played yet">Open a record and press ▶ Played it - each play goes in this log
          {' '}(and to Last.fm, if you connect it).</EmptyState>
      </section>
    )
  }
  const days = []
  for (const p of plays) {
    const day = p.played_at.slice(0, 10)
    if (days.at(-1)?.day !== day) days.push({ day, plays: [] })
    days.at(-1).plays.push(p)
  }
  const remove = async (p) => { await api.deleteVinylPlay(p.play_id); changed() }
  return (
    <section className="page vinyl">
      {days.map((d) => (
        <section key={d.day} className="card home-card">
          <h2 className="home-card-title">{shortDate(d.day)}</h2>
          <ul className="list plain-list">{d.plays.map((p) => <PlayRow key={p.play_id} play={p} onRemove={remove} />)}</ul>
        </section>
      ))}
    </section>
  )
}

// The collection in numbers.
export function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const [st, setSt] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.vinylStats().then(setSt).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!st) return <p className="muted loading">Loading...</p>
  const f = st.facts
  if (!f.records) return <section className="page vinyl"><EmptyState Icon={VinylIcon} title="No records yet">Your stats show up once you have some.</EmptyState></section>
  const bars = (rows) => rows.map((r) => ({ label: String(r.label), value: r.n, text: plural(r.n, 'record') }))
  const months = st.plays_by_month.map((m) => ({ label: monthName(m.month), value: m.plays, tip: monthName(m.month, true) }))
  const gain = f.value && f.paid ? f.value - f.paid : null
  return (
    <section className="page stats vinyl">
      <div className="home-stats">
        <Stat to="/vinyl/crate" Icon={VinylIcon} tone="tint" value={f.records} label="Records" sub={`${plural(f.discs, 'disc')} · ${plural(f.artists, 'artist')}`} />
        <Stat to="/vinyl/crate?sort=value" Icon={VinylIcon} tone="purple" value={f.value ? money(f.value) : '—'} label="Worth today"
          sub={gain != null ? `${gain >= 0 ? '+' : '−'}${money(Math.abs(gain))} on ${money(f.paid)} paid` : moneyLine(f) || 'from Discogs, weekly'} />
        <Stat to="/vinyl/crate?sort=year" Icon={VinylIcon} tone="teal" value={f.oldest_year ?? '—'} label="Oldest music"
          sub={st.oldest ? st.oldest.title : ''} />
        <Stat to="/vinyl/crate" Icon={VinylIcon} tone="ok" value={f.average_paid ? money(f.average_paid) : '—'} label="Average paid" sub="for records you've priced" />
      </div>
      <div className="home-grid">
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Plays per month</h2>
          {months.some((m) => m.value) ? <ColumnChart title="Month" rows={months} valueLabel="plays" tickEvery={3} />
            : <p className="muted small">Log a play and it shows here.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Genres</h2>
          {st.genres.length ? <BarList title="Genre" valueLabel="Records" rows={bars(st.genres)} /> : <p className="muted small">Genres come from Discogs.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Decades</h2>
          {st.decades.length ? <ColumnChart title="Decade" valueLabel="records" labelValues
            rows={st.decades.map((d) => ({ label: `${String(d.decade).slice(2)}s`, value: d.n, tip: `${d.decade}s` }))} />
            : <p className="muted small">Years come from Discogs (the album's first release).</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Top artists</h2>
          <BarList title="Artist" valueLabel="Records" rows={bars(st.artists)} />
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Styles</h2>
          {st.styles.length ? <BarList title="Style" valueLabel="Records" rows={bars(st.styles)} /> : <p className="muted small">Styles come from Discogs.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Formats</h2>
          <BarList title="Format" valueLabel="Records" rows={bars(st.formats)} />
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Labels</h2>
          {st.labels.length ? <BarList title="Label" valueLabel="Records" rows={bars(st.labels)} /> : <p className="muted small">No labels yet.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Pressed in</h2>
          {st.countries.length ? <BarList title="Country" valueLabel="Records" rows={bars(st.countries)} /> : <p className="muted small">Countries come from Discogs.</p>}
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Record grades</h2>
          {st.grades.length ? <BarList title="Grade" valueLabel="Records" rows={bars(st.grades)} /> : <p className="muted small">Grade your records (Edit details) to see this.</p>}
        </section>
        <section className="card home-card wide-card">
          <h2 className="home-card-title">The collection over the years</h2>
          {st.growth.length ? <ColumnChart title="Year" valueLabel="records in the collection" labelValues={st.growth.length <= 12}
            rows={st.growth.map((g) => ({ label: String(g.year), value: g.total, tip: `${g.year}: +${g.added}` }))} /> : null}
        </section>
        <section className="card home-card wide-card">
          <h2 className="home-card-title">What it's worth</h2>
          {st.value_by_month.length > 1 ? <LineChart title="Collection value" rows={st.value_by_month.map((v) => ({ x: `${v.month}-28`, y: v.value }))} valueLabel="AUD" />
            : <p className="muted small">The value is checked on Discogs every week; the line starts after the second month.</p>}
        </section>
        <RecordList title="Most valuable" rows={st.most_valuable} detail={(r) => money(r.value)} onOpen={(id) => openPanel('record', { id })} />
        <RecordList title="Most played" rows={st.most_played} detail={(r) => plural(r.plays, 'play')} onOpen={(id) => openPanel('record', { id })} />
        <RecordList title="Best buys" rows={st.best_buys} detail={(r) => `${money(r.price_paid)} → ${money(r.value)}`} onOpen={(id) => openPanel('record', { id })} />
      </div>
    </section>
  )
}

function RecordList({ title, rows, detail, onOpen }) {
  if (!rows.length) return null
  return (
    <section className="card home-card">
      <h2 className="home-card-title">{title}</h2>
      <ul className="list plain-list">
        {rows.map((r) => (
          <li key={r.record_id}>
            <button type="button" className="row-button" onClick={() => onOpen(r.record_id)}>
              <RecordCover record={r} className="vinyl-cover small" />
              <span className="grow"><span className="item-title">{r.title}</span><span className="item-meta">{r.artist}</span></span>
              <span className="small">{detail(r)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

// Discogs (sync, keep in step, values), Last.fm (connect, scrobble by default), the export.
export function ConnectView() {
  const { changed } = useApp()
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  const [allowUrl, setAllowUrl] = useState('')
  const load = () => api.vinylSettings().then(setS).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])
  const busy = s?.sync.running || s?.values.running
  useEffect(() => {
    if (!busy) return undefined
    const t = setInterval(() => api.vinylSettings().then((x) => { setS(x); if (!x.sync.running && !x.values.running) changed() }).catch(() => {}), 2000)
    return () => clearInterval(t)
  }, [busy, changed])
  if (!s) return error ? <p className="alert error">{error}</p> : <p className="muted loading">Loading...</p>
  const run = async (fn) => {
    setError('')
    try {
      const r = await fn()
      if (r?.discogs) setS(r); else await load()
    } catch (e) {
      setError(e.message)
    }
  }
  const d = s.discogs, l = s.lastfm, sync = s.sync, values = s.values
  const stage = { collection: 'Reading your collection', wantlist: 'Reading your wantlist', details: 'Reading each pressing',
    covers: 'Fetching covers', values: 'Checking values' }[sync.stage] ?? 'Starting'
  return (
    <section className="page vinyl vinyl-connect">
      <section className="card home-card">
        <h2 className="home-card-title">Discogs</h2>
        {!d.token ? (
          <div className="small">
            <p>To bring your collection across, the app needs your Discogs <strong>personal access token</strong>:</p>
            <ol>
              <li>On discogs.com: <strong>Settings → Developers → Generate new token</strong>.</li>
              <li>On the PC, add a line to the app's <code>.env</code> file: <code>DISCOGS_TOKEN=</code> followed by the token.</li>
              <li>Restart the app (<code>.\start.ps1</code>), then come back here.</li>
            </ol>
            <p className="muted">The token stays on the PC: it's never shown in the app or sent anywhere but Discogs.</p>
          </div>
        ) : (
          <>
            <p className="small">{d.username ? <>Connected as <strong>{d.username}</strong>. </> : 'Token found. '}
              {d.synced_at ? `Last synced ${timeAgo(d.synced_at)}.` : 'Not synced yet.'}
              {d.linked > 0 && ` ${plural(d.linked, 'record')} linked to your Discogs collection`}
              {d.only_here > 0 && `; ${d.only_here} only here`}{(d.linked > 0 || d.only_here > 0) && '.'}</p>
            {sync.running ? (
              <p className="muted small">{stage}... {sync.total ? `${sync.done} of ${sync.total}` : sync.done || ''}</p>
            ) : (
              <div className="button-row">
                <button type="button" className="primary" onClick={() => run(api.syncDiscogs)}>{d.synced_at ? 'Sync again' : 'Sync my collection'}</button>
                <button type="button" className="secondary" disabled={values.running} onClick={() => run(api.checkVinylValues)}>Check values now</button>
              </div>
            )}
            {!sync.running && sync.finished_at && !sync.error && (
              <p className="alert ok small">{plural(sync.added, 'record')} added, {sync.linked} linked, {sync.wanted} added to the wantlist.
                {sync.only_here > 0 && ` ${plural(sync.only_here, 'record')} you own here ${sync.only_here === 1 ? "isn't" : "aren't"} in your Discogs collection (they stay).`}</p>
            )}
            {values.running && <p className="muted small">Checking values on Discogs... {values.done} of {values.total}</p>}
            {(sync.error || d.error) && <p className="alert error small">{sync.error || d.error}</p>}
            {values.error && <p className="alert error small">{values.error}</p>}
            <label className="check small">
              <input type="checkbox" checked={d.mirror} onChange={(e) => run(() => api.setVinylSettings({ discogs_mirror: e.target.checked }))} />
              Keep Discogs in step: records I add here go into my Discogs collection too</label>
            <p className="muted small">Syncing brings in what's new on Discogs; your grades, notes and stars only fill blanks, and nothing here is
              removed. Values are checked on Discogs once a week: its suggested price for your record's grade (VG+ if you haven't graded it), else
              the cheapest copy for sale.</p>
          </>
        )}
      </section>

      <section className="card home-card">
        <h2 className="home-card-title">Last.fm</h2>
        {!l.configured ? (
          <div className="small">
            <p>Scrobbling sends each record you play to your Last.fm profile. It needs a free Last.fm API account:</p>
            <ol>
              <li>On last.fm, signed in: <strong>last.fm/api/account/create</strong> (any name, e.g. "Off the Clock"; leave the callback blank).</li>
              <li>Add two lines to the app's <code>.env</code>: <code>LASTFM_API_KEY=</code> and <code>LASTFM_API_SECRET=</code> with what it shows.</li>
              <li>Restart the app, then connect here.</li>
            </ol>
          </div>
        ) : l.connected ? (
          <>
            <p className="small">Scrobbling as <strong>{l.user}</strong>.</p>
            <label className="check small">
              <input type="checkbox" checked={l.auto} onChange={(e) => run(() => api.setVinylSettings({ lastfm_auto: e.target.checked }))} />
              Send every play to Last.fm (you can untick it for one play)</label>
            <button type="button" className="plain small destructive" onClick={() => run(async () => { await api.lastfmDisconnect(); setAllowUrl('') })}>Disconnect</button>
          </>
        ) : (
          <>
            <p className="small">1. Allow the app on last.fm. 2. Come back and press Finish.</p>
            <div className="button-row">
              {allowUrl ? <a className="button primary" href={allowUrl} target="_blank" rel="noreferrer">Allow on last.fm ↗</a>
                : <button type="button" className="primary" onClick={() => run(async () => setAllowUrl((await api.lastfmStart()).url))}>Connect Last.fm</button>}
              {(allowUrl || l.waiting) && <button type="button" className="secondary" onClick={() => run(api.lastfmFinish)}>Finish connecting</button>}
            </div>
          </>
        )}
      </section>

      <section className="card home-card">
        <h2 className="home-card-title">Export</h2>
        <p className="small">Every record you own, with its pressing, grades, what you paid and today's value, as a spreadsheet (CSV) - for
          insurance or a copy of your own. Records are also in Supplies → Value report.</p>
        <a className="button secondary" href={vinylExportUrl} download>Download the collection (CSV)</a>
      </section>
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}
