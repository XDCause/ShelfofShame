import { SuitcaseIcon } from '../../components/icons.jsx'
import EmptyState from '../../core/EmptyState.jsx'

// Travel: a placeholder for now - just the reminder in the sidebar (underConstruction puts a
// spanner after its name). Trips, plans and places come later.
function TravelPage() {
  return (
    <section className="page">
      <EmptyState Icon={SuitcaseIcon} title="Travel">
        Under construction. This is where trips will live - plans, places and memories.
      </EmptyState>
    </section>
  )
}

export default {
  id: 'travel',
  name: 'Travel',
  what: 'Trips and places (under construction)',
  Icon: SuitcaseIcon,
  underConstruction: true,
  pages: [
    { path: 'trips', label: 'Trips', Icon: SuitcaseIcon, render: () => <TravelPage /> },
  ],
}
