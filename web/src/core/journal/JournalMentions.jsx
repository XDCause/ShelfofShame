import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { PageRow, useNewPage } from './JournalList.jsx'

// For a model's or supply's panel: the journal pages that @mention it, and a button to start one
// that already mentions it. Opening a page closes the panel (onLeave).
export default function JournalMentions({ kind, id, name, onLeave }) {
  const newPage = useNewPage()
  const [pages, setPages] = useState(null)
  useEffect(() => { api.listPages({ mention: `${kind}:${id}` }).then(setPages).catch(() => setPages([])) }, [kind, id])

  const write = async () => {
    await newPage({
      content: [{ type: 'paragraph', content: [
        { type: 'mention', props: { kind, ref: String(id), label: name } }, { type: 'text', text: ' ', styles: {} }] }],
    })
    onLeave()
  }

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">In the journal</h4>
        <button type="button" className="plain small" onClick={write}>+ Write about it</button>
      </div>
      {pages?.length > 0
        ? <ul className="list journal-list">{pages.map((p) => <PageRow key={p.page_id} page={p} onClick={onLeave} />)}</ul>
        : <p className="muted small">No pages mention it yet. Type @ in a journal page to link one.</p>}
    </section>
  )
}
