// The scuba tools (modules/scuba: the profile chart, the planner, conditions, import) drawn with the API faked
// (answers shaped like api/app/scuba_tools.py). No React warnings on the way.
import { cleanup, createEvent, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { DiveProfile } from '../modules/scuba/DiveProfile.jsx'
import { ConditionsView } from '../modules/scuba/ScubaConditions.jsx'
import { ImportPanel } from '../modules/scuba/ScubaImport.jsx'
import { PlanView } from '../modules/scuba/ScubaPlan.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  const names = ['scubaNdl', 'scubaPlan', 'scubaAnalysis', 'scubaImport', 'scubaConditions', 'scubaToolSettings', 'scubaToolSites']
  return { ...real, api: { ...real.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } }
})

const changed = vi.fn()
const wrap = (ui) => render(<AppContext.Provider value={{ changed, openPanel: vi.fn(), refreshKey: 0 }}>{ui}</AppContext.Provider>)
const SETTINGS = { gas_o2: 32, tank_l: 12, sac_l_min: 18, gf_low: 40, gf_high: 85 }
const ANALYSIS = {
  profile: [[0, 0, 26], [60, 12, 25], [600, 18, 24], [1500, 8, 25], [1800, 5, 26], [1900, 0, 26]],
  ascent_warnings: [{ from_s: 1500, to_s: 1530, rate: 14 }], safety_stop: { found: false, seconds: 0 },
  tissues: [[0, 0], [600, 60], [1900, 40]], surface_gf: 41, cns: 3, otu: 12, max_ppo2: 1.4,
}

beforeEach(() => {
  vi.clearAllMocks()
  api.scubaToolSettings.mockResolvedValue(SETTINGS)
  api.scubaNdl.mockResolvedValue([{ depth: 18, ndl: 58 }, { depth: 39, ndl: null }])
  api.scubaAnalysis.mockResolvedValue(ANALYSIS)
})
afterEach(cleanup)

describe('DiveProfile', () => {
  it('draws nothing without a profile', () => {
    const { container } = wrap(<DiveProfile diveId={1} hasProfile={false} />)
    expect(container.querySelector('svg')).toBeNull()
    expect(api.scubaAnalysis).not.toHaveBeenCalled()
  })
  it('draws the chart, the warnings and the figures', async () => {
    const { container } = wrap(<DiveProfile diveId={7} hasProfile />)
    expect(await screen.findByText(/1 fast ascent/)).toBeTruthy()
    expect(api.scubaAnalysis).toHaveBeenCalledWith(7)
    expect(container.querySelector('.dive-fast')).toBeTruthy()
    expect(container.querySelector('.dive-stopband')).toBeTruthy()
    expect(screen.getByText(/No safety stop found/)).toBeTruthy()
    expect(screen.getByText('41%')).toBeTruthy()
    expect(screen.getByText('1.40 bar')).toBeTruthy()
  })
  it('reads off a point when touched', async () => {
    const { container } = wrap(<DiveProfile diveId={7} hasProfile />)
    await screen.findByText(/fast ascent/)
    const svg = container.querySelector('svg')
    svg.getBoundingClientRect = () => ({ left: 0, width: 480, top: 0, height: 278 })
    const move = createEvent.pointerMove(svg)       // (jsdom has no PointerEvent: give the event its position)
    Object.defineProperty(move, 'clientX', { value: 34 + ((480 - 42) * 600) / 1900 })
    fireEvent(svg, move)
    expect(screen.getByRole('status').textContent).toContain('10:00')
    expect(screen.getByRole('status').textContent).toContain('18.0 m')
  })
  it('says so when the analysis fails', async () => {
    api.scubaAnalysis.mockRejectedValue(new Error('This dive has no samples'))
    wrap(<DiveProfile diveId={7} hasProfile />)
    expect(await screen.findByText('This dive has no samples')).toBeTruthy()
  })
})

