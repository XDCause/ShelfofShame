// The journal list (core/journal/JournalList.jsx): pages under their day (pinned first), and each filter - a tag, a
// mood, words, private pages - asking the API for just those. The API is faked.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import JournalList from '../core/journal/JournalList.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, listPages: vi.fn(), journalTags: vi.fn(), notebooks: vi.fn(), journalToday: vi.fn(),
    onThisDay: vi.fn(), listTodos: vi.fn(), journalTemplates: vi.fn() } }
})

const page = (id, title, entry_date, extra = {}) => ({ page_id: id, title, entry_date, kind: 'notes', mood: null, mood_words: [],
  tags: [], snippet: '', pinned: false, private: false, created_at: `${entry_date}T09:00:00`, updated_at: `${entry_date}T09:00:00`, ...extra })
const PAGES = [page(1, 'Primed the Zero', '2026-10-20', { tags: ['build'] }), page(2, 'Club shoot notes', '2026-10-18', { mood: 'great' }),
  page(3, 'Ideas list', '2026-09-01', { pinned: true })]

beforeEach(() => {
  try { localStorage.clear() } catch { /* fine */ }
  api.listPages.mockResolvedValue(PAGES)
  api.journalTags.mockResolvedValue([{ name: 'build', pages: 1 }])
  for (const f of ['notebooks', 'onThisDay', 'listTodos', 'journalTemplates']) api[f].mockResolvedValue([])
  api.journalToday.mockResolvedValue({ did: [], pages: [] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const show = () => render(<MemoryRouter><AppContext.Provider value={{ refreshKey: 0, changed: vi.fn(), showToast: vi.fn(), openPanel: vi.fn() }}>
  <JournalList /></AppContext.Provider></MemoryRouter>)
const lastAsk = () => api.listPages.mock.calls.at(-1)[0]

describe('the journal', () => {
  it('lists the pages, pinned first, each under its day', async () => {
    show()
    expect(await screen.findByText('Primed the Zero')).toBeTruthy()
    const headings = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(headings[0]).toMatch(/Pinned/)
    expect(headings.some((h) => /20 October/.test(h))).toBe(true)
  })

  it('a tag, a mood and "All" each ask for the right pages', async () => {
    show()
    await screen.findByText('Primed the Zero')
    fireEvent.click(screen.getByRole('button', { name: /#build/ }))
    await waitFor(() => expect(lastAsk()).toMatchObject({ tag: 'build', mood: '' }))
    fireEvent.click(screen.getByRole('button', { name: 'Great days' }))
    await waitFor(() => expect(lastAsk()).toMatchObject({ tag: 'build', mood: 'great' }))
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    await waitFor(() => expect(lastAsk()).toMatchObject({ tag: '', mood: '', private: false }))
  })

  it('searching asks once you stop typing', async () => {
    show()
    await screen.findByText('Primed the Zero')
    fireEvent.change(screen.getByLabelText('Search the journal'), { target: { value: 'zero' } })
    await waitFor(() => expect(lastAsk()).toMatchObject({ q: 'zero' }))
  })

  it('private pages only when asked, with a word when there are none', async () => {
    show()
    await screen.findByText('Primed the Zero')
    api.listPages.mockResolvedValue([])
    fireEvent.click(screen.getByRole('button', { name: /Private/ }))
    await waitFor(() => expect(lastAsk()).toMatchObject({ private: true }))
    expect(await screen.findByText(/No private pages/)).toBeTruthy()
  })
})
