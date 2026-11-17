import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, dayDate, shortDate } from '../../api.js'
import { BookIcon, GridIcon, JournalIcon, LanguageIcon, SparkleIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { minutesText, plainFront, plural } from './answers.js'
import { useLanguageLists, useLanguages, useLanguageSummary } from './langParts.js'

// Language learning's pages: Today (the dashboard), Cards, the Study log and Resources. (Review: ReviewView.jsx;
// Progress: LanguageProgress.jsx.) Each page is about one language - the picker at the top switches, and remembers.

const WEEKDAY = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

// The languages as buttons (when there's more than one); Today adds "+ Add a language".
export function LanguagePicker({ languages, current, pick, adding = false }) {
  const { openPanel } = useApp()
  if (languages.length < 2 && !adding) return null
  return (
    <div className="chip-row lng-picker">
      {languages.length > 1 && (
        <div className="chip-row" role="group" aria-label="Language">
          {languages.map((l) => (
            <button key={l.language_id} type="button" className="chip-filter" aria-pressed={l.language_id === current?.language_id}
              onClick={() => pick(l.language_id)}>{l.name}{!l.active && ' (paused)'}</button>
          ))}
        </div>
      )}
      {adding && <button type="button" className="plain small" onClick={() => openPanel('langlanguage', {})}>+ Add a language</button>}
    </div>
  )
}

function NoLanguages() {
  const { openPanel } = useApp()
  return (
    <section className="page lng-page">
      <EmptyState Icon={LanguageIcon} title="Learn a language" action="+ Add a language" onAction={() => openPanel('langlanguage', {})}>
        Flashcards that come back just before you'd forget them (typed, heard or flipped), a study log with a daily goal and a
        streak, hours of listening and reading toward the milestones, the books and shows you're using, your tutor's notes,
        and what you can do at each level.
      </EmptyState>
    </section>
  )
}

// The page frame: the picker, then the page (given the language), or "add a language" when there's none.
function OneLanguage({ children, adding = false }) {
  const { languages, current, pick } = useLanguages()
  if (!languages) return <p className="muted loading">Loading...</p>
  if (!current) return <NoLanguages />
  return (
    <section className="page lng-page">
      <LanguagePicker languages={languages} current={current} pick={pick} adding={adding} />
      {children(current)}
    </section>
  )
}

// ---------------------------------------------------------------- Today
export function TodayView() {
  return <OneLanguage adding>{(lang) => <Today key={lang.language_id} lang={lang} />}</OneLanguage>
}

function Today({ lang }) {
  const { openPanel } = useApp()
  const { data: s, error } = useLanguageSummary(lang.language_id)
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const l = s.languages[0]
  const toDo = l.due + l.new
  const goal = l.daily_minutes
  const next = l.milestones.next
  return (
    <>
      <div className="toolbar lng-toolbar">
        <Link className={`button ${toDo ? 'primary' : 'secondary'}`} to="/language/review">{toDo ? `Review ${plural(toDo, 'card')}` : 'Review'}</Link>
        <button type="button" className="secondary" onClick={() => openPanel('langstudy', { languageId: l.language_id })}>+ Log study</button>
        <button type="button" className="plain" onClick={() => openPanel('langcard', { languageId: l.language_id })}>+ Add a card</button>
        <span className="grow" />
        <button type="button" className="plain small" onClick={() => openPanel('langlanguage', { id: l.language_id })}>{l.name} settings</button>
      </div>
      <div className="home-stats">
        <Stat to="/language/log" Icon={SparkleIcon} tone={s.streak.current ? 'ok' : 'low'} value={plural(s.streak.current, 'day')} label="Streak"
          sub={s.streak.longest ? `best ${plural(s.streak.longest, 'day')}` : 'study or review today to start one'} />
        <Stat to="/language/review" Icon={LanguageIcon} tone={toDo ? 'low' : 'ok'} value={toDo || 'Done'} label="Cards to review today"
          sub={`${l.due} due · ${l.new} new`} />
        <Stat to="/language/log" Icon={JournalIcon} tone={s.minutes_week >= goal * 7 ? 'ok' : 'teal'} value={minutesText(s.minutes_week)}
          label="Studied this week" sub={`goal ${minutesText(goal * 7)}`} />
        <Stat to="/language/progress" Icon={TrophyIcon} tone="purple" value={`${l.input_hours.toLocaleString()} h`} label="Input"
          sub={next ? `${next.to_go.toLocaleString()} h to ${next.hours} h` : 'every milestone reached'} />
        <Stat to="/language/cards" Icon={GridIcon} tone="tint" value={l.words_known.toLocaleString()} label="Words known"
          sub={`of ${plural(l.cards, 'card')}`} />
        <Stat to="/language/progress" Icon={BookIcon} tone={s.retention == null ? 'tint' : s.retention >= 85 ? 'ok' : 'low'}
          value={s.retention == null ? '—' : `${s.retention}%`} label="Remembered (30 days)" sub={s.retention_reviews ? plural(s.retention_reviews, 'review') : 'reviews of learnt cards'} />
      </div>
      <div className="home-grid">
        <div className="home-stack">
          <section className="card home-card">
            <h2 className="home-card-title">Today</h2>
            <Meter value={s.minutes_today} goal={goal} label={`${minutesText(s.minutes_today)} of ${minutesText(goal)}`} />
            <WeekStrip days={s.days.slice(-7)} today={s.today} goal={goal} />
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Twelve weeks</h2>
            <Heatmap days={s.days} today={s.today} goal={goal} />
          </section>
          <section className="card home-card">
            <div className="section-head">
              <h2 className="home-card-title">Latest study</h2>
              <Link className="button plain small" to="/language/log">All →</Link>
            </div>
            {s.recent.length === 0 ? <p className="muted small">Nothing logged yet. Classes, tutors, podcasts, shows, reading: log the minutes and they count toward your goal (reviews count by themselves).</p>
              : <ul className="list plain-list">{s.recent.map((x) => <StudyRow key={x.study_id} s={x} />)}</ul>}
          </section>
        </div>
        <div className="home-stack">
          <section className="card home-card">
            <h2 className="home-card-title">Input hours</h2>
            <Milestone hours={l.input_hours} milestones={l.milestones} />
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Level</h2>
            <p className="lng-level"><strong>{l.level ?? '—'}</strong>{l.goal_level && <> → <strong>{l.goal_level}</strong></>}
              {l.goal_date && <span className="muted small"> by {shortDate(l.goal_date)} ({daysTo(l.goal_date, s.today)})</span>}</p>
            {l.why && <p className="small lng-why">{l.why}</p>}
            <Link className="button plain small" to="/language/progress">What you can do →</Link>
          </section>
        </div>
      </div>
    </>
  )
}

const daysTo = (iso, today) => {
  const n = Math.round((dayDate(iso) - dayDate(today)) / 86400000)
  return n < 0 ? `${plural(-n, 'day')} ago` : n === 0 ? 'today' : `${plural(n, 'day')} to go`
}

export function Meter({ value, goal, label }) {
  const pct = goal ? Math.min(100, Math.round((100 * value) / goal)) : 0
  return (
    <div className="lng-meter">
      <div className="lng-meter-bar" role="progressbar" aria-label="Today's study against the goal" aria-valuemin={0} aria-valuemax={goal} aria-valuenow={Math.min(value, goal)}>
        <span className={pct >= 100 ? 'met' : ''} style={{ width: `${pct}%` }} />
      </div>
      <p className="small">{label}{pct >= 100 && ' - goal met'}</p>
    </div>
  )
}

// This week, Monday to Sunday: a column a day against the daily goal.
function WeekStrip({ days, today, goal }) {
  const top = Math.max(goal, ...days.map((d) => d.minutes)) || 1
  return (
    <ol className="lng-week" aria-label="Minutes each day this week">
      {days.map((d, i) => (
        <li key={d.day} className={d.day === today ? 'today' : d.day > today ? 'later' : ''}>
          <span className="lng-week-bar"><span className={d.minutes >= goal ? 'met' : ''} style={{ height: `${(100 * d.minutes) / top}%` }} /></span>
          <span className="lng-week-day" aria-hidden="true">{WEEKDAY[i]}</span>
          <span className="visually-hidden">{dayDate(d.day).toLocaleDateString('en-AU', { weekday: 'long' })}: {d.minutes} minutes</span>
        </li>
      ))}
    </ol>
  )
}

// 12 weeks x 7 days, a square a day, darker for more of the daily goal.
function Heatmap({ days, today, goal }) {
  const studied = days.filter((d) => d.minutes > 0).length
  const level = (m) => (m <= 0 ? 0 : m < goal / 2 ? 1 : m < goal ? 2 : m < goal * 2 ? 3 : 4)
  return (
    <>
      <div className="lng-heat" role="img" aria-label={`Studied on ${studied} of the last 84 days`}>
        {days.map((d) => (
          <span key={d.day} className={`lng-heat-${d.day > today ? 'x' : level(d.minutes)}`} title={`${shortDate(d.day)}: ${d.minutes} min`} />
        ))}
      </div>
      <p className="muted small">{plural(studied, 'day')} of study in 12 weeks. Darker: more of your {goal}-minute goal.</p>
    </>
  )
}

export function Milestone({ hours, milestones }) {
  const reached = milestones.reached.at(-1)
  const next = milestones.next
  const from = reached?.hours ?? 0
  const pct = next ? Math.round((100 * (hours - from)) / (next.hours - from)) : 100
  return (
    <div className="lng-milestone">
      <p><strong>{hours.toLocaleString()} hours</strong> of listening, watching, reading and conversation.</p>
      {next ? (
        <>
          <div className="lng-meter-bar" role="progressbar" aria-label={`Toward ${next.hours} hours`} aria-valuemin={from} aria-valuemax={next.hours} aria-valuenow={hours}>
            <span style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
          </div>
          <p className="small">{next.to_go.toLocaleString()} h to <strong>{next.hours} h</strong> - {next.what}.</p>
        </>
      ) : <p className="small">Past 1,500 hours: every milestone reached.</p>}
      {reached && <p className="muted small">Reached {reached.hours} h: {reached.what}.</p>}
    </div>
  )
}

function StudyRow({ s, showNotes = false }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('langstudy', { id: s.study_id })}>
        <span className="grow">
          <span className="item-title">{s.activity} · {minutesText(s.minutes)}</span>
          <span className="item-meta">{[shortDate(s.studied_on), s.with_whom && `with ${s.with_whom}`, s.resource].filter(Boolean).join(' · ')}</span>
          {showNotes && s.notes && <span className="small lng-row-notes">{s.notes}</span>}
        </span>
      </button>
    </li>
  )
}

