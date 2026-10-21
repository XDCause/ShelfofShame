// The Wishlist page (components/WishlistPage.jsx): tick something when you buy it, undo a mistaken tick, the hobby row.
// The API is faked: what "bought" does to each kind of thing is the API's job (tests/test_wanted_more.py).
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import WishlistPage from '../components/WishlistPage.jsx'
import { AppContext } from '../core/app-context.js'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, wanted: vi.fn(), wantedExtras: vi.fn(), gotWanted: vi.fn(), ungotWanted: vi.fn() } }
})

const WANTED = {
  default_shop: 'Hobbyrama', supplies: 0,
  shops: [
    { shop: 'Hobbyrama', total: 54, items: [{ kind: 'model', id: 1, name: '1/700 Yamato', label: 'Kit', price: 54, detail: 'Tamiya' }] },
    { shop: 'Good Games', total: 39.95, items: [{ kind: 'game', id: 2, name: 'Azul', label: 'Board game', price: 39.95 }] },
  ],
}
const EXTRAS = { 'model:1': { hobby: 'models', days: 3 }, 'game:2': { hobby: 'boardgames', days: 40 } }

beforeEach(() => {
  try { localStorage.clear() } catch { /* fine */ }
  api.wanted.mockResolvedValue(WANTED)
  api.wantedExtras.mockResolvedValue(EXTRAS)
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.useRealTimers() })

const app = () => ({ refreshKey: 0, openThing: vi.fn(), openPanel: vi.fn(), changed: vi.fn(), showToast: vi.fn() })
const show = (ctx) => render(<MemoryRouter><AppContext.Provider value={ctx}><WishlistPage settings={{}} lookups={{}} /></AppContext.Provider></MemoryRouter>)

describe('the Wishlist page', () => {
  it('ticks a bought thing, and the list catches up a few seconds later', async () => {
    api.gotWanted.mockResolvedValue({ kind: 'model', ref: 1, name: '1/700 Yamato' })
    const ctx = app()
    show(ctx)
    const tick = await screen.findByRole('button', { name: 'Bought 1/700 Yamato' })
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fireEvent.click(tick)
    await waitFor(() => expect(api.gotWanted).toHaveBeenCalledWith('model', 1))
    expect(await screen.findByRole('button', { name: 'Bought 1/700 Yamato - undo' })).toBeTruthy()
    expect(ctx.showToast).toHaveBeenCalledWith('1/700 Yamato: bought ✓')
    expect(ctx.changed).not.toHaveBeenCalled()                        // (time to undo first)
    await act(async () => { vi.advanceTimersByTime(6500) })
    expect(ctx.changed).toHaveBeenCalledTimes(1)
  })

  it('undoing a tick takes it back, and the list is left alone', async () => {
    api.gotWanted.mockResolvedValue({})
    api.ungotWanted.mockResolvedValue(null)
    const ctx = app()
    show(ctx)
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fireEvent.click(await screen.findByRole('button', { name: 'Bought Azul' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Bought Azul - undo' }))
    await waitFor(() => expect(api.ungotWanted).toHaveBeenCalledWith('game', 2))
    expect(await screen.findByRole('button', { name: 'Bought Azul' })).toBeTruthy()
    await act(async () => { vi.advanceTimersByTime(6500) })
    expect(ctx.changed).not.toHaveBeenCalled()
  })

  it('a tick the API refuses says why and stays unticked', async () => {
    api.gotWanted.mockRejectedValue(new Error("That isn't on your wishlist any more."))
    const ctx = app()
    show(ctx)
    fireEvent.click(await screen.findByRole('button', { name: 'Bought Azul' }))
    await waitFor(() => expect(ctx.showToast).toHaveBeenCalledWith("That isn't on your wishlist any more."))
    expect(screen.getByRole('button', { name: 'Bought Azul' }).getAttribute('aria-pressed')).toBe('false')
  })

  it('the hobby row narrows the list, and remembers the choice', async () => {
    show(app())
    expect(await screen.findByText('1/700 Yamato')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Board games/ }))
    await waitFor(() => expect(screen.queryByText('1/700 Yamato')).toBeNull())
    expect(screen.getByText('Azul')).toBeTruthy()
    expect(localStorage.getItem('offtheclock.wishHobby')).toBe('boardgames')
    fireEvent.click(screen.getByRole('button', { name: 'All hobbies' }))
    expect(await screen.findByText('1/700 Yamato')).toBeTruthy()
  })
})
