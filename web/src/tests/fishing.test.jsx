// Fishing's pages and panels (modules/fishing) drawn with the API faked (answers shaped like api/app/fishing*.py's):
// the dashboard with a trip on the water, the trip list and its filters, spots with finding boat ramps, the species
// page and its rules editor (the app ships no rules), the tackle box, stats; a trip's panel (conditions, catches with
// warnings, end it), a past trip, a catch (saved with its warnings shown); Home's tiles. No React warnings.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { FishingTiles } from '../modules/fishing/HomeTiles.jsx'
import { CatchPanel, NewTripPanel, TripPanel } from '../modules/fishing/FishingPanels.jsx'
import { SpeciesPanel, SpeciesView } from '../modules/fishing/FishingSpecies.jsx'
import { SpotPanel, SpotsView } from '../modules/fishing/FishingSpots.jsx'
import { StatsView } from '../modules/fishing/FishingStats.jsx'
import { LurePanel, TackleView } from '../modules/fishing/FishingTackle.jsx'
import { Dashboard, TripsView } from '../modules/fishing/FishingViews.jsx'

vi.mock('../modules/fishing/CatchPhotos.jsx', () => ({ CatchPhotos: ({ catchId, photos }) => <p>Photos of {catchId}: {photos.length}</p> }))
vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  const names = ['fishingSettings', 'saveFishingSettings', 'fishingSummary', 'fishingTrips', 'fishingTrip', 'addFishingTrip', 'updateFishingTrip', 'deleteFishingTrip',
    'endFishingTrip', 'addFishingCatch', 'updateFishingCatch', 'deleteFishingCatch', 'fishingSpecies', 'addFishingSpecies', 'updateFishingSpecies',
    'deleteFishingSpecies', 'fishingSpots', 'fishingSpot', 'addFishingSpot', 'updateFishingSpot', 'fishingLures', 'addFishingLure', 'updateFishingLure',
    'fishingStats', 'fishingOsmNear', 'fishingOsmImport', 'listGear']
  return { ...real, api: { ...real.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } }
})

const OPEN = { trip_id: 3, started_at: '2026-11-17T05:30:00+10:00', ended_at: null, hours: null, spot_id: 1, spot_name: 'Wellington Point', platform: 'shore',
  target: 'flathead', catches: 2, kept: 1, species: ['Dusky flathead'], best: { species: 'Dusky flathead', length_cm: 52 }, rating: null }
const DONE = { ...OPEN, trip_id: 2, ended_at: '2026-11-14T09:30:00+10:00', started_at: '2026-11-14T05:30:00+10:00', hours: 4, rating: 4, catches: 0, kept: 0, species: [], best: null }
const SUMMARY = { trips: 12, catches: 41, species: 6, hours: 38.5, this_year: { trips: 9, catches: 30 }, last_trip: OPEN, open_trip: OPEN,
  personal_bests: [{ species: 'Dusky flathead', length_cm: 62, weight_kg: 2.1, caught_at: '2026-10-01T06:00:00+10:00', catch_id: 5, trip_id: 3 }],
  alerts: [{ kind: 'sip', text: 'Stocked Impoundment Permit is due in 12 days', due: '2026-11-30' }], recent: [OPEN, DONE] }
const CATCHES = [
  { catch_id: 5, trip_id: 3, species_id: 1, species: null, species_name: 'Dusky flathead', caught_at: '2026-11-17T06:10:00+10:00', length_cm: 52, weight_kg: null, fate: 'kept',
    lure_id: 1, bait: null, lure_name: 'Zerek Shrimp', method: 'Casting', depth_m: null, lat: null, lon: null, notes: null, photos: [{ photo_id: 1, url: '/api/fishing/photos/1' }],
    warnings: ['Dusky flathead: 52 cm is over the maximum of 50 cm as you typed it on 3 Nov 2026 - check the official rules.'] },
  { catch_id: 6, trip_id: 3, species_id: null, species: 'Bream', species_name: 'Bream', caught_at: null, length_cm: null, weight_kg: null, fate: 'released', lure_id: null, bait: 'prawn',
    lure_name: 'prawn', method: null, depth_m: null, lat: null, lon: null, notes: null, photos: [], warnings: [] }]
