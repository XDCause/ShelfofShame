// Scuba's pages and panels (modules/scuba) drawn with the API faked (answers shaped like api/app/scuba*.py's): the
// dashboard with the no-fly time, the logbook, sites, trips, life list, stats, gear with service, certs; a dive's panel
// (facts, sightings saved, edit) and logging a new dive filled in from the last one; Home's tiles. No React warnings.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { ScubaTiles } from '../modules/scuba/HomeTiles.jsx'
import { CertPanel, CertsView, GearView, ServicePanel } from '../modules/scuba/ScubaGear.jsx'
import { DivePanel, NewDivePanel } from '../modules/scuba/ScubaPanels.jsx'
import { SitePanel, SitesView } from '../modules/scuba/ScubaSites.jsx'
import { SpeciesView, StatsView } from '../modules/scuba/ScubaStats.jsx'
import { TripPanel, TripsView } from '../modules/scuba/ScubaTrips.jsx'
import { Dashboard, LogView } from '../modules/scuba/ScubaViews.jsx'

vi.mock('../modules/scuba/DiveProfile.jsx', () => ({ DiveProfile: ({ diveId, hasProfile }) => (hasProfile ? <p>Profile of {diveId}</p> : null) }))
vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  const names = ['scubaSettings', 'saveScubaSettings', 'scubaSummary', 'scubaDives', 'scubaDive', 'addScubaDive', 'updateScubaDive', 'deleteScubaDive',
    'saveScubaSightings', 'scubaSpecies', 'scubaSites', 'scubaSite', 'addScubaSite', 'scubaTrips', 'scubaTrip', 'scubaCerts', 'addScubaCert', 'scubaGear',
    'scubaGearService', 'addScubaService', 'scubaStats', 'scubaOsmNear', 'scubaOsmImport']
  return { ...real, api: { ...real.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } }
})

const brief = (over = {}) => ({ dive_id: 1, dive_no: 124, dived_on: '2026-11-14', time_in: '08:30:00', site_id: 1, site_name: 'Flinders Reef', trip_id: null,
  max_depth: 18.4, minutes: 52, water_temp: 24, gas_o2: 32, rating: 4, tags: ['reef'], has_profile: true, sac: 14.2, ...over })
const FULL = { ...brief(), avg_depth: 11.2, air_temp: 27, visibility_m: 20, current: 'light', entry: 'boat', tank_l: 12, start_bar: 200, end_bar: 70, weight_kg: 6,
  suit: '3 mm shorty', buddy: 'Sam', guide: null, operator: 'Moreton Dive', notes: 'Turtle at the cleaning station.', computer: null, import_key: null,
  trip_name: null, sightings: [{ species: 'Green turtle', how_many: 2, notes: null }], surface_interval_min: null, prev_id: 2, next_id: null }
const FUTURE = new Date(Date.now() + 5 * 3600 * 1000).toISOString()
const SUMMARY = { dives: 124, minutes: 5025, dives_logged: 4, deepest: 31.2, longest: 61, last_dive: brief(), next_no: 125, sites: 3, species: 5, this_year: 9,
  no_fly_until: FUTURE, alerts: [{ kind: 'service', text: 'Regulator: annual service is due in 12 days', due: '2026-12-01' }], recent: [brief(), brief({ dive_id: 2, dive_no: 123 })] }
const SITE = { site_id: 1, name: 'Flinders Reef', place: 'Moreton Island', country: 'Australia', lat: -27.0, lon: 153.5, kind: 'Reef', entry: 'boat',
  depth_min: 5, depth_max: 24, osm: null, notes: null, dives: 3, last_on: '2026-11-14', deepest: 18.4, recent_dives: [brief()], species_seen: [{ species: 'Green turtle', dives: 2 }],
  avg_temp: 23.5, avg_vis: 18 }
const TRIP = { trip_id: 1, name: 'Easter at Julian Rocks', place: 'Byron Bay', operator: 'Dive Centre', start_on: '2026-04-03', end_on: '2026-04-06', notes: null,
  dives: 4, minutes: 180, deepest: 22, totals: { dives: 4, minutes: 180, deepest: 22, sites: 2 }, dive_list: [brief()] }
