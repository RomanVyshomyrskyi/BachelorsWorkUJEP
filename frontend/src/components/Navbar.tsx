/**
 * @module components/Navbar
 * @description Application navigation bar with routing links.
 * Highlights the current active page based on the URL path.
 */

import { Link, useLocation } from 'react-router-dom';

/**
 * Navigation bar component with links to Dashboard and Settings pages.
 *
 * Uses react-router-dom's `useLocation` hook to determine the current
 * route and apply an "active" class to the corresponding link.
 *
 * @component
 * @returns {JSX.Element} The navigation bar element.
 *
 * @example
 * // Used in App.tsx
 * function App() {
 *   return (
 *     <BrowserRouter>
 *       <Navbar />
 *       <Routes>...</Routes>
 *     </BrowserRouter>
 *   );
 * }
 */
function Navbar() {
  const location = useLocation();

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        Superset Dashboard Manager
      </Link>
      <div className="navbar-links">
        <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
          Dashboard
        </Link>
        <Link to="/settings" className={`nav-link ${location.pathname === '/settings' ? 'active' : ''}`}>
          Settings
        </Link>
      </div>
    </nav>
  );
}

export default Navbar;
