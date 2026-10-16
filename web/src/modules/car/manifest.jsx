import { CarIcon } from '../../components/icons.jsx'
import EmptyState from '../../core/EmptyState.jsx'

// Building my car: a modified Toyota 86. A placeholder for now - just the reminder in the sidebar
// (underConstruction puts a spanner after its name). The build list, parts and costs come later.
function CarPage() {
  return (
    <section className="page">
      <EmptyState Icon={CarIcon} title="Modified Toyota 86">
        Under construction. This is where the build will live - parts, mods, costs and progress.
      </EmptyState>
    </section>
  )
}

export default {
  id: 'car',
  name: 'Building my car',
  what: 'Modified Toyota 86 (under construction)',
  Icon: CarIcon,
  underConstruction: true,
  pages: [
    { path: 'build', label: 'The build', Icon: CarIcon, render: () => <CarPage /> },
  ],
}
