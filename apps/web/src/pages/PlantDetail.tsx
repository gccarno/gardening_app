import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { usePlant, useUpdatePlant, useDeletePlant } from '../hooks/usePlants';

type Tab = 'my-plant' | 'overview' | 'calendar' | 'how-to' | 'companions' | 'soil' | 'nutrition' | 'faqs';

const HOW_TO_STAGES: [string, string, string][] = [
  ['starting', '🪴', 'Starting'],
  ['seedling', '🌱', 'Seedling Stage'],
  ['vegetative', '🌿', 'Vegetative Stage'],
  ['flowering', '🌸', 'Flowering Stage'],
  ['harvest', '🌽', 'Harvest Stage'],
];

export default function PlantDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const plantId = parseInt(id!);
  const { data: plant, isLoading } = usePlant(plantId);
  const updateMut = useUpdatePlant();
  const deleteMut = useDeletePlant();

  const [tab, setTab] = useState<Tab>('my-plant');
  const [form, setForm] = useState({
    name: '', type: '', planted_date: '', expected_harvest: '', notes: '',
  });

  useEffect(() => {
    if (plant) {
      setForm({
        name: plant.name,
        type: plant.type ?? '',
        planted_date: plant.planted_date ?? '',
        expected_harvest: plant.expected_harvest ?? '',
        notes: plant.notes ?? '',
      });
    }
  }, [plant]);

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    await updateMut.mutateAsync({
      id: plantId,
      name: form.name,
      type: form.type || undefined,
      planted_date: form.planted_date || undefined,
      expected_harvest: form.expected_harvest || undefined,
      notes: form.notes || undefined,
    });
  }

  async function handleDelete() {
    if (!confirm(`Delete ${plant?.name}?`)) return;
    await deleteMut.mutateAsync(plantId);
    nav('/plants');
  }

  if (isLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;
  if (!plant) return <p className="muted" style={{ padding: '2rem' }}>Plant not found.</p>;

  const entry = plant.library;
  const nutrition = entry?.nutrition as Record<string, unknown> | undefined;
  const faqs = entry?.faqs as Array<{ q: string; a: string }> | undefined;
  const howToGrow = entry?.how_to_grow as Record<string, string> | undefined;
  const goodNeighbors = entry?.good_neighbors as string[] | undefined;
  const badNeighbors = entry?.bad_neighbors as string[] | undefined;
  const calendarRows = entry?.calendar_rows as Array<Record<string, unknown>> | undefined;
  const selectedZone = entry?.selected_zone as number | undefined;

  const availableTabs: Tab[] = ['my-plant'];
  if (entry) {
    availableTabs.push('overview', 'calendar', 'how-to', 'companions', 'soil');
    if (nutrition) availableTabs.push('nutrition');
    if (faqs?.length) availableTabs.push('faqs');
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
        <h1 style={{ margin: 0 }}>{plant.name}</h1>
        {plant.type && <span className={`lib-badge lib-badge--${plant.type}`}>{plant.type}</span>}
        <span className="lib-badge" style={{ background: '#e8f5e3', color: '#3a6b35' }}>{plant.status || 'planning'}</span>
        {entry && (
          <Link to={`/library/${entry.id}`}
                style={{ fontSize: '0.8rem', padding: '0.2rem 0.65rem', background: '#f0f5ef', border: '1px solid #c0d4be', borderRadius: '4px', color: '#3a5c37', textDecoration: 'none' }}>
            Library Entry →
          </Link>
        )}
      </div>

      {entry && (
        <>
          {entry.scientific_name && <p style={{ color: '#7a907a', fontStyle: 'italic', margin: '0 0 0.6rem' }}>{entry.scientific_name as string}</p>}
          <div className="plant-hero-stats" style={{ marginBottom: '1rem' }}>
            {entry.sunlight && <span className="hero-stat">☀️ {entry.sunlight as string}</span>}
            {entry.water && <span className="hero-stat">💧 {entry.water as string} water</span>}
            {entry.spacing_in && <span className="hero-stat">↔ {entry.spacing_in as number}" spacing</span>}
            {entry.days_to_harvest && <span className="hero-stat">🗓 {entry.days_to_harvest as number} days to harvest</span>}
            {entry.min_zone && entry.max_zone && <span className="hero-stat">🌍 Zones {entry.min_zone as number}–{entry.max_zone as number}</span>}
          </div>
        </>
      )}

      <div className="plant-tabs" style={{ marginTop: '0.5rem' }}>
        {availableTabs.map(t => (
          <button key={t} className={`plant-tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'my-plant' ? 'My Plant' : t === 'how-to' ? 'How to Grow' : t === 'faqs' ? 'FAQs' : t.charAt(0).toUpperCase() + t.slice(1).replace('-', ' ')}
          </button>
        ))}
      </div>

      {/* My Plant */}
      {tab === 'my-plant' && (
        <section style={{ marginTop: '1.25rem' }}>
          <h2>Edit Plant</h2>
          <form onSubmit={handleEdit} className="form">
            <label>Name <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required /></label>
            <label>Type <input type="text" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))} /></label>
            <label>Planted Date <input type="date" value={form.planted_date} onChange={e => setForm(f => ({ ...f, planted_date: e.target.value }))} /></label>
            <label>Expected Harvest <input type="date" value={form.expected_harvest} onChange={e => setForm(f => ({ ...f, expected_harvest: e.target.value }))} /></label>
            <label>Notes <textarea rows={3} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <button type="submit" disabled={updateMut.isPending}>Save Changes</button>
          </form>

          <h2>Beds</h2>
          {plant.bed_assignments && plant.bed_assignments.length > 0 ? (
            <ul className="card-list">
              {plant.bed_assignments.map(ba => (
                <li key={ba.bp_id} className="card">
                  <Link to={`/beds/${ba.bed_id}`}>{ba.bed_name}</Link>
                  {ba.garden_name && <span className="muted"> in {ba.garden_name}</span>}
                </li>
              ))}
            </ul>
          ) : <p className="muted">Not assigned to any bed. Use the Planner to assign.</p>}

          <h2>Tasks</h2>
          {plant.tasks && plant.tasks.length > 0 ? (
            <ul className="card-list">
              {plant.tasks.map(task => (
                <li key={task.id} className={`card ${task.completed ? 'completed' : ''}`}>
                  {task.title}
                  {task.due_date && <span className="muted"> Due {task.due_date}</span>}
                  {task.completed && <span className="badge">Done</span>}
                </li>
              ))}
            </ul>
          ) : <p className="muted">No tasks for this plant.</p>}

          <div className="actions" style={{ marginTop: '1.5rem' }}>
            <button className="btn-danger" onClick={handleDelete}>Delete Plant</button>
          </div>
        </section>
      )}

      {/* Overview */}
      {tab === 'overview' && entry && (
        <section style={{ marginTop: '1.25rem' }}>
          <dl className="details">
            {entry.scientific_name && <><dt>Scientific Name</dt><dd><em>{entry.scientific_name as string}</em></dd></>}
            {entry.sunlight && <><dt>Sunlight</dt><dd>{entry.sunlight as string}</dd></>}
            {entry.water && <><dt>Watering</dt><dd>{entry.water as string}</dd></>}
            {entry.spacing_in && <><dt>Spacing</dt><dd>{entry.spacing_in as number} inches apart</dd></>}
            {entry.days_to_germination && <><dt>Germination</dt><dd>{entry.days_to_germination as number} days</dd></>}
            {entry.days_to_harvest && <><dt>Days to Harvest</dt><dd>{entry.days_to_harvest as number} days</dd></>}
            {entry.min_zone && entry.max_zone && <><dt>Hardiness Zones</dt><dd>USDA Zones {entry.min_zone as number}–{entry.max_zone as number}</dd></>}
            {entry.temp_min_f && entry.temp_max_f && <><dt>Temperature Range</dt><dd>{entry.temp_min_f as number}–{entry.temp_max_f as number}°F</dd></>}
            {entry.soil_ph_min && entry.soil_ph_max && <><dt>Soil pH</dt><dd>{entry.soil_ph_min as number}–{entry.soil_ph_max as number}</dd></>}
            {entry.soil_type && <><dt>Soil Type</dt><dd>{entry.soil_type as string}</dd></>}
            {entry.notes && <><dt>Growing Notes</dt><dd>{entry.notes as string}</dd></>}
            {entry.family && <><dt>Plant Family</dt><dd>{entry.family as string}</dd></>}
            {entry.layer && <><dt>Garden Layer</dt><dd>{entry.layer as string}</dd></>}
            {entry.edible_parts && <><dt>Edible Parts</dt><dd>{entry.edible_parts as string}</dd></>}
            {entry.permapeople_description && <><dt>Description</dt><dd>{entry.permapeople_description as string}</dd></>}
          </dl>
          {entry.permapeople_link && (
            <p style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#7a907a' }}>
              Plant data sourced from <a href={entry.permapeople_link as string} target="_blank" rel="noopener" style={{ color: '#3a6b35' }}>Permapeople.org</a> — licensed under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener" style={{ color: '#3a6b35' }}>CC BY-SA 4.0</a>
            </p>
          )}
        </section>
      )}

      {/* Planting Calendar */}
      {tab === 'calendar' && entry && (
        <section style={{ marginTop: '1.25rem' }}>
          {calendarRows && calendarRows.length > 0 ? (
            <>
              <p className="muted" style={{ marginBottom: '1rem' }}>
                Dates are calculated from your region's average last spring frost.
                {selectedZone && <> <strong>Your garden is in Zone {selectedZone}.</strong></>}
              </p>
              {(() => {
                const myRow = calendarRows.find(r => r.zone === (selectedZone || 6));
                return myRow ? (
                  <div className="cal-highlight">
                    <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Zone {myRow.zone as number} — Your Schedule</h3>
                    <div className="cal-steps">
                      {!!myRow.start_indoors && <div className="cal-step cal-step--indoor"><span className="cal-step-icon">🪴</span><strong>Start Indoors</strong><span>{myRow.start_indoors as string}</span></div>}
                      {!!myRow.direct_sow && <div className="cal-step cal-step--sow"><span className="cal-step-icon">🌱</span><strong>Direct Sow</strong><span>{myRow.direct_sow as string}</span></div>}
                      {!!myRow.transplant && <div className="cal-step cal-step--transplant"><span className="cal-step-icon">🌿</span><strong>Transplant Out</strong><span>{myRow.transplant as string}</span></div>}
                      <div className="cal-step cal-step--frost"><span className="cal-step-icon">❄️</span><strong>Last Frost</strong><span>{myRow.last_frost as string}</span></div>
                      <div className="cal-step cal-step--harvest"><span className="cal-step-icon">🌽</span><strong>First Fall Frost</strong><span>{myRow.first_fall_frost as string}</span></div>
                    </div>
                  </div>
                ) : null;
              })()}
              <h3 style={{ margin: '1.5rem 0 0.75rem', fontSize: '1rem' }}>All Zones Reference</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className="lib-table">
                  <thead>
                    <tr>
                      <th>Zone</th>
                      <th>Last Spring Frost</th>
                      {!!calendarRows[0]?.start_indoors && <th>🪴 Start Indoors</th>}
                      {!!calendarRows[0]?.direct_sow && <th>🌱 Direct Sow</th>}
                      {!!calendarRows[0]?.transplant && <th>🌿 Transplant Out</th>}
                      <th>First Fall Frost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calendarRows.map(row => (
                      <tr key={row.zone as number} style={row.zone === selectedZone ? { background: '#f0f7ef', fontWeight: 600 } : undefined}>
                        <td>Zone {row.zone as number}</td>
                        <td>{row.last_frost as string}</td>
                        {row.start_indoors !== undefined && <td>{row.start_indoors as string}</td>}
                        {row.direct_sow !== undefined && <td>{row.direct_sow as string}</td>}
                        {row.transplant !== undefined && <td>{row.transplant as string}</td>}
                        <td>{row.first_fall_frost as string}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : <p className="muted">Planting calendar data not yet available for this plant.</p>}
        </section>
      )}

      {/* How to Grow */}
      {tab === 'how-to' && entry && (
        <section style={{ marginTop: '1.25rem' }}>
          {howToGrow ? (
            <div className="howto-stages">
              {HOW_TO_STAGES.filter(([key]) => howToGrow[key]).map(([key, icon, label]) => (
                <div key={key} className="howto-stage">
                  <div className="howto-stage-icon">{icon}</div>
                  <div className="howto-stage-body">
                    <h3 className="howto-stage-title">{label}</h3>
                    <p>{howToGrow[key]}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="muted">Growing guide not yet available for this plant.</p>}
        </section>
      )}

      {/* Companions */}
      {tab === 'companions' && entry && (
        <section style={{ marginTop: '1.25rem' }}>
          <div className="companions-grid">
            <div className="companions-col companions-col--good">
              <h3>👍 Good Neighbors</h3>
              {goodNeighbors?.length ? (
                <ul className="companion-list">{goodNeighbors.map((n, i) => <li key={i}>{n}</li>)}</ul>
              ) : <p className="muted">No data available.</p>}
            </div>
            <div className="companions-col companions-col--bad">
              <h3>👎 Bad Neighbors</h3>
              {badNeighbors?.length ? (
                <ul className="companion-list">{badNeighbors.map((n, i) => <li key={i}>{n}</li>)}</ul>
              ) : <p className="muted">No data available.</p>}
            </div>
          </div>
          <p className="muted" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
            Companion planting improves growth, deters pests, and maximizes space. Keep bad neighbors at least 3–4 ft apart when possible.
          </p>
        </section>
      )}

      {/* Soil & Care */}
      {tab === 'soil' && entry && (
        <section style={{ marginTop: '1.25rem' }}>
          {(entry.soil_ph_min || entry.soil_type || entry.temp_min_f) ? (
            <dl className="details">
              {entry.soil_ph_min && entry.soil_ph_max && <><dt>Soil pH</dt><dd>{entry.soil_ph_min as number}–{entry.soil_ph_max as number}</dd></>}
              {entry.soil_type && <><dt>Soil Type</dt><dd>{entry.soil_type as string}</dd></>}
              {entry.temp_min_f && entry.temp_max_f && <><dt>Growing Temp</dt><dd>{entry.temp_min_f as number}–{entry.temp_max_f as number}°F</dd></>}
              {entry.sunlight && <><dt>Sunlight</dt><dd>{entry.sunlight as string}</dd></>}
              {entry.water && <><dt>Watering</dt><dd>{entry.water as string}</dd></>}
              {entry.spacing_in && <><dt>Spacing</dt><dd>{entry.spacing_in as number} inches</dd></>}
              {entry.notes && <><dt>Growing Notes</dt><dd>{entry.notes as string}</dd></>}
            </dl>
          ) : <p className="muted">Soil and care data not yet available for this plant.</p>}
        </section>
      )}

      {/* Nutrition */}
      {tab === 'nutrition' && nutrition && (
        <section style={{ marginTop: '1.25rem' }}>
          <p className="muted" style={{ marginBottom: '1rem' }}>Per serving: <strong>{nutrition.serving_size as string}</strong></p>
          <div className="nutrition-panel">
            <div className="nutrition-facts">
              <div className="nf-header">Nutrition Facts</div>
              <div className="nf-serving">Serving size: {nutrition.serving_size as string}</div>
              <div className="nf-calories-row"><span>Calories</span><span className="nf-calories-val">{nutrition.calories as number}</span></div>
              <div className="nf-divider" />
              <div className="nf-row"><span>Protein</span><span>{nutrition.protein_g as number}g</span></div>
              <div className="nf-row"><span>Carbohydrates</span><span>{nutrition.carbs_g as number}g</span></div>
              <div className="nf-row nf-indent"><span>Dietary Fiber</span><span>{nutrition.fiber_g as number}g</span></div>
              <div className="nf-row"><span>Total Fat</span><span>{nutrition.fat_g as number}g</span></div>
              {(nutrition.vitamins as string[])?.length > 0 && (
                <>
                  <div className="nf-divider" />
                  <div className="nf-vitamins-label">Vitamins &amp; Minerals</div>
                  {(nutrition.vitamins as string[]).map((v, i) => (
                    <div key={i} className="nf-row nf-vitamin">
                      <span>{v.includes(':') ? v.split(':')[0] : v}</span>
                      <span>{v.includes(':') ? v.split(':')[1] : ''}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
            {!!nutrition.notes && (
              <div className="nutrition-notes">
                <h3 style={{ fontSize: '1rem', color: '#3a5c37', marginBottom: '0.5rem' }}>Health Benefits</h3>
                <p>{nutrition.notes as string}</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* FAQs */}
      {tab === 'faqs' && faqs && (
        <section style={{ marginTop: '1.25rem' }}>
          <div className="faq-list">
            {faqs.map((item, i) => (
              <details key={i} className="faq-item" open={i === 0}>
                <summary className="faq-q">{item.q}</summary>
                <p className="faq-a">{item.a}</p>
              </details>
            ))}
          </div>
        </section>
      )}

      <p style={{ marginTop: '2rem' }}><Link to="/plants">← Back to Plants</Link></p>
    </>
  );
}
