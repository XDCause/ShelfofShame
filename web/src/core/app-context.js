import { createContext, useContext } from 'react'

// What every page and module can use, provided by App:
//   lookups, settings, refreshKey        shared data (refreshKey changes after any edit)
//   changed()                            tell every page something changed (they reload)
//   openItem(id), openModel(id), openAdd(scan)   open a panel
//   adjusted(before, delta, autoWishId)  after a -/+: shows "Used one ... Undo"
//   showToast(text, ...actions)
export const AppContext = createContext(null)
export const useApp = () => useContext(AppContext)
