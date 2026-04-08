import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useGardens, useCreateGarden, useUpdateGarden, useDeleteGarden } from '../hooks/useGardens';

export default function GardenList() {
  const { data: gardens, isLoading } = useGardens();
  const createMut = useCreateGarden();
  const updateMut = useUpdateGarden();
  const deleteMut = useDeleteGarden();

  const [form, setForm] = useState({ name: '', description: '', unit: 'ft', zip_code: '' });
  const [renaming, setRenaming] = useState<Record<number, string>>({});

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createMut.mutateAsync(form);
    setForm({ name: '', description: '', unit: 'ft', zip_code: '' });
  }

  async function handleRename(id: number) {
    const name = renaming[id];
    if (!name?.trim()) return;
    await updateMut.mutateAsync({ id, name });
    setRenaming(r => { const c = { ...r }; delete c[id]; return c; });
  }

  return (
    <>
      <h1>Gardens</h1>

      <section>
        <h2>Create Garden</h2>
        <form onSubmit={handleCreate} className="form">
          <label>Name <input type="text" name="name" value={form.name} onChange={handleChange} required /></label>
          <label>Description <textarea name="description" rows={2} value={form.description} onChange={handleChange} /></label>
          <label>Unit
            <select name="unit" value={form.unit} onChange={handleChange}>
              <option value="ft">Feet (ft)</option>
              <option value="m">Meters (m)</option>
            </select>
          </label>
          <label>
            ZIP Code <small className="muted">(sets location, USDA zone &amp; weather)</small>
            <input type="text" name="zip_code" value={form.zip_code} onChange={handleChange}
                   placeholder="e.g. 10001" maxLength={10} />
          </label>
          <button type="submit" disabled={createMut.isPending}>Create Garden</button>
        </form>
      </section>

      <section>
        <h2>All Gardens</h2>
        {isLoading && <p className="muted">Loading…</p>}
        {gardens && gardens.length === 0 && <p className="muted">No gardens yet.</p>}
        {gardens && (
          <ul className="card-list">
            {gardens.map(g => (
              <li key={g.id} className="card">
                <div className="plant-card-body">
                  <Link to={`/gardens/${g.id}`}><strong>{g.name}</strong></Link>
                  <span className="muted"> ({g.unit})</span>
                  {g.description && <span className="muted"> — {g.description}</span>}
                  {g.city && (
                    <span className="muted" style={{ fontSize: '0.82rem' }}>
                      📍 {g.city}, {g.state}
                      {g.usda_zone && <span className="zone-badge" style={{ fontSize: '0.75rem', padding: '0.1rem 0.4rem', marginLeft: '0.3rem' }}>{g.usda_zone}</span>}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginLeft: 'auto' }}>
                  <Link to={`/planner?garden=${g.id}`} className="btn-small btn-link">Open Planner →</Link>
                  {renaming[g.id] !== undefined ? (
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <input
                        type="text"
                        value={renaming[g.id]}
                        onChange={e => setRenaming(r => ({ ...r, [g.id]: e.target.value }))}
                        style={{ font: 'inherit', padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', width: '10rem' }}
                      />
                      <button className="btn-small" onClick={() => handleRename(g.id)}>Save</button>
                      <button className="btn-small btn-link" onClick={() => setRenaming(r => { const c = { ...r }; delete c[g.id]; return c; })}>Cancel</button>
                    </div>
                  ) : (
                    <button className="btn-small btn-link" onClick={() => setRenaming(r => ({ ...r, [g.id]: g.name }))}>Rename</button>
                  )}
                  <button
                    className="btn-small btn-danger"
                    onClick={() => { if (confirm(`Delete garden "${g.name}" and all its data?`)) deleteMut.mutate(g.id); }}
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
