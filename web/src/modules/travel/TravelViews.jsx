import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { ColumnChart } from '../../components/charts.jsx'
import Fold from '../../components/Fold.jsx'
import { CalendarIcon, ChevronIcon, SuitcaseIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import Landscape from '../../components/Landscape.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import TravelMap from './TravelMap.jsx'
import { aud, codeFor, COUNTRIES, countryName, flag, PHASE_NAME, PHASE_TONE, plural, tripMeta, useTravelLists, useTravelSummary, when } from './travelParts.jsx'

// Travel's pages: the dashboard (the trip you're on or the next one, this year, countries, your passport), every
// trip, places (a map of everywhere, countries been and wanted, the bucket list) and your packing lists.

// Home: two numbers. With a trip on or coming up: the countdown (or where you are), then its packing (once it has a
// list) or the countries you've been to. With none: countries visited and this year's trips.
export function TravelTiles() {
  const { data: s } = useTravelSummary()
  if (!s) return <><StatSkeleton /><StatSkeleton /></>
  const now = s.now[0]
  const next = s.upcoming[0]
  const trip = now ?? next
  const countries = (
    <Stat to="/travel/places" Icon={TrophyIcon} tone="ok" value={s.countries_been} label="Countries visited"
      sub={s.bucket_list ? `${s.bucket_list} on the bucket list` : `${plural(s.places_been, 'place')} been`} />
  )
  if (trip) {
    return (
      <>
        {now ? <Stat to="/travel/dashboard" Icon={SuitcaseIcon} tone="ok" value={when(now)} label={now.name} sub="Travelling now" />
          : <Stat to="/travel/dashboard" Icon={SuitcaseIcon} tone="teal" value={next.starts_in === 1 ? 'Tomorrow' : plural(next.starts_in, 'day')}
            label={`Until ${next.name}`} sub={shortDate(next.start_date)} />}
        {trip.packing_count > 0
          ? <Stat to="/travel/trips" Icon={CalendarIcon} tone="tint" value={`${trip.packed_count}/${trip.packing_count}`} label="Packed"
            sub={trip.packed_count === trip.packing_count ? 'all packed' : `for ${trip.name}`} />
          : countries}
      </>
    )
  }
  if (!s.countries_been) return null
  return (
    <>
      {countries}
      <Stat to="/travel/trips" Icon={CalendarIcon} tone="tint" value={s.this_year.trips} label={`Trips in ${s.year}`}
        sub={`${plural(s.this_year.days, 'day')} away`} />
    </>
  )
}

// Home's feature: the trip you're on, or the next one - its picture (or a drawn coast), dates and a way in.
export function NextAdventure() {
  const { data: s } = useTravelSummary()
  const { openPanel } = useApp()
  const trip = s?.now[0] ?? s?.upcoming[0]
  if (!trip) return null
  return (
    <section className="card home-card next-adventure" aria-labelledby="home-trip">
      {trip.photo_url ? <img className="next-adventure-art" src={trip.photo_url} alt="" loading="lazy" />
        : <span className="next-adventure-art"><Landscape scene="coast" seed={trip.trip_id + 40} hue="#2fa39a" /></span>}
      <div className="next-adventure-text">
        <p className="next-adventure-eyebrow">{s.now[0] ? 'Travelling now' : 'Next adventure'}</p>
        <h2 id="home-trip" className="next-adventure-name">{trip.name}</h2>
        <p className="next-adventure-when">{tripMeta(trip)}</p>
        <button type="button" className="primary" onClick={() => openPanel('trip', { id: trip.trip_id })}>
          View trip <ChevronIcon size={14} /></button>
      </div>
    </section>
  )
}

function TripRow({ t }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('trip', { id: t.trip_id })}>
        {t.photo_url ? <img className="trip-thumb" src={t.photo_url} alt="" loading="lazy" />
          : <span className="trip-thumb"><SuitcaseIcon size={20} /></span>}
        <span className="grow">
          <span className="item-title">{t.name}</span>
          <span className="item-meta">{tripMeta(t)}</span>
        </span>
        <span className={`pill ${PHASE_TONE[t.phase]}`}>{t.phase === 'past' ? when(t) : t.phase === 'idea' ? 'Idea' : when(t)}</span>
      </button>
    </li>
  )
}