// ---------------------------------------------------------------- Cards
const CARD_FILTERS = [['', 'All'], ['due', 'Due today'], ['new', 'New'], ['learning', 'Learning'], ['review', 'Review'], ['known', 'Known'], ['suspended', 'Suspended']]

export function CardsView() {
  return <OneLanguage>{(lang) => <Cards key={lang.language_id} lang={lang} />}</OneLanguage>
}

function Cards({ lang }) {
  const { openPanel, refreshKey, showToast } = useApp()
  const [q, setQ] = useState('')
  const [state, setState] = useState('')
  const [cards, setCards] = useState(null)
  useEffect(() => {
    const t = setTimeout(() => api.languageCards({ language_id: lang.language_id, q: q.trim(), state }).then(setCards).catch((e) => showToast(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [lang.language_id, q, state, refreshKey, showToast])
  const add = () => openPanel('langcard', { languageId: lang.language_id })
  return (
    <>
      <div className="toolbar">
        <input type="search" className="lng-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a word" aria-label="Find a card" />
        <span className="grow" />
        <button type="button" className="primary" onClick={add}>+ Add a card</button>
        <button type="button" className="secondary" onClick={() => openPanel('langbulk', { languageId: lang.language_id })}>Paste many</button>
      </div>
      <div className="chip-row lng-filters" role="group" aria-label="Show">
        {CARD_FILTERS.map(([key, label]) => (
          <button key={key} type="button" className="chip-filter" aria-pressed={state === key} onClick={() => setState(key)}>{label}</button>
        ))}
      </div>
      {!cards ? <p className="muted loading">Loading...</p> : cards.length === 0 ? (
        q || state ? <p className="muted">No cards match.</p> : (
          <EmptyState Icon={GridIcon} title="No cards yet" action="+ Add a card" onAction={add}>
            Add words and phrases in {lang.name} - or paste a whole list ("el perro - the dog", one a line). A sentence with
            a {'{{word}}'} in double braces becomes a fill-the-gap card.
          </EmptyState>
        )
      ) : (
        <>
          <p className="muted small">{plural(cards.length, 'card')}{cards.length >= 500 && ' (the newest 500: search to find the rest)'}</p>
          <ul className="list lng-cards">
            {cards.map((c) => (
              <li key={c.card_id}>
                <button type="button" className="row-button" onClick={() => openPanel('langcard', { id: c.card_id })}>
                  <span className="grow">
                    <span className="item-title" lang={lang.voice ?? undefined}>{plainFront(c)}</span>
                    <span className="item-meta">{c.back}{c.tags.length > 0 && ` · ${c.tags.join(' ')}`}</span>
                  </span>
                  <CardPill c={c} />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}

function CardPill({ c }) {
  if (c.suspended) return <span className="pill">Suspended</span>
  if (c.state === 'new') return <span className="pill tint">New</span>
  if (c.known) return <span className="pill ok">Known</span>
  return <span className="pill low">{c.state === 'review' ? `due ${shortDate(c.due)}` : 'Learning'}</span>
}

// ---------------------------------------------------------------- Study log
export function LogView() {
  return <OneLanguage>{(lang) => <Log key={lang.language_id} lang={lang} />}</OneLanguage>
}

function Log({ lang }) {
  const { openPanel, refreshKey, showToast } = useApp()
  const lists = useLanguageLists()
  const [activity, setActivity] = useState('')
  const [rows, setRows] = useState(null)
  useEffect(() => {
    api.languageStudy({ language_id: lang.language_id, activity }).then(setRows).catch((e) => showToast(e.message))
  }, [lang.language_id, activity, refreshKey, showToast])
  const total = (rows ?? []).reduce((a, r) => a + r.minutes, 0)
  return (
    <>
      <div className="toolbar">
        <div className="chip-row" role="group" aria-label="Activity">
          <button type="button" className="chip-filter" aria-pressed={!activity} onClick={() => setActivity('')}>All</button>
          {(lists?.activities ?? []).map((a) => (
            <button key={a} type="button" className="chip-filter" aria-pressed={activity === a} onClick={() => setActivity(a)}>{a}</button>
          ))}
        </div>
        <button type="button" className="primary" onClick={() => openPanel('langstudy', { languageId: lang.language_id })}>+ Log study</button>
      </div>
      {!rows ? <p className="muted loading">Loading...</p> : rows.length === 0 ? (
        activity ? <p className="muted">No {activity.toLowerCase()} logged yet.</p> : (
          <EmptyState Icon={JournalIcon} title="Nothing logged yet" action="+ Log study" onAction={() => openPanel('langstudy', { languageId: lang.language_id })}>
            Log the time you spend on {lang.name} outside the cards: a class, a tutor (with what you covered), a podcast, a
            show, a book. Card reviews count by themselves.
          </EmptyState>
        )
      ) : (
        <>
          <p className="muted small">{plural(rows.length, 'entry', 'entries')} · {minutesText(total)}</p>
          <ul className="list lng-log">{rows.map((r) => <StudyRow key={r.study_id} s={r} showNotes />)}</ul>
        </>
      )}
    </>
  )
}

// ---------------------------------------------------------------- Resources
const STATUS_HEAD = { Using: 'Working through', Want: 'Want to try', Done: 'Finished', Dropped: 'Dropped' }

export function ResourcesView() {
  return <OneLanguage>{(lang) => <Resources key={lang.language_id} lang={lang} />}</OneLanguage>
}

function Resources({ lang }) {
  const { openPanel, refreshKey, showToast } = useApp()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.languageResources(lang.language_id).then(setRows).catch((e) => showToast(e.message)) }, [lang.language_id, refreshKey, showToast])
  const add = () => openPanel('langresource', { languageId: lang.language_id })
  if (!rows) return <p className="muted loading">Loading...</p>
  if (!rows.length) {
    return (
      <EmptyState Icon={BookIcon} title="No resources yet" action="+ Add a resource" onAction={add}>
        The textbook, the graded readers, the podcast, the show with subtitles: keep track of where you're up to, and log
        time against them.
      </EmptyState>
    )
  }
  return (
    <>
      <div className="toolbar"><span className="grow" /><button type="button" className="primary" onClick={add}>+ Add a resource</button></div>
      {Object.keys(STATUS_HEAD).filter((st) => rows.some((r) => r.status === st)).map((st) => (
        <section key={st} className="lng-res-group">
          <h2 className="section-title">{STATUS_HEAD[st]}</h2>
          <ul className="list">
            {rows.filter((r) => r.status === st).map((r) => (
              <li key={r.resource_id}>
                <button type="button" className="row-button" onClick={() => openPanel('langresource', { id: r.resource_id, resource: r })}>
                  <span className="grow">
                    <span className="item-title">{r.title}</span>
                    <span className="item-meta">{[r.kind, r.level, r.progress, r.minutes ? `${minutesText(r.minutes)} logged` : null,
                      r.last_used && `last ${shortDate(r.last_used)}`].filter(Boolean).join(' · ')}</span>
                  </span>
                </button>
                {r.url && <a className="button plain small" href={r.url} target="_blank" rel="noreferrer">Open</a>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  )
}
