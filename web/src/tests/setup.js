// Run before every web test file (vite.config.js test.setupFiles). jsdom - the pretend browser - has no matchMedia,
// which core/theme.js asks as soon as it loads ("is the device set to dark?"): answer "light", like a fresh browser.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => false,
  })
}
