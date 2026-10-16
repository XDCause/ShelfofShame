import { BootIcon } from '../../components/icons.jsx'
import EmptyState from '../../core/EmptyState.jsx'

// Hiking: a placeholder for now - just the reminder in the sidebar (underConstruction puts a spanner
// after its name). Hikes, trails and gear come later.
function HikingPage() {
  return (
    <section className="page">
      <EmptyState Icon={BootIcon} title="Hiking">
        Under construction. This is where your hiking will live - hikes, trails and gear.
      </EmptyState>
    </section>
  )
}

export default {
  id: 'hiking',
  name: 'Hiking',
  what: 'Hikes and trails (under construction)',
  Icon: BootIcon,
  underConstruction: true,
  pages: [
    { path: 'hikes', label: 'Hikes', Icon: BootIcon, render: () => <HikingPage /> },
  ],
}
