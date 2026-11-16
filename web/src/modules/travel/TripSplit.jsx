import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { inCurrency } from './travelParts.jsx'

// Splitting a trip's costs (api/app/travel_extras.py): who is on the trip, who paid each cost, who shares it, and who owes
// who at the end with the fewest payments. Each cost keeps the rate it was entered with, so every currency adds up in AUD;
// "Show in" turns the settle-up into another currency.

// The people a cost is shared by, as the API wants them: everyone = an empty list.
export function nextShare(shared, everyone, id) {
  const now = new Set(shared.length ? shared : everyone)
  if (now.has(id)) now.delete(id)
  else now.add(id)
  if (now.size === 0 || now.size === everyone.length) return []
  return everyone.filter((p) => now.has(p))
}

export default function SplitTab({ t }) {
  const { showToast } = useApp()
  const [s, setS] = useState(null)
  const [show, setShow] = useState('AUD')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const load = useCallback(() => api.tripSplit(t.trip_id, show === 'AUD' ? null : show).then((d) => { setS(d); setError('') })
    .catch((e) => setError(e.message)), [t.trip_id, show])
  useEffect(() => { load() }, [load])
  const run = async (call) => {
    try { setS(await call()); setError('') } catch (e) { showToast(e.message) }
  }
  if (!s) return <section className="panel-section">{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</section>
  const ids = s.people.map((p) => p.person_id)
  const money = (n) => inCurrency(n, s.currency)
  const save = (c, paid_by, shared_by) => run(() => (c.kind === 'expense' ? api.splitExpense(c.id, { paid_by, shared_by }) : api.splitBooking(c.id, { paid_by, shared_by })))
  const add = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    await run(() => api.addTripPerson(t.trip_id, name.trim()))
    setName('')
  }
  const currencies = ['AUD', ...t.money.currencies]
  return (
    <>
      <section className="panel-section">
        <h3 className="section-title">Who's on the trip</h3>
        <ul className="split-people">
          {s.people.map((p) => (
            <li key={p.person_id} className="split-person">{p.name}
              <button type="button" className="plain small" aria-label={`Remove ${p.name}`}
                onClick={() => { if (window.confirm(`Take ${p.name} off the trip? What they paid becomes unassigned.`)) run(() => api.deleteTripPerson(p.person_id)) }}>×</button></li>
          ))}
        </ul>
        <form className="split-add" onSubmit={add}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Add a person (include yourself)" aria-label="Person's name" maxLength={60} />
          <button type="submit" className="secondary" disabled={!name.trim()}>Add</button>
        </form>
        {s.people.length < 2 && <p className="hint">Add everyone who shares costs (you too), then say who paid each cost below.</p>}
      </section>
      {s.people.length >= 2 && (
        <>
          <section className="panel-section">
            <div className="section-head">
              <h3 className="section-title">Who owes who</h3>
              {currencies.length > 1 && (
                <label className="split-show">Show in <select value={show} onChange={(e) => setShow(e.target.value)} aria-label="Show amounts in">
                  {currencies.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
              )}
            </div>
            {s.settle.length === 0
              ? <p className="muted small">{s.counted ? 'All square: nobody owes anyone.' : 'Nothing to settle yet: say who paid at least one cost below.'}</p> : (
                <ul className="list plain-list split-settle">
                  {s.settle.map((p) => (
                    <li key={`${p.from_id}-${p.to_id}`}><strong>{p.from}</strong> pays <strong>{p.to}</strong> <span className="trip-cost">{money(p.amount)}</span></li>
                  ))}
                </ul>
              )}
            <table className="split-balances">
              <thead><tr><th scope="col">Person</th><th scope="col">Paid</th><th scope="col">Share</th><th scope="col">Balance</th></tr></thead>
              <tbody>
                {s.balances.map((b) => (
                  <tr key={b.person_id}><th scope="row">{b.name}</th><td>{money(b.paid)}</td><td>{money(b.share)}</td>
                    <td className={b.net < 0 ? 'trip-over' : ''}>{b.net > 0 ? '+' : ''}{money(b.net)}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="hint">{s.counted} cost{s.counted === 1 ? '' : 's'} split, {money(s.total)} in all.
              {s.unassigned > 0 && ` ${s.unassigned} more have no one marked as paying, so they're left out.`}</p>
          </section>
          <section className="panel-section">
            <h3 className="section-title">Who paid</h3>
            {s.items.length === 0 ? <p className="muted small">Costs from the Money and Bookings tabs show up here.</p> : (
              <ul className="list plain-list split-costs">
                {s.items.map((c) => (
                  <li key={`${c.kind}-${c.id}`} className="split-cost">
                    <span className="grow"><span className="item-title">{c.title}</span>
                      <span className="item-meta">{c.kind === 'booking' ? 'Booking' : 'Spent'} · {inCurrency(c.amount, c.currency)}
                        {c.currency !== 'AUD' && ` (${inCurrency(c.aud, 'AUD')})`}</span></span>
                    <label className="split-paid"><span className="visually-hidden">Paid by</span>
                      <select value={c.paid_by ?? ''} aria-label={`Who paid for ${c.title}`}
                        onChange={(e) => save(c, e.target.value ? Number(e.target.value) : null, c.shared_by)}>
                        <option value="">Not split</option>
                        {s.people.map((p) => <option key={p.person_id} value={p.person_id}>{p.name} paid</option>)}
                      </select></label>
                    {c.paid_by && (
                      <span className="split-shared" role="group" aria-label={`Shared by, for ${c.title}`}>
                        {s.people.map((p) => {
                          const on = c.shared_by.length ? c.shared_by.includes(p.person_id) : true
                          return (
                            <button key={p.person_id} type="button" className="chip-filter" aria-pressed={on}
                              onClick={() => save(c, c.paid_by, nextShare(c.shared_by, ids, p.person_id))}>{p.name}</button>
                          )
                        })}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="hint">Tap names to choose who shares a cost; all lit means everyone. Amounts are shared equally.</p>
          </section>
        </>
      )}
    </>
  )
}