describe('PlanView', () => {
  it('shows the caveat, the NDL table and the calculators', async () => {
    wrap(<PlanView />)
    expect(await screen.findByText(/For learning and checking - your dive computer and training rule/)).toBeTruthy()
    expect(await screen.findByText('58 min')).toBeTruthy()
    expect(screen.getByText(/beyond this gas/)).toBeTruthy()
    expect(api.scubaNdl).toHaveBeenCalledWith({ gas_o2: 32, gf_high: 85 })
    expect(screen.getAllByText('33.8 m').length).toBeGreaterThan(0)     // MOD of EAN32 at 1.4
    expect(screen.getByText('35% oxygen')).toBeTruthy()                 // best mix at 30 m
  })
  it('plans a dive with the API', async () => {
    api.scubaPlan.mockResolvedValue({ ndl: 0, stops: [{ depth: 3, minutes: 2 }], tts: 6, runtime: 46, ppo2: 1.28, mod: 33.8, cns: 5, otu: 20,
      gas_l: 1500, gas_bar: 125, end_bar: 75, turn_bar: 130, rock_bottom_bar: 50, warnings: ['Past the no-stop limit'] })
    wrap(<PlanView />)
    fireEvent.click(await screen.findByRole('button', { name: 'Plan it' }))
    expect(await screen.findByText('Past the no-stop limit')).toBeTruthy()
    expect(api.scubaPlan).toHaveBeenCalledWith(expect.objectContaining({ depth: 18, minutes: 40, gas_o2: 32, gf_high: 85, repetitive: false }))
    expect(screen.getByText('3 m')).toBeTruthy()
    expect(screen.getByText('50 bar')).toBeTruthy()
  })
})

describe('ConditionsView', () => {
  it('lists seven days for a chosen site', async () => {
    api.scubaToolSites.mockResolvedValue([{ site_id: 3, name: 'Flinders Reef', lat: -26.97, lon: 153.5 }, { site_id: 4, name: 'No position' }])
    api.scubaConditions.mockResolvedValue({ place: 'Flinders Reef', days: [
      { date: '2026-11-20', wave_max: 0.8, swell_max: 1.1, swell_period: 9, swell_dir: 90, sst: 24.5, wind_max_kmh: 15, verdict: 'good', why: 'Light wind, small swell',
        tide: [{ time: '2026-11-20T05:10', height: 1.82, type: 'high' }] },
      { date: '2026-11-21', wave_max: 2.4, swell_max: 2.2, swell_period: 7, swell_dir: 135, sst: 24, wind_max_kmh: 35, verdict: 'poor', why: 'Big swell', tide: [] },
    ] })
    wrap(<ConditionsView />)
    const select = await screen.findByLabelText('Dive site')
    expect(screen.queryByText('No position')).toBeNull()
    fireEvent.change(select, { target: { value: '3' } })
    expect(await screen.findByText('Good')).toBeTruthy()
    expect(api.scubaConditions).toHaveBeenCalledWith({ site_id: '3' })
    expect(screen.getByText('Poor')).toBeTruthy()
    expect(screen.getByText('Light wind, small swell')).toBeTruthy()
    expect(screen.getByText(/05:10/)).toBeTruthy()
    expect(screen.getByText(/Open-Meteo/)).toBeTruthy()
  })
})

describe('ImportPanel', () => {
  it('previews a file, then imports it', async () => {
    api.scubaImport
      .mockResolvedValueOnce({ format: 'Subsurface', found: 2, added: 0, skipped: 1, dives: [{ dived_on: '2026-10-01', time_in: '09:30:00', max_depth: 21.4, minutes: 48, site: 'Wolf Rock' }] })
      .mockResolvedValueOnce({ format: 'Subsurface', found: 2, added: 1, skipped: 1, dives: [{ dived_on: '2026-10-01', max_depth: 21.4, minutes: 48, site: 'Wolf Rock', dive_id: 9 }] })
    const onClose = vi.fn()
    const { container } = wrap(<ImportPanel onClose={onClose} />)
    const file = new File(['<divelog/>'], 'dives.ssrf', { type: 'text/xml' })
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } })
    expect(await screen.findByText(/already in your log/)).toBeTruthy()
    expect(api.scubaImport).toHaveBeenCalledWith(file, true)
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))
    expect(await screen.findByText(/Imported 1 dive/)).toBeTruthy()
    expect(api.scubaImport).toHaveBeenLastCalledWith(file, false)
    await waitFor(() => expect(changed).toHaveBeenCalled())
  })
  it('shows the problem with a bad file', async () => {
    api.scubaImport.mockRejectedValue(new Error('Not a dive log'))
    const { container } = wrap(<ImportPanel onClose={vi.fn()} />)
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [new File(['x'], 'a.xml')] } })
    expect(await screen.findByText('Not a dive log')).toBeTruthy()
    expect(screen.getByText(/How do I get a file/)).toBeTruthy()
  })
})