const GEAR = [{ gear_id: 7, name: 'Regulator', kind: 'Regulator', brand: 'Apeks', size: null, condition: 'Good', photo_url: null,
  last_service: { service_id: 1, done_on: '2025-12-01', what: 'Annual service', done_by: null, next_due: '2026-12-01' }, next_due: '2026-12-01', services: 1, dives_since_service: 12 },
{ gear_id: 8, name: 'Fins', kind: 'Fins', brand: null, size: null, condition: 'Good', photo_url: null, last_service: null, next_due: null, services: 0, dives_since_service: 124 }]
const STATS = { year: null, totals: { dives: 124, dives_logged: 4, minutes: 5025, hours: 83.8, avg_depth: 17, avg_minutes: 48, sites: 3, trips: 1, dive_days: 4, species: 5 },
  records: { deepest: brief({ max_depth: 31.2 }), longest: brief({ minutes: 61 }), coldest: brief({ water_temp: 19 }), warmest: brief({ water_temp: 28 }), best_vis: null },
  by_year: [{ year: 2025, dives: 3, minutes: 140 }, { year: 2026, dives: 4, minutes: 200 }],
  by_month: Array.from({ length: 24 }, (_, i) => ({ month: `${2025 + Math.floor((i + 0) / 12)}-${String((i % 12) + 1).padStart(2, '0')}`, dives: i % 3, minutes: 40 })),
  depth_bands: [{ band: '0-10', dives: 1 }, { band: '10-18', dives: 2 }, { band: '18-30', dives: 1 }, { band: '30-40', dives: 0 }, { band: '40+', dives: 0 }],
  sac_trend: [{ dive_id: 1, dived_on: '2026-11-01', sac: 15 }, { dive_id: 2, dived_on: '2026-11-14', sac: 14.2 }], top_sites: [{ site_id: 1, name: 'Flinders Reef', dives: 3 }],
  tags: [{ tag: 'reef', dives: 3 }], temps: [{ dived_on: '2026-11-01', water_temp: 23 }, { dived_on: '2026-11-14', water_temp: 24 }] }
const SETTINGS = { gas_o2: 21, tank_l: 12, start_bar: 200, sac_l_min: 20, gf_low: 40, gf_high: 85, ppo2_max: 1.4, dives_before: 120, minutes_before: 4800,
  medical_due: null, insurance_until: null, home_lat: null, home_lon: null }

let app
let errors
const draw = (ui) => render(<MemoryRouter><AppContext.Provider value={app}>{ui}</AppContext.Provider></MemoryRouter>)

beforeEach(() => {
  app = { refreshKey: 0, changed: vi.fn(), showToast: vi.fn(), openPanel: vi.fn(), openThing: vi.fn() }
  errors = vi.spyOn(console, 'error')
  api.scubaSettings.mockResolvedValue(SETTINGS)
  api.scubaSummary.mockResolvedValue(SUMMARY)
  api.scubaDives.mockResolvedValue([brief(), brief({ dive_id: 2, dive_no: 123, site_name: 'Wolf Rock', has_profile: false, gas_o2: 21 })])
  api.scubaDive.mockResolvedValue(FULL)
  api.scubaSpecies.mockResolvedValue([{ species: 'Green turtle', dives: 2, total: 3, first_on: '2026-04-04', last_on: '2026-11-14', first_dive_id: 1 }])
  api.scubaSites.mockResolvedValue([{ ...SITE }, { ...SITE, site_id: 2, name: 'Wolf Rock', lat: null, lon: null, dives: 0, last_on: null }])
  api.scubaSite.mockResolvedValue(SITE)
  api.scubaTrips.mockResolvedValue([TRIP])
  api.scubaTrip.mockResolvedValue(TRIP)
  api.scubaCerts.mockResolvedValue([{ cert_id: 1, agency: 'PADI', name: 'Open Water Diver', cert_no: '123', certified_on: '2019-03-02', instructor: 'Kim',
    expires_on: null, notes: null }])
  api.scubaGear.mockResolvedValue(GEAR)
  api.scubaGearService.mockResolvedValue([{ service_id: 1, gear_id: 7, done_on: '2025-12-01', what: 'Annual service', done_by: 'Dive shop', cost: 180, next_due: '2026-12-01', notes: null }])
  api.scubaStats.mockResolvedValue(STATS)
})
afterEach(() => {
  expect(errors).not.toHaveBeenCalled()
  cleanup()
  vi.clearAllMocks()
  errors.mockRestore()
})

