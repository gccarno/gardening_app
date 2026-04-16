import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useGardens } from '../hooks/useGardens';
import { usePlants, useCreatePlant, useDeletePlant, useSetPlantStatus } from '../hooks/usePlants';
import { useTasks, useToggleTask } from '../hooks/useTasks';
import type { Plant } from '../api/plants';
import { plantImageUrl } from '../utils/images';
import GanttChart, { type GanttRow } from '../components/GanttChart';

type Tab = 'planning' | 'growing' | 'reminder' | 'timeline';

// Group plants by library_id or name and return one GanttRow per group
function groupToGanttRows(plants: Plant[], status: string): GanttRow[] {
  const map = new Map<string, Plant[]>();
  for (const p of plants) {
    const key = p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  }
  return [...map.values()].map(group => {
    // Use earliest planted/transplant dates, latest harvest
    const planted   = group.map(p => p.planted_date).filter(Boolean).sort()[0] ?? null;
    const transplant = group.map(p => p.transplant_date).filter(Boolean).sort()[0] ?? null;
    const harvest   = group.map(p => p.expected_harvest).filter(Boolean).sort().at(-1) ?? null;
    const rep = group[0];
    return {
      id: rep.id,
      name: rep.name,
      count: group.length,
      status,
      planted: planted ?? null,
      harvest: harvest ?? null,
      transplant: transplant ?? null,
      germDays: rep.days_to_germination ?? null,
      daysToHarvest: rep.days_to_harvest ?? null,
      sowIndoorWeeks: rep.sow_indoor_weeks ?? null,
      directSowOffset: rep.direct_sow_offset ?? null,
      transplantOffset: rep.transplant_offset ?? null,
      tempMaxF: rep.temp_max_f ?? null,
      href: `/plants/${rep.id}`,
    };
  });
}

