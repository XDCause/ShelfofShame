import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../../api.js'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import EmptyState from '../EmptyState.jsx'
import { dueText, groupGoals, hobbyName, periodChoices, periodLabel, ProgressBar, progressText, STATUS } from './goalParts.jsx'

const SHOWS = [['active', 'Active'], ['paused', 'Paused'], ['done', 'Done'], ['dropped', 'Dropped'], ['', 'All']]

// Goals: a card per goal (how far along, what's next, when it's due), in sections - this year's goals,
// 3-year goals, next year's, no set time, past years'. Tap one for its own page. "+ New goal" asks
// for the name and when it's for, then opens the goal's page to fill in the rest.
export default function GoalsPage() {
  const { refreshKey } = useApp()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [show, setShow] = useState('')
  const [when, setWhen] = useState(null)        // a periodChoices value; null = this year
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  useEffect(() => { api.goals().then(setData).catch((e) => setError(e.message)) }, [refreshKey])

  const add = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try {
      const choice = choices.find((c) => c.value === (when ?? choices[0].value))
      const goal = await api.addGoal({ title, timeframe: choice.timeframe, period_start: choice.period_start })
      navigate(`/goals/${goal.goal_id}`)
    } catch (err) {
      setError(err.message)
    }
  }

  if (error && !data) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const choices = periodChoices(data.this_year)
  const shown = data.goals.filter((g) => !show || g.status === show)
  const sections = groupGoals(shown, data.this_year)
  const newForm = (
    <form className="goal-new card" onSubmit={add}>
      <label className="field grow">What's the goal?
        <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Read 30 books this year" maxLength={200} />
      </label>
      <div className="segmented goal-when" role="group" aria-label="When">
        {choices.map((c) => (
          <button key={c.value || 'none'} type="button" aria-pressed={(when ?? choices[0].value) === c.value} onClick={() => setWhen(c.value)}>{c.label}</button>
        ))}
      </div>
      <button type="submit" className="primary" disabled={!title.trim()}>Add</button>
      <button type="button" className="plain" onClick={() => { setAdding(false); setTitle('') }}>Cancel</button>
    </form>
  )

  return (
    <section className="page goals-page">
      {data.goals.length === 0 && !adding ? (
        <EmptyState Icon={TargetIcon} title="No goals yet" action="+ New goal" onAction={() => setAdding(true)}>
          Write down what you're aiming for - why it matters, the plan, the steps - and track how it's going.
        </EmptyState>
      ) : (
        <>
          <div className="toolbar">
            <div className="chip-row scroll">
              {SHOWS.map(([k, label]) => (
                <button key={k || 'all'} type="button" className="chip-filter" aria-pressed={show === k} onClick={() => setShow(k)}>
                  {label} <span className="chip-count">{k ? data.counts[k] : data.goals.length}</span>
                </button>
              ))}
            </div>
            {!adding && <button type="button" className="primary" onClick={() => setAdding(true)}>+ New goal</button>}
          </div>
          {error && <p className="alert error">{error}</p>}
          {adding && newForm}
          {shown.length === 0 ? <p className="muted">No {STATUS[show]?.label.toLowerCase()} goals.</p>
            : sections.map((s) => <GoalSection key={s.key || 'none'} section={s} thisYear={data.this_year} />)}
        </>
      )}
    </section>
  )
}

function GoalSection({ section: s, thisYear }) {
  const done = s.goals.filter((g) => g.status === 'done').length
  const past = s.timeframe && s.start + (s.timeframe === 'year' ? 0 : 2) < thisYear
  const title = s.timeframe === 'year' && s.start === thisYear ? `${thisYear} goals`
    : s.timeframe === 'year' && s.start === thisYear + 1 ? `${thisYear + 1} goals (next year)` : periodLabel(s.timeframe, s.start)
  return (
    <section className={`goal-section${past ? ' past' : ''}`} aria-label={title}>
      <h2 className="goal-section-title">{s.timeframe ? title : 'Other goals'}
        {s.timeframe && <span className="muted small">{done} of {s.goals.length} done</span>}</h2>
      <ul className="goal-grid">{s.goals.map((g) => <GoalCard key={g.goal_id} goal={g} />)}</ul>
    </section>
  )
}

// The title always comes first (a row of pills above it put titles at different heights side by side).
function GoalCard({ goal: g }) {
  const due = dueText(g)
  const progress = progressText(g)
  return (
    <li>
      <Link to={`/goals/${g.goal_id}`} className={`goal-tile card ${g.status}`}>
        <span className="goal-title">{g.title}</span>
        <span className="goal-tile-top">
          {g.pinned && <span className="pill purple">Pinned</span>}
          <span className="pill">{g.hobby ? hobbyName(g.hobby) : 'Life in general'}</span>
          {g.status !== 'active' && <span className={`pill ${STATUS[g.status].tone}`}>{STATUS[g.status].label}</span>}
          {due && <span className={`goal-due ${g.days_left != null && g.days_left < 0 ? 'late' : ''}`}>{due}</span>}
        </span>
        {g.why && <span className="goal-why">{g.why}</span>}
        <ProgressBar goal={g} />
        {(progress || g.progress != null) && (
          <span className="item-meta">{[progress, g.progress != null && `${Math.round(g.progress * 100)}%`].filter(Boolean).join(' · ')}</span>
        )}
        {g.next_step && g.status === 'active' && <span className="goal-next"><span className="muted">Next:</span> {g.next_step}</span>}
      </Link>
    </li>
  )
}
