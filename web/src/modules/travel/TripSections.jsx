import { useEffect, useState } from 'react'
import { api, clock, isoDay, today } from '../../api.js'
import { BarList } from '../../components/charts.jsx'
import { useApp } from '../../core/app-context.js'
import { MODULES } from '../index.js'
import { aud, inCurrency, plural, useTravelLists } from './travelParts.jsx'

// A trip's working tabs: the day plan, bookings, money and packing. Every change answers with the whole trip
// (onTrip), so the header's counts and warnings stay right.

// Each day of the trip, from its first to its last.
export function tripDays(t) {
  if (!t.start_date) return []
  const days = []
  const last = new Date(`${t.end_date ?? t.start_date}T12:00:00`)
  for (let d = new Date(`${t.start_date}T12:00:00`); d <= last && days.length < 366; d.setDate(d.getDate() + 1)) days.push(isoDay(d))
  return days
}
export const dayLabel = (iso, t) => {
  const d = new Date(`${iso}T12:00:00`)
  const n = t.start_date ? Math.round((d - new Date(`${t.start_date}T12:00:00`)) / 864e5) + 1 : null
  return `${d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })}${n ? ` · Day ${n}` : ''}`
}
const timeOf = (iso) => (iso && iso.slice(11, 16) !== '00:00' ? clock(iso.slice(11, 16)) : null)

function useBusy(onTrip) {
  const { showToast } = useApp()
  const [busy, setBusy] = useState(false)
  const run = async (call) => {
    setBusy(true)
    try {
      onTrip(await call())
      return true
    } catch (e) {
      showToast(e.message)
      return false
    } finally {
      setBusy(false)
    }
  }
  return [busy, run]
}

// ---------------------------------------------------------------------------------------------
// Plan: before you go, then day by day (bookings that start that day, and your plans)
// ---------------------------------------------------------------------------------------------
export function PlanTab({ t, onTrip }) {
  const [busy, run] = useBusy(onTrip)
  const days = tripDays(t)
  const [title, setTitle] = useState('')
  const [day, setDay] = useState('')
  const [at, setAt] = useState('')
  const add = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    if (await run(() => api.addPlanItem(t.trip_id, { title: title.trim(), day: day || null, at: at || null }))) { setTitle(''); setAt('') }
  }
  const before = t.plan.filter((i) => !i.day)
  const outside = t.plan.filter((i) => i.day && !days.includes(i.day))
  return (
    <section className="panel-section">
      <h3 className="section-title">Before you go</h3>
      {before.length === 0 ? <p className="muted small">Visa, insurance, a pet sitter, telling the bank... add what needs doing.</p>
        : <ul className="trip-checklist">{before.map((i) => <PlanItem key={i.item_id} i={i} busy={busy} run={run} />)}</ul>}
      {days.map((d) => {
        const bookings = t.bookings.filter((b) => b.starts_at?.slice(0, 10) === d || (b.ends_at?.slice(0, 10) === d && ['Stay', 'Campsite', 'Car hire'].includes(b.kind)))
        const items = t.plan.filter((i) => i.day === d)
        return (
          <div key={d} className={`trip-day${d === today() ? ' today' : ''}`}>
            <h4 className="trip-day-head">{dayLabel(d, t)}{d === today() && <span className="pill ok">Today</span>}</h4>
            {bookings.length + items.length === 0 ? <p className="muted small">Nothing planned.</p> : (
              <ul className="trip-checklist">
                {bookings.map((b) => {
                  const out = b.ends_at?.slice(0, 10) === d && b.starts_at?.slice(0, 10) !== d
                  const at2 = timeOf(out ? b.ends_at : b.starts_at)
                  return (
                    <li key={`b${b.booking_id}${out ? 'o' : ''}`} className="trip-booking-line">
                      <span className="pill tint">{b.kind}</span>
                      <span className="grow">{at2 && <strong>{at2} </strong>}{out ? (b.kind === 'Car hire' ? 'Return: ' : 'Check out: ') : ''}{b.title}
                        {(b.from_place || b.to_place) && <span className="muted"> · {[b.from_place, b.to_place].filter(Boolean).join(' → ')}</span>}</span>
                    </li>
                  )
                })}
                {items.map((i) => <PlanItem key={i.item_id} i={i} busy={busy} run={run} />)}
              </ul>
            )}
          </div>
        )
      })}
      {outside.length > 0 && (
        <>
          <h4 className="trip-day-head">Outside the trip's dates</h4>
          <ul className="trip-checklist">{outside.map((i) => <PlanItem key={i.item_id} i={i} busy={busy} run={run} />)}</ul>
        </>
      )}
      {!t.start_date && <p className="muted small">Give the trip dates (Edit details) to plan it day by day.</p>}
      <form className="trip-add" onSubmit={add}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. teamLab Planets, apply for the visa" aria-label="Add to the plan" maxLength={300} />
        <select value={day} onChange={(e) => setDay(e.target.value)} aria-label="Day">
          <option value="">Before you go</option>
          {days.map((d) => <option key={d} value={d}>{dayLabel(d, t)}</option>)}
        </select>
        {day && <input type="time" value={at} onChange={(e) => setAt(e.target.value)} aria-label="Time" />}
        <button type="submit" className="secondary" disabled={busy || !title.trim()}>Add</button>
      </form>
    </section>
  )
}

