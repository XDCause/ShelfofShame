// The Supplies page (components/InventoryView.jsx): search, "need attention", a filter from Options, and the hobby row
// (Models = the paints and such; another hobby = its own kit). The API is faked.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import InventoryView from '../components/InventoryView.jsx'
import { AppContext } from '../core/app-context.js'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, listSupplies: vi.fn(), owned: vi.fn() } }
})

const supply = (id, name, category, stock_status = 'OK', extra = {}) => ({
  supply_id: id, item_ref: `SUP-${String(id).padStart(4, '0')}`, name, category, brand: 'Tamiya', product_code: `T8${id}`,
  qty_on_hand: stock_status === 'Out' ? 0 : 1, reorder_at: 0, stock_status, condition: 'Sealed', location: null,
  location_path: null, unit_price: 3.95, has_image: false, swatch: null, used_on: [], ...extra,
})
const SUPPLIES = [
  supply(1, 'Acrylic XF1 Flat Black', 'Paint'), supply(2, 'Acrylic XF2 Flat White', 'Paint', 'Out'),
  supply(3, 'Extra Thin Cement', 'Glue / Cement'), supply(4, 'Panel Line Accent Color Black', 'Weathering', 'Low'),
]
const OWNED = [{ hobby: 'volleyball', kind: 'Knee pads', open: 'gear', id: 5, name: 'Pads Pro', detail: 'Mizuno', status: 'Good',
  amount: null, attention: false, photo_url: null }]

beforeEach(() => {
  try { localStorage.clear() } catch { /* fine */ }
  api.listSupplies.mockResolvedValue(SUPPLIES)
  api.owned.mockResolvedValue(OWNED)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const app = { openThing: vi.fn(), openPanel: vi.fn(), changed: vi.fn(), showToast: vi.fn(),
  lookups: { locations: [], categories: [], brands: [] } }
const show = () => render(<MemoryRouter><AppContext.Provider value={app}>
  <InventoryView refreshKey={0} onOpen={vi.fn()} onAdd={vi.fn()} onAdjusted={vi.fn()} /></AppContext.Provider></MemoryRouter>)
const names = () => SUPPLIES.map((s) => s.name).filter((n) => screen.queryByText(n))

describe('the Supplies page', () => {
  it('search keeps only what matches - every word, anywhere', async () => {
    show()
    expect(await screen.findByText('Extra Thin Cement')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'flat black' } })
    await waitFor(() => expect(names()).toEqual(['Acrylic XF1 Flat Black']))
  })

  it('"need attention" shows just what is Low or Out', async () => {
    show()
    fireEvent.click(await screen.findByRole('button', { name: '2 need attention' }))
    await waitFor(() => expect(names().sort()).toEqual(['Acrylic XF2 Flat White', 'Panel Line Accent Color Black']))
  })

  it('a category from Options narrows the list', async () => {
    show()
    await screen.findByText('Extra Thin Cement')
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Paint' } })
    await waitFor(() => expect(names()).toEqual(['Acrylic XF1 Flat Black', 'Acrylic XF2 Flat White']))
  })

  it("the hobby row swaps to another hobby's kit, and remembers it", async () => {
    show()
    await screen.findByText('Extra Thin Cement')
    const row = within(screen.getByRole('group', { name: 'Hobby' }))       // (each hobby's section has a fold button too)
    fireEvent.click(row.getByRole('button', { name: /^Volleyball/ }))
    expect(await screen.findByText('Pads Pro')).toBeTruthy()
    expect(names()).toEqual([])                                             // (the model supplies are Models')
    expect(localStorage.getItem('hobby-inventory.suppliesHobby')).toBe('volleyball')
    fireEvent.click(row.getByRole('button', { name: /^Models/ }))
    await waitFor(() => expect(names().length).toBe(4))
    expect(screen.queryByText('Pads Pro')).toBeNull()
  })
})
