import { useEffect, useState } from 'react'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { VOICES, clozeParts, plainFront, speak, voiceFor } from './answers.js'
import { rememberLanguage, useLanguageLists } from './langParts.js'

// Language learning's panels: a language, a card, pasting many cards, a study log entry, a resource.

const LEVEL_NAMES = { A0: 'A0 - just starting', A1: 'A1 - beginner', A2: 'A2 - elementary', B1: 'B1 - intermediate',
  B2: 'B2 - upper intermediate', C1: 'C1 - advanced', C2: 'C2 - mastery' }
const levelOptions = (levels) => (levels ?? []).map((l) => [l, LEVEL_NAMES[l] ?? l])
const tagsFrom = (text) => (text ?? '').split(/[\s,]+/).map((t) => t.trim().toLowerCase()).filter(Boolean)

function Loading({ title, onClose }) {
  return <Drawer title={title} onClose={onClose}><p className="muted">Loading...</p></Drawer>
}

// A language: its name (the voice follows it), your level and the one you're aiming for, minutes a day, new cards a day.
export function LanguagePanel({ id = null, onClose }) {
  const { changed, showToast } = useApp()
  const lists = useLanguageLists()
  const [lang, setLang] = useState(null)
  useEffect(() => {
    if (id != null) api.languages().then((all) => setLang(all.find((l) => l.language_id === id) ?? null)).catch((e) => showToast(e.message))
  }, [id, showToast])
  if (!lists || (id != null && !lang)) return <Loading title="Language" onClose={onClose} />
  const fields = [
    { name: 'name', label: 'Language', required: true, list: 'lng-names', placeholder: 'e.g. Spanish' },
    { name: 'voice', label: 'Voice (for listening)', placeholder: 'e.g. es-MX', hint: 'A language tag: es-ES Spain, es-MX Mexico, pt-PT, pt-BR... Filled in from the name.' },
    { name: 'level', label: 'Your level now', type: 'select', options: levelOptions(lists.levels) },
    { name: 'goal_level', label: 'Aiming for', type: 'select', options: levelOptions(lists.goal_levels) },
    { name: 'goal_date', label: 'By', type: 'date' },
    { name: 'daily_minutes', label: 'Minutes a day', type: 'number', min: 1, required: true },
    { name: 'new_per_day', label: 'New cards a day', type: 'number', min: 0, required: true, hint: 'Each new card brings reviews for weeks: 10-20 is plenty.' },
    { name: 'prior_input_hours', label: 'Input hours before this app', type: 'number', step: 0.5, min: 0 },
    { name: 'started_on', label: 'Started', type: 'date' },
    { name: 'active', label: 'Status', type: 'select', options: [['true', 'Learning now'], ['false', 'Paused']], required: true },
    { name: 'why', label: 'Why you\'re learning it', type: 'textarea', placeholder: 'A trip, family, a job, the films...' },
  ]
  const onField = (name, value, setForm) => {
    if (name === 'name') setForm((f) => (f.voice && f.voice !== voiceFor(lang?.name ?? '') ? f : { ...f, voice: voiceFor(value) ?? f.voice }))
  }
  const save = async (data) => {
    const body = { ...data, active: data.active !== 'false', prior_input_hours: data.prior_input_hours ?? 0, started_on: data.started_on ?? undefined }
    if (lang) await api.updateLanguage(lang.language_id, body)
    else rememberLanguage((await api.addLanguage(body)).language_id)       // (the pages switch to it)
    changed()
    showToast(lang ? 'Saved' : `Added ${data.name}`)
    onClose()
  }
  return (
    <FormPanel title={lang ? lang.name : 'Add a language'} fields={fields} record={lang} onField={onField} onSave={save} onClose={onClose}
      defaults={{ daily_minutes: 20, new_per_day: 10, active: 'true', started_on: today() }} saveLabel={lang ? 'Save' : 'Add'}
      onDelete={lang && (async () => { await api.deleteLanguage(lang.language_id); changed(); onClose() })} deleteLabel="Remove with its cards and log"
      before={<datalist id="lng-names">{Object.keys(VOICES).map((n) => <option key={n} value={n} />)}</datalist>} />
  )
}

