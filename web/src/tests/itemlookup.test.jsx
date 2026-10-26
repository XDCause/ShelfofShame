// The wishlist's + Add (components/WishForm.jsx) uses Add a supply's look-up (components/ItemLookup.jsx): what it
// finds fills the form in. The API is faked.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import WishForm from '../components/WishForm.jsx'
import { AppContext } from '../core/app-context.js'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, listSupplies: vi.fn(), catalogInfo: vi.fn(), searchCatalog: vi.fn(), lookupItem: vi.fn() } }
})

const LOOKUPS = {
  categories: [{ id: 3, name: 'Tool' }], brands: [{ id: 1, name: 'Tamiya' }, { id: 7, name: 'Trumpeter' }],
  paint_types: [], finishes: [], priorities: ['Normal', 'High'],
}
const CUTTER = {
  maker: 'Trumpeter', brand_id: 7, product_code: '08005', title: 'Masking Tape Cutter', name: 'Masking Tape Cutter',
  is_tool: true, has_image: false, suggested: { name: 'Masking Tape Cutter', category_id: 3 },
}

beforeEach(() => {
  api.listSupplies.mockResolvedValue([])
  api.catalogInfo.mockResolvedValue({ products: 1 })
  api.searchCatalog.mockResolvedValue([])
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const show = () => render(
  <AppContext.Provider value={{ openModel: vi.fn() }}>
    <WishForm wish={null} lookups={LOOKUPS} onSaved={vi.fn()} onCancel={vi.fn()} onCatalogAdded={vi.fn()} />
  </AppContext.Provider>)

describe("the wishlist's look-up", () => {
  it('a Trumpeter number fills the form in, like Add a supply', async () => {
    api.lookupItem.mockResolvedValue({ found: [CUTTER], missed: [{ maker: 'Tamiya', status: 404, message: 'no' }] })
    show()
    fireEvent.change(screen.getByPlaceholderText(/XF-76, 81776/), { target: { value: '08005' } })
    fireEvent.click(screen.getByRole('button', { name: 'Look up' }))
    expect(await screen.findByText('Found at Trumpeter.')).toBeTruthy()
    await waitFor(() => expect(screen.getByLabelText(/^Name/).value).toBe('Masking Tape Cutter'))
    expect(screen.getByLabelText(/^Category/).value).toBe('3')
  })
})
