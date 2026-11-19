// "Share my shelf" (modules/boardgames/ShelfShare.jsx) with the API faked: the options, the count, the file made.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { ShelfSharePanel } from '../modules/boardgames/ShelfShare.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, listBoardGames: vi.fn() } }
})

const GAMES = [
  { game_id: 1, name: 'Wingspan', kind: 'game', status: 'Owned', categories: [], price_paid: 89.95, photo_url: '/api/board-games/1/photo?v=1' },
  { game_id: 2, name: 'Azul', kind: 'game', status: 'Owned', categories: [] },
  { game_id: 3, name: 'Gloomhaven', kind: 'game', status: 'Wanted', categories: [] },
]
const wrap = (ui) => render(<AppContext.Provider value={{ changed: vi.fn(), openPanel: vi.fn(), refreshKey: 0 }}>{ui}</AppContext.Provider>)

beforeEach(() => {
  vi.clearAllMocks()
  api.listBoardGames.mockResolvedValue(GAMES)
  URL.createObjectURL = vi.fn(() => 'blob:shelf')
  URL.revokeObjectURL = vi.fn()
  globalThis.fetch = vi.fn(async () => ({ ok: false }))     // the photo can't be read here: the card gets a letter
})
afterEach(cleanup)

describe('share my shelf', () => {
  it('counts the list chosen and makes a file to download', async () => {
    wrap(<ShelfSharePanel onClose={() => {}} />)
    expect(await screen.findByText('2 games on the shelf.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: "Games I'd like" }))
    expect(screen.getByText('1 game on the list.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Games I own' }))
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Our games' } })
    fireEvent.click(screen.getByRole('button', { name: 'Make the file' }))
    const link = await screen.findByRole('link', { name: 'Download' })
    expect(link.getAttribute('href')).toBe('blob:shelf')
    expect(link.getAttribute('download')).toMatch(/^board-games-\d{4}-\d{2}-\d{2}\.html$/)
    const file = URL.createObjectURL.mock.calls[0][0]
    const html = await new Promise((resolve) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.readAsText(file) })
    expect(html).toContain('<h1>Our games</h1>')
    expect(html).toContain('Wingspan')
    expect(html).not.toContain('Gloomhaven')
    expect(html).not.toContain('89.95')
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/board-games/1/photo?v=1', { credentials: 'same-origin' })
  })

  it('a changed option asks for the file to be made again', async () => {
    wrap(<ShelfSharePanel onClose={() => {}} />)
    await screen.findByText('2 games on the shelf.')
    fireEvent.click(screen.getByLabelText('Photos', { exact: false }))
    fireEvent.click(screen.getByRole('button', { name: 'Make the file' }))
    await screen.findByRole('link', { name: 'Download' })
    expect(globalThis.fetch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByLabelText('My ratings'))
    expect(screen.queryByRole('link', { name: 'Download' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Make the file' })).toBeTruthy()
  })
})
