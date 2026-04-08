import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useGardens, useDashboard, useWateringStatus, useSetDefaultGarden } from '../hooks/useGardens';
import ChatWidget from '../components/ChatWidget';

// ── WMO weather code descriptions ─────────────────────────────────────────────
const WMO: Record<number, string> = {
  0: 'Clear sky ☀️', 1: 'Mainly clear 🌤', 2: 'Partly cloudy ⛅', 3: 'Overcast ☁️',
  45: 'Fog 🌫', 48: 'Icy fog 🌫',
  51: 'Light drizzle 🌦', 53: 'Drizzle 🌦', 55: 'Heavy drizzle 🌧',
  61: 'Light rain 🌧', 63: 'Rain 🌧', 65: 'Heavy rain 🌧',
  71: 'Light snow ❄️', 73: 'Snow ❄️', 75: 'Heavy snow ❄️',
  80: 'Rain showers 🌦', 81: 'Rain showers 🌧', 82: 'Heavy showers 🌧',
  85: 'Snow showers 🌨', 86: 'Heavy snow showers 🌨',
  95: 'Thunderstorm ⛈', 96: 'Thunderstorm ⛈', 99: 'Thunderstorm ⛈',
};

// ── Weather card ──────────────────────────────────────────────────────────────
function WeatherCard({ lat, lon }: { lat: number; lon: number }) {
  const [weather, setWeather] = useState<{
    temp: string; feels: string | null; wind: string | null; precip: string | null; desc: string;
  } | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const url =
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&current=temperature_2m,apparent_temperature,precipitation,weathercode,windspeed_10m` +
      `&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=auto`;

    fetch(url, { signal: controller.signal })
      .then(r => r.json())
      .then(data => {
        const c = data.current ?? {};
        setWeather({
          temp:   c.temperature_2m != null ? `${Math.round(c.temperature_2m)}°F` : '—',
          feels:  c.apparent_temperature != null ? `${Math.round(c.apparent_temperature)}°F` : null,
          wind:   c.windspeed_10m != null ? `${Math.round(c.windspeed_10m)} mph` : null,
          precip: c.precipitation != null ? `${c.precipitation} in` : null,
          desc:   WMO[c.weathercode] ?? 'Unknown',
        });
      })
      .catch(() => setError(true));

    return () => controller.abort();
  }, [lat, lon]);

  return (
    <div className="info-card" id="weather-card">
      <div className="info-card__header">🌤 Current Weather</div>
      <div className="info-card__body">
        {error ? (
          <span className="muted" style={{ fontSize: '0.82rem' }}>Weather unavailable</span>
        ) : !weather ? (
          <span className="muted" style={{ fontSize: '0.85rem' }}>Loading…</span>
        ) : (
          <>
            <div className="weather-main">
              <span className="weather-temp">{weather.temp}</span>
              <span className="weather-desc">{weather.desc}</span>
            </div>
            <div className="weather-details">
              {[
                weather.feels ? `Feels like ${weather.feels}` : null,
                weather.wind  ? `Wind ${weather.wind}`        : null,
                weather.precip ? `Precip ${weather.precip}`   : null,
              ].filter(Boolean).join(' · ')}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Watering status card ──────────────────────────────────────────────────────
const URGENCY: Record<string, { icon: string; text: string; cls: string }> = {
  urgent:      { icon: '🔴', text: 'Urgent',      cls: 'watering-urgent' },
  water_today: { icon: '🟡', text: 'Water today', cls: 'watering-today' },
  consider:    { icon: '🟢', text: 'Check soil',  cls: 'watering-consider' },
  ok:          { icon: '✅', text: 'OK',           cls: 'watering-ok' },
};

function WateringCard({ gardenId }: { gardenId: number }) {
  const { data, isLoading, isError } = useWateringStatus(gardenId);

  return (
    <div className="info-card" id="watering-card">
      <div className="info-card__header">💧 Watering Status</div>
      <div className="info-card__body">
        {isLoading && <span className="muted" style={{ fontSize: '0.85rem' }}>Loading…</span>}
        {isError  && <span className="muted" style={{ fontSize: '0.82rem' }}>Watering status unavailable</span>}
        {data && (!data.beds || data.beds.length === 0) && (
          <span className="muted" style={{ fontSize: '0.85rem' }}>Add plants to beds to see watering status.</span>
        )}
        {data && data.beds && data.beds.map((b: any) => {
          const u = URGENCY[b.label] ?? URGENCY.ok;
          const dsw = b.days_since_watered >= 99 ? 'Never' : `${b.days_since_watered}d ago`;
          return (
            <div key={b.bed_name} className={`watering-row ${u.cls}`}>
              <span className="watering-icon">{u.icon}</span>
              <div className="watering-info">
                <span className="watering-bed">{b.bed_name}</span>
                <span className="watering-detail">{u.text} · Last watered: {dsw}</span>
              </div>
              <span className="watering-score">{b.urgency_score}</span>
            </div>
          );
        })}
        {data && !data.has_weather_data && (
          <p className="watering-tip muted">Tip: fetch weather history on the garden page to improve accuracy.</p>
        )}
        {data && data.forecast_today && data.forecast_today.precip_prob > 60 && (
          <p className="watering-tip muted">🌧 {data.forecast_today.precip_prob}% chance of rain today.</p>
        )}
      </div>
    </div>
  );
}

// ── Dashboard page ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { data: gardens, isLoading: gardensLoading } = useGardens();
  const setDefaultMut = useSetDefaultGarden();

  // Resolve selected garden from localStorage (fallback: first garden)
  const [selectedId, setSelectedId] = useState<number | undefined>(() => {
    const stored = localStorage.getItem('defaultGardenId');
    return stored ? parseInt(stored, 10) : undefined;
  });

  const selected = gardens?.find(g => g.id === selectedId) ?? gardens?.[0];
  const effectiveId = selected?.id;

  const { data: dash } = useDashboard(effectiveId);

  function handleGardenChange(id: number) {
    setSelectedId(id);
    localStorage.setItem('defaultGardenId', String(id));
    setDefaultMut.mutate(id);
  }

  if (gardensLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;

  // ── No gardens yet ───────────────────────────────────────────────────────────
  if (!gardens || gardens.length === 0) {
    return (
      <>
        <div className="getting-started">
          <div className="getting-started__icon">🌱</div>
          <h2>Welcome to Garden Planner</h2>
          <p>Create your first garden to get started tracking beds, plants, and tasks.</p>
          <Link to="/gardens" className="btn">→ Create Your First Garden</Link>
        </div>
        <ChatWidget />
      </>
    );
  }

  return (
    <>
      {/* Garden selector bar */}
      <div className="garden-selector-bar">
        <span className="garden-selector-label">Viewing:</span>
        <select
          className="garden-selector-select"
          value={effectiveId ?? ''}
          onChange={e => handleGardenChange(parseInt(e.target.value, 10))}
        >
          {gardens.map(g => (
            <option key={g.id} value={g.id}>
              {g.name}{g.city ? ` · ${g.city}` : ''}
            </option>
          ))}
        </select>
        {selected?.usda_zone && (
          <span className="garden-selector-meta">Zone {selected.usda_zone}</span>
        )}
        {selected?.last_frost_date && (
          <span className="garden-selector-meta">
            Last frost {new Date(selected.last_frost_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </span>
        )}
      </div>

      {/* Nav tiles */}
      <nav className="nav-tiles" aria-label="Quick navigation">
        {[
          { to: '/gardens', icon: '🏡', label: 'Gardens',  desc: 'Manage your spaces' },
          { to: '/planner', icon: '🗺',  label: 'Planner',  desc: '2D drag-and-drop layout' },
          { to: '/beds',    icon: '🛏',  label: 'Beds',     desc: 'Raised beds & plots' },
          { to: '/plants',  icon: '🌿',  label: 'Plants',   desc: 'Track what you\'re growing' },
          { to: '/tasks',   icon: '✅',  label: 'Tasks',    desc: 'Watering, fertilizing & more' },
          { to: '/library', icon: '📚',  label: 'Library',  desc: 'Plant references' },
        ].map(t => (
          <Link key={t.to} to={t.to} className="nav-tile">
            <span className="nav-tile__icon">{t.icon}</span>
            <span className="nav-tile__label">{t.label}</span>
            <span className="nav-tile__desc">{t.desc}</span>
          </Link>
        ))}
      </nav>

      {/* Metrics row */}
      {dash && (
        <div className="metric-row">
          <Link to="/beds"   className="metric-card">
            <span className="metric-card__num">{dash.metrics.bed_count}</span>
            <span className="metric-card__label">Beds</span>
          </Link>
          <Link to="/plants" className="metric-card">
            <span className="metric-card__num">{dash.metrics.plant_count}</span>
            <span className="metric-card__label">Plants</span>
          </Link>
          <Link to="/plants" className="metric-card">
            <span className="metric-card__num">{dash.metrics.plants_active}</span>
            <span className="metric-card__label">Active</span>
          </Link>
          <Link to="/tasks"  className="metric-card">
            <span className="metric-card__num">{dash.metrics.task_count}</span>
            <span className="metric-card__label">Open Tasks</span>
          </Link>
          <Link to="/tasks"  className={`metric-card${dash.metrics.overdue_tasks > 0 ? ' metric-card--alert' : ''}`}>
            <span className="metric-card__num">{dash.metrics.overdue_tasks}</span>
            <span className="metric-card__label">Overdue</span>
          </Link>
        </div>
      )}

      {/* Quick actions */}
      <div className="quick-actions">
        <Link to="/tasks"   className="btn btn--ghost">+ Add Task</Link>
        <Link to="/plants"  className="btn btn--ghost">+ Add Plant</Link>
        <Link to="/beds"    className="btn btn--ghost">+ Add Bed</Link>
        {effectiveId && (
          <Link to={`/planner?garden=${effectiveId}`} className="btn btn--ghost">Open Planner</Link>
        )}
      </div>

      {/* Info row: weather + season */}
      <div className="info-row">
        {selected?.latitude && selected.longitude && (
          <WeatherCard lat={selected.latitude} lon={selected.longitude} />
        )}
        {dash && (
          <div className="info-card season-card">
            <div className="info-card__header">{dash.season_icon} {dash.season} · {dash.hint_action}</div>
            <div className="info-card__body">
              <p style={{ marginBottom: '0.4rem' }}>{dash.hint_text}</p>
              <p style={{ fontSize: '0.8rem', color: '#5a7a57' }}>
                <strong>Good to plant:</strong> {dash.hint_crops}
              </p>
              {dash.frost_context && (
                <p style={{ fontSize: '0.78rem', color: '#7a9a77', marginTop: '0.3rem' }}>
                  🌡 {dash.frost_context}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Watering status */}
      {effectiveId && <WateringCard gardenId={effectiveId} />}

      {/* Three-column content */}
      {dash && (
        <div className="dash-columns dash-columns--3">
          <section className="dash-col">
            <h2>Upcoming Tasks</h2>
            {dash.upcoming_tasks.length > 0 ? (
              <ul className="card-list">
                {dash.upcoming_tasks.map(t => (
                  <li key={t.id} className="card">
                    <span className="task-title">{t.title}</span>
                    {t.task_type && t.task_type !== 'other' && (
                      <span className="muted"> [{t.task_type}]</span>
                    )}
                    {t.due_date && (
                      <span className="muted"> Due {t.due_date}</span>
                    )}
                    {t.plant_name && <span className="muted"> — {t.plant_name}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No upcoming tasks. <Link to="/tasks">Add one →</Link></p>
            )}
            <Link to="/tasks" style={{ fontSize: '0.85rem' }}>View all tasks →</Link>
          </section>

          <section className="dash-col">
            <h2>Recently Added Plants</h2>
            {dash.recent_plants.length > 0 ? (
              <ul className="card-list">
                {dash.recent_plants.map(p => (
                  <li key={p.id} className="card">
                    <Link to={`/plants/${p.id}`}>{p.name}</Link>
                    {p.type && <span className="muted"> ({p.type})</span>}
                    {p.status && p.status !== 'planning' && (
                      <span className={`status-badge status--${p.status}`}>{p.status}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No plants added yet. <Link to="/plants">Add one →</Link></p>
            )}
            <Link to="/plants" style={{ fontSize: '0.85rem' }}>View all plants →</Link>
          </section>

          <section className="dash-col">
            <h2>Recent Activity</h2>
            {dash.recent_activity.length > 0 ? (
              <ul className="activity-list">
                {dash.recent_activity.map(t => (
                  <li key={t.id} className="activity-item">
                    <span className="activity-icon">✅</span>
                    <span className="activity-text">
                      {t.title}
                      {t.completed_date && (
                        <span className="muted activity-date"> {t.completed_date}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No completed tasks in the last 14 days.</p>
            )}
          </section>
        </div>
      )}

      {/* Chat widget */}
      <ChatWidget
        gardenId={effectiveId}
        gardenName={selected?.name}
        zone={selected?.usda_zone ?? undefined}
      />
    </>
  );
}
