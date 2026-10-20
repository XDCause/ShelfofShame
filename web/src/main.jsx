import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App.jsx'
import { applyTheme } from './core/theme.js'
// The two typefaces, bundled with the app (no outside font site): Fraunces for titles, Manrope for text.
import '@fontsource-variable/fraunces/full.css'
import '@fontsource-variable/manrope'
import './styles.css'

applyTheme() // light or dark before the first paint (core/theme.js)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
