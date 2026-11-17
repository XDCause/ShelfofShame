import { useEffect, useState } from 'react'
import { api, dayDate, isoDay, shortDate } from '../../api.js'
import { BarList, ColumnChart } from '../../components/charts.jsx'
import { useApp } from '../../core/app-context.js'
import { minutesText, plainFront, plural } from './answers.js'
import { LanguagePicker, Milestone } from './LanguageViews.jsx'
import { useLanguageLists, useLanguages, useLanguageSummary } from './langParts.js'

// Progress: input hours and the milestones, the CEFR can-do checklist (tick what you can do; the level you're at
// follows), and the numbers - minutes a week, by activity, reviews a day and how many were remembered, what's coming
// due, and the cards you keep forgetting ("leeches": rewrite them, add an example, or suspend them).

const STATE_LABEL = { new: 'New', learning: 'Learning', relearning: 'Relearning', review: 'Review (under 3 weeks)', known: 'Known (3 weeks +)', suspended: 'Suspended' }
const plusDays = (iso, n) => { const d = dayDate(iso); d.setDate(d.getDate() + n); return isoDay(d) }
const dm = (iso) => dayDate(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })

export function ProgressView() {
  const { languages, current, pick } = useLanguages()
  if (!languages) return <p className="muted loading">Loading...</p>
  if (!current) return <section className="page lng-page"><p className="muted">Add a language first (Today).</p></section>
  return (
    <section className="page lng-page">
      <LanguagePicker languages={languages} current={current} pick={pick} />
      <Progress key={current.language_id} lang={current} />
    </section>
  )
}

