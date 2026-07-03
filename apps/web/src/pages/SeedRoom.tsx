import { useState } from 'react';
import { apiFetch } from '@garden/shared';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useGardens } from '../hooks/useGardens';

const STAGES = ['sowing', 'germinating', 'seedling', 'hardening', 'ready'] as const;
type Stage = typeof STAGES[number];

const STAGE_COLORS: Record<Stage, string> = {
  sowing:      '#8a6a40',
  germinating: '#5a9e54',
  seedling:    '#3a8c5a',
  hardening:   '#4a80b4',
  ready:       '#d4a84b',
};

interface SeedTray {
  id: number;
  garden_id: number;
  library_id: number | null;
  plant_name: string;
  slot_number: number;
  sow_date: string | null;
  germination_date: string | null;
  transplant_ready_date: string | null;
  stage: Stage;
  notes: string | null;
  image_url: string | null;
}

function useGardenId() {
  const { data: gardens } = useGardens();
  const stored = localStorage.getItem('defaultGardenId');
  const storedId = stored ? parseInt(stored, 10) : undefined;
  return gardens?.find(g => g.id === storedId)?.id ?? gardens?.[0]?.id;
}

function useSeedRoom(gardenId?: number) {
  return useQuery<SeedTray[]>({
    queryKey: ['seed-room', gardenId],
    queryFn: () => apiFetch(`/api/gardens/${gardenId}/seed-room`).then(r => r.json()),
    enabled: !!gardenId,
  });
}

function SlotCard({
  slotNumber,
  tray,
  onAdd,
  onAdvance,
  onRemove,
}: {
  slotNumber: number;
  tray?: SeedTray;
  onAdd: (slot: number) => void;
  onAdvance: (id: number) => void;
  onRemove: (id: number) => void;
}) {
  if (!tray) {
    return (
      <div
        className="seed-slot seed-slot--empty"
        onClick={() => onAdd(slotNumber)}
        title="Click to add a seed"
      >
        <span className="seed-slot__num">{slotNumber}</span>
        <span className="seed-slot__empty-label">+ Add seed</span>
      </div>
    );
  }

  const color = STAGE_COLORS[tray.stage] ?? '#7a907a';
  return (
    <div className="seed-slot seed-slot--filled" style={{ borderColor: color }}>
      <div className="seed-slot__header">
        <span className="seed-slot__num">{slotNumber}</span>
        <span className="seed-slot__stage" style={{ background: color }}>{tray.stage}</span>
        <button className="seed-slot__remove" onClick={() => onRemove(tray.id)} title="Remove">×</button>
      </div>
      {tray.image_url && (
        <img className="seed-slot__img" src={tray.image_url} alt={tray.plant_name} />
      )}
      <div className="seed-slot__name">{tray.plant_name}</div>
      {tray.sow_date && (
        <div className="seed-slot__date">Sown: {tray.sow_date}</div>
      )}
      {tray.notes && (
        <div className="seed-slot__notes">{tray.notes}</div>
      )}
      {tray.stage !== 'ready' && (
        <button className="btn btn--ghost seed-slot__advance" onClick={() => onAdvance(tray.id)}>
          Advance →
        </button>
      )}
    </div>
  );
}

export default function SeedRoom() {
  const gardenId = useGardenId();
  const { data: trays, isLoading } = useSeedRoom(gardenId);
  const qc = useQueryClient();

  const [addSlot, setAddSlot] = useState<number | null>(null);
  const [form, setForm] = useState({ plant_name: '', sow_date: '', notes: '' });

  const addMut = useMutation({
    mutationFn: (slot: number) =>
      apiFetch(`/api/gardens/${gardenId}/seed-room`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slot_number: slot,
          plant_name: form.plant_name,
          sow_date: form.sow_date || undefined,
          notes: form.notes || undefined,
        }),
      }).then(r => { if (!r.ok) throw new Error('Failed'); return r.json(); }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['seed-room', gardenId] });
      setAddSlot(null);
      setForm({ plant_name: '', sow_date: '', notes: '' });
    },
  });

  const advanceMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/seed-room/${id}/advance-stage`, { method: 'POST' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['seed-room', gardenId] }),
  });

  const removeMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/seed-room/${id}`, { method: 'DELETE' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['seed-room', gardenId] }),
  });

  const traysBySlot = new Map((trays ?? []).map(t => [t.slot_number, t]));

  if (!gardenId) return <p className="muted" style={{ padding: '2rem' }}>Select a garden first.</p>;
  if (isLoading)  return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1100px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.25rem' }}>Seed Room</h1>
      <p className="muted" style={{ marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        Virtual seed-starting shelf — track 24 slots from sow to transplant-ready.
      </p>

      {/* Stage legend */}
      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        {STAGES.map(s => (
          <span key={s} style={{
            background: STAGE_COLORS[s], color: '#fff', borderRadius: '4px',
            padding: '0.15rem 0.5rem', fontSize: '0.78rem',
          }}>{s}</span>
        ))}
      </div>

      {/* 24-slot grid */}
      <div className="seed-grid">
        {Array.from({ length: 24 }, (_, i) => i + 1).map(slot => (
          <SlotCard
            key={slot}
            slotNumber={slot}
            tray={traysBySlot.get(slot)}
            onAdd={s => setAddSlot(s)}
            onAdvance={id => advanceMut.mutate(id)}
            onRemove={id => removeMut.mutate(id)}
          />
        ))}
      </div>

      {/* Add seed modal */}
      {addSlot !== null && (
        <div className="modal-overlay" onClick={() => setAddSlot(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h3>Add seed to slot {addSlot}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              <input
                className="form-input"
                placeholder="Plant name *"
                value={form.plant_name}
                onChange={e => setForm(f => ({ ...f, plant_name: e.target.value }))}
              />
              <label style={{ fontSize: '0.85rem' }}>
                Sow date
                <input
                  type="date"
                  className="form-input"
                  value={form.sow_date}
                  onChange={e => setForm(f => ({ ...f, sow_date: e.target.value }))}
                />
              </label>
              <textarea
                className="form-input"
                placeholder="Notes (optional)"
                rows={2}
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              />
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  className="btn"
                  disabled={!form.plant_name || addMut.isPending}
                  onClick={() => addMut.mutate(addSlot)}
                >
                  {addMut.isPending ? 'Saving…' : 'Add Seed'}
                </button>
                <button className="btn btn--ghost" onClick={() => setAddSlot(null)}>Cancel</button>
              </div>
              {addMut.isError && <p style={{ color: 'red', fontSize: '0.85rem' }}>Slot may already be occupied.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