export function Dashboard() {
  const { data: s, error } = useTravelSummary()
  const { openPanel } = useApp()
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const empty = !s.now.length && !s.upcoming.length && !s.ideas.length && !s.recent.length
  const y = s.this_year
  const focus = s.now[0] ?? s.upcoming[0]
  const coming = s.now.length > 0 || s.upcoming.length > 0
  return (
    <section className="page travel">
      {empty && (
        <section className="card empty-start">
          <h2 className="home-card-title">Where to?</h2>
          <p className="small">Plan your next trip - bookings, a day-by-day plan, a budget and a packing list - or start with the places
            you've been and the ones you want to go.</p>
          <div className="button-row">
            <button type="button" className="primary" onClick={() => openPanel('trip', {})}>+ Plan a trip</button>
            <button type="button" className="secondary" onClick={() => openPanel('tplace', {})}>+ A place you want to go</button>
            <Link className="button plain" to="/travel/places">Countries you've been to →</Link>
          </div>
        </section>
      )}
      {/* Plan a trip: in Coming up's heading when there's a trip coming (no row of its own), otherwise up here */}
      {!empty && !coming && (
        <div className="toolbar"><span className="grow" />
          <button type="button" className="primary" onClick={() => openPanel('trip', {})}>+ Plan a trip</button>
        </div>
      )}
      <div className="home-stats">
        {focus ? (
          <Stat to="/travel/trips" Icon={SuitcaseIcon} tone={focus.phase === 'now' ? 'ok' : 'teal'}
            value={focus.phase === 'now' ? when(focus) : focus.starts_in === 1 ? 'Tomorrow' : plural(focus.starts_in, 'day')}
            label={focus.phase === 'now' ? focus.name : `Until ${focus.name}`} sub={tripMeta(focus)} />
        ) : <Stat to="/travel/trips" Icon={SuitcaseIcon} tone="teal" value="—" label="No trip booked" sub={s.ideas.length ? plural(s.ideas.length, 'idea') : 'Plan one'} />}
        <Stat to="/travel/trips" Icon={CalendarIcon} tone="tint" value={y.trips} label={`Trips in ${s.year}`} sub={`${plural(y.days, 'day')} away`} />
        <Stat to="/travel/places" Icon={TrophyIcon} tone="ok" value={s.countries_been} label="Countries visited"
          sub={`${plural(s.places_been, 'place')} been · ${s.bucket_list} on the bucket list`} />
        <Stat to="/travel/trips" Icon={TargetIcon} tone="purple" value={aud(y.spent)} label={`Spent travelling in ${s.year}`} sub="bookings + spent there" />
      </div>
      {s.passport_warning && <p className="alert low">{s.passport_warning}</p>}
      <div className="home-grid">
        <div className="home-stack">
          {coming && (
            <section className="card home-card">
              <h2 className="home-card-title">Coming up
                <button type="button" className="primary small trip-plan" onClick={() => openPanel('trip', {})}>+ Plan a trip</button></h2>
              <ul className="list plain-list">{[...s.now, ...s.upcoming].map((t) => <TripRow key={t.trip_id} t={t} />)}</ul>
            </section>
          )}
          {s.ideas.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Ideas</h2>
              <ul className="list plain-list">{s.ideas.map((t) => <TripRow key={t.trip_id} t={t} />)}</ul>
            </section>
          )}
          {s.recent.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Been <Link to="/travel/trips" className="small">All trips →</Link></h2>
              <ul className="list plain-list">{s.recent.map((t) => <TripRow key={t.trip_id} t={t} />)}</ul>
            </section>
          )}
          <PassportCard passport={s.passport} />
        </div>
        <div className="home-stack">
          {s.years.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Days away each year</h2>
              <ColumnChart title="Days away each year" valueLabel="days" labelValues
                rows={s.years.map((r) => ({ label: String(r.year), value: r.days, tip: `${plural(r.trips, 'trip')} · ${aud(r.spent)}` }))} />
            </section>
          )}
        </div>
      </div>
    </section>
  )
}

