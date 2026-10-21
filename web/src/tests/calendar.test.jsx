// The calendar's helpers and Quick add (core/calendar/calendarParts.jsx). Quick add's API calls are faked: what the
// words mean is the API's job (tests/test_calendar_more.py); here it's what the page does with the answer.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { QuickAdd, isLogged, isoWeek, repeatText, weatherLine } from '../core/calendar/calendarParts.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, parseEvent: vi.fn(), addEvent: vi.fn() } }
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('repeatText', () => {
  const on = (repeats, extra = {}) => repeatText({ starts_on: '2026-11-14', repeats, ...extra })   // a Saturday, the 2nd
  it('says each kind of repeat in words', () => {
    expect(on('weekly')).toBe('every week')
    expect(on('weekly', { repeat_every: 3 })).toBe('every 3 weeks')
    expect(on('fortnightly')).toBe('every two weeks')
    expect(on('weekdays', { repeat_days: [0, 3] })).toBe('every Mon & Thu')
    expect(on('weekdays', { repeat_days: [5], repeat_every: 2 })).toBe('every 2 weeks on Sat')
    expect(on('monthly')).toBe('monthly on the 14th')
    expect(repeatText({ starts_on: '2026-11-21', repeats: 'monthly' })).toBe('monthly on the 21st')
    expect(on('monthly_nth')).toBe('every 2nd Saturday')
    expect(repeatText({ starts_on: '2026-11-28', repeats: 'monthly_nth' })).toBe('every 4th Saturday')
    expect(repeatText({ starts_on: '2026-10-31', repeats: 'monthly_nth' })).toBe('every last Saturday')   // (a 5th one: the last)
    expect(on('yearly')).toBe('every year on 14 November')
    expect(on('never')).toBe('')
  })
})

describe('weeks, logging and weather', () => {
  it('finds the Monday-first week a day is in', () => {
    expect(isoWeek('2026-10-21')).toEqual(['2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23', '2026-10-24', '2026-10-25'])
    expect(isoWeek('2026-11-01')[0]).toBe('2026-10-26')            // a Sunday belongs to the week before
  })
  it('knows an event was logged by its own record or by its hobby logging something that day', () => {
    expect(isLogged({ logged_id: 4, hobby: 'volleyball' }, [])).toBe(true)
    expect(isLogged({ hobby: 'volleyball' }, [{ kind: 'volleyball' }])).toBe(true)
    expect(isLogged({ hobby: 'volleyball' }, [{ kind: 'game' }])).toBe(false)
    expect(isLogged({ hobby: null }, [{ kind: 'game' }])).toBe(false)
  })
  it('says the weather in one line', () => {
    expect(weatherLine({ icon: '☀️', max: 27.6, rain_chance: 10 })).toBe('☀️ 28° · 10% rain')
    expect(weatherLine({ max: 19.2, rain_chance: null })).toBe(' 19°')
    expect(weatherLine(null)).toBe('')
  })
})

describe('Quick add', () => {
  const app = (over = {}) => ({ openPanel: vi.fn(), changed: vi.fn(), showToast: vi.fn(), ...over })
  const show = (ctx) => render(<AppContext.Provider value={ctx}><QuickAdd /></AppContext.Provider>)
  const READ = { title: 'Volleyball', hobby: 'volleyball', starts_on: '2026-10-27', start_time: '19:00:00', end_time: '21:00:00',
    location: 'Sports hall', repeats: 'weekly', repeat_every: 1, repeat_days: null, repeat_until: null }

  it('shows what it understood, then adds it', async () => {
    api.parseEvent.mockResolvedValue(READ)
    api.addEvent.mockResolvedValue({ ...READ, event_id: 9 })
    const ctx = app()
    show(ctx)
    fireEvent.change(screen.getByLabelText('Add an event in plain words'), { target: { value: 'Volleyball Tue 7-9pm at Sports hall weekly' } })
    expect(await screen.findByText('Volleyball', { selector: 'strong' })).toBeTruthy()      // (its title; the hobby is a chip)
    expect(api.parseEvent).toHaveBeenCalledWith('Volleyball Tue 7-9pm at Sports hall weekly')
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(api.addEvent).toHaveBeenCalledWith(READ))
    expect(ctx.changed).toHaveBeenCalled()
    expect(ctx.showToast).toHaveBeenCalledWith('Volleyball added for 27 Oct 2026')
    await waitFor(() => expect(screen.getByLabelText('Add an event in plain words').value).toBe(''))
  })

  it('Edit first opens the full form with it filled in', async () => {
    api.parseEvent.mockResolvedValue(READ)
    const ctx = app()
    show(ctx)
    fireEvent.change(screen.getByLabelText('Add an event in plain words'), { target: { value: 'Volleyball Tue' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit first' }))
    expect(ctx.openPanel).toHaveBeenCalledWith('event', { prefill: READ })
  })

  it('a failed add says why and keeps the words', async () => {
    api.parseEvent.mockResolvedValue(READ)
    api.addEvent.mockRejectedValue(new Error('The API is down'))
    const ctx = app()
    show(ctx)
    fireEvent.change(screen.getByLabelText('Add an event in plain words'), { target: { value: 'Volleyball Tue' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Add' }))
    await waitFor(() => expect(ctx.showToast).toHaveBeenCalledWith('The API is down'))
    expect(screen.getByLabelText('Add an event in plain words').value).toBe('Volleyball Tue')
    expect(ctx.changed).not.toHaveBeenCalled()
  })
})