const TRIP = { ...OPEN, companions: 'Sam', notes: 'Windy.', conditions: { moon_phase: 'Full moon', moon_pct: 99, wind_kmh: 14, tide: [{ time: '2026-11-17T06:10', kind: 'high' }] },
  catches: CATCHES, fish_per_hour: null, prev_id: 2, next_id: null }
const SPECIES = [
  { species_id: 1, name: 'Dusky flathead', sci_name: 'Platycephalus fuscus', water: 'estuary', min_cm: 40, max_cm: 50, bag: 5, closed_from: '08-01', closed_to: '08-31', no_take: false,
    rules_checked_on: '2026-11-03', notes: null, caught: 3, kept: 1, best_cm: 62, last_on: '2026-11-17' },
  { species_id: 2, name: 'Snapper', sci_name: null, water: 'salt', min_cm: null, max_cm: null, bag: null, closed_from: null, closed_to: null, no_take: false,
    rules_checked_on: null, notes: null, caught: 0, kept: 0, best_cm: null, last_on: null }]
const LURES = [{ lure_id: 1, name: 'Zerek Shrimp', kind: 'soft plastic', brand: 'Zerek', colour: 'Clear', size: '3.5"', qty: 4, retired: false, notes: null, catches: 5, species: ['Dusky flathead'] },
  { lure_id: 2, name: 'Old spinner', kind: 'lure', brand: null, colour: null, size: null, qty: null, retired: true, notes: null, catches: 1, species: ['Bream'] }]
const SPOT = { spot_id: 1, name: 'Wellington Point', place: 'Moreton Bay', water: 'salt', kind: 'Jetty', lat: -27.46, lon: 153.24, sip_needed: false, osm: null, notes: null,
  trips: 4, catches: 9, last_on: '2026-11-17', fish_per_hour: 0.8, trip_list: [OPEN], species_caught: [{ species: 'Dusky flathead', catches: 3 }] }
const STATS = { year: null, totals: { trips: 12, catches: 41, kept: 10, released: 31, hours: 38.5, blanks: 2 },
  by_month: Array.from({ length: 24 }, (_, i) => ({ month: `${2025 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}`, trips: 1, catches: i % 4 })),
  by_species: [{ species: 'Dusky flathead', catches: 3, kept: 1, best_cm: 62, avg_cm: 48 }],
  seasons: [{ species: 'Dusky flathead', months: [0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 1, 0] }], by_hour: Array.from({ length: 24 }, (_, h) => (h === 6 ? 5 : 0)),
  by_moon: [{ phase: 'Full moon', catches: 6, trips: 2 }], by_tide: [{ stage: 'rising', catches: 4 }, { stage: 'high', catches: 1 }, { stage: 'falling', catches: 0 }, { stage: 'low', catches: 0 }],
  top_lures: [{ lure_id: 1, name: 'Zerek Shrimp', catches: 5 }], top_spots: [{ spot_id: 1, name: 'Wellington Point', catches: 9, fish_per_hour: 0.8 }], length_trend: [] }
const SETTINGS = { home_lat: -27.47, home_lon: 153.02, sip_until: null, boat_rego_until: null, rules_url: 'https://example.test/rules', updated_at: '2026-11-01T00:00:00Z' }

let app
let errors
const draw = (ui) => render(<MemoryRouter><AppContext.Provider value={app}>{ui}</AppContext.Provider></MemoryRouter>)

beforeEach(() => {
  app = { refreshKey: 0, changed: vi.fn(), showToast: vi.fn(), openPanel: vi.fn(), openThing: vi.fn() }
  errors = vi.spyOn(console, 'error')
  api.fishingSettings.mockResolvedValue(SETTINGS)
  api.fishingSummary.mockResolvedValue(SUMMARY)
  api.fishingTrips.mockResolvedValue([OPEN, DONE])
  api.fishingTrip.mockResolvedValue(TRIP)
  api.fishingSpecies.mockResolvedValue(SPECIES)
  api.fishingSpots.mockResolvedValue([SPOT, { ...SPOT, spot_id: 2, name: 'Somerset Dam', lat: null, lon: null, kind: 'Dam', water: 'fresh', sip_needed: true, trips: 0, catches: 0, last_on: null, fish_per_hour: null }])
  api.fishingSpot.mockResolvedValue(SPOT)
  api.fishingLures.mockResolvedValue(LURES)
  api.fishingStats.mockResolvedValue(STATS)
  api.listGear.mockResolvedValue([])
})
afterEach(() => {
  expect(errors).not.toHaveBeenCalled()
  cleanup()
  vi.clearAllMocks()
  errors.mockRestore()
})

