import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useGarden, useUpdateGarden, useDeleteGarden } from '../hooks/useGardens';
import { useBeds, useDeleteBed } from '../hooks/useBeds';

const WMO: Record<number, string> = {
  0:'Clear sky ☀️',1:'Mainly clear 🌤',2:'Partly cloudy ⛅',3:'Overcast ☁️',
  45:'Fog 🌫',48:'Icy fog 🌫',51:'Light drizzle 🌦',53:'Drizzle 🌦',55:'Heavy drizzle 🌧',
  61:'Light rain 🌧',63:'Rain 🌧',65:'Heavy rain 🌧',71:'Light snow ❄️',73:'Snow ❄️',
  75:'Heavy snow ❄️',80:'Rain showers 🌦',81:'Rain showers 🌧',82:'Heavy showers 🌧',
  95:'Thunderstorm ⛈',96:'Thunderstorm ⛈',99:'Thunderstorm ⛈',
};

function wmoIcon(desc: string) {
  const c = desc.toLowerCase();
  if (c.includes('thunder')) return '⛈';
  if (c.includes('snow')) return '❄';
  if (c.includes('rain') || c.includes('drizzle') || c.includes('shower')) return '🌧';
  if (c.includes('fog')) return '🌫';
  if (c.includes('overcast')) return '☁';
  if (c.includes('partly') || c.includes('mainly clear')) return '⛅';
  if (c.includes('clear')) return '☀';
  return '🌡';
}

