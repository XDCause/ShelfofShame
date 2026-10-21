import { MODULES, moduleFor } from '../modules/index.js'

// Each main page's banner and colour (the hobbies' are in their manifests: hue, banner). A banner shows
// your own picture for the area if you've added one (core/banners.js), or a drawn landscape.
export const CORE_AREAS = {
  home: { hue: '#84a85c', banner: { scene: 'peaks', seed: 3 } },
  journal: { hue: '#8f9f6a', banner: { scene: 'forest', seed: 11, time: 'dawn', extras: ['fog'], tagline: 'Capture the moments that matter.' } },
  calendar: { hue: '#6f93a8', banner: { scene: 'peaks', seed: 5, time: 'blue', extras: ['distant', 'stars', 'moon', 'lake', 'trees'], tagline: "What's ahead, and what happened." } },
  goals: { hue: '#c9963f', banner: { scene: 'peaks', seed: 21, extras: ['snow', 'birds'], tagline: 'Small steps, steady climbs.' } },
  supplies: { hue: '#c9963f', banner: { scene: 'hills', seed: 8, extras: ['clouds', 'rays', 'trees'], tagline: 'Everything on the shelf, and what to top up.' } },
  wishlist: { hue: '#c0653f', banner: { scene: 'hills', seed: 29, time: 'dawn', extras: ['clouds', 'birds'], tagline: 'Things worth saving up for.' } },
  hobbies: { hue: '#84a85c', banner: { scene: 'forest', seed: 33, extras: ['lake', 'birds'], tagline: 'Everything you do off the clock.' } },
}

// The area a page belongs to: a hobby, or one of the core pages above (only their top pages - an open
// journal page or goal is for writing, not a banner).
const BANNER_TABS = ['/goals/todo', '/journal/calendar', '/journal/map', '/journal/insights']

export function areaFor(pathname) {
  const module = moduleFor(pathname)
  if (module) return { id: module.id, name: module.name, hue: module.hue, banner: module.banner }
  const top = pathname.split('/')[1] || 'home'
  // A core area's own page has its banner; deeper pages (a goal, a journal page) don't - except the tabs' pages.
  if (!CORE_AREAS[top] || (pathname.split('/').length > 2 && !BANNER_TABS.includes(pathname))) return null
  return { id: top, ...CORE_AREAS[top] }
}

export const hueOf = (id) => CORE_AREAS[id]?.hue ?? MODULES.find((m) => m.id === id)?.hue ?? CORE_AREAS.home.hue
