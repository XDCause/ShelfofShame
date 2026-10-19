// Every hobby module. A module is one manifest:
//   id        its address: /<id>/<page path>
//   name      what it's called (Board games); `what` says what it's for
//   Icon      its icon in the sidebar and on the Hobbies page
//   pages     [{path, label, Icon, render(app)}] - render gets the app context (core/app-context.js).
//             Two or more pages show as tabs at the top of the hobby.
//   home      its parts of Home: {Tiles (stat tiles, in Home's shared row), Cards (a card or two)}
//   actions   Home's quick actions: [{label, Icon, run(app)}]
//   panels    side panels it adds: {type: Component}; any page opens one with app.openPanel(type, props)
//   underConstruction  true = a placeholder for a hobby still to build (a spanner after its name). Only dev
//                      (and its walk-through copy) shows it: prod's build leaves it out - the sidebar, Hobbies,
//                      Home, pickers and its pages - until the flag comes off. Same code in both; the web image is
//                      built with APP_ENV (docker-compose.yml -> web/Dockerfile -> VITE_APP_ENV).
// Supplies, the wishlist, the journal and the calendar are the core, shared by every hobby.
// Adding a hobby = adding a folder here and one line below. See docs/ROADMAP.md.
import boardgames from './boardgames/manifest.jsx'
import car from './car/manifest.jsx'
import shooting from './shooting/manifest.jsx'
import hiking from './hiking/manifest.jsx'
import gardening from './gardening/manifest.jsx'
import travel from './travel/manifest.jsx'
import chess from './chess/manifest.jsx'
import reading from './reading/manifest.jsx'
import models from './models/manifest.jsx'
import videogames from './videogames/manifest.jsx'
import volleyball from './volleyball/manifest.jsx'

const ALL = [models, boardgames, volleyball, videogames, chess, reading, car, travel, shooting, hiking, gardening]
export const SHOW_UNFINISHED = import.meta.env.VITE_APP_ENV !== 'prod'
export const MODULES = ALL.filter((m) => SHOW_UNFINISHED || !m.underConstruction)

// Every module's panels in one map, for App to open by type.
export const MODULE_PANELS = Object.assign({}, ...MODULES.map((m) => m.panels ?? {}))

export const moduleFor = (pathname) => MODULES.find((m) => pathname === `/${m.id}` || pathname.startsWith(`/${m.id}/`))
export const pageFor = (pathname) => {
  const module = moduleFor(pathname)
  return module && module.pages.find((p) => pathname.startsWith(`/${module.id}/${p.path}`))
}
