// The fishing tools (modules/fishing: the forecast, catch photos, the live trip page) drawn with the API faked (answers
// shaped like api/app/fishing*.py's). No React warnings on the way.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { CatchPhotos } from '../modules/fishing/CatchPhotos.jsx'
import { DayBar, ForecastView, hm, minutesOf, moonPath, spans } from '../modules/fishing/FishingForecast.jsx'
import { LiveView } from '../modules/fishing/FishingLive.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  const names = ['fishingForecast', 'fishingSolunar', 'addFishingPhoto', 'deleteFishingPhoto', 'fishingLiveSummary', 'fishingLiveSpots',
    'fishingLiveSpecies', 'fishingLiveLures', 'fishingLiveAddSpot', 'fishingLiveStart', 'fishingLiveCatch', 'fishingLiveEnd']
  return { ...real, api: { ...real.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } }
})

let app
let errors
const draw = (ui) => render(<MemoryRouter><AppContext.Provider value={app}>{ui}</AppContext.Provider></MemoryRouter>)

const SPOTS = [
  { spot_id: 1, name: 'Wynnum jetty', lat: -27.45, lon: 153.17, water: 'estuary' },
  { spot_id: 2, name: 'Somerset dam', lat: null, lon: null, water: 'fresh' },
]
const SPECIES = [{ species_id: 1, name: 'Dusky flathead' }, { species_id: 2, name: 'Yellowfin bream' }]
const LURES = [{ lure_id: 4, name: 'Zerek Prawn 3.5"' }]
const DAY = {
  date: '2026-11-18', sunrise: '2026-11-18T04:58', sunset: '2026-11-18T18:21', rating: 3, score: 4, why: 'Dawn major with the tide turning',
  moon: { phase: 'Waxing crescent', pct: 23, rise: '08:10', set: '21:55' },
  majors: [{ start: '05:10', end: '07:10' }, { start: '17:30', end: '19:30' }], minors: [{ start: '08:10', end: '09:10' }],
  tide: [{ time: '2026-11-18T04:40', height: 0.4, kind: 'low' }, { time: '2026-11-18T10:50', height: 1.9, kind: 'high' }],
  wind_max: 18, wind_dir: 135, gusts: 28, pressure_mean: 1016, pressure_trend: 'falling', rain_mm: 0, sst: 23.4,
  best: [{ start: '05:10', end: '06:10', why: 'Major period at dawn' }],
}
const FORECAST = { place: 'Wynnum jetty', water: 'estuary', days: [DAY, { ...DAY, date: '2026-11-19', rating: 1, best: [], majors: [] }], credit: 'Open-Meteo' }

beforeEach(() => {
  app = { refreshKey: 0, changed: vi.fn(), showToast: vi.fn(), openPanel: vi.fn() }
  errors = vi.spyOn(console, 'error')
  try { localStorage.clear() } catch { /* none */ }
  api.fishingLiveSpots.mockResolvedValue(SPOTS)
  api.fishingLiveSpecies.mockResolvedValue(SPECIES)
  api.fishingLiveLures.mockResolvedValue(LURES)
  api.fishingLiveSummary.mockResolvedValue({ open_trip: null })
  api.fishingForecast.mockResolvedValue(FORECAST)
  api.fishingSolunar.mockResolvedValue({ ...DAY, date: undefined, tide: [] })
})
afterEach(() => {
  expect(errors).not.toHaveBeenCalled()
  cleanup()
  vi.clearAllMocks()
  errors.mockRestore()
})

describe('forecast pictures', () => {
  it('reads times in any shape and splits a period that runs over midnight', () => {
    expect(hm('2026-11-18T05:12')).toBe('05:12')
    expect(hm('05:12:00')).toBe('05:12')
    expect(minutesOf('02:30')).toBe(150)
    expect(minutesOf(null)).toBeNull()
    expect(spans('23:00', '01:00')).toEqual([[1380, 1440], [0, 60]])
    expect(spans('05:00', '07:00')).toEqual([[300, 420]])
  })
  it('draws the lit part of the moon on the left while it waxes (southern sky)', () => {
    expect(moonPath(0, true)).toBe('')
    expect(moonPath(100, true)).toContain('A10 10 0 1 1')
    expect(moonPath(50, true)).toMatch(/^M12 2 A10 10 0 0 0 12 22 A0.00 10/)       // waxing: outer arc on the left (sweep 0)
    expect(moonPath(50, false)).toMatch(/^M12 2 A10 10 0 0 1 12 22/)
  })
  it('puts the periods and the tide on the 24 h bar and says them for a screen reader', () => {
    const { container } = render(<DayBar day={DAY} />)
    expect(container.querySelectorAll('.fst-bar-major')).toHaveLength(2)
    expect(container.querySelectorAll('.fst-bar-minor')).toHaveLength(1)
    expect(container.querySelector('.fst-bar-tide')).toBeTruthy()
    expect(screen.getByRole('img', { name: /major 05:10 to 07:10.*high 1\.9 m/ })).toBeTruthy()
  })
  it('draws a day with no tide and no periods without a curve', () => {
    const { container } = render(<DayBar day={{ date: '2026-11-18', majors: [], minors: [] }} />)
    expect(container.querySelector('.fst-bar-tide')).toBeNull()
  })
})

