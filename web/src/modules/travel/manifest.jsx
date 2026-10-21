import { BoxIcon, CalendarIcon, SuitcaseIcon, TrophyIcon } from '../../components/icons.jsx'
import { TravelTiles, NextAdventure } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const BookingPanel = part(() => import('./TravelPanels.jsx'), 'BookingPanel')
const PlacePanel = part(() => import('./TravelPanels.jsx'), 'PlacePanel')
const Dashboard = part(() => import('./TravelViews.jsx'), 'Dashboard')
const PackingListsView = part(() => import('./TravelViews.jsx'), 'PackingListsView')
const PlacesView = part(() => import('./TravelViews.jsx'), 'PlacesView')
const TripsView = part(() => import('./TravelViews.jsx'), 'TripsView')
const TripPanel = part(() => import('./TripPanel.jsx'))

// Travel (api/app/travel.py, travel_trip.py): trips - ideas, coming up, on now, been - each with its bookings, a day-by-day
// plan, money (a budget; other currencies in AUD), packing (lists, your hobby gear), places (its stops and route) and a
// journal with photos; a map of everywhere you've been and want to go, countries and a bucket list. Trips show on the
// calendar (each day, flights, check-ins) and in the activity feed; @mention them in the journal.
export default {
  id: 'travel',
  name: 'Travel',
  // its colour (lagoon: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#2fa39a',
  banner: { scene: 'coast', seed: 2, time: 'dawn', extras: ['clouds'], tagline: 'Somewhere new is waiting.' },
  what: 'Trips: bookings, plans, budget, packing, places and memories',
  Icon: SuitcaseIcon,
  home: { Tiles: TravelTiles, Feature: NextAdventure },
  actions: [{ label: 'Plan a trip', Icon: SuitcaseIcon, run: (app) => app.openPanel('trip', {}) }],
  panels: { trip: TripPanel, tbooking: BookingPanel, tplace: PlacePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'trips', label: 'Trips', Icon: SuitcaseIcon, render: () => <TripsView /> },
    { path: 'places', label: 'Places', Icon: CalendarIcon, render: () => <PlacesView /> },
    { path: 'packing', label: 'Packing lists', Icon: BoxIcon, render: () => <PackingListsView /> },
  ],
}
