import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { JournalIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import { PageRow, useNewPage } from './JournalList.jsx'
import TodoList from './TodoList.jsx'

const today = () => new Date().toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })

// The journal on the Home page: start today's entry, open to-dos, and the latest few pages.
export default function JournalHome() {
  const { refreshKey } = useApp()
  const newPage = useNewPage()
  const [pages, setPages] = useState(null)
  useEffect(() => { api.listPages({ limit: 3 }).then(setPages).catch(() => setPages([])) }, [refreshKey])

  return (
    <section className="card home-card" aria-labelledby="home-journal">
      <h2 id="home-journal" className="home-card-title"><JournalIcon size={20} /> Journal
        <Link to="/journal" className="small">All pages</Link></h2>
      <button type="button" className="secondary" onClick={() => newPage({ title: today() })}>
        Write today's entry
      </button>
      <TodoList limit={5} />
      {pages?.length > 0 && (
        <>
          <h3 className="section-title home-journal-title">Latest pages</h3>
          <ul className="list journal-list">{pages.map((p) => <PageRow key={p.page_id} page={p} />)}</ul>
        </>
      )}
    </section>
  )
}
