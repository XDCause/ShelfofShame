import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, isoDay, shortDate } from '../../api.js'
import { weatherText } from './JournalExtras.jsx'
import { moodOf } from './moods.js'

const ago = (days) => { const d = new Date(); d.setDate(d.getDate() - days); return isoDay(d) }

// Journal > Print / PDF: the pages between two days laid out to print, or to save as a PDF from the print window
// (Day One's PDF export and printed books, done by the browser). Only the controls at the top don't print.
export default function JournalPrint() {
  const [params, setParams] = useSearchParams()
  const start = params.get('start') || ago(30)
  const end = params.get('end') || isoDay(new Date())
  const notebook = params.get('notebook') || ''
  const secret = params.get('private') === 'true'
  const [pages, setPages] = useState(null)
  const [notebooks, setNotebooks] = useState([])
  const [error, setError] = useState('')
  useEffect(() => { api.notebooks().then(setNotebooks).catch(() => {}) }, [])
  useEffect(() => {
    setPages(null)
    setError('')
    api.exportPages({ start, end, notebook, private: secret || '' }).then(setPages).catch((e) => setError(e.message))
  }, [start, end, notebook, secret])
  const set = (key, value) => setParams((p) => { const n = new URLSearchParams(p); if (value) n.set(key, value); else n.delete(key); return n })

  return (
    <section className="page jx-print">
      <div className="jx-print-controls card">
        <Link to="/journal" className="plain">‹ Journal</Link>
        <label>From <input type="date" value={start} onChange={(e) => e.target.value && set('start', e.target.value)} /></label>
        <label>To <input type="date" value={end} onChange={(e) => e.target.value && set('end', e.target.value)} /></label>
        <select value={notebook} onChange={(e) => set('notebook', e.target.value)} aria-label="Notebook">
          <option value="">Every notebook</option>
          {notebooks.map((n) => <option key={n.notebook_id} value={n.notebook_id}>{n.name}</option>)}
        </select>
        <label className="pin"><input type="checkbox" checked={secret} onChange={(e) => set('private', e.target.checked ? 'true' : '')} /> Include private pages</label>
        <span className="grow" />
        <button type="button" className="primary" disabled={!pages?.length} onClick={() => window.print()}>Print or save as PDF</button>
      </div>
      {error && <p className="alert error">{error}</p>}
      {!pages && !error && <p className="muted loading">Loading...</p>}
      {pages?.length === 0 && <p className="empty card">No pages between {shortDate(start)} and {shortDate(end)}.</p>}
      {pages?.length > 0 && (
        <>
          <header className="jx-print-cover">
            <p className="jx-print-kicker">Off the Clock · Journal</p>
            <h1>{shortDate(start)} – {shortDate(end)}</h1>
            <p className="muted">{pages.length} page{pages.length === 1 ? '' : 's'}</p>
          </header>
          {pages.map((p) => <PrintedPage key={p.page_id} page={p} />)}
        </>
      )}
    </section>
  )
}

function PrintedPage({ page: p }) {
  const mood = moodOf(p.mood)
  const previews = Object.fromEntries(p.drawings.map((d) => [String(d.drawing_id), d.preview_url]))
  const board = p.kind === 'whiteboard' ? p.drawings.find((d) => d.board) : null
  return (
    <article className="jx-printed">
      <p className="jx-printed-meta">
        {new Date(`${p.entry_date}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        {mood && ` · ${mood.face} ${mood.label}${p.mood_words.length ? ` (${p.mood_words.join(', ')})` : ''}`}
        {p.place_name && ` · 📍 ${p.place_name}`}{p.weather && ` · ${weatherText(p.weather)}`}
      </p>
      <h2>{p.title || 'Untitled'}</h2>
      {p.tags.length > 0 && <p className="jx-printed-tags">{p.tags.map((t) => `#${t}`).join('  ')}</p>}
      {board?.preview_url ? <img className="jx-printed-img" src={board.preview_url} alt="The whiteboard" /> : <Blocks blocks={p.content} previews={previews} />}
    </article>
  )
}

// BlockNote's blocks as plain HTML (no editor: quick, and prints cleanly).
function Blocks({ blocks, previews }) {
  const out = []
  let list = null
  const flush = () => { if (list) { out.push(list.ordered ? <ol key={`l${out.length}`}>{list.items}</ol> : <ul key={`l${out.length}`}>{list.items}</ul>); list = null } }
  for (const b of blocks ?? []) {
    const kids = b.children?.length ? <Blocks blocks={b.children} previews={previews} /> : null
    if (!b.content?.length && !kids && !['image', 'drawing', 'table'].includes(b.type)) continue    // (a template's empty lines)
    if (['bulletListItem', 'numberedListItem', 'checkListItem', 'toggleListItem'].includes(b.type)) {
      const ordered = b.type === 'numberedListItem'
      if (list && list.ordered !== ordered) flush()
      list ??= { ordered, items: [] }
      list.items.push(
        <li key={b.id ?? list.items.length} className={b.type === 'checkListItem' ? 'jx-check' : undefined}>
          {b.type === 'checkListItem' && <span aria-hidden="true">{b.props?.checked ? '☑ ' : '☐ '}</span>}<Inline content={b.content} />{kids}
        </li>,
      )
      continue
    }
    flush()
    const key = b.id ?? out.length
    if (b.type === 'heading') {
      const H = `h${Math.min(6, (b.props?.level ?? 2) + 1)}`
      out.push(<H key={key}><Inline content={b.content} /></H>)
    } else if (b.type === 'quote') out.push(<blockquote key={key}><Inline content={b.content} /></blockquote>)
    else if (b.type === 'image' && b.props?.url) {
      out.push(<figure key={key}><img className="jx-printed-img" src={b.props.url} alt={b.props.caption || ''} />{b.props.caption && <figcaption>{b.props.caption}</figcaption>}</figure>)
    } else if (b.type === 'drawing' && previews[b.props?.drawingId]) {
      out.push(<img key={key} className="jx-printed-img" src={previews[b.props.drawingId]} alt="A sketch" />)
    } else if (b.type === 'codeBlock') out.push(<pre key={key}><Inline content={b.content} /></pre>)
    else if (b.type === 'table') {
      out.push(<table key={key} className="table compact"><tbody>{(b.content?.rows ?? []).map((r, i) => (
        <tr key={i}>{r.cells.map((c, j) => <td key={j}><Inline content={Array.isArray(c) ? c : c.content} /></td>)}</tr>
      ))}</tbody></table>)
    } else if (b.content?.length) out.push(<p key={key}><Inline content={b.content} /></p>)
    if (kids) out.push(<div key={`${key}k`} className="jx-printed-kids">{kids}</div>)
  }
  flush()
  return <>{out}</>
}

function Inline({ content }) {
  if (!Array.isArray(content)) return typeof content === 'string' ? content : null
  return content.map((c, i) => {
    if (c.type === 'mention') return <strong key={i}>@{c.props?.label}</strong>
    if (c.type === 'link') return <u key={i}><Inline content={c.content} /></u>
    let el = c.text ?? ''
    if (c.styles?.bold) el = <strong>{el}</strong>
    if (c.styles?.italic) el = <em>{el}</em>
    if (c.styles?.underline) el = <u>{el}</u>
    if (c.styles?.strike) el = <s>{el}</s>
    return <span key={i}>{el}</span>
  })
}
