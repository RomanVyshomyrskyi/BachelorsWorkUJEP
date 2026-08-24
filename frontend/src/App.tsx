/**
 * @module App
 * @description Root application component with routing and layout.
 * Sets up React Router, toast notifications, and the main navigation structure.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Navbar from './components/Navbar';
import DashboardPage from './pages/DashboardPage';
import SettingsPage from './pages/SettingsPage';

/**
 * Root application component.
 *
 * Configures:
 * - BrowserRouter for client-side routing
 * - Toaster for toast notifications (positioned top-right)
 * - Navbar for navigation
 * - Routes for Dashboard (/) and Settings (/settings) pages
 *
 * @component
 * @returns {JSX.Element} The application root with routing and layout.
 *
 * @example
 * // Rendered in main.tsx
 * createRoot(document.getElementById('root')!).render(
 *   <StrictMode>
 *     <App />
 *   </StrictMode>,
 * );
 */
function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Toaster position="top-right" />
        <Navbar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
