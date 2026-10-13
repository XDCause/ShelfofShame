import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import TagsInput from './TagsInput.jsx'

const Editor = lazy(() => import('./Editor.jsx'))
const SAVE_AFTER_MS = 700  // save this long after you stop typing

// The parts of a page the server works out from what you wrote.
const derived = ({ links, mentioned_in, suggestions }) => ({ links, mentioned_in, suggestions })

// One journal page: title, date, icon, tags, pin, the editor, and what it links to.
// Everything saves by itself as you go ("Saving..." / "Saved").
export default function JournalPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { openItem, openModel, changed, showToast } = useApp()
  const [page, setPage] = useState(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')        // '', 'saving', 'saved'
  const [confirmDelete, setConfirmDelete] = useState(false)
  const pending = useRef({})                        // changes not sent yet
  const timer = useRef(null)

  useEffect(() => {
    setPage(null)
    api.getPage(id).then(setPage).catch((e) => setError(e.message))
  }, [id])

  // Send whatever has changed; the reply refreshes links, tags and "mentioned in".
  const flush = useCallback(async () => {
    clearTimeout(timer.current)
    const data = pending.current
    if (!Object.keys(data).length) return
    pending.current = {}
    setStatus('saving')
    try {
      const saved = await api.updatePage(id, data)
      // Only take what the server works out: what you've typed since stays as it is.
      setPage((p) => ({ ...p, ...derived(saved) }))
      setStatus('saved')
      changed()
    } catch (e) {
      setError(e.message)
      setStatus('')
    }
  }, [id, changed])

  const save = useCallback((data, now = false) => {
    pending.current = { ...pending.current, ...data }
    setStatus('saving')
    clearTimeout(timer.current)
    if (now) flush()
    else timer.current = setTimeout(flush, SAVE_AFTER_MS)
  }, [flush])

  // Leaving the page (or closing the tab) saves anything still waiting.
  useEffect(() => {
    const beforeUnload = () => flush()
    window.addEventListener('beforeunload', beforeUnload)
    return () => { window.removeEventListener('beforeunload', beforeUnload); flush() }
  }, [flush])

  // "Sherman: Mark as In progress" - Apply does it (and says so), Not now hides it for this page.
  const answer = async (s, apply) => {
    try {
      await flush()
      const saved = apply ? await api.applySuggestion(page.page_id, s.key) : await api.dismissSuggestion(page.page_id, s.key)
      setPage((p) => ({ ...p, ...derived(saved) }))
      if (apply) {
        changed()
        showToast(`${s.name}: ${s.label.replace(/^Mark as /, 'now ').replace(/^Tick build step /, 'build step ')} ✓`)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  const openMention = (kind, ref) => {
    if (kind === 'model') openModel(ref)
    else if (kind === 'supply') openItem(ref)
    else navigate(`/journal/${ref}`)
  }

  if (error) return <p className="alert error">{error} <Link to="/journal">Back to the journal</Link></p>
  if (!page) return <p className="muted loading">Loading...</p>

  const edit = (field, now = false) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setPage((p) => ({ ...p, [field]: value }))
    save({ [field]: field === 'icon' ? value.trim() || null : value }, now)
  }

  return (
    <article className="journal-page">
      <div className="journal-bar">
        <Link to="/journal" className="plain">‹ Journal</Link>
        <span className="spacer" />
        <span className="save-status muted small" role="status" aria-live="polite">
          {status === 'saving' ? 'Saving...' : status === 'saved' ? 'Saved' : ''}
        </span>
        <label className="pin">
          <input type="checkbox" checked={page.pinned} onChange={edit('pinned', true)} /> Pinned
        </label>
        {confirmDelete ? (
          <span className="confirm">
            Delete this page?
            <button type="button" className="danger" onClick={async () => {
              clearTimeout(timer.current)
              pending.current = {}
              await api.deletePage(page.page_id)
              changed()
              navigate('/journal')
            }}>Delete</button>
            <button type="button" className="plain" onClick={() => setConfirmDelete(false)}>Cancel</button>
          </span>
        ) : (
          <button type="button" className="plain destructive" onClick={() => setConfirmDelete(true)}>Delete</button>
        )}
      </div>

      <div className="journal-head">
        <input className="journal-icon" value={page.icon ?? ''} onChange={edit('icon')} maxLength={4}
          placeholder="🙂" aria-label="Icon (an emoji)" />
        <input className="journal-title" value={page.title} onChange={edit('title')} placeholder="Untitled"
          aria-label="Title" autoFocus={!page.title} />
      </div>
      <div className="journal-meta">
        <input type="date" value={page.entry_date} aria-label="Date" required
          onChange={(e) => e.target.value && edit('entry_date', true)(e)} />
        <TagsInput tags={page.tags} onChange={(tags) => { setPage((p) => ({ ...p, tags })); save({ tags }, true) }} />
      </div>

      <Suspense fallback={<p className="muted loading">Opening the editor...</p>}>
        <Editor key={page.page_id} pageId={page.page_id} initialContent={page.content}
          onChange={(content) => save({ content })} onOpenMention={openMention} />
      </Suspense>

      {page.suggestions.length > 0 && (
        <aside className="suggestions" aria-label="Suggestions">
          {page.suggestions.map((s) => (
            <div key={s.key} className="suggestion">
              <span className="grow">
                <button type="button" className="mention mention-model" onClick={() => openModel(s.id)}>@{s.name}</button>
                {' '}{s.label}?
              </span>
              <button type="button" className="secondary" onClick={() => answer(s, true)}>Yes</button>
              <button type="button" className="plain" onClick={() => answer(s, false)}>Not now</button>
            </div>
          ))}
        </aside>
      )}

      {(page.links.length > 0 || page.mentioned_in.length > 0) && (
        <footer className="journal-links">
          {page.links.length > 0 && (
            <div>
              <h4 className="section-title">Mentions</h4>
              <div className="chips">
                {page.links.map((l) => (
                  <button key={`${l.kind}-${l.id}`} type="button" className={`mention mention-${l.kind}`}
                    disabled={!l.name} onClick={() => openMention(l.kind, l.id)}>@{l.name ?? 'deleted'}</button>
                ))}
              </div>
            </div>
          )}
          {page.mentioned_in.length > 0 && (
            <div>
              <h4 className="section-title">Mentioned in</h4>
              <ul className="list compact">
                {page.mentioned_in.map((p) => (
                  <li key={p.page_id}><Link to={`/journal/${p.page_id}`}>{p.icon} {p.title || 'Untitled'}</Link>
                    <span className="muted small">{shortDate(p.entry_date)}</span></li>
                ))}
              </ul>
            </div>
          )}
        </footer>
      )}
    </article>
  )
}
