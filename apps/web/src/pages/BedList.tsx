import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useGardens } from '../hooks/useGardens';
import { useBeds, useCreateBed, useUpdateBed, useDeleteBed } from '../hooks/useBeds';

export default function BedList() {
  const { data: gardens } = useGardens();
  const [gardenFilter, setGardenFilter] = useState<number | undefined>(undefined);
  const { data: beds, isLoading } = useBeds(gardenFilter);
  const createMut = useCreateBed();
  const updateMut = useUpdateBed();
  const deleteMut = useDeleteBed();

  const [form, setForm] = useState({
    name: '', garden_id: '', location: '', description: '',
    width_ft: '4', height_ft: '8', depth_ft: '', soil_notes: '',
  });
  const [renaming, setRenaming] = useState<Record<number, string>>({});

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.garden_id) return;
    await createMut.mutateAsync({
      name: form.name,
      garden_id: parseInt(form.garden_id),
      location: form.location || undefined,
      description: form.description || undefined,
      width_ft: parseFloat(form.width_ft) || 4,
      height_ft: parseFloat(form.height_ft) || 8,
      depth_ft: form.depth_ft ? parseFloat(form.depth_ft) : undefined,
      soil_notes: form.soil_notes || undefined,
    });
    setForm({ name: '', garden_id: form.garden_id, location: '', description: '', width_ft: '4', height_ft: '8', depth_ft: '', soil_notes: '' });
  }

  async function handleRename(id: number) {
    const name = renaming[id];
    if (!name?.trim()) return;
    await updateMut.mutateAsync({ id, name });
    setRenaming(r => { const c = { ...r }; delete c[id]; return c; });
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <h1 style={{ margin: 0 }}>Garden Beds</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label htmlFor="garden-filter" style={{ fontSize: '0.9rem', fontWeight: 600, color: '#3a5c37', whiteSpace: 'nowrap' }}>Garden:</label>
          <select
            id="garden-filter"
            value={gardenFilter ?? ''}
            onChange={e => setGardenFilter(e.target.value ? parseInt(e.target.value) : undefined)}
            style={{ font: 'inherit', padding: '0.35rem 0.6rem', border: '1px solid #c0d4be', borderRadius: '4px', background: '#fbfefb' }}
          >
            <option value="">All gardens</option>
            {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
      </div>

      <section>
        <h2>Add Bed</h2>
        <form onSubmit={handleCreate} className="form">
          <label>Garden
            <select name="garden_id" value={form.garden_id} onChange={handleChange} required>
              <option value="">— select a garden —</option>
              {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </label>
          <label>Name <input type="text" name="name" value={form.name} onChange={handleChange} required /></label>
          <label>Location <input type="text" name="location" value={form.location} onChange={handleChange} /></label>
          <label>Description <textarea name="description" rows={2} value={form.description} onChange={handleChange} /></label>
          <label>Width (ft) <input type="number" name="width_ft" step="0.5" min="1" value={form.width_ft} onChange={handleChange} /></label>
          <label>Height (ft) <input type="number" name="height_ft" step="0.5" min="1" value={form.height_ft} onChange={handleChange} /></label>
          <label>Depth (ft) <input type="number" name="depth_ft" step="0.5" min="0" value={form.depth_ft} onChange={handleChange} placeholder="e.g. 1" /></label>
          <label>Soil Notes <textarea name="soil_notes" rows={2} value={form.soil_notes} onChange={handleChange} placeholder="e.g. raised bed with compost mix" /></label>
          <button type="submit" disabled={createMut.isPending}>Add Bed</button>
        </form>
      </section>

      <section>
        <h2>All Beds</h2>
        {isLoading && <p className="muted">Loading…</p>}
        {beds && beds.length === 0 && (
          <p className="muted">No beds yet. Create one above or <Link to="/gardens">create a garden</Link> first.</p>
        )}
        {beds && beds.length > 0 && (
          <ul className="card-list">
            {beds.map(b => (
              <li key={b.id} className="card">
                <div className="plant-card-body">
                  <Link to={`/beds/${b.id}`}><strong>{b.name}</strong></Link>
                  {b.garden_name && <span className="muted" style={{ fontSize: '0.8rem' }}>📍 {b.garden_name}</span>}
                  {b.location && <span className="muted">— {b.location}</span>}
                  <span className="muted">({b.plant_count ?? 0} plant{b.plant_count !== 1 ? 's' : ''})</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginLeft: 'auto' }}>
                  <Link to={`/beds/${b.id}`} className="btn-small btn-link">View →</Link>
                  {renaming[b.id] !== undefined ? (
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <input
                        type="text"
                        value={renaming[b.id]}
                        onChange={e => setRenaming(r => ({ ...r, [b.id]: e.target.value }))}
                        style={{ font: 'inherit', padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', width: '10rem' }}
                      />
                      <button className="btn-small" onClick={() => handleRename(b.id)}>Save</button>
                      <button className="btn-small btn-link" onClick={() => setRenaming(r => { const c = { ...r }; delete c[b.id]; return c; })}>Cancel</button>
                    </div>
                  ) : (
                    <button className="btn-small btn-link" onClick={() => setRenaming(r => ({ ...r, [b.id]: b.name }))}>Rename</button>
                  )}
                  <button
                    className="btn-small btn-danger"
                    onClick={() => { if (confirm(`Delete bed "${b.name}"?`)) deleteMut.mutate(b.id); }}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
