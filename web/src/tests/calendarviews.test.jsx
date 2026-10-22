// The calendar page (core/calendar/CalendarPage.jsx): the month with an event and a holiday on their days, the views as
// tabs (Week and Agenda ask for their own span of days), and moving to the next month. The API is faked.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import CalendarPage from '../core/calendar/CalendarPage.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, calendar: vi.fn(), upcoming: vi.fn(), todos: vi.fn(), calendarYear: vi.fn(), searchEvents: vi.fn(),
    countdowns: vi.fn(), calendarBalance: vi.fn(), eventWeather: vi.fn(), parseEvent: vi.fn() } }
})

const DATA = {
  events: [{ event_id: 1, title: 'Club shoot', day: '2026-11-14', hobby: 'shooting', start_time: '08:00:00', end_time: null,
    repeats: 'monthly_nth', starts_on: '2026-11-14', location: 'The range' }],
  happened: [], moods: [], todos: [], goals: [],
  holidays: [{ day: '2026-11-03', name: 'Test Holiday' }],
}
beforeEach(() => {
  try { localStorage.clear() } catch { /* fine */ }
  api.calendar.mockResolvedValue(DATA)
  for (const f of ['upcoming', 'todos', 'searchEvents', 'countdowns', 'calendarBalance']) api[f].mockResolvedValue([])
  api.eventWeather.mockResolvedValue({ weather: [], error: null, home: null })
  api.calendarYear.mockResolvedValue({ year: 2026, holidays: [], days: [] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const show = (url = '/calendar?day=2026-11-14') => render(
  <MemoryRouter initialEntries={[url]}><AppContext.Provider value={{ refreshKey: 0, openPanel: vi.fn(), changed: vi.fn(), showToast: vi.fn() }}>
    <Routes><Route path="/calendar" element={<CalendarPage />} /></Routes>
  </AppContext.Provider></MemoryRouter>)
const lastSpan = () => api.calendar.mock.calls.at(-1)

describe('the calendar', () => {
  it('shows the month, with an event and a holiday on their days', async () => {
    show()
    expect(await screen.findByRole('heading', { name: 'November 2026' })).toBeTruthy()
    const [start, end] = lastSpan()
    expect(start <= '2026-11-01' && end >= '2026-11-30').toBe(true)                // (the whole month, Monday-first weeks)
    expect((await screen.findAllByText(/Club shoot/)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Test Holiday/).length).toBeGreaterThan(0)
  })

  it('Week and Agenda each ask for their own days', async () => {
    show()
    await screen.findByRole('heading', { name: 'November 2026' })
    fireEvent.click(screen.getByRole('link', { name: 'Week' }))
    await waitFor(() => expect(lastSpan()).toEqual(['2026-11-09', '2026-11-15']))
    fireEvent.click(screen.getByRole('link', { name: 'Agenda' }))
    await waitFor(() => expect(lastSpan()).toEqual(['2026-11-14', '2027-01-12']))   // (60 days from the day picked)
    expect((await screen.findAllByText(/Club shoot/)).length).toBeGreaterThan(0)
  })

  it('the next month is one tap away', async () => {
    show()
    await screen.findByRole('heading', { name: 'November 2026' })
    fireEvent.click(screen.getByRole('button', { name: 'Next month' }))
    expect(await screen.findByRole('heading', { name: 'December 2026' })).toBeTruthy()
  })

  it('a calendar that cannot load says why', async () => {
    api.calendar.mockRejectedValue(new Error('The API is down'))
    show()
    expect(await screen.findByText(/The API is down/)).toBeTruthy()
  })
})