function PassportCard({ passport }) {
  const { changed, showToast } = useApp()
  const [value, setValue] = useState(passport.passport_expires ?? '')
  const save = async (e) => {
    e.preventDefault()
    try {
      await api.saveTravelSettings({ passport_expires: value || null })
      changed()
      showToast('Saved')
    } catch (err) {
      showToast(err.message)
    }
  }
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Passport</h2>
      <form className="trip-add" onSubmit={save}>
        <label className="grow small">Expires <input type="date" value={value} onChange={(e) => setValue(e.target.value)} aria-label="Passport expires" /></label>
        <button type="submit" className="secondary" disabled={value === (passport.passport_expires ?? '')}>Save</button>
      </form>
      <p className="hint">{passport.passport_expires ? `${plural(passport.passport_days, 'day')} left. ` : ''}Overseas trips are checked against it:
        many countries want 6 months left when you arrive.</p>
    </section>
  )
}

// Every trip: on now, coming up, ideas, been, cancelled - with a search.
export function TripsView() {
  const { refreshKey, openPanel } = useApp()
  const [trips, setTrips] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [phase, setPhase] = useState('')
  useEffect(() => { api.trips().then(setTrips).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  const words = q.trim().toLowerCase()
  const shown = (trips ?? []).filter((t) => (!phase || t.phase === phase)
    && (!words || [t.name, t.destination, t.kind, ...t.countries.map(countryName)].join(' ').toLowerCase().includes(words)))
  const groups = ['now', 'upcoming', 'idea', 'past', 'cancelled'].map((p) => [p, shown.filter((t) => t.phase === p)]).filter(([, l]) => l.length)
  const counts = Object.fromEntries(['now', 'upcoming', 'idea', 'past', 'cancelled'].map((p) => [p, (trips ?? []).filter((t) => t.phase === p).length]))
  return (
    <section className="page travel">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search trips, places, countries..."
          aria-label="Search your trips" />
        <button type="button" className="primary" onClick={() => openPanel('trip', {})}>+ Plan a trip</button>
      </div>
      {trips && trips.length > 0 && (
        <div className="chip-row" role="group" aria-label="Show">
          <button type="button" className="chip-filter" aria-pressed={!phase} onClick={() => setPhase('')}>All <span className="chip-count">{trips.length}</span></button>
          {Object.entries(counts).filter(([, n]) => n).map(([p, n]) => (
            <button key={p} type="button" className="chip-filter" aria-pressed={phase === p} onClick={() => setPhase(phase === p ? '' : p)}>
              {p === 'upcoming' ? 'Coming up' : p === 'idea' ? 'Ideas' : PHASE_NAME[p]} <span className="chip-count">{n}</span></button>
          ))}
        </div>
      )}
      {!trips ? <p className="muted loading">Loading...</p> : trips.length === 0 ? (
        <EmptyState Icon={SuitcaseIcon} title="No trips yet" action="+ Plan a trip" onAction={() => openPanel('trip', {})}>
          Plan the next one, write down an idea, or add the trips you've been on.</EmptyState>
      ) : groups.length === 0 ? <p className="empty card">No trips match that.</p> : groups.map(([p, list]) => (
        <section key={p} className="trip-group">
          <h2 className="section-title">{p === 'upcoming' ? 'Coming up' : p === 'idea' ? 'Ideas' : p === 'now' ? 'Travelling now' : PHASE_NAME[p]}</h2>
          <ul className="list plain-list card">{list.map((t) => <TripRow key={t.trip_id} t={t} />)}</ul>
        </section>
      ))}
    </section>
  )
}

// Places: everything on one map, countries been and wanted, and every place by where it stands.
export function PlacesView() {
  const { refreshKey, openPanel, openThing } = useApp()
  const [places, setPlaces] = useState(null)
  const [photos, setPhotos] = useState([])
  const [countries, setCountries] = useState(null)
  const [show, setShow] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    Promise.all([api.travelPlaces(), api.travelCountries(), api.travelPhotos()])
      .then(([p, c, ph]) => { setPlaces(p); setCountries(c); setPhotos(ph) }).catch((e) => setError(e.message))
  }, [refreshKey])
  const onMap = useMemo(() => (places ?? []).filter((p) => !show || p.shown === show), [places, show])
  if (error) return <p className="alert error">{error}</p>
  if (!places || !countries) return <p className="muted loading">Loading...</p>
  const openPlace = (p) => (p.trip_id ? openPanel('tplace', { id: p.place_id, tripId: p.trip_id }) : openPanel('tplace', { id: p.place_id }))
  return (
    <section className="page travel">
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Show places">
          {[['', 'All'], ['Been', 'Been'], ['Planned', 'Going'], ['Want', 'Want to go']].map(([k, label]) => (
            <button key={k} type="button" aria-pressed={show === k} onClick={() => setShow(k)}>{label}</button>
          ))}
        </div>
        <span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('tplace', {})}>+ Add a place</button>
      </div>
      <TravelMap places={onMap} photos={show === '' || show === 'Been' ? photos : []} label="Map of your places"
        onPlace={openPlace} onPhoto={(ph) => openThing('trip', ph.trip_id)} />
      <div className="home-grid">
        <div className="home-stack">
          <Countries countries={countries} onChanged={setCountries} />
        </div>
        <div className="home-stack">
          <section className="card home-card">
            <h2 className="home-card-title">{show ? ({ Been: 'Been', Planned: 'Going', Want: 'Bucket list' })[show] : 'Places'} · {onMap.length}</h2>
            {onMap.length === 0 ? <p className="muted small">{show === 'Want' || !places.length
              ? 'Somewhere you want to go one day? Add it - it goes on your bucket list until a trip takes you there.' : 'None here.'}</p> : (
              <ul className="list plain-list">{onMap.map((p) => (
                <li key={p.place_id}><button type="button" className="row-button" onClick={() => openPlace(p)}>
                  <span className="grow"><span className="item-title">{flag(p.country)} {p.name}</span>
                    <span className="item-meta">{[p.kind, p.region || countryName(p.country), p.trip_name].filter(Boolean).join(' · ')}</span></span>
                  <span className={`pill ${{ Been: 'ok', Planned: 'tint', Want: 'purple' }[p.shown]}`}>{{ Been: 'Been', Planned: 'Going', Want: 'Want' }[p.shown]}</span>
                </button></li>))}</ul>
            )}
          </section>
        </div>
      </div>
    </section>
  )
}