const CARD_FIELDS = [
  { name: 'front', label: 'Word or phrase', required: true, wide: true, hint: 'In the language. A sentence with {{double braces}} around a word is a cloze card: Ayer {{fui}} al cine.' },
  { name: 'back', label: 'Meaning', required: true, wide: true, hint: 'Several answers? Separate them with commas.' },
  { name: 'example', label: 'Example sentence', wide: true },
  { name: 'example_meaning', label: 'Example means', wide: true },
  { name: 'tags', label: 'Tags', wide: true, placeholder: 'e.g. food verbs a1', hint: 'One word each, spaces between.' },
  { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Gender, irregular forms, a memory trick...' },
]
const STATE_NAMES = { new: 'New', learning: 'Learning', relearning: 'Relearning', review: 'Review' }

// A card: new ones reopen empty after each add (quick entry); a saved one shows its memory and history too.
export function CardPanel({ id = null, languageId = null, onClose }) {
  const { changed, showToast } = useApp()
  const [card, setCard] = useState(null)
  const [voice, setVoice] = useState(null)
  const [fresh, setFresh] = useState(0)          // bumped after each add: a new, empty form (the panel itself stays open)
  useEffect(() => { if (id != null) api.languageCard(id).then(setCard).catch((e) => showToast(e.message)) }, [id, showToast])
  const langId = card?.language_id ?? languageId
  useEffect(() => {
    if (langId != null) api.languages().then((all) => setVoice(all.find((l) => l.language_id === langId)?.voice ?? null)).catch(() => {})
  }, [langId])
  if (id != null && !card) return <Loading title="Card" onClose={onClose} />
  if (langId == null) return <Drawer title="Add a card" onClose={onClose}><p className="muted">Add a language first.</p></Drawer>
  const save = async (data) => {
    const body = { ...data, tags: tagsFrom(data.tags) }
    if (card) {
      setCard({ ...card, ...(await api.updateLanguageCard(card.card_id, body)) })
      changed()
      showToast('Saved')
      onClose()
    } else {
      const made = await api.addLanguageCard({ ...body, language_id: langId })
      changed()
      showToast(`Added: ${plainFront(made)}`)
      setFresh((n) => n + 1)       // a fresh form for the next one (closing and reopening would keep this one: same panel key)
    }
  }
  const act = async (patch, message) => {
    try {
      setCard({ ...card, ...(await api.updateLanguageCard(card.card_id, patch)) })
      changed()
      showToast(message)
    } catch (e) {
      showToast(e.message)
    }
  }
  const record = card && { ...card, tags: (card.tags ?? []).join(' ') }
  const said = card && (card.kind === 'cloze' ? clozeParts(card.front).full : card.front)
  return (
    <FormPanel key={fresh} title={card ? plainFront(card) : 'Add a card'} fields={CARD_FIELDS} record={record} onSave={save} onClose={onClose}
      saveLabel={card ? 'Save' : 'Add and next'}
      onDelete={card && (async () => { await api.deleteLanguageCard(card.card_id); changed(); onClose() })}
      before={card ? (
        <section className="panel-section">
          <div className="button-row">
            <span className={`pill ${card.suspended ? '' : card.known ? 'ok' : card.state === 'new' ? 'tint' : 'low'}`}>
              {card.suspended ? 'Suspended' : card.known ? 'Known' : STATE_NAMES[card.state]}</span>
            {card.state !== 'new' && <span className="muted small">due {shortDate(card.due)} · {card.reps} reviews · {card.lapses} lapses
              {card.stability != null && ` · remembered for ~${Math.round(card.stability)} days`}</span>}
            <span className="spacer" />
            <button type="button" className="plain small" onClick={() => speak(said, voice) || showToast('This browser has no voice for it')}>Say it</button>
          </div>
          <div className="button-row">
            <button type="button" className="plain small" onClick={() => act({ suspended: !card.suspended }, card.suspended ? 'Back in reviews' : 'Suspended: out of reviews')}>
              {card.suspended ? 'Unsuspend' : 'Suspend'}</button>
            {card.state !== 'new' && <button type="button" className="plain small" onClick={() => act({ reset: true }, 'Reset: new again')}>Forget (make it new)</button>}
          </div>
          {card.history?.length > 0 && (
            <details className="lng-history">
              <summary>{card.history.length} answers</summary>
              <ul className="plain-list small">{card.history.map((h) => (
                <li key={h.reviewed_at}>{shortDate(h.reviewed_at)} · {['', 'Again', 'Hard', 'Good', 'Easy'][h.grade]} · {h.mode}
                  {h.interval_days > 0 && ` · next in ${Math.round(h.interval_days)} d`}</li>))}</ul>
            </details>
          )}
        </section>
      ) : null} />
  )
}

// Paste many: one "word - meaning" a line (a spreadsheet's two columns paste as word<tab>meaning).
export function BulkPanel({ languageId = null, onClose }) {
  const { changed, showToast } = useApp()
  const [text, setText] = useState('')
  const [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const lines = text.split('\n').filter((l) => l.trim() && !l.trim().startsWith('#')).length
  const add = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await api.addLanguageCards({ language_id: languageId, text, tags: tagsFrom(tags) })
      setResult(r)
      if (r.added) { changed(); showToast(`Added ${r.added} card${r.added === 1 ? '' : 's'}`) }
      if (!r.unreadable.length) setText('')
      else setText(r.unreadable.join('\n'))
    } catch (err) {
      setError(err.message)
    }
    setBusy(false)
  }
  const footer = (
    <>
      <button type="submit" form="lng-bulk" className="primary" disabled={busy || !lines || languageId == null}>Add {lines || ''} card{lines === 1 ? '' : 's'}</button>
      <button type="button" className="plain" onClick={onClose}>Close</button>
    </>
  )
  return (
    <Drawer title="Paste many cards" onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <form id="lng-bulk" onSubmit={add} className="lng-bulk">
        <label className="field">One card a line: word - meaning
          <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder={'el perro - the dog\nla casa - the house\nAyer {{fui}} al cine - Yesterday I went to the cinema'} />
        </label>
        <p className="hint">Between them: a dash, =, ; or a tab (two columns pasted from a spreadsheet). Words already in the deck are skipped.</p>
        <label className="field">Tags for all of them<input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="e.g. chapter3" /></label>
      </form>
      {result && (
        <div className="lng-bulk-result" role="status">
          <p><strong>{result.added} added.</strong>{result.skipped.length > 0 && ` ${result.skipped.length} already there: ${result.skipped.slice(0, 8).join(', ')}${result.skipped.length > 8 ? '...' : ''}.`}</p>
          {result.unreadable.length > 0 && <p className="small">{result.unreadable.length} line{result.unreadable.length === 1 ? '' : 's'} couldn't be read (no dash or tab): left in the box to fix.</p>}
        </div>
      )}
    </Drawer>
  )
}

// A study log entry. day: the calendar's day (Log it); languageId: the language you're on.
export function StudyPanel({ id = null, day = null, languageId = null, onClose }) {
  const { changed, showToast } = useApp()
  const lists = useLanguageLists()
  const [entry, setEntry] = useState(null)
  const [languages, setLanguages] = useState(null)
  const [resources, setResources] = useState([])
  const [lang, setLang] = useState(null)
  useEffect(() => {
    if (id != null) api.languageStudyEntry(id).then((e) => { setEntry(e); setLang(e.language_id) }).catch((e) => showToast(e.message))
  }, [id, showToast])
  useEffect(() => {
    Promise.all([api.languages(), api.languageResources()]).then(([l, r]) => { setLanguages(l); setResources(r) }).catch((e) => showToast(e.message))
  }, [showToast])
  if (!lists || !languages || (id != null && !entry)) return <Loading title="Study" onClose={onClose} />
  if (!languages.length) return <Drawer title="Log study" onClose={onClose}><p className="muted">Add a language first.</p></Drawer>
  const chosen = lang ?? languageId ?? languages.find((l) => l.active)?.language_id ?? languages[0].language_id
  const fields = [
    { name: 'language_id', label: 'Language', type: 'select', required: true, options: languages.map((l) => [String(l.language_id), l.name]) },
    { name: 'studied_on', label: 'Day', type: 'date', required: true },
    { name: 'activity', label: 'What you did', type: 'select', required: true, options: lists.activities },
    { name: 'minutes', label: 'Minutes', type: 'number', min: 1, required: true },
    { name: 'resource_id', label: 'With (a resource)', type: 'select',
      options: resources.filter((r) => r.language_id === Number(chosen) && (r.status === 'Using' || r.resource_id === entry?.resource_id)).map((r) => [String(r.resource_id), r.title]) },
    { name: 'with_whom', label: 'Tutor, teacher or partner', placeholder: 'e.g. Lucía on italki' },
    { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'What you covered, words that came up, what to work on next' },
  ]
  const save = async (data) => {
    const body = { ...data, language_id: Number(data.language_id), resource_id: data.resource_id ? Number(data.resource_id) : null }
    if (entry) await api.updateLanguageStudy(entry.study_id, body)
    else await api.addLanguageStudy(body)
    changed()
    showToast(entry ? 'Saved' : `Logged ${data.minutes} min of ${data.activity.toLowerCase()}`)
    onClose()
  }
  return (
    <FormPanel title={entry ? `${entry.language}: ${entry.activity.toLowerCase()}` : 'Log study'} fields={fields} record={entry}
      defaults={{ language_id: chosen, studied_on: day ?? today(), activity: 'Listening', minutes: 30 }}
      onField={(name, value, setForm) => { if (name === 'language_id') { setLang(Number(value)); setForm((f) => ({ ...f, resource_id: '' })) } }}
      onSave={save} onClose={onClose} saveLabel={entry ? 'Save' : 'Log it'}
      before={<p className="muted small">Listening, watching, reading, tutors and classes count as input hours.</p>}
      onDelete={entry && (async () => { await api.deleteLanguageStudy(entry.study_id); changed(); onClose() })} />
  )
}

// A resource: a book, show, podcast, course...
export function ResourcePanel({ id = null, resource = null, languageId = null, onClose }) {
  const { changed, showToast } = useApp()
  const lists = useLanguageLists()
  if (!lists) return <Loading title="Resource" onClose={onClose} />
  const fields = [
    { name: 'title', label: 'Title', required: true, wide: true },
    { name: 'kind', label: 'Kind', type: 'select', required: true, options: lists.resource_kinds },
    { name: 'status', label: 'Status', type: 'select', required: true, options: [['Using', 'Working through it'], ['Want', 'Want to try'], ['Done', 'Finished'], ['Dropped', 'Dropped']] },
    { name: 'level', label: 'Level', type: 'select', options: lists.goal_levels },
    { name: 'progress', label: 'Where you\'re up to', placeholder: 'e.g. chapter 4, season 2 episode 3' },
    { name: 'url', label: 'Link', type: 'url', wide: true, placeholder: 'https://' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const save = async (data) => {
    if (resource) await api.updateLanguageResource(resource.resource_id, data)
    else await api.addLanguageResource({ ...data, language_id: languageId })
    changed()
    showToast(resource ? 'Saved' : `Added ${data.title}`)
    onClose()
  }
  return (
    <FormPanel title={resource ? resource.title : 'Add a resource'} fields={fields} record={resource} defaults={{ kind: 'Book', status: 'Using' }}
      onSave={save} onClose={onClose} saveLabel={resource ? 'Save' : 'Add'}
      onDelete={resource && id != null && (async () => { await api.deleteLanguageResource(resource.resource_id); changed(); onClose() })} />
  )
}
