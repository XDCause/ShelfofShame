// The journal look (core/look.js) and its top bar (core/Navigation.jsx JournalNav): the core pages as tabs, and a
// Hobbies menu named after the hobby you're in that lists every hobby and closes on Escape.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import { applyLook, readLook } from '../core/look.js'
import { JournalNav } from '../core/Navigation.jsx'
import { MODULES } from '../modules/index.js'

afterEach(() => { cleanup(); try { localStorage.clear() } catch { /* fine */ } })

const at = (path) => render(<MemoryRouter initialEntries={[path]}><JournalNav env="dev" /></MemoryRouter>)

describe('the journal look', () => {
  it('is botanical unless chosen, and ignores a value it does not know', () => {
    expect(readLook()).toBe('botanical')
    localStorage.setItem('offtheclock.look', 'neon')
    expect(readLook()).toBe('botanical')
    localStorage.setItem('offtheclock.look', 'journal')
    applyLook()
    expect(document.documentElement.dataset.look).toBe('journal')
  })

  it('shows the core pages and marks the one you are on', () => {
    at('/calendar')
    const nav = screen.getByRole('navigation', { name: 'Sections' })
    for (const name of ['Home', 'Goals', 'Journal', 'Calendar', 'Supplies', 'Wishlist']) {
      expect(nav.querySelector(`a[title="${name}"]`)).not.toBeNull()
    }
    expect(nav.querySelector('a[title="Calendar"]').className).toContain('active')
    expect(screen.getByText('dev')).toBeTruthy()
  })

  it("names the hobby you're in and lists every hobby, closing on Escape", () => {
    const hobby = MODULES[0]
    const { container } = at(`/${hobby.id}`)
    const menu = container.querySelector('.jl-hobbies')
    expect(menu.querySelector('summary').textContent).toContain(hobby.name)
    for (const m of MODULES) expect(menu.querySelector(`a[href="/${m.id}"]`)).not.toBeNull()
    expect(menu.querySelector('a[href="/hobbies"]').textContent).toBe('All hobbies')
    menu.open = true
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(menu.open).toBe(false)
  })
})