function Countries({ countries, onChanged }) {
  const { showToast } = useApp()
  const [name, setName] = useState('')
  const [status, setStatus] = useState('Been')
  const [year, setYear] = useState('')
  const add = async (e) => {
    e.preventDefault()
    const code = codeFor(name)
    if (!code) { showToast(`Which country is "${name}"?`); return }
    try {
      onChanged(await api.setTravelCountry(code, { status, first_year: year ? Number(year) : null }))
      setName('')
      setYear('')
    } catch (err) {
      showToast(err.message)
    }
  }
  const forget = async (code) => { try { onChanged(await api.forgetTravelCountry(code)) } catch (err) { showToast(err.message) } }
  return (
    <section className="card home-card">
      <h2 className="home-card-title">Countries · {countries.been.length} visited</h2>
      {countries.been.length === 0 ? <p className="muted small">Add the countries you've been to - before the app too. Trips add theirs
        once they start.</p> : (
        <ul className="travel-flags" aria-label="Countries visited">{countries.been.map((c) => (
          <li key={c.code} title={[c.first_year && `First in ${c.first_year}`, c.trips && plural(c.trips, 'trip')].filter(Boolean).join(' · ')}>
            <span className="travel-flag" aria-hidden="true">{flag(c.code)}</span>
            <span className="grow">{countryName(c.code)}{c.first_year && <span className="muted small"> {c.first_year}</span>}</span>
            {c.added && !c.trips && !c.places && <button type="button" className="plain small" aria-label={`Forget ${countryName(c.code)}`}
              onClick={() => forget(c.code)}>×</button>}
          </li>))}</ul>
      )}
      {countries.want.length > 0 && (
        <>
          <h3 className="section-title">Want to go · {countries.want.length}</h3>
          <ul className="travel-flags" aria-label="Countries you want to go to">{countries.want.map((c) => (
            <li key={c.code}><span className="travel-flag" aria-hidden="true">{flag(c.code)}</span>
              <span className="grow">{countryName(c.code)}{c.places > 0 && <span className="muted small"> {plural(c.places, 'place')}</span>}</span>
              {c.added && <button type="button" className="plain small" aria-label={`Forget ${countryName(c.code)}`} onClick={() => forget(c.code)}>×</button>}
            </li>))}</ul>
        </>
      )}
      <form className="trip-add" onSubmit={add}>
        <input value={name} onChange={(e) => setName(e.target.value)} list="travel-all-countries" placeholder="A country" aria-label="Country" />
        <datalist id="travel-all-countries">{COUNTRIES.map((c) => <option key={c.code} value={c.name} />)}</datalist>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Been or want to go">
          <option value="Been">Been</option><option value="Want">Want to go</option>
        </select>
        {status === 'Been' && <input type="number" min="1900" max="2100" value={year} onChange={(e) => setYear(e.target.value)} placeholder="Year"
          aria-label="First year there" className="trip-year" />}
        <button type="submit" className="secondary" disabled={!name.trim()}>Add</button>
      </form>
    </section>
  )
}

