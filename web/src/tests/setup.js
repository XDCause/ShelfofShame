import { configure } from '@testing-library/react'

// Run before every web test file (vite.config.js test.setupFiles). jsdom - the pretend browser - has no matchMedia,
// which core/theme.js asks as soon as it loads ("is the device set to dark?"): answer "light", like a fresh browser.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => false,
  })
}

// findBy... / waitFor wait up to 5 s (not 1): with 45 test files run side by side with the API and browser tests, a
// busy PC took over a second to load a lazy page and a different test failed on each run (2026-11-18).
configure({ asyncUtilTimeout: 5000 })