describe('fishing pages', () => {
  it('shows the dashboard: the trip on the water, the numbers, the permit reminder, the personal bests', async () => {
    draw(<Dashboard />)
    expect(await screen.findByText('41')).toBeTruthy()
    expect(screen.getByText(/You are on the water: Wellington Point/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Back to the water' }).getAttribute('href')).toBe('/fishing/live')
    expect(screen.getByRole('link', { name: 'Go fishing' }).getAttribute('href')).toBe('/fishing/live')
    expect(screen.getByText(/Stocked Impoundment Permit is due in 12 days/)).toBeTruthy()
    expect(screen.getByText('62 cm')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Log a past trip' }))
    expect(app.openPanel).toHaveBeenCalledWith('fishingnewtrip', {})
    fireEvent.click(screen.getByText('Dusky flathead', { selector: '.item-title' }))
    expect(app.openPanel).toHaveBeenCalledWith('fishingcatch', { id: 5, tripId: 3 })
  })

  it('an empty log says how to start and points at the rules', async () => {
    api.fishingSummary.mockResolvedValue({ ...SUMMARY, trips: 0, catches: 0, species: 0, hours: 0, last_trip: null, open_trip: null, personal_bests: [], alerts: [], recent: [] })
    draw(<Dashboard />)
    expect(await screen.findByText('Start your fishing log')).toBeTruthy()
    expect(screen.getByText(/the app ships none/)).toBeTruthy()
  })

  it('lists trips and filters them through the API; a blank trip says so', async () => {
    draw(<TripsView />)
    expect(await screen.findByText('on the water')).toBeTruthy()
    expect(screen.getByText('Blank')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search trips'), { target: { value: 'flathead' } })
    await waitFor(() => expect(api.fishingTrips).toHaveBeenLastCalledWith({ spot_id: '', year: '', q: 'flathead' }))
    fireEvent.change(screen.getByLabelText('Spot'), { target: { value: '1' } })
    await waitFor(() => expect(api.fishingTrips).toHaveBeenLastCalledWith({ spot_id: '1', year: '', q: 'flathead' }))
  })

  it('shows spots with a map link only where there is a position', async () => {
    draw(<SpotsView />)
    expect(await screen.findByText('Somerset Dam')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: /on the map/ })).toHaveLength(1)
    expect(screen.getByText('permit needed')).toBeTruthy()
    expect(screen.getByText('0.8 fish an hour')).toBeTruthy()
  })

  it('finds boat ramps near home and adds one', async () => {
    api.fishingOsmNear.mockResolvedValue([{ osm: 'node/9', name: 'Stand-in Ramp', kind: 'Boat ramp', lat: -27.4, lon: 153.4, already: null }])
    api.fishingOsmImport.mockResolvedValue({ spot_id: 7 })
    draw(<SpotsView />)
    fireEvent.click(await screen.findByRole('button', { name: 'Find boat ramps and spots near...' }))
    const home = await screen.findByRole('button', { name: 'My home' })
    await waitFor(() => expect(home.disabled).toBe(false))
    fireEvent.click(home)
    fireEvent.click(await screen.findByRole('button', { name: 'Add' }))
    await waitFor(() => expect(app.openPanel).toHaveBeenCalledWith('fishingspot', { id: 7 }))
    expect(api.fishingOsmNear).toHaveBeenCalledWith({ lat: '-27.47000', lon: '153.02000', km: '20', what: 'ramps' })
    expect(api.fishingOsmImport).toHaveBeenCalledWith('node/9')
  })

  it('the species page says the app ships no rules, links the official page and shows YOUR rules and counts', async () => {
    draw(<SpeciesView />)
    expect(await screen.findByText(/The app ships no fishing rules/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Official fishing rules/ }).getAttribute('href')).toBe('https://example.test/rules')
    expect(await screen.findByText(/min 40 cm · max 50 cm · bag 5 · closed 1 Aug - 31 Aug \(checked on/)).toBeTruthy()
    expect(screen.getByText('no rules typed yet')).toBeTruthy()
    expect(screen.getByText('best 62 cm')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'With rules' }))
    expect(screen.queryByText('Snapper')).toBeNull()
  })

  it('the tackle box lists lures with what they caught, hides the lost ones, and has the gear below', async () => {
    draw(<TackleView />)
    expect(await screen.findByText('Zerek Shrimp')).toBeTruthy()
    expect(screen.getByText(/caught Dusky flathead/)).toBeTruthy()
    expect(screen.queryByText('Old spinner')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Show lost/ }))
    expect(screen.getByText('Old spinner')).toBeTruthy()
    expect(await screen.findByText('No gear yet')).toBeTruthy()
    expect(api.listGear).toHaveBeenCalledWith('fishing')
  })

  it('shows stats: the totals, a seasons grid, the moon, the tide, and the settings', async () => {
    draw(<StatsView />)
    expect(await screen.findByText('Totals')).toBeTruthy()
    expect(screen.getByText('When each species bites')).toBeTruthy()
    expect(screen.getAllByText('6 fish · 2 trips').length).toBeGreaterThan(0)
    expect(screen.getByText('Your fishing settings')).toBeTruthy()
    fireEvent.click(await screen.findByRole('button', { name: '2026' }))
    await waitFor(() => expect(api.fishingStats).toHaveBeenLastCalledWith({ year: '2026', species_id: '' }))
  })

  it("Home's tiles: back to the water, the trips, the last trip, the biggest fish; nothing before the first trip", async () => {
    draw(<FishingTiles />)
    expect(await screen.findByText('Back to the water')).toBeTruthy()
    expect(screen.getByText('Fishing trips')).toBeTruthy()
    expect(screen.getByText('Biggest fish')).toBeTruthy()
    cleanup()
    api.fishingSummary.mockResolvedValue({ ...SUMMARY, trips: 0, open_trip: null })
    const { container } = draw(<FishingTiles />)
    await waitFor(() => expect(container.querySelector('.skeleton')).toBeNull())
    expect(container.textContent).toBe('')
  })
})