// Your packing lists: the starting ones and your own (saved from a trip, or made here).
export function PackingListsView() {
  const lists = useTravelLists()
  const { showToast } = useApp()
  const [saved, setSaved] = useState(null)
  const [newName, setNewName] = useState('')
  useEffect(() => { api.packingLists().then(setSaved).catch((e) => showToast(e.message)) }, [showToast])
  const call = async (fn) => { try { setSaved(await fn()) } catch (e) { showToast(e.message) } }
  if (!saved || !lists) return <p className="muted loading">Loading...</p>
  return (
    <section className="page travel">
      <form className="toolbar" onSubmit={(e) => { e.preventDefault(); call(() => api.addPackingList({ name: newName.trim(), items: [] })).then(() => setNewName('')) }}>
        <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="A new list, e.g. Ski trip" aria-label="New packing list" maxLength={80} />
        <button type="submit" className="primary" disabled={!newName.trim()}>+ New list</button>
      </form>
      <p className="muted small">A trip's Packing tab adds any of these in one go (nothing twice). A trip's own list can be saved as a new one.</p>
      {saved.map((l) => <PackingList key={l.list_id} l={l} groups={lists.groups} call={call} />)}
    </section>
  )
}

function PackingList({ l, groups, call }) {
  const [name, setName] = useState('')
  const [grp, setGrp] = useState('Other')
  const [confirm, setConfirm] = useState(false)
  const save = (items) => call(() => api.updatePackingList(l.list_id, { items }))
  return (
    <Fold title={l.name} detail={plural(l.count, 'thing')} className="card packing-list-fold">
      {groups.map((g) => [g, l.items.filter((i) => (i.grp ?? 'Other') === g)]).filter(([, items]) => items.length).map(([g, items]) => (
        <div key={g} className="packing-list-group">
          <span className="muted small">{g}</span>
          <ul className="chips">{items.map((i) => (
            <li key={i.name} className="chip">{i.name}
              <button type="button" className="plain small" aria-label={`Remove ${i.name}`}
                onClick={() => save(l.items.filter((x) => x.name !== i.name))}>×</button></li>))}</ul>
        </div>
      ))}
      <form className="trip-add" onSubmit={(e) => { e.preventDefault(); if (name.trim()) { save([...l.items, { name: name.trim(), grp }]); setName('') } }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Add a thing" aria-label={`Add to ${l.name}`} maxLength={200} />
        <select value={grp} onChange={(e) => setGrp(e.target.value)} aria-label="Group">{groups.map((g) => <option key={g} value={g}>{g}</option>)}</select>
        <button type="submit" className="secondary" disabled={!name.trim()}>Add</button>
        <span className="spacer" />
        {confirm ? (
          <span className="confirm">Delete {l.name}?
            <button type="button" className="danger small" onClick={() => call(() => api.deletePackingList(l.list_id))}>Delete</button>
            <button type="button" className="plain small" onClick={() => setConfirm(false)}>Cancel</button></span>
        ) : <button type="button" className="plain destructive small" onClick={() => setConfirm(true)}>Delete list</button>}
      </form>
    </Fold>
  )
}
