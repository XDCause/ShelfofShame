import { createContext, useContext } from 'react'

// What every page and module can use, provided by App:
//   lookups, settings, refreshKey        shared data (refreshKey changes after any edit)
//   changed()                            tell every page something changed (they reload)
//   openItem(id), openModel(id), openAdd(scan)   open a panel
//   openPanel(type, props)               open a panel by type: 'event' or a module's (modules/index.js)
//   openThing(kind, id)                  open what a search result / mention / activity row points at
//   adjusted(before, delta, autoWishId)  after a -/+: shows "Used one ... Undo"
//   showToast(text, ...actions)
export const AppContext = createContext(null)
export const useApp = () => useContext(AppContext)
