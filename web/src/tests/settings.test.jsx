// Settings (components/SettingsPanel.jsx): its groups and the find box, Look and theme (light / dark / system, the
// look), Name and banners, Backups (the last one, Back up now), and System (components/SystemStatus.jsx: each check's state and what to do). The API is faked.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import SettingsPanel, { Backups, LookAndTheme, NameAndBanners } from '../components/SettingsPanel.jsx'
import SystemStatus, { SystemWarning, useSystemAttention } from '../components/SystemStatus.jsx'
import { AppContext } from '../core/app-context.js'

// How Home uses it (behind the "!"): the hook asks, the warning shows.
const HomeWarning = () => <SystemWarning data={useSystemAttention()} />

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, updateSettings: vi.fn(), backups: vi.fn(), backUpNow: vi.fn(), system: vi.fn(),
    checkSystem: vi.fn() } }
})
beforeEach(() => { try { localStorage.clear() } catch { /* fine */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Look and theme, name', () => {
  it('switches light and dark, and remembers it on this device', () => {
    render(<LookAndTheme />)
    expect(screen.getByRole('button', { name: 'System' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('offtheclock.theme')).toBe('dark')
    expect(screen.getByRole('button', { name: 'Dark' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('switches the look between botanical and journal, and remembers it on this device', () => {
    render(<LookAndTheme />)
    expect(screen.getByRole('button', { name: 'Botanical' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Journal' }))
    expect(document.documentElement.dataset.look).toBe('journal')
    expect(localStorage.getItem('offtheclock.look')).toBe('journal')
    expect(screen.getByRole('button', { name: 'Journal' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Botanical' }))
    expect(document.documentElement.dataset.look).toBe('botanical')
  })

  it("saves the name Home greets, only when it changed", async () => {
    api.updateSettings.mockResolvedValue({ your_name: 'Alex' })
    const onSettings = vi.fn()
    render(<NameAndBanners settings={{ your_name: 'Sam' }} onSettings={onSettings} />)
    const name = screen.getByLabelText('Your name')
    fireEvent.blur(name)
    expect(api.updateSettings).not.toHaveBeenCalled()
    fireEvent.change(name, { target: { value: 'Alex' } })
    fireEvent.blur(name)
    await waitFor(() => expect(api.updateSettings).toHaveBeenCalledWith({ your_name: 'Alex' }))
    expect(onSettings).toHaveBeenCalledWith({ your_name: 'Alex' })
  })
})

describe('The panel', () => {
  const LOOKUPS = { brands: [{ id: 1, name: 'Tamiya', uses: 3 }], categories: [], locations: [] }
  const panel = (props = {}) => render(<SettingsPanel lookups={LOOKUPS} settings={{ default_shop: 'Hobbyrama' }}
    onClose={vi.fn()} onSettings={vi.fn()} onListsChanged={vi.fn()} {...props} />)

  it('groups the rows, says how things are while closed, and finds a setting by what it is for', async () => {
    api.system.mockResolvedValue({ worst: 'warn', checks: [], attention: [{ key: 'disk' }, { key: 'steam' }] })
    api.backups.mockResolvedValue({ available: true, backups: [{ name: 'b.dump', created_at: '2026-11-15T20:00:00' }] })
    panel()
    for (const group of ['This device', 'You', 'Shopping', 'Lists', 'Your data', 'Behind the scenes']) {
      expect(screen.getByRole('heading', { name: group })).toBeTruthy()
    }
    expect(screen.getByText('Hobbyrama')).toBeTruthy()                        // Default shop's row says which
    expect(await screen.findByText('2 to look at')).toBeTruthy()             // System: what needs a look
    expect(await screen.findByText('last 15 Nov 2026')).toBeTruthy()         // Backups: the last one
    fireEvent.change(screen.getByLabelText('Find a setting'), { target: { value: 'excel' } })
    expect(screen.queryByRole('heading', { name: 'Shopping' })).toBeNull()
    expect(screen.getByText('Export to CSV')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: 'Download CSV', hidden: true })).toHaveLength(7)   // the only match: opened
    fireEvent.change(screen.getByLabelText('Find a setting'), { target: { value: 'zebra' } })
    expect(screen.getByText('No setting matches "zebra".')).toBeTruthy()
  })

  it('opens at the row it was asked for', () => {
    api.system.mockResolvedValue({ worst: 'ok', checks: [], attention: [] })
    api.backups.mockResolvedValue({ available: false, backups: [] })
    const { container } = panel({ section: 'brands' })
    expect(container.ownerDocument.querySelector('details.lookup[open]').textContent).toContain('Tamiya')
  })
})

describe('Backups', () => {
  const LIST = { available: true, keep: 14, log: [], backups: [
    { name: 'hobby_inventory_20261022_020000.dump', size: 11864682, created_at: '2026-10-22T02:00:00' },
    { name: 'hobby_inventory_20261021_020000.dump', size: 11800000, created_at: '2026-10-21T02:00:00' },
  ] }

  it('shows the last backup, and Back up now makes one', async () => {
    api.backups.mockResolvedValue(LIST)
    api.backUpNow.mockResolvedValue({ name: 'hobby_inventory_20261022_101500.dump', size: 11870000 })
    render(<Backups />)
    expect(await screen.findByText('22 Oct 2026')).toBeTruthy()
    expect(screen.getByText(/the newest 14 are kept/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Back up now' }))
    expect(await screen.findByText('Backed up: hobby_inventory_20261022_101500.dump (11592 KB).')).toBeTruthy()
    expect(api.backups).toHaveBeenCalledTimes(2)                                // (the list again, with the new one)
  })

  it('says why when the backup fails, and when the folder is missing', async () => {
    api.backups.mockResolvedValueOnce(LIST)
    api.backUpNow.mockRejectedValue(new Error("The backup failed: the new backup can't be read back"))
    render(<Backups />)
    fireEvent.click(await screen.findByRole('button', { name: 'Back up now' }))
    expect(await screen.findByText(/can't be read back/)).toBeTruthy()
    cleanup()
    api.backups.mockResolvedValue({ available: false, backups: [], log: [] })
    render(<Backups />)
    expect(await screen.findByText(/isn't connected to the app/)).toBeTruthy()
  })
})

describe('System', () => {
  const CHECKS = { worst: 'bad', checks: [
    { key: 'backup', label: 'Backup', state: 'ok', detail: 'Last backup 3 hours ago (read back and checked)' },
    { key: 'drive_sync', label: 'Drive upload', state: 'bad', detail: '2 not uploaded yet (2 nights running)',
      fix: 'Is Google Drive for desktop running and signed in?' },
    { key: 'steam', label: 'Steam sync', state: 'off', detail: 'No Steam key or profile set' },
  ] }

  it('lists every check with its state and what to do', async () => {
    api.system.mockResolvedValue(CHECKS)
    render(<SystemStatus />)
    expect(await screen.findByText('Drive upload')).toBeTruthy()
    expect(screen.getByText('Problem')).toBeTruthy()
    expect(screen.getByText('OK')).toBeTruthy()
    expect(screen.getByText('Off')).toBeTruthy()
    expect(screen.getByText('Is Google Drive for desktop running and signed in?')).toBeTruthy()
  })

  it('Check now asks the failing websites again and reads everything again', async () => {
    const failing = { worst: 'warn', checks: [{ key: 'sites', label: 'Website check', state: 'warn', detail: '1 site failing' }] }
    const fine = { worst: 'ok', checks: [{ key: 'sites', label: 'Website check', state: 'ok', detail: 'every site fine' }] }
    api.system.mockResolvedValueOnce(failing).mockResolvedValue(fine)
    api.checkSystem.mockResolvedValue({ rechecking: ['Open-Meteo'] })
    render(<SystemStatus />)
    expect(await screen.findByText('1 site failing')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Check now' }))
    expect(await screen.findByText('every site fine')).toBeTruthy()
    expect(api.checkSystem).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/^Checked at /)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Check now' }).disabled).toBe(false)
  })

  it("Home's warning shows only what needs a look, and opens Settings", async () => {
    api.system.mockResolvedValue({ ...CHECKS, attention: [CHECKS.checks[1]] })
    const openPanel = vi.fn()
    render(<AppContext.Provider value={{ refreshKey: 0, openPanel }}><HomeWarning /></AppContext.Provider>)
    expect(await screen.findByText(/Drive upload: 2 not uploaded yet/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Open the System panel ›' }))
    expect(openPanel).toHaveBeenCalledWith('settings', { section: 'system' })     // opened at System
    cleanup()
    api.system.mockResolvedValue({ worst: 'ok', checks: [], attention: [] })
    const { container } = render(<AppContext.Provider value={{ refreshKey: 0, openPanel }}><HomeWarning /></AppContext.Provider>)
    await waitFor(() => expect(api.system).toHaveBeenCalled())
    expect(container.textContent).toBe('')
  })
})