function Progress({ lang }) {
  const { refreshKey, showToast, openPanel } = useApp()
  const { data: s } = useLanguageSummary(lang.language_id)
  const lists = useLanguageLists()
  const [stats, setStats] = useState(null)
  const [cando, setCando] = useState(null)
  useEffect(() => {
    api.languageStats(lang.language_id).then(setStats).catch((e) => showToast(e.message))
    api.languageCando(lang.language_id).then(setCando).catch((e) => showToast(e.message))
  }, [lang.language_id, refreshKey, showToast])
  if (!s || !stats || !cando || !lists) return <p className="muted loading">Loading...</p>
  const l = s.languages[0]
  const tick = async (item, done) => {
    const before = cando
    setCando((all) => all.map((c) => (c.item === item ? { ...c, done_on: done ? s.today : null } : c)))     // ticked at once
    try { setCando(await api.setLanguageCando(lang.language_id, item, done)) } catch (e) { setCando(before); showToast(e.message) }
  }

  // twelve weeks (Monday first), every one shown even with nothing in it
  const monday = plusDays(s.today, -((dayDate(s.today).getDay() + 6) % 7))
  const byWeek = Object.fromEntries(stats.weeks.map((w) => [w.week, w]))
  const weeks = Array.from({ length: 12 }, (_, i) => plusDays(monday, (i - 11) * 7)).map((w) => ({
    label: dm(w), value: byWeek[w]?.minutes ?? 0, tip: `week of ${dm(w)}: ${byWeek[w]?.input ?? 0} min of input` }))
  const byDay = Object.fromEntries(stats.reviews.map((r) => [r.day, r]))
  const reviews = Array.from({ length: 30 }, (_, i) => plusDays(s.today, i - 29)).map((d) => ({
    label: dm(d), value: byDay[d]?.reviews ?? 0,
    tip: byDay[d] ? `${byDay[d].remembered} remembered, ${byDay[d].new} new` : 'none' }))
  const due = Object.fromEntries(stats.forecast.map((f) => [f.day, f.cards]))
  const forecast = Array.from({ length: 14 }, (_, i) => plusDays(s.today, i)).map((d, i) => ({
    label: i === 0 ? 'Today' : dm(d), value: due[d] ?? 0 }))
  const levels = lists.goal_levels
  return (
      <div className="home-grid">
        <div className="home-stack">
          <section className="card home-card">
            <h2 className="home-card-title">Input hours</h2>
            <Milestone hours={l.input_hours} milestones={l.milestones} />
            <ol className="lng-ladder">
              {lists.milestones.map((m) => (
                <li key={m.hours} className={l.input_hours >= m.hours ? 'reached' : ''}>
                  <strong>{m.hours.toLocaleString()} h</strong> <span className="small">{m.what}</span>
                </li>
              ))}
            </ol>
            <p className="muted small">Dreaming Spanish's levels for an English speaker learning Spanish - a language close to yours
              takes about half the hours, a distant one (Japanese, Arabic) more. Hours before the app: {l.name} settings.</p>
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Minutes a week</h2>
            <ColumnChart title="Minutes studied each week" rows={weeks} valueLabel="minutes" tickEvery={2} />
          </section>
          {stats.by_activity.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Time by activity</h2>
              <BarList title="Minutes by activity" rows={stats.by_activity.map((a) => ({ label: a.activity, value: a.minutes, text: minutesText(a.minutes) }))} valueLabel="minutes" />
            </section>
          )}
          <section className="card home-card">
            <h2 className="home-card-title">Reviews a day</h2>
            <ColumnChart title="Cards reviewed each day" rows={reviews} valueLabel="reviews" tickEvery={7} />
            {s.retention != null && <p className="small">{s.retention}% of reviews of learnt cards remembered in the last 30 days.
              {s.retention < 80 ? ' Under 80%: try fewer new cards a day.' : s.retention > 95 ? ' Over 95%: you could take on more new cards.' : ' Right where it should be (FSRS aims for 90%).'}</p>}
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Coming due</h2>
            <ColumnChart title="Cards coming due, the next 14 days" rows={forecast} valueLabel="cards" tickEvery={7} />
            <BarList title="Cards by stage" rows={Object.entries(stats.states).map(([k, v]) => ({ label: STATE_LABEL[k] ?? k, value: v }))} valueLabel="cards" />
          </section>
          {stats.hardest.length > 0 && (
            <section className="card home-card">
              <h2 className="home-card-title">Cards you keep forgetting</h2>
              <ul className="list plain-list">{stats.hardest.map((c) => (
                <li key={c.card_id}><button type="button" className="row-button" onClick={() => openPanel('langcard', { id: c.card_id })}>
                  <span className="grow"><span className="item-title">{plainFront(c)}</span><span className="item-meta">{c.back}</span></span>
                  <span className="pill out">{plural(c.lapses, 'lapse')}</span></button></li>))}</ul>
              <p className="muted small">Give them an example sentence or a memory trick - or suspend them for now.</p>
            </section>
          )}
        </div>
        <div className="home-stack">
          <section className="card home-card lng-cando">
            <h2 className="home-card-title">What you can do</h2>
            <p className="small">Your level: <strong>{l.level ?? 'not set'}</strong>{l.goal_level && <> · aiming for <strong>{l.goal_level}</strong>{l.goal_date && ` by ${shortDate(l.goal_date)}`}</>}</p>
            {levels.map((lv) => {
              const items = cando.filter((c) => c.level === lv)
              const done = items.filter((c) => c.done_on).length
              return (
                <fieldset key={lv} className="lng-cando-level">
                  <legend>{lv} <span className="muted small">{done} of {items.length}</span></legend>
                  {items.map((c) => (
                    <label key={c.item} className="lng-cando-item">
                      <input type="checkbox" checked={!!c.done_on} onChange={(e) => tick(c.item, e.target.checked)} />
                      <span>{c.text}{c.done_on && <span className="muted small"> · {shortDate(c.done_on)}</span>}</span>
                    </label>
                  ))}
                </fieldset>
              )
            })}
            <p className="muted small">The Common European Framework's levels, in our own words. Tick what you can do comfortably - when a
              level's all ticked, it's time to move your level up (in {l.name} settings).</p>
          </section>
        </div>
      </div>
  )
}
