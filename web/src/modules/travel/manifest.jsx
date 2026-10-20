import { BoxIcon, CalendarIcon, SuitcaseIcon, TrophyIcon } from '../../components/icons.jsx'
import { BookingPanel, PlacePanel } from './TravelPanels.jsx'
import { Dashboard, PackingListsView, PlacesView, TravelTiles, TripsView } from './TravelViews.jsx'
import TripPanel from './TripPanel.jsx'

// Travel (api/app/travel.py, travel_trip.py): trips - ideas, coming up, on now, been - each with its bookings, a day-by-day
// plan, money (a budget; other currencies in AUD), packing (lists, your hobby gear), places (its stops and route) and a
// journal with photos; a map of everywhere you've been and want to go, countries and a bucket list. Trips show on the
// calendar (each day, flights, check-ins) and in the activity feed; @mention them in the journal.
export default {
  id: 'travel',
  name: 'Travel',
  what: 'Trips: bookings, plans, budget, packing, places and memories',
  Icon: SuitcaseIcon,
  home: { Tiles: TravelTiles },
  actions: [{ label: 'Plan a trip', Icon: SuitcaseIcon, run: (app) => app.openPanel('trip', {}) }],
  panels: { trip: TripPanel, tbooking: BookingPanel, tplace: PlacePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'trips', label: 'Trips', Icon: SuitcaseIcon, render: () => <TripsView /> },
    { path: 'places', label: 'Places', Icon: CalendarIcon, render: () => <PlacesView /> },
    { path: 'packing', label: 'Packing lists', Icon: BoxIcon, render: () => <PackingListsView /> },
  ],
}
