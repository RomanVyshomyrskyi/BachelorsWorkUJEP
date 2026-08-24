/**
 * @module main
 * @description Application entry point.
 * Mounts the React app to the DOM root element with StrictMode enabled.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/global.css'
import App from './App'

/**
 * Creates and renders the root React application.
 *
 * - Mounts to the DOM element with id "root"
 * - Wraps the app in StrictMode for development-time checks
 * - Imports global CSS styles
 *
 * @example
 * // This file is the entry point configured in vite.config.ts
 * // It is automatically loaded by Vite when the app starts.
 */
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
