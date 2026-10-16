import { CrosshairIcon } from '../../components/icons.jsx'
import EmptyState from '../../core/EmptyState.jsx'

// Precision shooting: a placeholder for now - just the reminder in the sidebar (underConstruction puts
// a spanner after its name). Sessions, scores and gear come later.
function ShootingPage() {
  return (
    <section className="page">
      <EmptyState Icon={CrosshairIcon} title="Precision shooting">
        Under construction. This is where your shooting will live - range sessions, scores and gear.
      </EmptyState>
    </section>
  )
}

export default {
  id: 'shooting',
  name: 'Precision shooting',
  what: 'Range sessions and scores (under construction)',
  Icon: CrosshairIcon,
  underConstruction: true,
  pages: [
    { path: 'sessions', label: 'Sessions', Icon: CrosshairIcon, render: () => <ShootingPage /> },
  ],
}
