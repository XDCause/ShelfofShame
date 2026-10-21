// Goals (core/goals): the sections they're grouped into, the "when" choices, a new goal, and a goal's Next up - ticking
// a step, and putting undated steps in your own order with the arrow keys. The API is faked.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { NextUp } from '../core/goals/GoalPage.jsx'
import GoalsPage from '../core/goals/GoalsPage.jsx'
import { groupGoals, periodChoices } from '../core/goals/goalParts.jsx'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, api: { ...real.api, goals: vi.fn(), addGoal: vi.fn(), orderTodos: vi.fn(), todoDone: vi.fn(), todoUndone: vi.fn(), addTodo: vi.fn() } }
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const app = (over = {}) => ({ refreshKey: 0, openPanel: vi.fn(), changed: vi.fn(), showToast: vi.fn(), ...over })
const goal = (id, title, timeframe, period_start, extra = {}) =>
  ({ goal_id: id, title, timeframe, period_start, status: 'active', hobby: null, progress: null, ...extra })

describe('grouping and the when choices', () => {
  it('puts this year first, then 3-year goals running now, next year, no set time, and past years last', () => {
    const sections = groupGoals([
      goal(1, 'Old', 'year', 2024), goal(2, 'Someday', null, null), goal(3, 'Next', 'year', 2027),
      goal(4, 'Big', 'three_years', 2025), goal(5, 'Now', 'year', 2026),
    ], 2026)
    expect(sections.map((s) => s.goals[0].title)).toEqual(['Now', 'Big', 'Next', 'Someday', 'Old'])
  })
  it('offers this year, the next two, two 3-year spans and no set time - and keeps an old goal\'s own period', () => {
    expect(periodChoices(2026).map((c) => c.label)).toEqual(
      ['This year (2026)', 'Next year (2027)', '2028', '3 years (2026–2028)', '3 years (2027–2029)', 'No set time'])
    const old = periodChoices(2026, { timeframe: 'year', period_start: 2023 })
    expect(old[0]).toMatchObject({ value: 'year:2023', timeframe: 'year', period_start: 2023 })
  })
})

describe('the Goals page', () => {
  const DATA = { this_year: 2026, counts: { active: 2, paused: 0, done: 1, dropped: 0 },
    goals: [goal(1, 'Read 30 books', 'year', 2026), goal(2, 'Finish three kits', 'year', 2026), goal(3, 'Learn the Sicilian', 'year', 2026, { status: 'done' })] }
  const show = (ctx = app()) => render(
    <MemoryRouter initialEntries={['/goals']}><AppContext.Provider value={ctx}>
      <Routes><Route path="/goals" element={<GoalsPage />} /><Route path="/goals/:id" element={<p>the goal's own page</p>} /></Routes>
    </AppContext.Provider></MemoryRouter>)

  it('lists the goals with a count for each status, and a status narrows the list', async () => {
    api.goals.mockResolvedValue(DATA)
    show()
    expect(await screen.findByText('Read 30 books')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Done/ }))
    await waitFor(() => expect(screen.queryByText('Read 30 books')).toBeNull())
    expect(screen.getByText('Learn the Sicilian')).toBeTruthy()
  })

  it('a new goal asks its name and when, then opens its own page', async () => {
    api.goals.mockResolvedValue(DATA)
    api.addGoal.mockResolvedValue({ goal_id: 42 })
    show()
    fireEvent.click((await screen.findAllByRole('button', { name: '+ New goal' }))[0])
    fireEvent.change(screen.getByLabelText("What's the goal?"), { target: { value: 'Hike 300 km' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next year (2027)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(api.addGoal).toHaveBeenCalledWith({ title: 'Hike 300 km', timeframe: 'year', period_start: 2027 }))
    expect(await screen.findByText("the goal's own page")).toBeTruthy()
  })
})

describe("a goal's Next up", () => {
  const G = { goal_id: 7, hobby: null, todos_total: 3, todos_done: 0, todos: [
    { todo_id: 1, title: 'Prime', due_on: null, repeats: 'never' },
    { todo_id: 2, title: 'Paint', due_on: null, repeats: 'never' },
    { todo_id: 3, title: 'Decals', due_on: null, repeats: 'never' },
  ] }

  it('moves an undated step with the arrow keys and saves the new order', async () => {
    api.orderTodos.mockResolvedValue({})
    const reload = vi.fn()
    render(<AppContext.Provider value={app()}><NextUp goal={G} reload={reload} /></AppContext.Provider>)
    fireEvent.keyDown(screen.getByRole('button', { name: /^Move Paint/ }), { key: 'ArrowUp' })
    await waitFor(() => expect(api.orderTodos).toHaveBeenCalledWith([2, 1, 3]))
    expect(reload).toHaveBeenCalled()
    expect(screen.getAllByRole('checkbox').map((c) => c.getAttribute('aria-label'))).toEqual(['Done: Paint', 'Done: Prime', 'Done: Decals'])
    fireEvent.keyDown(screen.getByRole('button', { name: /^Move Decals/ }), { key: 'ArrowDown' })   // (already last: stays)
    await waitFor(() => expect(api.orderTodos).toHaveBeenLastCalledWith([2, 1, 3]))
  })

  it('ticking a step says so, with Undo', async () => {
    api.todoDone.mockResolvedValue({ next: null })
    const ctx = app()
    render(<AppContext.Provider value={ctx}><NextUp goal={G} reload={vi.fn()} /></AppContext.Provider>)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Done: Prime' }))
    await waitFor(() => expect(api.todoDone).toHaveBeenCalledWith(1))
    expect(ctx.showToast).toHaveBeenCalledWith('Done: Prime', expect.objectContaining({ label: 'Undo' }))
  })
})