function PlanItem({ i, busy, run }) {
  return (
    <li className={i.done ? 'done' : ''}>
      <label className="tick-row grow">
        <input type="checkbox" checked={i.done} disabled={busy} onChange={() => run(() => api.updatePlanItem(i.item_id, { done: !i.done }))} />
        <span>{i.at && <strong>{clock(i.at)} </strong>}{i.title}{i.place_name && <span className="muted"> · {i.place_name}</span>}</span>
      </label>
      <button type="button" className="plain small" aria-label={`Remove ${i.title}`} disabled={busy}
        onClick={() => run(() => api.deletePlanItem(i.item_id))}>×</button>
    </li>
  )
}

// ---------------------------------------------------------------------------------------------
// Bookings
// ---------------------------------------------------------------------------------------------
const whenText = (b) => {
  if (!b.starts_at) return null
  const d = new Date(b.starts_at)
  const day = d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' })
  return `${day}${timeOf(b.starts_at) ? ` ${timeOf(b.starts_at)}` : ''}`
}

export function BookingsTab({ t, onClose }) {
  const { openPanel } = useApp()
  const open = (props) => { onClose(); openPanel('tbooking', { tripId: t.trip_id, ...props }) }
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Bookings</h3>
        <button type="button" className="primary small" onClick={() => open({})}>+ Add a booking</button>
      </div>
      {t.bookings.length === 0 ? <p className="muted small">Flights, places to stay, a hire car, tours, insurance - with their times,
        booking references and what they cost (in any currency).</p> : (
        <ul className="list plain-list trip-bookings">{t.bookings.map((b) => (
          <li key={b.booking_id}>
            <button type="button" className="row-button" onClick={() => open({ id: b.booking_id })}>
              <span className="pill tint">{b.kind}</span>
              <span className="grow">
                <span className="item-title">{b.title}</span>
                <span className="item-meta">{[whenText(b), [b.from_place, b.to_place].filter(Boolean).join(' → '), b.provider,
                  b.reference && `Ref ${b.reference}`].filter(Boolean).join(' · ')}</span>
              </span>
              {b.cost != null && (
                <span className="trip-cost">{inCurrency(b.cost, b.currency)}
                  {b.currency !== 'AUD' && <span className="muted small"> {aud(b.cost_aud)}</span>}</span>
              )}
              {b.cost != null && <span className={`pill ${b.paid ? 'ok' : 'low'}`}>{b.paid ? 'Paid' : 'To pay'}</span>}
            </button>
          </li>))}</ul>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------------------------
// Money: budget against spent, by category; money spent there; rates
// ---------------------------------------------------------------------------------------------
export function MoneyTab({ t, onTrip }) {
  const lists = useTravelLists()
  const [busy, run] = useBusy(onTrip)
  const m = t.money
  const lastCurrency = t.expenses[0]?.currency ?? m.currencies[0] ?? 'AUD'
  const inTrip = t.start_date && today() >= t.start_date && today() <= (t.end_date ?? t.start_date)
  const [form, setForm] = useState({ amount: '', currency: lastCurrency, category: 'Food', what: '', spent_on: inTrip ? today() : (t.start_date ?? today()) })
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const add = async (e) => {
    e.preventDefault()
    const ok = await run(() => api.addExpense(t.trip_id, { ...form, amount: Number(form.amount), what: form.what.trim() || null }))
    if (ok) setForm((f) => ({ ...f, amount: '', what: '' }))
  }
  const used = Math.min(100, m.budget ? (100 * m.spent) / m.budget : 0)
  return (
    <>
      <section className="panel-section">
        <h3 className="section-title">Budget</h3>
        <dl className="trip-money">
          <div><dt>Spent</dt><dd>{aud(m.spent)}</dd></div>
          <div><dt>Budget</dt><dd>{m.budget != null ? aud(m.budget) : '—'}</dd></div>
          {m.left != null && <div><dt>{m.left < 0 ? 'Over' : 'Left'}</dt><dd className={m.left < 0 ? 'trip-over' : ''}>{aud(Math.abs(m.left))}</dd></div>}
          {m.per_day != null && <div><dt>A day</dt><dd>{aud(m.per_day)}</dd></div>}
          {m.unpaid > 0 && <div><dt>Still to pay</dt><dd>{aud(m.unpaid)}</dd></div>}
        </dl>
        {m.budget != null && (
          <span className={`fill-bar ${m.spent > m.budget ? 'out' : 'tint'} trip-budget-bar`} role="img"
            aria-label={`${Math.round(used)}% of the budget spent`}><span style={{ width: `${used}%` }} /></span>
        )}
        {m.budget == null && <p className="muted small">Set a budget in Edit details to see what's left.</p>}
        {m.by_category.length > 0 && (
          <BarList title="Spent by category" valueLabel="AUD"
            rows={m.by_category.map((c) => ({ label: c.category, value: c.aud, text: aud(c.aud) }))} />
        )}
        <p className="hint">Bookings and what you spend there, in AUD. Other currencies are converted at the day's rate when you
          add them (or yours, set below).</p>
      </section>
      <section className="panel-section">
        <h3 className="section-title">Spent there</h3>
        <form className="trip-expense-form" onSubmit={add}>
          <input type="number" min="0" step="0.01" inputMode="decimal" value={form.amount} onChange={set('amount')} aria-label="Amount" placeholder="Amount" required />
          <select value={form.currency} onChange={set('currency')} aria-label="Currency">
            {(lists?.currencies ?? ['AUD']).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={form.category} onChange={set('category')} aria-label="Category">
            {(lists?.categories ?? ['Food']).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input value={form.what} onChange={set('what')} placeholder="What (e.g. Ramen)" aria-label="What" maxLength={300} />
          <input type="date" value={form.spent_on} onChange={set('spent_on')} aria-label="Day" required />
          <button type="submit" className="secondary" disabled={busy || form.amount === ''}>Add</button>
        </form>
        {t.expenses.length > 0 && (
          <ul className="list plain-list trip-expenses">{t.expenses.map((e) => (
            <li key={e.expense_id} className="trip-expense">
              <span className="grow"><span className="item-title">{e.what || e.category}</span>
                <span className="item-meta">{[new Date(`${e.spent_on}T12:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
                  e.what && e.category].filter(Boolean).join(' · ')}</span></span>
              <span className="trip-cost">{inCurrency(e.amount, e.currency)}{e.currency !== 'AUD' && <span className="muted small"> {aud(e.aud)}</span>}</span>
              <button type="button" className="plain small" aria-label={`Remove ${e.what || e.category}`} disabled={busy}
                onClick={() => run(() => api.deleteExpense(e.expense_id))}>×</button>
            </li>))}</ul>
        )}
      </section>
      <Rates t={t} run={run} busy={busy} currencies={lists?.currencies ?? []} />
    </>
  )
}

function Rates({ t, run, busy, currencies }) {
  const [published, setPublished] = useState(null)
  const [currency, setCurrency] = useState('')
  const [rate, setRate] = useState('')
  const used = [...new Set([...t.money.currencies, ...Object.keys(t.rates)])]
  useEffect(() => { if (used.length) api.travelRates().then(setPublished).catch(() => setPublished({ aud_per: {} })) }, [used.length])
  const save = async (e) => {
    e.preventDefault()
    if (await run(() => api.setTripRate(t.trip_id, currency, rate === '' ? null : Number(rate), true))) { setRate(''); setCurrency('') }
  }
  return (
    <section className="panel-section">
      <h3 className="section-title">Rates</h3>
      {used.length > 0 && (
        <ul className="list plain-list trip-rates">{used.map((c) => (
          <li key={c}>
            <span className="grow"><strong>1 {c}</strong> = {t.rates[c] ? `${t.rates[c]} AUD (yours)` : published?.aud_per?.[c] ? `${published.aud_per[c]} AUD today` : '—'}</span>
            {t.rates[c] && <button type="button" className="plain small" disabled={busy}
              onClick={() => run(() => api.setTripRate(t.trip_id, c, null))}>Use today's</button>}
          </li>))}</ul>
      )}
      <form className="trip-add" onSubmit={save}>
        <select value={currency} onChange={(e) => setCurrency(e.target.value)} aria-label="Currency for your rate" required>
          <option value="">Currency...</option>
          {[...new Set([...currencies.filter((c) => c !== 'AUD'), ...used])].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input type="number" min="0" step="any" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)}
          placeholder="AUD for 1" aria-label="Your rate (AUD for 1)" />
        <button type="submit" className="secondary" disabled={busy || !currency}>Set rate</button>
      </form>
      <p className="hint">Your own rate (what your card or the money changer gave you) is used for this trip and re-prices what's
        there. Rates: Frankfurter (the European Central Bank's).</p>
    </section>
  )
}

// ---------------------------------------------------------------------------------------------
// Packing
// ---------------------------------------------------------------------------------------------
export function PackingTab({ t, onTrip }) {
  const { showToast } = useApp()
  const lists = useTravelLists()
  const [busy, run] = useBusy(onTrip)
  const [saved, setSaved] = useState(null)
  const [listId, setListId] = useState('')
  const [hobby, setHobby] = useState(t.hobby ?? '')
  const [name, setName] = useState('')
  const [grp, setGrp] = useState('Clothes')
  const [saveAs, setSaveAs] = useState('')
  useEffect(() => { api.packingLists().then(setSaved).catch(() => setSaved([])) }, [])
  const add = async (e) => {
    e.preventDefault()
    if (name.trim() && await run(() => api.addPacking(t.trip_id, { name: name.trim(), grp }))) setName('')
  }
  const groups = (lists?.groups ?? []).map((g) => [g, t.packing.filter((p) => p.grp === g)]).filter(([, items]) => items.length)
  return (
    <section className="panel-section">
      <div className="section-head">
        <h3 className="section-title">Packing{t.packing_count > 0 && ` · ${t.packed_count} of ${t.packing_count}`}</h3>
        {t.packed_count > 0 && <button type="button" className="plain small" disabled={busy}
          onClick={() => run(() => api.unpackAll(t.trip_id))} title="Untick everything - to pack for home">Untick all</button>}
      </div>
      {t.packing_count > 0 && (
        <span className="fill-bar ok trip-pack-bar" role="img" aria-label={`${t.packed_count} of ${t.packing_count} packed`}>
          <span style={{ width: `${(100 * t.packed_count) / t.packing_count}%` }} /></span>
      )}
      <div className="trip-pack-tools">
        <select value={listId} onChange={(e) => setListId(e.target.value)} aria-label="A packing list">
          <option value="">Add a packing list...</option>
          {(saved ?? []).map((l) => <option key={l.list_id} value={l.list_id}>{l.name} ({l.count})</option>)}
        </select>
        <button type="button" className="secondary" disabled={busy || !listId}
          onClick={async () => { if (await run(() => api.packFromList(t.trip_id, Number(listId)))) setListId('') }}>Add list</button>
        <select value={hobby} onChange={(e) => setHobby(e.target.value)} aria-label="Gear for a hobby">
          <option value="">Pack your gear for...</option>
          {['hiking', 'shooting', 'volleyball'].map((h) => <option key={h} value={h}>{MODULES.find((m) => m.id === h)?.name ?? h}</option>)}
        </select>
        <button type="button" className="secondary" disabled={busy || !hobby} onClick={() => run(() => api.packGear(t.trip_id, hobby))}>Add gear</button>
      </div>
      {t.packing.length === 0 ? <p className="muted small">Start from a list (Essentials, Overseas, Camping...), add your gear for a hobby,
        or type things below. Tick them off as they go in the bag.</p> : groups.map(([g, items]) => (
        <div key={g} className="trip-pack-group">
          <h4 className="trip-day-head">{g} <span className="muted small">{items.filter((i) => i.packed).length}/{items.length}</span></h4>
          <ul className="trip-checklist">{items.map((p) => (
            <li key={p.item_id} className={p.packed ? 'done' : ''}>
              <label className="tick-row grow">
                <input type="checkbox" checked={p.packed} disabled={busy} onChange={() => run(() => api.updatePacking(p.item_id, { packed: !p.packed }))} />
                <span>{p.name}{p.qty > 1 && <span className="muted"> ×{p.qty}</span>}{p.gear_id && <span className="pill teal">your gear</span>}</span>
              </label>
              <button type="button" className="plain small" aria-label={`Remove ${p.name}`} disabled={busy}
                onClick={() => run(() => api.deletePacking(p.item_id))}>×</button>
            </li>))}</ul>
        </div>
      ))}
      <form className="trip-add" onSubmit={add}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Rain jacket" aria-label="Thing to pack" maxLength={200} />
        <select value={grp} onChange={(e) => setGrp(e.target.value)} aria-label="Group">
          {(lists?.groups ?? []).map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <button type="submit" className="secondary" disabled={busy || !name.trim()}>Add</button>
      </form>
      {t.packing.length > 0 && (
        <form className="trip-add" onSubmit={async (e) => {
          e.preventDefault()
          try {
            setSaved(await api.addPackingList({ name: saveAs.trim(), from_trip: t.trip_id }))
            showToast(`Saved as "${saveAs.trim()}" - it's in Packing lists`)
            setSaveAs('')
          } catch (err) {
            showToast(err.message)
          }
        }}>
          <input value={saveAs} onChange={(e) => setSaveAs(e.target.value)} placeholder="Save this list as..." aria-label="Save as a packing list" maxLength={80} />
          <button type="submit" className="plain" disabled={!saveAs.trim()}>Save as a list</button>
        </form>
      )}
      <p className="hint">{plural(t.packing.filter((p) => !p.packed).length, 'thing')} still to pack.</p>
    </section>
  )
}
