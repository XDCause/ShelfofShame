import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App.jsx'
import AuthGate from './core/auth/AuthGate.jsx'
import { applyLook } from './core/look.js'
import { applyTheme } from './core/theme.js'
// The typefaces, bundled with the app (no outside font site): Playfair Display for titles, Inter for text,
// Caveat for Home's handwritten line; Fraunces for the journal look's headings (core/look.js).
import '@fontsource-variable/playfair-display'
import '@fontsource-variable/inter/opsz.css'
import '@fontsource-variable/caveat'
import '@fontsource-variable/fraunces'
import './styles.css'

applyTheme() // light or dark before the first paint (core/theme.js)
applyLook()  // and the look: botanical or journal (core/look.js)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      {/* signed in first (core/auth): nothing of the app loads until then */}
      <AuthGate><App /></AuthGate>
    </BrowserRouter>
  </StrictMode>,
)
