import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { JournalIcon } from '../../components/icons.jsx'
import { useApp } from '../app-context.js'
import { PageRow, useNewPage } from './JournalList.jsx'

const today = () => new Date().toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })

// The journal on the Home page: start today's entry, and the latest few pages.
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
      {pages?.length > 0 && <ul className="list journal-list home-journal">{pages.map((p) => <PageRow key={p.page_id} page={p} />)}</ul>}
    </section>
  )
}
