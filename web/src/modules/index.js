// Every hobby module. A module is one manifest:
//   id        its address: /<id>/<page path>
//   name      what it's called (Shelf of Shame); `what` says what it is (Model kits)
//   Icon      its icon in the sidebar
//   pages     [{path, label, Icon, render(app)}] - render gets the app context (core/app-context.js)
//   HomeCard  its card on the Home page
// Adding a hobby = adding a folder here and one line below. See docs/ROADMAP.md.
import models from './models/manifest.jsx'

export const MODULES = [models]

export const moduleFor = (pathname) => MODULES.find((m) => pathname === `/${m.id}` || pathname.startsWith(`/${m.id}/`))
export const pageFor = (pathname) => {
  const module = moduleFor(pathname)
  return module && module.pages.find((p) => pathname.startsWith(`/${module.id}/${p.path}`))
}
