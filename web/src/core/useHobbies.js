import { useMemo } from 'react'
import { MODULES } from '../modules/index.js'
import { orderModules } from '../modules/order.js'
import { useApp } from './app-context.js'

// Every hobby in the order the user wants: favourites first, then A-Z (modules/order.js). Use this for any list of hobbies.
export function useHobbies() {
  const stars = useApp()?.settings?.favourite_hobbies      // (no app around, e.g. in a test: just A-Z)
  return useMemo(() => orderModules(MODULES, stars), [stars])
}