describe('fishing panels', () => {
  it('a trip: its facts, the conditions saved with it, catches with their warnings, and End trip', async () => {
    api.endFishingTrip.mockResolvedValue({ ...TRIP, ended_at: '2026-11-17T09:30:00+10:00', hours: 4 })
    draw(<TripPanel id={3} onClose={() => {}} />)
    expect(await screen.findByText('Conditions then')).toBeTruthy()
    expect(screen.getByText('Full moon')).toBeTruthy()
    expect(screen.getByText(/over the maximum of 50 cm as you typed it/)).toBeTruthy()
    expect(screen.getByText('Bream')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'End trip' }))
    await waitFor(() => expect(api.endFishingTrip).toHaveBeenCalledWith(3))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'End trip' })).toBeNull())
  })

  it('a trip adds a catch (the panel closes before the next opens)', async () => {
    const onClose = vi.fn()
    draw(<TripPanel id={3} onClose={onClose} />)
    fireEvent.click(await screen.findByRole('button', { name: '+ Add a catch' }))
    expect(onClose).toHaveBeenCalled()
    expect(app.openPanel).toHaveBeenCalledWith('fishingcatch', { tripId: 3 })
  })

  it('a past trip is saved with its two timestamps, then opened to add the fish', async () => {
    api.addFishingTrip.mockResolvedValue({ ...TRIP, trip_id: 8 })
    draw(<NewTripPanel day="2026-11-10" onClose={() => {}} />)
    await waitFor(() => expect(screen.getByLabelText(/^Spot/).value).toBe('1'))
    expect(screen.getByLabelText(/^Date/).value).toBe('2026-11-10')
    fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'bream' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save trip' }))
    await waitFor(() => expect(app.openPanel).toHaveBeenCalledWith('fishingtrip', { id: 8 }))
    const body = api.addFishingTrip.mock.calls[0][0]
    expect(body).toMatchObject({ spot_id: 1, platform: 'shore', target: 'bream' })
    expect(new Date(body.started_at).toLocaleString('en-CA', { hour12: false })).toMatch(/2026-11-10, 06:00/)
    expect(new Date(body.ended_at) > new Date(body.started_at)).toBe(true)
  })

  it('a new catch saves the species as a number, shows the rule warnings, and goes back to the trip', async () => {
    api.addFishingCatch.mockResolvedValue({ ...CATCHES[0], catch_id: 9, warnings: ['Dusky flathead: no more than 5 as you typed it - check the official rules.'] })
    const onClose = vi.fn()
    draw(<CatchPanel tripId={3} onClose={onClose} />)
    fireEvent.change(await screen.findByLabelText(/^Species/), { target: { value: '1' } })
    expect(screen.getByText(/Your rules for Dusky flathead: min 40 cm/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText(/^Length/), { target: { value: '45.5' } })
    fireEvent.change(screen.getByLabelText(/^What happened/), { target: { value: 'kept' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log the catch' }))
    expect(await screen.findByText(/no more than 5 as you typed it/)).toBeTruthy()
    const [trip, body] = api.addFishingCatch.mock.calls[0]
    expect(trip).toBe(3)
    expect(body).toMatchObject({ species_id: 1, length_cm: 45.5, fate: 'kept', lure_id: 1 })      // (the lure repeats the last catch's)
    fireEvent.click(screen.getByRole('button', { name: 'Back to the trip' }))
    expect(onClose).toHaveBeenCalled()
    expect(app.openPanel).toHaveBeenCalledWith('fishingtrip', { id: 3 })
  })

  it('a catch with no warnings goes straight back; photos show', async () => {
    api.updateFishingCatch.mockResolvedValue({ ...CATCHES[1], warnings: [] })
    draw(<CatchPanel id={6} tripId={3} onClose={() => {}} />)
    expect(await screen.findByText('Photos of 6: 0')).toBeTruthy()
    fireEvent.change(screen.getByLabelText(/^Length/), { target: { value: '28' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(app.openPanel).toHaveBeenCalledWith('fishingtrip', { id: 3 }))
    expect(api.updateFishingCatch.mock.calls[0][1]).toMatchObject({ length_cm: 28, species: 'Bream', species_id: null })
  })

  it('the rules editor: the closed season is sent as MM-DD, no take as a yes / no, and the app says it ships none', async () => {
    api.updateFishingSpecies.mockResolvedValue(SPECIES[0])
    draw(<SpeciesPanel id={1} onClose={() => {}} />)
    expect(await screen.findByText(/The app ships none/)).toBeTruthy()
    expect(screen.getByLabelText(/^Minimum size/).value).toBe('40')
    fireEvent.change(screen.getByLabelText(/^Maximum size/), { target: { value: '60' } })
    fireEvent.change(screen.getByLabelText(/^Closed season from: month/), { target: { value: '6' } })
    fireEvent.change(screen.getAllByLabelText('day')[0], { target: { value: '15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.updateFishingSpecies).toHaveBeenCalled())
    expect(api.updateFishingSpecies.mock.calls[0][0]).toBe(1)
    expect(api.updateFishingSpecies.mock.calls[0][1]).toMatchObject({ min_cm: 40, max_cm: 60, closed_from: '06-15', closed_to: '08-31', no_take: false, bag: 5 })
  })

  it('half a closed season is refused with a message, not sent', async () => {
    draw(<SpeciesPanel id={2} onClose={() => {}} />)
    fireEvent.change(await screen.findByLabelText(/^Closed season from: month/), { target: { value: '6' } })
    fireEvent.change(screen.getAllByLabelText('day')[0], { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Give both ends of the closed season, or neither.')).toBeTruthy()
    expect(api.updateFishingSpecies).not.toHaveBeenCalled()
  })

  it('a spot lists its trips and fish; a lure saves with its kind', async () => {
    draw(<SpotPanel id={1} onClose={() => {}} />)
    expect(await screen.findByText('Caught here')).toBeTruthy()
    expect(screen.getByText(/Dusky flathead ×3/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Log a trip here' })).toBeTruthy()
    cleanup()
    api.addFishingLure.mockResolvedValue({ lure_id: 3 })
    draw(<LurePanel onClose={() => {}} />)
    fireEvent.change(await screen.findByLabelText(/^Name/), { target: { value: 'Live yabby' } })
    fireEvent.change(screen.getByLabelText(/^Kind/), { target: { value: 'live bait' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.addFishingLure).toHaveBeenCalled())
    expect(api.addFishingLure.mock.calls[0][0]).toMatchObject({ name: 'Live yabby', kind: 'live bait', retired: false })
  })
})