export default function PlantList() {
  const [tab, setTab] = useState<Tab>('planning');
  const [gardenFilter, setGardenFilter] = useState<number | undefined>(undefined);
  const [ganttFilter, setGanttFilter] = useState('all');
  const [addForm, setAddForm] = useState({
    name: '', type: '', notes: '', garden_id: '',
    planted_date: '', expected_harvest: '',
  });

  const { data: gardens } = useGardens();
  const { data: allPlants, isLoading } = usePlants({ garden_id: gardenFilter });
  const { data: tasks } = useTasks();
  const createMut = useCreatePlant();
  const deleteMut = useDeletePlant();
  const statusMut = useSetPlantStatus();
  const toggleTaskMut = useToggleTask();

  const today = new Date().toISOString().slice(0, 10);
  const planningPlants = allPlants?.filter(p => !p.status || p.status === 'planning') ?? [];
  const growingPlants = allPlants?.filter(p => p.status === 'growing') ?? [];
  const pendingTasks = tasks?.filter(t => !t.completed) ?? [];

  const ganttRows: GanttRow[] = [
    ...groupToGanttRows(growingPlants, 'growing'),
    ...groupToGanttRows(planningPlants, 'planning'),
  ];

  // Use the first garden with frost dates for the timeline reference lines
  const frostGarden = gardens?.find(g => g.last_frost_date);
  const lastFrost = frostGarden?.last_frost_date ? new Date(frostGarden.last_frost_date + 'T00:00:00') : null;
  const firstFallFrost = frostGarden?.first_frost_date ? new Date(frostGarden.first_frost_date + 'T00:00:00') : null;

  function handleFormChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setAddForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleAdd(e: React.FormEvent, status: string) {
    e.preventDefault();
    await createMut.mutateAsync({
      name: addForm.name,
      type: addForm.type || undefined,
      notes: addForm.notes || undefined,
      garden_id: addForm.garden_id ? parseInt(addForm.garden_id) : undefined,
      planted_date: addForm.planted_date || undefined,
      expected_harvest: addForm.expected_harvest || undefined,
      status,
    });
    setAddForm(f => ({ ...f, name: '', type: '', notes: '', planted_date: '', expected_harvest: '' }));
  }

  function PlantCard({ plant, tabCtx }: { plant: Plant; tabCtx: Tab }) {
    return (
      <li className="card">
        {plant.image_filename && (
          <img src={plantImageUrl(plant.image_filename) ?? ''} className="plant-card-img" alt={plant.name} />
        )}
        <div className="plant-card-body">
          <Link to={`/plants/${plant.id}`}><strong>{plant.name}</strong></Link>
          {plant.type && <span className="muted">({plant.type})</span>}
          {plant.garden_id && <span className="muted" style={{ fontSize: '0.8rem' }}>📍 {gardens?.find(g => g.id === plant.garden_id)?.name}</span>}
          {tabCtx === 'growing' && plant.planted_date && (
            <span className="muted">planted {new Date(plant.planted_date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
          )}
          {tabCtx === 'growing' && plant.expected_harvest && (() => {
            const daysLeft = Math.round((new Date(plant.expected_harvest + 'T12:00:00').getTime() - Date.now()) / 86400000);
            return <span className="muted" style={daysLeft < 0 ? { color: '#b84040' } : undefined}>harvest {daysLeft < 0 ? `overdue by ${-daysLeft} days` : daysLeft === 0 ? 'today' : `in ${daysLeft} days`}</span>;
          })()}
          {plant.library_id && (
            <Link to={`/library/${plant.library_id}`}
                  style={{ fontSize: '0.78rem', padding: '0.15rem 0.5rem', background: '#f0f5ef', border: '1px solid #c0d4be', borderRadius: '4px', color: '#3a5c37', textDecoration: 'none' }}>
              📖 Library
            </Link>
          )}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          {tabCtx === 'planning' && (
            <button className="btn-small" onClick={() => statusMut.mutate({ id: plant.id, status: 'growing' })}>Plant now →</button>
          )}
          {tabCtx === 'growing' && (
            <button className="btn-small btn-link" onClick={() => statusMut.mutate({ id: plant.id, status: 'planning' })}>← Planning</button>
          )}
          <button className="btn-danger btn-small"
                  onClick={() => { if (confirm(`Delete ${plant.name}?`)) deleteMut.mutate(plant.id); }}>Delete</button>
        </div>
      </li>
    );
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <h1 style={{ margin: 0 }}>Plants</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.9rem', fontWeight: 600, color: '#3a5c37', whiteSpace: 'nowrap' }}>Garden:</label>
          <select
            value={gardenFilter ?? ''}
            onChange={e => setGardenFilter(e.target.value ? parseInt(e.target.value) : undefined)}
            style={{ font: 'inherit', padding: '0.35rem 0.6rem', border: '1px solid #c0d4be', borderRadius: '4px', background: '#fbfefb' }}
          >
            <option value="">All gardens</option>
            {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
      </div>

      <div className="plant-tabs">
        {(['planning', 'growing', 'reminder', 'timeline'] as Tab[]).map(t => (
          <button key={t} className={`plant-tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'reminder' ? 'Reminders' : t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'planning' && planningPlants.length > 0 && <span className="tab-count">{planningPlants.length}</span>}
            {t === 'growing' && growingPlants.length > 0 && <span className="tab-count">{growingPlants.length}</span>}
            {t === 'reminder' && pendingTasks.length > 0 && <span className="tab-count">{pendingTasks.length}</span>}
          </button>
        ))}
      </div>

      {tab === 'planning' && (
        <section>
          <p className="muted" style={{ marginBottom: '1rem' }}>
            Plants you are considering growing. Browse the <Link to="/library">Plant Library</Link> to add plants with full growing info.
          </p>
          {isLoading ? <p className="muted">Loading…</p> : planningPlants.length > 0 ? (
            <ul className="card-list" style={{ marginBottom: '1.5rem' }}>
              {planningPlants.map(p => <PlantCard key={p.id} plant={p} tabCtx="planning" />)}
            </ul>
          ) : <p className="muted" style={{ marginBottom: '1.5rem' }}>No plants in planning yet.</p>}
          <details style={{ maxWidth: '480px' }}>
            <summary style={{ cursor: 'pointer', color: '#3a5c37', fontWeight: 600, marginBottom: '0.5rem' }}>+ Add a Plant to Planning</summary>
            <form onSubmit={e => handleAdd(e, 'planning')} className="form" style={{ marginTop: '0.75rem' }}>
              <label>Garden
                <select name="garden_id" value={addForm.garden_id} onChange={handleFormChange}>
                  <option value="">— unassigned —</option>
                  {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </label>
              <label>Name <input type="text" name="name" value={addForm.name} onChange={handleFormChange} required placeholder="e.g. Tomato" /></label>
              <label>Type <input type="text" name="type" value={addForm.type} onChange={handleFormChange} placeholder="e.g. Vegetable, Herb, Flower" /></label>
              <label>Notes <textarea name="notes" rows={2} value={addForm.notes} onChange={handleFormChange} /></label>
              <button type="submit" disabled={createMut.isPending}>Add to Planning</button>
            </form>
          </details>
        </section>
      )}

      {tab === 'growing' && (
        <section>
          <p className="muted" style={{ marginBottom: '1rem' }}>Plants currently in the ground or a bed.</p>
          {isLoading ? <p className="muted">Loading…</p> : growingPlants.length > 0 ? (
            <ul className="card-list" style={{ marginBottom: '1.5rem' }}>
              {growingPlants.map(p => <PlantCard key={p.id} plant={p} tabCtx="growing" />)}
            </ul>
          ) : <p className="muted" style={{ marginBottom: '1.5rem' }}>No plants growing yet.</p>}
          <details style={{ maxWidth: '480px' }}>
            <summary style={{ cursor: 'pointer', color: '#3a5c37', fontWeight: 600, marginBottom: '0.5rem' }}>+ Add a Growing Plant</summary>
            <form onSubmit={e => handleAdd(e, 'growing')} className="form" style={{ marginTop: '0.75rem' }}>
              <label>Garden
                <select name="garden_id" value={addForm.garden_id} onChange={handleFormChange}>
                  <option value="">— unassigned —</option>
                  {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </label>
              <label>Name <input type="text" name="name" value={addForm.name} onChange={handleFormChange} required placeholder="e.g. Tomato" /></label>
              <label>Type <input type="text" name="type" value={addForm.type} onChange={handleFormChange} placeholder="e.g. Vegetable, Herb, Flower" /></label>
              <label>Planted Date <input type="date" name="planted_date" value={addForm.planted_date} onChange={handleFormChange} /></label>
              <label>Expected Harvest <input type="date" name="expected_harvest" value={addForm.expected_harvest} onChange={handleFormChange} /></label>
              <label>Notes <textarea name="notes" rows={2} value={addForm.notes} onChange={handleFormChange} /></label>
              <button type="submit" disabled={createMut.isPending}>Add to Growing</button>
            </form>
          </details>
        </section>
      )}

      {tab === 'reminder' && (
        <section>
          <h2>Tasks</h2>
          {pendingTasks.length > 0 ? (
            <ul className="card-list" style={{ marginBottom: '1.5rem' }}>
              {pendingTasks.map(task => {
                const overdue = task.due_date && task.due_date < today;
                return (
                  <li key={task.id} className="card">
                    <div className="task-row">
                      <div>
                        <Link to={`/tasks/${task.id}`}><strong>{task.title}</strong></Link>
                        {task.plant_name && <span className="muted"> ({task.plant_name})</span>}
                        {task.due_date && (
                          <span className="muted" style={overdue ? { color: '#b84040' } : undefined}>
                            {' '}due {new Date(task.due_date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            {overdue && ' — overdue'}
                          </span>
                        )}
                      </div>
                      <div className="task-actions">
                        <button className="btn-small" onClick={() => toggleTaskMut.mutate(task.id)}>Done</button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : <p className="muted">No pending reminders or tasks.</p>}
        </section>
      )}

      {tab === 'timeline' && (
        <section>
          <p className="muted" style={{ marginBottom: '1rem' }}>Compare your plants side-by-side across the growing season.</p>
          {ganttRows.length > 0 ? (
            <>
              <div className="gantt-filters">
                {[['all', 'All'], ['growing', 'Growing only'], ['planning', 'Planning only']].map(([f, lbl]) => (
                  <button key={f} className={`btn-filter${ganttFilter === f ? ' active' : ''}`} onClick={() => setGanttFilter(f)}>{lbl}</button>
                ))}
              </div>
              <div className="gantt-legend" style={{ marginBottom: '0.5rem', fontSize: '0.8rem' }}>
                <span className="gantt-swatch gantt-swatch--indoor" /> Start Indoors &ensp;
                <span className="gantt-swatch gantt-swatch--germ" /> Germination &ensp;
                <span className="gantt-swatch gantt-swatch--grow" /> Growing &ensp;
                <span className="gantt-swatch gantt-swatch--fall" /> Fall Window &ensp;
                <span className="gantt-swatch gantt-swatch--harvest" /> Harvest &ensp;
                <span className="gantt-swatch gantt-swatch--today" /> Today &ensp;
                <span className="gantt-cal-pin gantt-cal-pin--start-indoors gantt-cal-pin--legend" /> 🪴 Start Indoors &ensp;
                <span className="gantt-cal-pin gantt-cal-pin--direct-sow gantt-cal-pin--legend" /> 🌱 Direct Sow &ensp;
                <span className="gantt-cal-pin gantt-cal-pin--transplant gantt-cal-pin--legend" /> 🌿 Transplant
              </div>
              <GanttChart rows={ganttRows} filter={ganttFilter} lastFrost={lastFrost} firstFallFrost={firstFallFrost} />
            </>
          ) : (
            <p className="muted">No plants yet. Add a plant and set a planted date to see the timeline.</p>
          )}
        </section>
      )}
    </>
  );
}