describe('ForecastView', () => {
  it('offers the spots with a position, and shows seven-day cards for the one picked', async () => {
    draw(<ForecastView />)
    const select = await screen.findByLabelText('Spot')
    expect(screen.queryByRole('option', { name: 'Somerset dam' })).toBeNull()       // no position: no forecast
    fireEvent.change(select, { target: { value: '1' } })
    await waitFor(() => expect(api.fishingForecast).toHaveBeenCalledWith({ spot_id: 1 }))
    expect(await screen.findByText('Wynnum jetty', { selector: 'h2' })).toBeTruthy()
    expect(screen.getAllByRole('img', { name: 'Day rating 3 of 4' })).toHaveLength(1)
    expect(screen.getByText('05:10-07:10, 17:30-19:30')).toBeTruthy()
    expect(screen.getByText(/Major period at dawn/)).toBeTruthy()
    expect(screen.getAllByText(/Waxing crescent/).length).toBeGreaterThan(0)
    expect(screen.getByText(/old angling theory/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Open-Meteo' })).toBeTruthy()
  })
  it('looks up any other day with the solunar route for the same place', async () => {
    draw(<ForecastView />)
    fireEvent.change(await screen.findByLabelText('Spot'), { target: { value: '1' } })
    const date = await screen.findByLabelText(/Any other day/)
    fireEvent.change(date, { target: { value: '2026-06-21' } })
    await waitFor(() => expect(api.fishingSolunar).toHaveBeenCalledWith({ lat: -27.45, lon: 153.17, date: '2026-06-21' }))
    expect(await screen.findByText(/21 Jun/)).toBeTruthy()
  })
  it('shows an answer that failed, and the kept-forecast note', async () => {
    api.fishingForecast.mockRejectedValueOnce(new Error('Open-Meteo is away'))
    draw(<ForecastView />)
    fireEvent.change(await screen.findByLabelText('Spot'), { target: { value: '1' } })
    expect((await screen.findByRole('alert')).textContent).toContain('Open-Meteo is away')
    api.fishingForecast.mockResolvedValueOnce({ ...FORECAST, kept_since: new Date().toISOString() })
    fireEvent.change(screen.getByLabelText('Spot'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Spot'), { target: { value: '1' } })
    expect(await screen.findByText(/last forecast kept/)).toBeTruthy()
  })
})

describe('CatchPhotos', () => {
  const photos = [{ photo_id: 7, url: '/api/fishing/photos/7' }]
  it('shows thumbnails, enlarges one and deletes it', async () => {
    api.deleteFishingPhoto.mockResolvedValue(null)
    const onChange = vi.fn()
    render(<CatchPhotos catchId={3} photos={photos} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Show photo large' }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Show photo large' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete photo' }))
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([]))
    expect(api.deleteFishingPhoto).toHaveBeenCalledWith(7)
  })
  it('adds a photo picked from the file chooser', async () => {
    api.addFishingPhoto.mockResolvedValue({ photo_id: 8, url: '/api/fishing/photos/8' })
    const onChange = vi.fn()
    const { container } = render(<CatchPhotos catchId={3} photos={photos} onChange={onChange} />)
    const file = new File([new Uint8Array([1, 2, 3])], 'fish.jpg', { type: 'image/jpeg' })
    fireEvent.change(container.querySelector('input[data-source="gallery"]'), { target: { files: [file] } })
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([...photos, { photo_id: 8, url: '/api/fishing/photos/8' }]))
    expect(api.addFishingPhoto.mock.calls[0][0]).toBe(3)
  })
  it('says when a photo could not be saved', async () => {
    api.addFishingPhoto.mockRejectedValue(new Error('Too big'))
    const { container } = render(<CatchPhotos catchId={3} photos={[]} />)
    fireEvent.change(container.querySelector('input[data-source="gallery"]'), { target: { files: [new File([new Uint8Array([1])], 'f.jpg', { type: 'image/jpeg' })] } })
    expect((await screen.findByRole('alert')).textContent).toContain('Too big')
  })
})

describe('LiveView', () => {
  const start = async () => {
    draw(<LiveView />)
    fireEvent.change(await screen.findByLabelText('Where'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Boat' }))
    fireEvent.change(screen.getByLabelText('After'), { target: { value: 'Flathead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start fishing' }))
  }
  const logCatch = async (species = 'Dusky flathead', fate = 'Released') => {
    fireEvent.click(await screen.findByRole('button', { name: 'Fish!' }))
    fireEvent.click(await screen.findByRole('button', { name: species }))
    fireEvent.change(screen.getByLabelText('Length (cm)'), { target: { value: '47.5' } })
    fireEvent.click(screen.getByRole('button', { name: fate }))
  }

  it('starts a trip at a spot and shows the timer and the day\'s periods', async () => {
    api.fishingLiveStart.mockResolvedValue({ trip_id: 12 })
    await start()
    expect(await screen.findByLabelText('Time fishing')).toBeTruthy()
    await waitFor(() => expect(api.fishingLiveStart).toHaveBeenCalledWith(expect.objectContaining({ spot_id: 1, platform: 'boat', target: 'Flathead' })))
    expect(await screen.findByText('05:10-07:10, 17:30-19:30')).toBeTruthy()
    expect(api.fishingForecast).toHaveBeenCalledWith({ spot_id: 1 })
    expect(localStorage.getItem('offtheclock.fishing.queue')).toBeNull()      // sent: nothing waiting
  })

  it('logs a catch in three taps with the time, sends it with a client key and shows the rule warnings', async () => {
    api.fishingLiveStart.mockResolvedValue({ trip_id: 12 })
    api.fishingLiveCatch.mockResolvedValue({ catch_id: 90, warnings: ['Under the minimum size as you typed it - check the official rules'] })
    await start()
    await logCatch('Dusky flathead', 'Kept')
    await waitFor(() => expect(api.fishingLiveCatch).toHaveBeenCalled())
    const [tripId, body] = api.fishingLiveCatch.mock.calls[0]
    expect(tripId).toBe(12)                                                     // the temporary trip id was swapped first
    expect(body).toMatchObject({ species_id: 1, fate: 'kept', length_cm: 47.5 })
    expect(body.client_key).toMatch(/^tmp-c-/)
    expect(body.caught_at).toBeTruthy()
    expect(await screen.findByText(/Under the minimum size/)).toBeTruthy()
    expect(screen.getByText('47.5 cm')).toBeTruthy()
  })

  it('works with no signal: waits in the queue, shows the badge, and sends everything in order when back', async () => {
    const down = Object.assign(new Error('Failed to fetch'), { status: undefined })
    api.fishingLiveStart.mockRejectedValue(down)
    api.fishingLiveCatch.mockRejectedValue(down)
    api.fishingLiveEnd.mockRejectedValue(down)
    await start()
    await logCatch('Yellowfin bream', 'Released')
    expect(await screen.findByText(/2 waiting to send/)).toBeTruthy()           // the trip start and the catch
    const kept = JSON.parse(localStorage.getItem('offtheclock.fishing.queue'))
    expect(kept.map((q) => q.kind)).toEqual(['trip', 'catch'])
    expect(kept[1].trip).toBe(kept[0].temp)
    expect(screen.getByText('Yellowfin bream')).toBeTruthy()                    // shown from this phone's copy
    fireEvent.click(screen.getByRole('button', { name: 'End trip' }))
    fireEvent.click(screen.getByRole('button', { name: 'End trip' }))           // the "End this trip now?" question
    expect((await screen.findByText('Trip ended'))).toBeTruthy()
    expect(JSON.parse(localStorage.getItem('offtheclock.fishing.queue')).map((q) => q.kind)).toEqual(['trip', 'catch', 'end'])

    // signal is back
    api.fishingLiveStart.mockReset().mockResolvedValue({ trip_id: 31 })
    api.fishingLiveCatch.mockReset().mockResolvedValue({ catch_id: 55, warnings: [] })
    api.fishingLiveEnd.mockReset().mockResolvedValue({})
    window.dispatchEvent(new Event('online'))
    await waitFor(() => expect(api.fishingLiveEnd).toHaveBeenCalled())
    expect(api.fishingLiveStart).toHaveBeenCalledTimes(1)
    expect(api.fishingLiveCatch.mock.calls[0][0]).toBe(31)
    expect(api.fishingLiveEnd.mock.calls[0][0]).toBe(31)
    await waitFor(() => expect(localStorage.getItem('offtheclock.fishing.queue')).toBeNull())
    expect(await screen.findByText(/Everything is saved/)).toBeTruthy()
  })

  it('carries on a trip that is open on the server, and ends it', async () => {
    api.fishingLiveSummary.mockResolvedValue({ open_trip: { trip_id: 5, started_at: new Date(Date.now() - 3600000).toISOString(), spot_id: 1,
      spot_name: 'Wynnum jetty', platform: 'shore', target: null, catches: 2 } })
    api.fishingLiveEnd.mockResolvedValue({})
    draw(<LiveView />)
    expect(await screen.findByText('Wynnum jetty', { selector: 'h2' })).toBeTruthy()
    expect(screen.getByText('1 h 00 min')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'End trip' }))
    fireEvent.click(screen.getByRole('button', { name: 'End trip' }))
    await waitFor(() => expect(api.fishingLiveEnd).toHaveBeenCalledWith(5, { ended_at: expect.any(String) }))
  })

  it('types a species that is not on the list', async () => {
    api.fishingLiveStart.mockResolvedValue({ trip_id: 12 })
    api.fishingLiveCatch.mockResolvedValue({ catch_id: 90, warnings: [] })
    await start()
    fireEvent.click(await screen.findByRole('button', { name: 'Fish!' }))
    fireEvent.change(await screen.findByLabelText('Find or type a species'), { target: { value: 'Pikey bream' } })
    fireEvent.click(screen.getByRole('button', { name: /Use "Pikey bream"/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Released' }))
    await waitFor(() => expect(api.fishingLiveCatch).toHaveBeenCalled())
    expect(api.fishingLiveCatch.mock.calls[0][1]).toMatchObject({ species: 'Pikey bream', fate: 'released' })
    expect(api.fishingLiveCatch.mock.calls[0][1].species_id).toBeUndefined()
  })

  it('queues a photo for a catch and sends it once the catch has its id', async () => {
    api.fishingLiveStart.mockResolvedValue({ trip_id: 12 })
    api.fishingLiveCatch.mockResolvedValue({ catch_id: 90, warnings: [] })
    api.addFishingPhoto.mockResolvedValue({ photo_id: 1 })
    await start()
    const container = document.body
    await logCatch()
    await waitFor(() => expect(api.fishingLiveCatch).toHaveBeenCalled())
    const input = await waitFor(() => {
      const el = container.querySelector('input[data-source="gallery"]')
      if (!el) throw new Error('no picker yet')
      return el
    })
    fireEvent.change(input, { target: { files: [new File([new Uint8Array([1, 2, 3])], 'f.jpg', { type: 'image/jpeg' })] } })
    await waitFor(() => expect(api.addFishingPhoto).toHaveBeenCalled())
    expect(api.addFishingPhoto.mock.calls[0][0]).toBe(90)
  })

  it('starts with a new spot named from where you stand when none is within 2 km', async () => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: {
      getCurrentPosition: (ok) => ok({ coords: { latitude: -27.9, longitude: 153.4, accuracy: 8 } }) } })
    try {
      api.fishingLiveAddSpot.mockResolvedValue({ spot_id: 9 })
      api.fishingLiveStart.mockResolvedValue({ trip_id: 12 })
      draw(<LiveView />)
      fireEvent.click(await screen.findByRole('button', { name: 'Use my position' }))
      expect(await screen.findByText(/No spot of yours within 2 km/)).toBeTruthy()
      fireEvent.change(screen.getByLabelText('Name this spot'), { target: { value: 'North Stradbroke gutter' } })
      fireEvent.click(screen.getByRole('button', { name: 'Start fishing' }))
      await waitFor(() => expect(api.fishingLiveStart).toHaveBeenCalledWith(expect.objectContaining({ spot_id: 9 })))
      expect(api.fishingLiveAddSpot).toHaveBeenCalledWith({ name: 'North Stradbroke gutter', lat: -27.9, lon: 153.4 })
    } finally {
      delete navigator.geolocation
    }
  })

  it('finds the spot of yours that is near', async () => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: {
      getCurrentPosition: (ok) => ok({ coords: { latitude: -27.4505, longitude: 153.1702, accuracy: 8 } }) } })
    try {
      draw(<LiveView />)
      fireEvent.click(await screen.findByRole('button', { name: 'Use my position' }))
      expect(await screen.findByText(/Wynnum jetty, \d+ m away/)).toBeTruthy()
      expect(screen.getByLabelText('Where').value).toBe('1')
    } finally {
      delete navigator.geolocation
    }
  })

  it('still offers its pickers with no signal, from the last visit', async () => {
    const down = Object.assign(new Error('Failed to fetch'), { status: undefined })
    api.fishingLiveSpots.mockResolvedValueOnce(SPOTS)
    draw(<LiveView />)
    expect(await screen.findByRole('option', { name: 'Wynnum jetty' })).toBeTruthy()
    cleanup()
    api.fishingLiveSpots.mockRejectedValue(down)
    api.fishingLiveSummary.mockRejectedValue(down)
    draw(<LiveView />)
    expect(await screen.findByRole('option', { name: 'Wynnum jetty' })).toBeTruthy()
  })
})
