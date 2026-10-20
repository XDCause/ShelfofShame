import { MODULES, moduleFor } from '../modules/index.js'

// Each main page's banner and colour (the hobbies' are in their manifests: hue, banner). A banner shows
// your own picture for the area if you've added one (core/banners.js), or a drawn landscape.
export const CORE_AREAS = {
  home: { hue: '#84a85c', banner: { scene: 'peaks', seed: 3 } },
  journal: { hue: '#8f9f6a', banner: { scene: 'forest', seed: 11, tagline: 'Capture the moments that matter.' } },
  calendar: { hue: '#6f93a8', banner: { scene: 'hills', seed: 5, tagline: "What's ahead, and what happened." } },
  goals: { hue: '#c9963f', banner: { scene: 'peaks', seed: 21, tagline: 'Small steps, steady climbs.' } },
  supplies: { hue: '#c9963f', banner: { scene: 'hills', seed: 8, tagline: 'Everything on the shelf, and what to top up.' } },
  wishlist: { hue: '#c0653f', banner: { scene: 'hills', seed: 29, tagline: 'Things worth saving up for.' } },
  hobbies: { hue: '#84a85c', banner: { scene: 'forest', seed: 33, tagline: 'Everything you do off the clock.' } },
}

// The area a page belongs to: a hobby, or one of the core pages above (only their top pages - an open
// journal page or goal is for writing, not a banner).
export function areaFor(pathname) {
  const module = moduleFor(pathname)
  if (module) return { id: module.id, name: module.name, hue: module.hue, banner: module.banner }
  const top = pathname.split('/')[1] || 'home'
  if (!CORE_AREAS[top] || pathname.split('/').length > 2) return null
  return { id: top, ...CORE_AREAS[top] }
}

export const hueOf = (id) => CORE_AREAS[id]?.hue ?? MODULES.find((m) => m.id === id)?.hue ?? CORE_AREAS.home.hue