describe('scuba pages', () => {
  it('shows the dashboard: the dives, the no-fly countdown, what is due, the last dives', async () => {
    draw(<Dashboard />)
    expect(await screen.findByText('124')).toBeTruthy()
    expect(screen.getByText(/83.8 h underwater/)).toBeTruthy()
    expect(screen.getByText(/No-fly time: 4 h|No-fly time: 5 h/)).toBeTruthy()
    expect(screen.getByText(/Regulator: annual service is due in 12 days/)).toBeTruthy()
    expect(screen.getAllByText('Flinders Reef').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Log a dive' }))
    expect(app.openPanel).toHaveBeenCalledWith('scubanewdive', {})
  })

  it('the dashboard of an empty logbook says how to start; no no-fly time before a dive', async () => {
    api.scubaSummary.mockResolvedValue({ ...SUMMARY, dives: 0, minutes: 0, last_dive: null, recent: [], alerts: [], no_fly_until: null, this_year: 0 })
    draw(<Dashboard />)
    expect(await screen.findByText('Start your logbook')).toBeTruthy()
    expect(screen.queryByLabelText('No-fly time')).toBeNull()
  })

  it('lists dives and searches them through the API', async () => {
    draw(<LogView />)
    expect(await screen.findByText('Wolf Rock')).toBeTruthy()
    expect(screen.getByText('EAN32')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search dives'), { target: { value: 'turtle' } })
    await waitFor(() => expect(api.scubaDives).toHaveBeenLastCalledWith({ site_id: '', year: '', q: 'turtle' }))
    fireEvent.click(screen.getAllByRole('button', { name: /Flinders Reef/ })[0])
    expect(app.openPanel).toHaveBeenCalledWith('scubadive', { id: 1 })
  })

  it('shows sites with a map link only where there is a position, trips, the life list and certs', async () => {
    draw(<SitesView />)
    expect(await screen.findByText('Wolf Rock')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: /on the map/ })).toHaveLength(1)
    cleanup()
    draw(<TripsView />)
    expect(await screen.findByText('Easter at Julian Rocks')).toBeTruthy()
    cleanup()
    draw(<SpeciesView />)
    expect(await screen.findByText('Green turtle')).toBeTruthy()
    cleanup()
    draw(<CertsView />)
    expect(await screen.findByText('Open Water Diver')).toBeTruthy()
  })

  it('finds dive sites near a place and adds one', async () => {
    api.scubaOsmNear.mockResolvedValue([{ osm: 'node/9', name: 'Stand-in Wreck', lat: -27.4, lon: 153.4, km: 12.3 }])
    api.scubaOsmImport.mockResolvedValue({ site_id: 5 })
    api.scubaSettings.mockResolvedValue({ ...SETTINGS, home_lat: -27.47, home_lon: 153.02 })
    draw(<SitesView />)
    fireEvent.click(await screen.findByRole('button', { name: 'Find dive sites near...' }))
    const home = await screen.findByRole('button', { name: 'My home' })
    await waitFor(() => expect(home.disabled).toBe(false))
    fireEvent.click(home)
    fireEvent.click(await screen.findByRole('button', { name: 'Add' }))
    await waitFor(() => expect(app.openPanel).toHaveBeenCalledWith('scubasite', { id: 5 }))
    expect(api.scubaOsmNear).toHaveBeenCalledWith({ lat: '-27.47000', lon: '153.02000', km: '30' })
    expect(api.scubaOsmImport).toHaveBeenCalledWith('node/9')
  })

  it('shows stats, records and the settings', async () => {
    draw(<StatsView />)
    expect(await screen.findByText('Records')).toBeTruthy()
    expect(screen.getByText('31.2 m')).toBeTruthy()
    expect(screen.getByText('Your diving settings')).toBeTruthy()
    fireEvent.click(await screen.findByRole('button', { name: '2025' }))
    await waitFor(() => expect(api.scubaStats).toHaveBeenLastCalledWith({ year: '2025' }))
  })

  it('shows gear with when it is next due and opens its service log', async () => {
    draw(<GearView />)
    expect((await screen.findAllByText('Regulator')).length).toBeGreaterThan(0)
    expect(screen.getByText(/12 dives since/)).toBeTruthy()
    expect(screen.getByText('Never serviced')).toBeTruthy()
    fireEvent.click(screen.getByText('Regulator', { selector: '.item-title' }))
    expect(app.openPanel).toHaveBeenCalledWith('scubaservice', { gearId: 7 })
  })

  it("Home's tiles: the dives, the last dive and the no-fly time; nothing before the first dive", async () => {
    draw(<ScubaTiles />)
    expect(await screen.findByText('Dives')).toBeTruthy()
    expect(screen.getByText('Last dive')).toBeTruthy()
    expect(screen.getByText('No-fly time left')).toBeTruthy()
    cleanup()
    api.scubaSummary.mockResolvedValue({ ...SUMMARY, dives: 0 })
    const { container } = draw(<ScubaTiles />)
    await waitFor(() => expect(container.querySelector('.skeleton')).toBeNull())
    expect(container.textContent).toBe('')
  })
})

