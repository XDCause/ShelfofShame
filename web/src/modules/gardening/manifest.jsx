import { SproutIcon } from '../../components/icons.jsx'
import EmptyState from '../../core/EmptyState.jsx'

// Gardening: a placeholder for now - just the reminder in the sidebar (underConstruction puts a spanner
// after its name). Plants, beds, sowing and harvests come later.
function GardeningPage() {
  return (
    <section className="page">
      <EmptyState Icon={SproutIcon} title="Gardening">
        Under construction. This is where your garden will live - plants, beds, what to sow and when, and harvests.
      </EmptyState>
    </section>
  )
}

export default {
  id: 'gardening',
  name: 'Gardening',
  what: 'Plants, beds and harvests (under construction)',
  Icon: SproutIcon,
  underConstruction: true,
  pages: [
    { path: 'garden', label: 'Garden', Icon: SproutIcon, render: () => <GardeningPage /> },
  ],
}