export default function GardenDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const gardenId = parseInt(id!);
  const { data: garden, isLoading } = useGarden(gardenId);
  const { data: beds } = useBeds(gardenId);
  const updateMut = useUpdateGarden();
  const deleteMut = useDeleteGarden();
  const deleteBedMut = useDeleteBed();

  const [form, setForm] = useState({
    name: '', description: '', unit: 'ft', last_frost_date: '',
    watering_frequency_days: '7', water_source: '', zip_code: '',
  });
  const [weather, setWeather] = useState<{ current: any; daily: any[]; frost: any } | null>(null);
  const [weatherErr, setWeatherErr] = useState(false);
  const [fetchingWeather, setFetchingWeather] = useState(false);
  const [fetchMsg, setFetchMsg] = useState('');
  const [bulkMsg, setBulkMsg] = useState('');

  useEffect(() => {
    if (garden) {
      setForm({
        name:                    garden.name,
        description:             garden.description ?? '',
        unit:                    garden.unit,
        last_frost_date:         garden.last_frost_date ?? '',
        watering_frequency_days: String(garden.watering_frequency_days ?? 7),
        water_source:            garden.water_source ?? '',
        zip_code:                garden.zip_code ?? '',
      });
    }
  }, [garden]);

  useEffect(() => {
    if (!garden?.latitude || !garden?.longitude) return;
    const ctrl = new AbortController();
    fetch(`/api/gardens/${gardenId}/weather`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(d => setWeather(d))
      .catch(() => setWeatherErr(true));
    return () => ctrl.abort();
  }, [gardenId, garden?.latitude]);

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    await updateMut.mutateAsync({
      id: gardenId,
      ...form,
      watering_frequency_days: parseInt(form.watering_frequency_days),
    });
  }

  async function handleDelete() {
    if (!confirm(`Delete ${garden?.name}?`)) return;
    await deleteMut.mutateAsync(gardenId);
    nav('/gardens');
  }

  async function handleFetchWeather() {
    setFetchingWeather(true);
    setFetchMsg('Fetching…');
    try {
      const r = await fetch(`/api/gardens/${gardenId}/fetch-weather`, { method: 'POST' });
      const d = await r.json();
      setFetchMsg(d.ok ? `Saved ${d.days_saved} days. 7-day rainfall: ${d.rainfall_7d.total_in}".` : d.error);
    } catch { setFetchMsg('Request failed.'); }
    setFetchingWeather(false);
  }

  async function handleBulkCare(action: string) {
    setBulkMsg('Updating…');
    try {
      const r = await fetch(`/api/gardens/${gardenId}/bulk-care`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const d = await r.json();
      const label = action === 'water' ? 'Watered' : action === 'fertilize' ? 'Fertilized' : 'Mulched';
      setBulkMsg(d.ok ? `${label} ${d.updated} plant(s). Task recorded.` : d.error);
    } catch { setBulkMsg('Request failed.'); }
  }

  if (isLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;
  if (!garden) return <p className="muted" style={{ padding: '2rem' }}>Garden not found.</p>;

  return (
    <>
      <h1>{garden.name}</h1>

      {/* Location & Weather */}
      <section className="weather-section">
        <h2>Location &amp; Weather</h2>
        {garden.city && (
          <div className="location-header">
            <span className="location-label">{garden.city}, {garden.state} {garden.zip_code}</span>
            {garden.usda_zone && <span className="zone-badge">Zone {garden.usda_zone}</span>}
          </div>
        )}
        {garden.zone_temp_range && <p className="muted">Average winter low: {garden.zone_temp_range}.</p>}

        <form onSubmit={async e => { e.preventDefault(); await updateMut.mutateAsync({ id: gardenId, zip_code: form.zip_code }); }}
              style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <input type="text" value={form.zip_code} onChange={e => setForm(f => ({ ...f, zip_code: e.target.value }))}
                 placeholder="Enter ZIP code" maxLength={10}
                 style={{ width: '140px', font: 'inherit', padding: '0.4rem 0.6rem', border: '1px solid #c0d4be', borderRadius: '4px', background: '#fbfefb' }} />
          <button type="submit">{garden.zip_code ? 'Update Location' : 'Set Location'}</button>
        </form>

        {garden.latitude && (
          <div id="weather-widget">
            {weatherErr && <p className="muted">Could not load weather data.</p>}
            {!weather && !weatherErr && <p className="muted">Loading weather…</p>}
            {weather && (
              <>
                <div className="weather-current">
                  <div className="wc-icon">{wmoIcon(weather.current.condition)}</div>
                  <div className="wc-temp">{Math.round(weather.current.temp)}°F</div>
                  <div className="wc-details">
                    <span>{weather.current.condition}</span>
                    <span>💧 {weather.current.humidity}% humidity</span>
                    <span>💨 {Math.round(weather.current.wind_speed)} mph</span>
                  </div>
                </div>
                <div className="frost-row">
                  {weather.frost.last_spring !== 'none' ? (
                    <>
                      <span className="frost-item">🌱 Last spring frost: <strong>{weather.frost.last_spring}</strong></span>
                      <span className="frost-item">🍂 First fall frost: <strong>{weather.frost.first_fall}</strong></span>
                    </>
                  ) : <span className="frost-item">🌴 Frost-free zone</span>}
                </div>
                <div className="forecast-strip">
                  {weather.daily.map((day: any) => {
                    const d = new Date(day.date + 'T12:00:00');
                    const label = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()];
                    return (
                      <div key={day.date} className="forecast-day">
                        <div className="fd-label">{label}</div>
                        <div className="fd-icon">{wmoIcon(day.condition)}</div>
                        <div className="fd-high">{Math.round(day.high)}°</div>
                        <div className="fd-low">{Math.round(day.low)}°</div>
                        {day.precip_prob != null && <div className="fd-precip">💧{day.precip_prob}%</div>}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {/* Edit Garden */}
      <details style={{ marginBottom: '1.5rem' }}>
        <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#3a5c37' }}>Edit Garden</summary>
        <form onSubmit={handleEdit} className="form" style={{ marginTop: '0.75rem' }}>
          <label>Name <input type="text" name="name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required /></label>
          <label>Description <textarea rows={2} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></label>
          <label>Unit
            <select value={form.unit} onChange={e => setForm(f => ({ ...f, unit: e.target.value }))}>
              <option value="ft">Feet (ft)</option>
              <option value="m">Meters (m)</option>
            </select>
          </label>
          <label>Last Frost Date <input type="date" value={form.last_frost_date} onChange={e => setForm(f => ({ ...f, last_frost_date: e.target.value }))} /></label>
          <label>Water Every (days) <input type="number" min={1} max={30} value={form.watering_frequency_days} onChange={e => setForm(f => ({ ...f, watering_frequency_days: e.target.value }))} /></label>
          <label>Water Source
            <select value={form.water_source} onChange={e => setForm(f => ({ ...f, water_source: e.target.value }))}>
              <option value="">— Not set —</option>
              <option value="rain">Rain only</option>
              <option value="hose">Hose</option>
              <option value="drip">Drip irrigation</option>
              <option value="sprinkler">Sprinkler</option>
            </select>
          </label>
          <button type="submit" disabled={updateMut.isPending}>Save Changes</button>
        </form>
      </details>

      {/* Rainfall & Watering */}
      {garden.latitude && (
        <section>
          <h2>Rainfall &amp; Watering</h2>
          <div className="actions">
            <button onClick={handleFetchWeather} disabled={fetchingWeather}>Fetch Weather History</button>
            {fetchMsg && <span className="muted"> {fetchMsg}</span>}
          </div>
        </section>
      )}

      {/* Bulk Care */}
      <section>
        <h2>Bulk Care</h2>
        <p className="muted">Mark all plants in all beds as cared for today:</p>
        <div className="actions">
          <button onClick={() => handleBulkCare('water')}>Water All</button>
          <button onClick={() => handleBulkCare('fertilize')}>Fertilize All</button>
          <button onClick={() => handleBulkCare('mulch')}>Mulch All</button>
        </div>
        {bulkMsg && <div className="muted">{bulkMsg}</div>}
      </section>

      {/* Beds */}
      <h2>Beds in this Garden</h2>
      {beds && beds.length > 0 ? (
        <ul className="card-list">
          {beds.map(b => (
            <li key={b.id} className="card">
              <Link to={`/beds/${b.id}`}>{b.name}</Link>
              <span className="muted"> {b.width_ft}×{b.height_ft} {garden.unit}</span>
              <button
                className="btn-danger btn-small"
                style={{ marginLeft: 'auto' }}
                onClick={() => { if (confirm(`Delete bed ${b.name}?`)) deleteBedMut.mutate(b.id); }}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      ) : <p className="muted">No beds in this garden.</p>}

      <div className="actions" style={{ marginTop: '1rem' }}>
        <Link to={`/planner?garden=${garden.id}`} className="btn-small btn-link">Open Planner →</Link>
      </div>
      <div className="actions">
        <button className="btn-danger" onClick={handleDelete}>Delete Garden</button>
      </div>
      <p><Link to="/gardens">← Back to Gardens</Link></p>
    </>
  );
}
