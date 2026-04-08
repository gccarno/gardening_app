import { Link, NavLink, useLocation } from 'react-router-dom';

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const isPlanner = pathname.startsWith('/planner');

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
        </ul>
      </nav>

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
