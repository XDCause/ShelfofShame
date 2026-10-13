import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { JournalIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import { PageRow } from './JournalList.jsx'
import TodoList from './TodoList.jsx'

// The journal on the Home page: open to-dos and the latest few pages. ("Write today's entry"
// is in the hero at the top of Home.)
export default function JournalHome() {
  const { refreshKey } = useApp()
  const [pages, setPages] = useState(null)
  useEffect(() => { api.listPages({ limit: 3 }).then(setPages).catch(() => setPages([])) }, [refreshKey])

  return (
    <section className="card home-card" aria-labelledby="home-journal">
      <h2 id="home-journal" className="home-card-title"><JournalIcon size={20} /> Journal
        <Link to="/journal" className="small">All pages →</Link></h2>
      <TodoList limit={5} />
      {pages?.length > 0 ? (
        <>
          <h3 className="section-title home-journal-title">Latest pages</h3>
          <ul className="list journal-list">{pages.map((p) => <PageRow key={p.page_id} page={p} />)}</ul>
        </>
      ) : pages && <p className="muted small">No pages yet. "Write today's entry" starts one.</p>}
    </section>
  )
}
