import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useBed, useBedGrid, useUpdateBed, useDeleteBed, usePlaceInGrid, useSaveBedPlantCare, useRemoveBedPlant } from '../hooks/useBeds';
import { useLibrary } from '../hooks/useLibrary';
import { fetchBedPlant } from '../api/beds';
import type { BedPlantDetail, GridPlant } from '../api/beds';

export default function BedDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const bedId = parseInt(id!);

  const { data: bed, isLoading } = useBed(bedId);
  const { data: gridData, refetch: refetchGrid } = useBedGrid(bedId);
  const updateMut = useUpdateBed();
  const deleteMut = useDeleteBed();
  const placeMut = usePlaceInGrid();
  const careMut = useSaveBedPlantCare();
  const removeMut = useRemoveBedPlant();

  const [libSearch, setLibSearch] = useState('');
  const { data: libData } = useLibrary({ q: libSearch || undefined });
  const libEntries = libData?.entries ?? [];

  const [selectedLibId, setSelectedLibId] = useState<number | null>(null);
  const [placed, setPlaced] = useState<Record<string, GridPlant>>({});
  const [carePanel, setCarePanel] = useState<(BedPlantDetail & { key: string }) | null>(null);
  const [careSaved, setCareSaved] = useState(false);
  const [careForm, setCareForm] = useState({ last_watered: '', last_fertilized: '', health_notes: '' });

  const [form, setForm] = useState({
    name: '', location: '', description: '', depth_ft: '',
    soil_notes: '', soil_ph: '', clay_pct: '', compost_pct: '', sand_pct: '',
  });

  useEffect(() => {
    if (bed) {
      setForm({
        name: bed.name,
        location: bed.location ?? '',
        description: bed.description ?? '',
        depth_ft: bed.depth_ft ? String(bed.depth_ft) : '',
        soil_notes: bed.soil_notes ?? '',
        soil_ph: bed.soil_ph ? String(bed.soil_ph) : '',
        clay_pct: bed.clay_pct ? String(bed.clay_pct) : '',
        compost_pct: bed.compost_pct ? String(bed.compost_pct) : '',
        sand_pct: bed.sand_pct ? String(bed.sand_pct) : '',
      });
    }
  }, [bed]);

  useEffect(() => {
    if (gridData?.placed) {
      const m: Record<string, GridPlant> = {};
      for (const p of gridData.placed) m[`${p.grid_x},${p.grid_y}`] = p;
      setPlaced(m);
    }
  }, [gridData]);

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    await updateMut.mutateAsync({
      id: bedId,
      name: form.name,
      location: form.location || undefined,
      description: form.description || undefined,
      depth_ft: form.depth_ft ? parseFloat(form.depth_ft) : undefined,
      soil_notes: form.soil_notes || undefined,
      soil_ph: form.soil_ph ? parseFloat(form.soil_ph) : undefined,
      clay_pct: form.clay_pct ? parseFloat(form.clay_pct) : undefined,
      compost_pct: form.compost_pct ? parseFloat(form.compost_pct) : undefined,
      sand_pct: form.sand_pct ? parseFloat(form.sand_pct) : undefined,
    });
  }

  async function handleDelete() {
    if (!confirm(`Delete ${bed?.name}?`)) return;
    await deleteMut.mutateAsync(bedId);
    nav('/beds');
  }

  const handleCellClick = useCallback(async (x: number, y: number) => {
    const key = `${x},${y}`;
    if (placed[key]) {
      const detail = await fetchBedPlant(placed[key].id);
      setCarePanel({ ...detail, key });
      setCareForm({
        last_watered: detail.last_watered ?? '',
        last_fertilized: detail.last_fertilized ?? '',
        health_notes: detail.health_notes ?? '',
      });
      setCareSaved(false);
    } else {
      if (!selectedLibId) return;
      const result = await placeMut.mutateAsync({ bedId, library_id: selectedLibId, grid_x: x, grid_y: y });
      if (result.ok) refetchGrid();
      else alert(result.error || 'Error placing plant');
    }
  }, [placed, selectedLibId, bedId, placeMut, refetchGrid]);

  async function handleCareSave(e: React.FormEvent) {
    e.preventDefault();
    if (!carePanel) return;
    await careMut.mutateAsync({
      bpId: carePanel.id,
      last_watered: careForm.last_watered || null,
      last_fertilized: careForm.last_fertilized || null,
      health_notes: careForm.health_notes || null,
    });
    setCareSaved(true);
    setTimeout(() => setCareSaved(false), 2000);
  }

  async function handleCareRemove() {
    if (!carePanel) return;
    if (!confirm(`Remove ${carePanel.plant_name} from this cell?`)) return;
    await removeMut.mutateAsync({ bpId: carePanel.id, bedId });
    setCarePanel(null);
    refetchGrid();
  }

  if (isLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;
  if (!bed) return <p className="muted" style={{ padding: '2rem' }}>Bed not found.</p>;

  const cols = Math.max(1, Math.round(bed.width_ft));
  const rows = Math.max(1, Math.round(bed.height_ft));

  return (
    <>
      <h1>{bed.name}</h1>

      <details style={{ marginBottom: '1.5rem' }}>
        <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#3a5c37' }}>Edit Bed</summary>
        <form onSubmit={handleEdit} className="form" style={{ marginTop: '0.75rem' }}>
          <label>Name <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required /></label>
          <label>Location <input type="text" value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} /></label>
          <label>Description <textarea rows={2} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></label>
          <label>Depth (ft) <input type="number" step="0.5" min="0" value={form.depth_ft} onChange={e => setForm(f => ({ ...f, depth_ft: e.target.value }))} placeholder="e.g. 1" /></label>
          <label>Soil Notes <textarea rows={2} value={form.soil_notes} onChange={e => setForm(f => ({ ...f, soil_notes: e.target.value }))} /></label>
          <label>Soil pH <input type="number" min="0" max="14" step="0.1" value={form.soil_ph} onChange={e => setForm(f => ({ ...f, soil_ph: e.target.value }))} placeholder="e.g. 6.5" /></label>
          <label>Soil Composition (%)</label>
          <div className="soil-mix-row">
            <input type="number" min="0" max="100" step="1" placeholder="Clay %" value={form.clay_pct} onChange={e => setForm(f => ({ ...f, clay_pct: e.target.value }))} />
            <input type="number" min="0" max="100" step="1" placeholder="Compost %" value={form.compost_pct} onChange={e => setForm(f => ({ ...f, compost_pct: e.target.value }))} />
            <input type="number" min="0" max="100" step="1" placeholder="Sand %" value={form.sand_pct} onChange={e => setForm(f => ({ ...f, sand_pct: e.target.value }))} />
          </div>
          <button type="submit" disabled={updateMut.isPending}>Save Changes</button>
        </form>
      </details>

      {(bed.description || bed.location || bed.depth_ft || bed.soil_notes || bed.soil_ph || bed.clay_pct || bed.compost_pct || bed.sand_pct) && (
        <dl className="details" style={{ marginBottom: '1.5rem' }}>
          {bed.location && <><dt>Location</dt><dd>{bed.location}</dd></>}
          {bed.description && <><dt>Description</dt><dd>{bed.description}</dd></>}
          {bed.depth_ft && <><dt>Depth</dt><dd>{bed.depth_ft} ft</dd></>}
          {bed.soil_notes && <><dt>Soil Notes</dt><dd>{bed.soil_notes}</dd></>}
          {bed.soil_ph && <><dt>Soil pH</dt><dd>{bed.soil_ph}</dd></>}
          {(bed.clay_pct || bed.compost_pct || bed.sand_pct) && (
            <>
              <dt>Soil Mix</dt>
              <dd>
                {[bed.clay_pct && `Clay ${Math.round(bed.clay_pct)}%`, bed.compost_pct && `Compost ${Math.round(bed.compost_pct)}%`, bed.sand_pct && `Sand ${Math.round(bed.sand_pct)}%`].filter(Boolean).join(' · ')}
              </dd>
            </>
          )}
        </dl>
      )}

      <h2>Bed Grid &mdash; {cols}ft wide &times; {rows}ft tall</h2>

      <div className="bed-grid-layout">
        <div>
          <div
            className="bed-grid"
            style={{ '--cols': cols, '--rows': rows } as React.CSSProperties}
          >
            {Array.from({ length: rows }, (_, y) =>
              Array.from({ length: cols }, (_, x) => {
                const key = `${x},${y}`;
                const p = placed[key];
                return (
                  <div
                    key={key}
                    className={`bed-cell ${p ? 'occupied' : 'empty'}`}
                    onClick={() => handleCellClick(x, y)}
                    title={p ? `${p.plant_name} — click for care info` : 'Click to place selected plant'}
                    style={p?.image_filename ? {
                      backgroundImage: `url('/static/plant_images/${p.image_filename}')`,
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                    } : undefined}
                  >
                    {p && <span className="cell-label">{p.plant_name}</span>}
                  </div>
                );
              })
            )}
          </div>
          <p className="muted" style={{ marginTop: '0.5rem' }}>Each cell = 1 ft × 1 ft</p>
        </div>

        <div className="bed-grid-sidebar">
          <h3>Place a Plant</h3>
          <input
            type="text"
            className="bed-plant-select"
            placeholder="Search library…"
            value={libSearch}
            onChange={e => setLibSearch(e.target.value)}
            style={{ marginBottom: '0.4rem' }}
          />
          <select
            className="bed-plant-select"
            size={8}
            style={{ height: 'auto' }}
            value={selectedLibId ?? ''}
            onChange={e => setSelectedLibId(parseInt(e.target.value))}
          >
            {libEntries.map(e => (
              <option key={e.id} value={e.id}>{e.name}{e.type ? ` (${e.type})` : ''}</option>
            ))}
          </select>
          <p className="muted" style={{ marginTop: '0.75rem' }}>1. Select a plant above.</p>
          <p className="muted">2. Click an empty cell to place it.</p>
          <p className="muted">3. Click a placed plant to view/edit its care info.</p>
        </div>
      </div>

      {carePanel && (
        <div className="care-panel" style={{ display: 'block' }}>
          <div className="care-panel-header">
            {carePanel.image_filename && (
              <img src={`/static/plant_images/${carePanel.image_filename}`} alt="" className="care-img" />
            )}
            <div>
              <h3 style={{ margin: '0 0 0.2rem' }}>{carePanel.plant_name}</h3>
              {carePanel.scientific_name && <span className="muted" style={{ fontSize: '0.85rem', fontStyle: 'italic' }}>{carePanel.scientific_name}</span>}
            </div>
            <button className="btn-small" style={{ marginLeft: 'auto' }} onClick={() => setCarePanel(null)}>Close</button>
          </div>

          <dl className="details" style={{ margin: '0.75rem 0' }}>
            {carePanel.sunlight && <><dt>Sunlight</dt><dd>{carePanel.sunlight}</dd></>}
            {carePanel.water && <><dt>Water</dt><dd>{carePanel.water}</dd></>}
            {carePanel.spacing_in && <><dt>Spacing</dt><dd>{carePanel.spacing_in}"</dd></>}
            {carePanel.days_to_harvest && <><dt>Days to Harvest</dt><dd>{carePanel.days_to_harvest}</dd></>}
          </dl>

          <form onSubmit={handleCareSave} className="form" style={{ maxWidth: '420px' }}>
            <label>Last Watered <input type="date" value={careForm.last_watered} onChange={e => setCareForm(f => ({ ...f, last_watered: e.target.value }))} /></label>
            <label>Last Fertilized <input type="date" value={careForm.last_fertilized} onChange={e => setCareForm(f => ({ ...f, last_fertilized: e.target.value }))} /></label>
            <label>Health Notes (diseases, pests, observations)
              <textarea rows={3} value={careForm.health_notes} onChange={e => setCareForm(f => ({ ...f, health_notes: e.target.value }))}
                        placeholder="e.g. aphids spotted on lower leaves, treated with neem oil" />
            </label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="submit">Save</button>
              <button type="button" className="btn-danger" onClick={handleCareRemove}>Remove Plant</button>
            </div>
            {careSaved && <p className="muted" style={{ marginTop: '0.4rem' }}>Saved.</p>}
          </form>
        </div>
      )}

      <div className="actions" style={{ marginTop: '1.5rem' }}>
        <button className="btn-danger" onClick={handleDelete}>Delete Bed</button>
      </div>
      <p><Link to="/beds">← Back to Beds</Link></p>
    </>
  );
}
