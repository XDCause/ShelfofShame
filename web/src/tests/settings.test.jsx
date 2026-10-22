// Settings (components/SettingsPanel.jsx): Appearance (light / dark / system, your name), Backups (the last one, Back
// up now), and System (components/SystemStatus.jsx: each check's state and what to do). The API is faked.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { Appearance, Backups } from '../components/SettingsPanel.jsx'
import SystemStatus, { SystemWarning } from '../components/SystemStatus.jsx'
import { AppContext } from '../core/app-context.js'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, updateSettings: vi.fn(), backups: vi.fn(), backUpNow: vi.fn(), system: vi.fn() } }
})
beforeEach(() => { try { localStorage.clear() } catch { /* fine */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Appearance', () => {
  it('switches light and dark, and remembers it on this device', () => {
    render(<Appearance settings={{ your_name: 'Sam' }} onSettings={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'System' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('offtheclock.theme')).toBe('dark')
    expect(screen.getByRole('button', { name: 'Dark' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it("saves the name Home greets, only when it changed", async () => {
    api.updateSettings.mockResolvedValue({ your_name: 'Alex' })
    const onSettings = vi.fn()
    render(<Appearance settings={{ your_name: 'Sam' }} onSettings={onSettings} />)
    const name = screen.getByLabelText('Your name')
    fireEvent.blur(name)
    expect(api.updateSettings).not.toHaveBeenCalled()
    fireEvent.change(name, { target: { value: 'Alex' } })
    fireEvent.blur(name)
    await waitFor(() => expect(api.updateSettings).toHaveBeenCalledWith({ your_name: 'Alex' }))
    expect(onSettings).toHaveBeenCalledWith({ your_name: 'Alex' })
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

  it("Home's warning shows only what needs a look, and opens Settings", async () => {
    api.system.mockResolvedValue({ ...CHECKS, attention: [CHECKS.checks[1]] })
    const openPanel = vi.fn()
    render(<AppContext.Provider value={{ refreshKey: 0, openPanel }}><SystemWarning /></AppContext.Provider>)
    expect(await screen.findByText(/Drive upload: 2 not uploaded yet/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Open the System panel ›' }))
    expect(openPanel).toHaveBeenCalledWith('settings')
    cleanup()
    api.system.mockResolvedValue({ worst: 'ok', checks: [], attention: [] })
    const { container } = render(<AppContext.Provider value={{ refreshKey: 0, openPanel }}><SystemWarning /></AppContext.Provider>)
    await waitFor(() => expect(api.system).toHaveBeenCalled())
    expect(container.textContent).toBe('')
  })
})
