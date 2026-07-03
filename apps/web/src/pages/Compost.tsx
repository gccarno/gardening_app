import { useState } from 'react';
import { apiFetch } from '@garden/shared';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useGardens } from '../hooks/useGardens';

const STAGES = ['building', 'active', 'curing', 'ready'] as const;
type Stage = typeof STAGES[number];

const STAGE_COLORS: Record<Stage, string> = {
  building: '#8a6a40',
  active:   '#5a9e54',
  curing:   '#4a80b4',
  ready:    '#d4a84b',
};

const STAGE_TIPS: Record<Stage, string> = {
  building: 'Add alternating layers of greens (nitrogen) and browns (carbon). Keep it moist.',
  active:   'Turn the pile every 1-2 weeks. It should heat up to 130-160°F.',
  curing:   'Stop adding materials. Let the pile rest and stabilize for 2-4 weeks.',
  ready:    'Compost is dark, earthy-smelling, and crumbly. Ready to use!',
};

interface CompostMaterial {
  material: string;
  date_added: string;
  quantity_lbs: number | null;
}

interface CompostBin {
  id: number;
  garden_id: number;
  name: string;
  started_date: string | null;
  estimated_ready_date: string | null;
  stage: Stage;
  notes: string | null;
  materials: CompostMaterial[];
  created_at: string;
}

function useGardenId() {
  const { data: gardens } = useGardens();
  const stored = localStorage.getItem('defaultGardenId');
  const storedId = stored ? parseInt(stored, 10) : undefined;
  return gardens?.find(g => g.id === storedId)?.id ?? gardens?.[0]?.id;
}

function useCompost(gardenId?: number) {
  return useQuery<CompostBin[]>({
    queryKey: ['compost', gardenId],
    queryFn: () => apiFetch(`/api/gardens/${gardenId}/compost`).then(r => r.json()),
    enabled: !!gardenId,
  });
}

function formatDate(iso?: string | null) {
  if (!iso) return '—';
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function Compost() {
  const gardenId = useGardenId();
  const qc = useQueryClient();
  const { data: bins, isLoading } = useCompost(gardenId);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newStarted, setNewStarted] = useState(new Date().toISOString().split('T')[0]);

  const [addMatBin, setAddMatBin] = useState<number | null>(null);
  const [matForm, setMatForm] = useState({ material: '', quantity_lbs: '' });

  const createMut = useMutation({
    mutationFn: () =>
      apiFetch(`/api/gardens/${gardenId}/compost`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, started_date: newStarted }),
      }).then(r => r.json()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compost', gardenId] });
      setShowCreate(false);
      setNewName('');
    },
  });

  const advanceMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/compost/${id}/advance-stage`, { method: 'POST' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compost', gardenId] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/compost/${id}`, { method: 'DELETE' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compost', gardenId] }),
  });

  const addMatMut = useMutation({
    mutationFn: ({ id }: { id: number }) =>
      apiFetch(`/api/compost/${id}/add-material`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          material: matForm.material,
          quantity_lbs: matForm.quantity_lbs ? parseFloat(matForm.quantity_lbs) : null,
        }),
      }).then(r => r.json()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compost', gardenId] });
      setAddMatBin(null);
      setMatForm({ material: '', quantity_lbs: '' });
    },
  });

  if (!gardenId) return <p className="muted" style={{ padding: '2rem' }}>Select a garden first.</p>;
  if (isLoading)  return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;

  return (
    <div style={{ padding: '1.5rem', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0 }}>Compost Helper</h1>
        <button className="btn" onClick={() => setShowCreate(s => !s)}>
          {showCreate ? 'Cancel' : '+ New Bin'}
        </button>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <input
              className="form-input"
              placeholder="Bin name (e.g. Back yard pile) *"
              value={newName}
              onChange={e => setNewName(e.target.value)}
            />
            <label style={{ fontSize: '0.85rem' }}>
              Started date
              <input
                type="date"
                className="form-input"
                value={newStarted}
                onChange={e => setNewStarted(e.target.value)}
              />
            </label>
            <button
              className="btn"
              disabled={!newName || createMut.isPending}
              onClick={() => createMut.mutate()}
            >
              {createMut.isPending ? 'Creating…' : 'Create Bin'}
            </button>
          </div>
        </div>
      )}

      {(!bins || bins.length === 0) ? (
        <p className="muted">No compost bins yet. Create one to start tracking!</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {bins.map(bin => {
            const color = STAGE_COLORS[bin.stage] ?? '#7a907a';
            return (
              <div key={bin.id} className="card" style={{ padding: '1rem', borderLeft: `4px solid ${color}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: '1.05rem' }}>{bin.name}</span>
                    <span
                      style={{
                        marginLeft: '0.6rem', background: color, color: '#fff',
                        borderRadius: '4px', padding: '0.1rem 0.5rem', fontSize: '0.78rem',
                      }}
                    >
                      {bin.stage}
                    </span>
                  </div>
                  <button
                    className="btn btn--ghost"
                    style={{ fontSize: '0.78rem', color: '#c0392b' }}
                    onClick={() => { if (confirm('Delete this bin?')) deleteMut.mutate(bin.id); }}
                  >
                    Delete
                  </button>
                </div>

                <div className="muted" style={{ fontSize: '0.82rem', marginTop: '0.4rem' }}>
                  Started: {formatDate(bin.started_date)} ·
                  Est. ready: {formatDate(bin.estimated_ready_date)}
                </div>

                <p style={{ fontSize: '0.85rem', margin: '0.6rem 0', color: '#3a6b36', fontStyle: 'italic' }}>
                  {STAGE_TIPS[bin.stage]}
                </p>

                {bin.materials.length > 0 && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <strong style={{ fontSize: '0.85rem' }}>Materials added:</strong>
                    <ul style={{ margin: '0.3rem 0 0 1rem', fontSize: '0.82rem' }}>
                      {bin.materials.map((m, i) => (
                        <li key={i}>
                          {m.material}
                          {m.quantity_lbs ? ` (${m.quantity_lbs} lbs)` : ''}
                          <span className="muted"> — {m.date_added}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.8rem', flexWrap: 'wrap' }}>
                  {bin.stage !== 'ready' && (
                    <button
                      className="btn btn--ghost"
                      style={{ fontSize: '0.82rem' }}
                      onClick={() => advanceMut.mutate(bin.id)}
                    >
                      Advance to next stage →
                    </button>
                  )}
                  <button
                    className="btn btn--ghost"
                    style={{ fontSize: '0.82rem' }}
                    onClick={() => setAddMatBin(bin.id)}
                  >
                    + Add material
                  </button>
                </div>

                {addMatBin === bin.id && (
                  <div style={{ marginTop: '0.6rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <input
                      className="form-input"
                      placeholder="Material (e.g. kitchen scraps, dry leaves)"
                      value={matForm.material}
                      onChange={e => setMatForm(f => ({ ...f, material: e.target.value }))}
                      style={{ flex: 2 }}
                    />
                    <input
                      className="form-input"
                      placeholder="lbs (optional)"
                      type="number"
                      min="0"
                      value={matForm.quantity_lbs}
                      onChange={e => setMatForm(f => ({ ...f, quantity_lbs: e.target.value }))}
                      style={{ flex: 1 }}
                    />
                    <button
                      className="btn"
                      disabled={!matForm.material || addMatMut.isPending}
                      onClick={() => addMatMut.mutate({ id: bin.id })}
                    >
                      Add
                    </button>
                    <button className="btn btn--ghost" onClick={() => setAddMatBin(null)}>Cancel</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
