import { lazy } from 'react'

// A hobby's page or panel, loaded the first time it's shown: its code isn't in the main download, so the app opens
// faster (health check, 2026-10-21 - the main file was 1.3 MB with every hobby in it). App.jsx shows "Loading..."
// for the moment it takes. Home's tiles stay in the main download (each hobby's HomeTiles.jsx).
//   const Dashboard = part(() => import('./ChessViews.jsx'), 'Dashboard')
//   const GamePanel = part(() => import('./GamePanel.jsx'))            // (its default export)
export const part = (load, name = 'default') => lazy(() => load().then((m) => ({ default: m[name] })))
