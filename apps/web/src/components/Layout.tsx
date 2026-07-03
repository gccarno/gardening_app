import { useState, useEffect, useRef } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import ThemePanel from './ThemePanel';
import { useAuth } from '../auth/AuthContext';

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const isPlanner = pathname.startsWith('/planner');
  const [showTheme, setShowTheme] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  useEffect(() => {
    if (!showTheme) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        const btn = document.querySelector('.theme-toggle-btn');
        if (btn && btn.contains(e.target as Node)) return;
        setShowTheme(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showTheme]);

  return (
    <>
      <nav>
        <Link to="/planner" className="nav-brand">Garden Planner</Link>
        <ul>
          <li><NavLink to="/gardens">Gardens</NavLink></li>
          <li><NavLink to="/planner">Planner</NavLink></li>
          <li><NavLink to="/plants">Plants</NavLink></li>
          <li><NavLink to="/tasks">Tasks</NavLink></li>
          <li><NavLink to="/library">Library</NavLink></li>
          <li><NavLink to="/identify">Identify</NavLink></li>
        </ul>
        <button
          className="theme-toggle-btn"
          onClick={() => setShowTheme(v => !v)}
          title="Customize theme"
        >🎨</button>
        <button
          className="logout-btn"
          onClick={handleLogout}
          title={user ? `Signed in as ${user.email}` : 'Sign out'}
        >Sign out</button>
      </nav>
      {showTheme && (
        <div ref={panelRef}>
          <ThemePanel onClose={() => setShowTheme(false)} />
        </div>
      )}

      <main className={isPlanner ? 'fullwidth' : undefined}>{children}</main>

      {!isPlanner && (
        <footer className="app-footer">
          <div className="app-footer__inner">
            <span className="app-footer__brand">🌱 Garden Planner</span>
            <nav className="app-footer__links">
              <Link to="/library">Plant Library</Link>
              <Link to="/gardens">My Gardens</Link>
              <a href="https://en.wikipedia.org/wiki/Hardiness_zone" target="_blank" rel="noopener">USDA Zones ↗</a>
              <a href="https://www.almanac.com/gardening/planting-calendar" target="_blank" rel="noopener">Planting Calendar ↗</a>
              <a href="https://open-meteo.com" target="_blank" rel="noopener">Weather via Open-Meteo ↗</a>
            </nav>
          </div>
        </footer>
      )}
    </>
  );
}
