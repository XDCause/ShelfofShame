// Stocktake (core/supplies/SuppliesTools.jsx): one item at a time; a count that can't be saved says so and stays on
// that item (the review of 2026-10-21 found it swallowed the error and looked stuck).
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { Stocktake } from '../core/supplies/SuppliesTools.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, stocktake: vi.fn(), countSupply: vi.fn() } }
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const ITEMS = [
  { supply_id: 1, name: 'Acrylic XF1 Flat Black', qty_on_hand: 2, brand: 'Tamiya', product_code: 'T81701', counted_at: null },
  { supply_id: 2, name: 'Extra Thin Cement', qty_on_hand: 1, brand: 'Tamiya', product_code: 'T87038', counted_at: '2026-09-01T10:00:00' },
]
const show = (ctx) => render(<MemoryRouter><AppContext.Provider value={ctx}><Stocktake /></AppContext.Provider></MemoryRouter>)

describe('Stocktake', () => {
  it('goes through the items, least recently counted first, and saves each count', async () => {
    api.stocktake.mockResolvedValue(ITEMS)
    api.countSupply.mockResolvedValue({})
    const ctx = { changed: vi.fn(), showToast: vi.fn() }
    show(ctx)
    expect(await screen.findByText(/Acrylic XF1 Flat Black/)).toBeTruthy()
    expect(screen.getByText('Never counted')).toBeTruthy()
    expect(screen.getByText('1 of 2')).toBeTruthy()
    await screen.findByRole('button', { name: '✓ Still 2' })              // (its count filled in)
    fireEvent.click(screen.getByRole('button', { name: 'One less' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save: 1' }))
    await waitFor(() => expect(api.countSupply).toHaveBeenCalledWith(1, 1))
    expect(await screen.findByText(/Extra Thin Cement/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '✓ Still 1' }))
    await waitFor(() => expect(api.countSupply).toHaveBeenCalledWith(2, 1))
    expect(await screen.findByText(/All counted - 2 checked/)).toBeTruthy()
    expect(ctx.changed).toHaveBeenCalledTimes(2)
  })

  it('a count that cannot be saved says so and stays on the item', async () => {
    api.stocktake.mockResolvedValue(ITEMS)
    api.countSupply.mockRejectedValue(new Error('Failed to fetch'))
    const ctx = { changed: vi.fn(), showToast: vi.fn() }
    show(ctx)
    fireEvent.click(await screen.findByRole('button', { name: 'Empty' }))
    await waitFor(() => expect(ctx.showToast).toHaveBeenCalledWith('Not saved: Failed to fetch'))
    expect(screen.getByText(/Acrylic XF1 Flat Black/)).toBeTruthy()
    expect(screen.getByText('1 of 2')).toBeTruthy()
    expect(ctx.changed).not.toHaveBeenCalled()
  })

  it('Skip moves on without saving', async () => {
    api.stocktake.mockResolvedValue(ITEMS)
    show({ changed: vi.fn(), showToast: vi.fn() })
    fireEvent.click(await screen.findByRole('button', { name: 'Skip' }))
    expect(await screen.findByText(/Extra Thin Cement/)).toBeTruthy()
    expect(api.countSupply).not.toHaveBeenCalled()
  })
})