describe('scuba panels', () => {
  it('a dive: its facts, the profile, the sightings saved, and the older dive one step back', async () => {
    api.saveScubaSightings.mockResolvedValue([{ species: 'Green turtle', how_many: 2, notes: null }, { species: 'Manta ray', how_many: 1, notes: null }])
    draw(<DivePanel id={1} onClose={() => {}} />)
    expect(await screen.findByText('Dive 124 · Flinders Reef')).toBeTruthy()
    expect(screen.getByText('14.2 L/min')).toBeTruthy()
    expect(screen.getByText('130 bar')).toBeTruthy()
    expect(screen.getByText('Profile of 1')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '+ Add a sighting' }))
    fireEvent.change(screen.getByLabelText('Species 2'), { target: { value: 'Manta ray' } })
    fireEvent.change(screen.getByLabelText('How many 2'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save sightings' }))
    await waitFor(() => expect(api.saveScubaSightings).toHaveBeenCalledWith(1, [
      { species: 'Green turtle', how_many: 2, notes: null }, { species: 'Manta ray', how_many: 1, notes: null }]))
    api.scubaDive.mockResolvedValue({ ...FULL, dive_id: 2, dive_no: 123, prev_id: null, next_id: 1, site_name: 'Wolf Rock' })
    fireEvent.click(screen.getByRole('button', { name: '← Older' }))
    expect(await screen.findByText('Dive 123 · Wolf Rock')).toBeTruthy()
  })

  it('editing a dive sends the changes with tags as a list', async () => {
    api.updateScubaDive.mockResolvedValue({ ...FULL, buddy: 'Alex' })
    draw(<DivePanel id={1} onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.change(await screen.findByLabelText('Buddy'), { target: { value: 'Alex' } })
    fireEvent.change(screen.getByLabelText(/^Tags/), { target: { value: 'night, Wreck' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.updateScubaDive).toHaveBeenCalled())
    const [id, body] = api.updateScubaDive.mock.calls[0]
    expect(id).toBe(1)
    expect(body).toMatchObject({ buddy: 'Alex', tags: ['night', 'wreck'], site_id: 1, rating: 4, gas_o2: 32 })
    expect(app.changed).toHaveBeenCalled()
  })

  it('a new dive starts from your settings and the last dive, then opens the saved one', async () => {
    api.addScubaDive.mockResolvedValue({ ...FULL, dive_id: 9, dive_no: 125 })
    const onClose = vi.fn()
    draw(<NewDivePanel onClose={onClose} />)
    await waitFor(() => expect(screen.getByLabelText(/^Site/).value).toBe('1'))
    expect(screen.getByLabelText(/^Oxygen in the gas/).value).toBe('32')      // the last dive's gas
    expect(screen.getByLabelText('Start (bar)').value).toBe('200')               // the settings'
    expect(screen.getByLabelText('Buddy').value).toBe('Sam')
    fireEvent.change(screen.getByLabelText('Max depth (m)'), { target: { value: '21.5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save dive' }))
    await waitFor(() => expect(app.openPanel).toHaveBeenCalledWith('scubadive', { id: 9 }))
    expect(api.addScubaDive.mock.calls[0][0]).toMatchObject({ max_depth: 21.5, site_id: 1, gas_o2: 32, buddy: 'Sam', tags: [] })
    expect(onClose).toHaveBeenCalled()
  })

  it('a site and a trip list their dives; a card and a service log open', async () => {
    draw(<SitePanel id={1} onClose={() => {}} />)
    expect(await screen.findByText('Seen here')).toBeTruthy()
    expect(screen.getByText(/Green turtle ×2/)).toBeTruthy()
    cleanup()
    draw(<TripPanel id={1} onClose={() => {}} />)
    expect(await screen.findByRole('heading', { name: 'Dives' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Log a dive on it' })).toBeTruthy()
    cleanup()
    draw(<ServicePanel gearId={7} onClose={() => {}} />)
    expect(await screen.findByText('Service log')).toBeTruthy()
    expect(screen.getAllByText('Annual service').length).toBeGreaterThan(0)
    cleanup()
    draw(<CertPanel id={1} onClose={() => {}} />)
    expect(await screen.findByDisplayValue('Open Water Diver')).toBeTruthy()
  })

  it('a service is logged against the gear', async () => {
    api.addScubaService.mockResolvedValue({ service_id: 2 })
    draw(<ServicePanel gearId={7} onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: '+ Log a service' }))
    fireEvent.change(await screen.findByLabelText(/What was done/), { target: { value: 'Visual inspection' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.addScubaService).toHaveBeenCalled())
    expect(api.addScubaService.mock.calls[0][0]).toBe(7)
    expect(api.addScubaService.mock.calls[0][1]).toMatchObject({ what: 'Visual inspection', next_due: null })
  })
})
