import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { usePlannerCtx } from '../PlannerContext';
import { api, GARDEN_PALETTE, PATTERNS, type GardenPlant } from '../types';
import { plantImageUrl } from '../../utils/images';

export default function InfoTab() {
  const {
    gardenId, garden,
    canvasBeds, setCanvasBeds,
    paletteBeds, setPaletteBeds,
    canvasPlants, setCanvasPlants,
    gardenPlants, setGardenPlants,
    selectedBed, setSelectedBed,
    carePanel, setCarePanel,
    setRightPanelOpen,
    setRightPanelTab,
    groupInfoPlants, setGroupInfoPlants,
    libInfo, setLibInfo,
    libEditMode, setLibEditMode,
    libImageMode, setLibImageMode,
    highlightLibId, setHighlightLibId,
    weather,
    tasks,
    taskForm, setTaskForm,
    taskSaved,
    loadPanelData,
    handleAddTask,
    showLibInfo,
  } = usePlannerCtx();

  // ── Local state ───────────────────────────────────────────────────────────────
  const [careForm, setCareForm] = useState({
    planted_date: '', transplant_date: '', plant_notes: '',
    last_watered: '', last_fertilized: '', last_harvest: '', health_notes: '', stage: 'seedling',
  });
  const [careSaved, setCareSaved] = useState(false);
  const [bedEditMode, setBedEditMode] = useState(false);
  const [bedEditForm, setBedEditForm] = useState({
    name: '', width_ft: '', height_ft: '', depth_ft: '',
    location: '', description: '', soil_notes: '', soil_ph: '',
    clay_pct: '', compost_pct: '', sand_pct: '',
  });
  const [libEditForm, setLibEditForm] = useState<{
    sunlight: string; water: string; spacing_in: string;
    days_to_germination: string; days_to_harvest: string; notes: string;
  }>({ sunlight: '', water: '', spacing_in: '', days_to_germination: '', days_to_harvest: '', notes: '' });
  const [libImages, setLibImages] = useState<{id: number; filename: string; is_primary: boolean; source: string}[]>([]);
  const [editingPlantId, setEditingPlantId] = useState<number | null>(null);
  const [plantEditForm, setPlantEditForm] = useState<{
    status: string; planted_date: string; transplant_date: string; expected_harvest: string; notes: string;
  }>({ status: 'planning', planted_date: '', transplant_date: '', expected_harvest: '', notes: '' });
  const [plantEditSaved, setPlantEditSaved] = useState(false);
  const [bulkStatusValue, setBulkStatusValue] = useState<string>('growing');
  const [bulkSaving, setBulkSaving] = useState(false);
  const [bulkWaterAmount, setBulkWaterAmount] = useState<'light' | 'moderate' | 'heavy'>('moderate');
  const [bulkFertType, setBulkFertType] = useState('balanced');
  const [bulkFertNpk, setBulkFertNpk] = useState('');
  const [bulkCareSaving, setBulkCareSaving] = useState(false);
  const [rainAmount, setRainAmount] = useState<'light' | 'moderate' | 'heavy'>('moderate');

  // ── Effects: sync local state from context changes ────────────────────────────
  // When Planner sets a new carePanel (chip click / canvas plant click), populate careForm
  useEffect(() => {
    if (!carePanel) return;
    setCareForm({
      planted_date: carePanel.planted_date || '',
      transplant_date: carePanel.transplant_date || '',
      plant_notes: carePanel.plant_notes || '',
      last_watered: carePanel.last_watered || '',
      last_fertilized: carePanel.last_fertilized || '',
      last_harvest: carePanel.last_harvest || '',
      health_notes: carePanel.health_notes || '',
      stage: carePanel.stage || 'seedling',
    });
    setCareSaved(false);
  }, [carePanel?.id]);

  // Reset bed edit mode when selected bed changes
  useEffect(() => {
    setBedEditMode(false);
  }, [selectedBed?.id]);

  // Reset plant editing when group changes
  useEffect(() => {
    setEditingPlantId(null);
    setPlantEditSaved(false);
  }, [groupInfoPlants]);

  // ── Handlers ──────────────────────────────────────────────────────────────────
  function wIcon(str: string) {
    const s = (str || '').toLowerCase();
    if (s.includes('thunder')) return '⛈️';
    if (s.includes('snow')) return '❄️';
    if (s.includes('rain') || s.includes('drizzle') || s.includes('shower')) return '🌧️';
    if (s.includes('fog') || s.includes('mist')) return '🌫️';
    if (s.includes('overcast')) return '☁️';
    if (s.includes('partly') || s.includes('cloud')) return '🌤️';
    if (s.includes('clear') || s.includes('sunny')) return '☀️';
    return '🌡️';
  }

  function summarizeStatuses(plants: GardenPlant[]) {
    const counts: Record<string, number> = {};
    for (const p of plants) {
      const s = p.status || 'planning';
      counts[s] = (counts[s] || 0) + 1;
    }
    return Object.entries(counts).map(([s, n]) => `${s} ×${n}`).join(', ');
  }

  async function handleCareSave(e: React.FormEvent) {
    e.preventDefault();
    if (!carePanel) return;
    if (carePanel.is_bed) {
      await api('POST', `/api/bedplants/${carePanel.id}/care`, {
        planted_date: careForm.planted_date || null,
        transplant_date: careForm.transplant_date || null,
        plant_notes: careForm.plant_notes || null,
        last_watered: careForm.last_watered || null,
        last_fertilized: careForm.last_fertilized || null,
        last_harvest: careForm.last_harvest || null,
        health_notes: careForm.health_notes || null,
        stage: careForm.stage || null,
      });
    } else if (carePanel.plant_id) {
      await api('POST', `/api/plants/${carePanel.plant_id}/care`, {
        planted_date: careForm.planted_date || null,
        transplant_date: careForm.transplant_date || null,
        plant_notes: careForm.plant_notes || null,
      });
    }
    const gp = await api('GET', `/api/plants?garden_id=${gardenId}`) as GardenPlant[];
    setGardenPlants(gp);
    setCareSaved(true);
    setTimeout(() => setCareSaved(false), 2000);
  }

  function startBedEdit() {
    if (!selectedBed) return;
    setBedEditForm({
      name: selectedBed.name,
      width_ft: String(selectedBed.width_ft),
      height_ft: String(selectedBed.height_ft),
      depth_ft: selectedBed.depth_ft != null ? String(selectedBed.depth_ft) : '',
      location: selectedBed.location || '',
      description: selectedBed.description || '',
      soil_notes: selectedBed.soil_notes || '',
      soil_ph: selectedBed.soil_ph != null ? String(selectedBed.soil_ph) : '',
      clay_pct: selectedBed.clay_pct != null ? String(selectedBed.clay_pct) : '',
      compost_pct: selectedBed.compost_pct != null ? String(selectedBed.compost_pct) : '',
      sand_pct: selectedBed.sand_pct != null ? String(selectedBed.sand_pct) : '',
    });
    setBedEditMode(true);
  }

  async function handleBedSave(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedBed) return;
    const r = await api('PUT', `/api/beds/${selectedBed.id}`, {
      name: bedEditForm.name || selectedBed.name,
      width_ft: parseFloat(bedEditForm.width_ft) || selectedBed.width_ft,
      height_ft: parseFloat(bedEditForm.height_ft) || selectedBed.height_ft,
      depth_ft: bedEditForm.depth_ft ? parseFloat(bedEditForm.depth_ft) : null,
      location: bedEditForm.location || null,
      description: bedEditForm.description || null,
      soil_notes: bedEditForm.soil_notes || null,
      soil_ph: bedEditForm.soil_ph ? parseFloat(bedEditForm.soil_ph) : null,
      clay_pct: bedEditForm.clay_pct ? parseFloat(bedEditForm.clay_pct) : null,
      compost_pct: bedEditForm.compost_pct ? parseFloat(bedEditForm.compost_pct) : null,
      sand_pct: bedEditForm.sand_pct ? parseFloat(bedEditForm.sand_pct) : null,
    });
    if (r.id) {
      const updated = { ...selectedBed, ...r };
      setSelectedBed(updated);
      setCanvasBeds(prev => prev.map(b => b.id === updated.id ? updated : b));
      setPaletteBeds(prev => prev.map(b => b.id === updated.id ? updated : b));
      setBedEditMode(false);
    }
  }

  function openLibEdit() {
    if (!libInfo) return;
    setLibEditForm({
      sunlight: libInfo.sunlight || '',
      water: libInfo.water || '',
      spacing_in: libInfo.spacing_in != null ? String(libInfo.spacing_in) : '',
      days_to_germination: libInfo.days_to_germination != null ? String(libInfo.days_to_germination) : '',
      days_to_harvest: libInfo.days_to_harvest != null ? String(libInfo.days_to_harvest) : '',
      notes: '',
    });
    setLibEditMode(true);
  }

  async function handleLibEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!libInfo) return;
    const body: Record<string, unknown> = {};
    if (libEditForm.sunlight)            body.sunlight = libEditForm.sunlight;
    if (libEditForm.water)               body.water = libEditForm.water;
    if (libEditForm.spacing_in)          body.spacing_in = parseFloat(libEditForm.spacing_in);
    if (libEditForm.days_to_germination) body.days_to_germination = parseInt(libEditForm.days_to_germination);
    if (libEditForm.days_to_harvest)     body.days_to_harvest = parseInt(libEditForm.days_to_harvest);
    if (libEditForm.notes)               body.notes = libEditForm.notes;
    await api('POST', `/api/library/${libInfo.id}/patch`, body);
    await showLibInfo(libInfo.id);
    setLibEditMode(false);
  }

  async function openLibImageMode() {
    if (!libInfo) return;
    const imgs = await api('GET', `/api/library/${libInfo.id}/images`);
    setLibImages(Array.isArray(imgs) ? imgs : []);
    setLibImageMode(true);
  }

  async function setLibPrimaryImage(imgId: number) {
    if (!libInfo) return;
    await api('POST', `/api/library/images/${imgId}/set-primary`);
    await showLibInfo(libInfo.id);
    const imgs = await api('GET', `/api/library/${libInfo.id}/images`);
    setLibImages(Array.isArray(imgs) ? imgs : []);
    setLibImageMode(true);
  }

  async function uploadLibImage(file: File) {
    if (!libInfo) return;
    const fd = new FormData();
    fd.append('file', file);
    await fetch(`/api/library/${libInfo.id}/images`, { method: 'POST', body: fd });
    await showLibInfo(libInfo.id);
    const imgs = await api('GET', `/api/library/${libInfo.id}/images`);
    setLibImages(Array.isArray(imgs) ? imgs : []);
    setLibImageMode(true);
  }

  function startPlantEdit(p: GardenPlant) {
    setEditingPlantId(p.id);
    setPlantEditForm({
      status: p.status || 'planning',
      planted_date: p.planted_date || '',
      transplant_date: p.transplant_date || '',
      expected_harvest: p.expected_harvest || '',
      notes: p.notes || '',
    });
    setPlantEditSaved(false);
  }

  async function handlePlantEditSave(plantId: number, e: React.FormEvent) {
    e.preventDefault();
    await api('PUT', `/api/plants/${plantId}`, {
      notes: plantEditForm.notes,
      planted_date: plantEditForm.planted_date || null,
      transplant_date: plantEditForm.transplant_date || null,
      expected_harvest: plantEditForm.expected_harvest || null,
    });
    await api('POST', `/api/plants/${plantId}/status`, { status: plantEditForm.status });
    const gp = await api('GET', `/api/plants?garden_id=${gardenId}`) as GardenPlant[];
    setGardenPlants(gp);
    if (groupInfoPlants) {
      const rep = groupInfoPlants[0];
      const key = rep.library_id != null ? `lib_${rep.library_id}` : `name_${rep.name}`;
      const updated = gp.filter(p => (p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`) === key);
      setGroupInfoPlants(updated.length > 0 ? updated : null);
    }
    setEditingPlantId(null);
    setPlantEditSaved(true);
    setTimeout(() => setPlantEditSaved(false), 2500);
  }

  async function handleBulkStatusUpdate() {
    if (!groupInfoPlants || groupInfoPlants.length === 0) return;
    setBulkSaving(true);
    await api('POST', '/api/plants/bulk-status', {
      ids: groupInfoPlants.map(p => p.id),
      status: bulkStatusValue,
    });
    const gp = await api('GET', `/api/plants?garden_id=${gardenId}`) as GardenPlant[];
    setGardenPlants(gp);
    const rep = groupInfoPlants[0];
    const key = rep.library_id != null ? `lib_${rep.library_id}` : `name_${rep.name}`;
    const updated = gp.filter(p => (p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`) === key);
    setGroupInfoPlants(updated.length > 0 ? updated : null);
    setBulkSaving(false);
  }

  async function handleBulkCare(type: 'water' | 'fertilize') {
    if (!groupInfoPlants?.length) return;
    setBulkCareSaving(true);
    const today = new Date().toISOString().split('T')[0];
    const body: Record<string, string> = type === 'water'
      ? { last_watered: today, watering_amount: bulkWaterAmount }
      : { last_fertilized: today, fertilizer_type: bulkFertType, ...(bulkFertNpk ? { fertilizer_npk: bulkFertNpk } : {}) };
    await api('POST', '/api/plants/bulk-care', { ids: groupInfoPlants.map(p => p.id), ...body });
    const gp = await api('GET', `/api/plants?garden_id=${gardenId}`) as GardenPlant[];
    setGardenPlants(gp);
    const rep = groupInfoPlants[0];
    const key = rep.library_id != null ? `lib_${rep.library_id}` : `name_${rep.name}`;
    const updated = gp.filter(p => (p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`) === key);
    setGroupInfoPlants(updated.length > 0 ? updated : null);
    setBulkCareSaving(false);
  }

  async function handleLogRain() {
    if (!gardenId) return;
    await api('POST', `/api/gardens/${gardenId}/bulk-care`, {
      action: 'water', watering_amount: rainAmount, create_task: false,
    });
    const updated = await api('GET', `/api/gardens/${gardenId}/canvas-plants`);
    setCanvasPlants(updated);
    const gp = await api('GET', `/api/plants?garden_id=${gardenId}`) as GardenPlant[];
    setGardenPlants(gp);
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  const w = weather as {
    current?: { temp: number; condition: string; humidity: number; wind_speed: number };
    daily?: { date: string; high: number; low: number; condition: string; precip_prob?: number }[];
    frost?: { last_spring: string; first_fall: string };
  } | null;

  return (<>

    {/* Garden info */}
    {garden && (
      <div>
        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37', marginBottom: '0.4rem' }}>Garden Info</div>
        {garden.usda_zone && <div style={{ display: 'inline-block', background: '#d4edcc', borderRadius: '3px', padding: '1px 6px', fontSize: '0.78rem', marginBottom: '0.3rem' }}>Zone {garden.usda_zone}</div>}
        {garden.city && <div style={{ fontSize: '0.78rem', color: '#5a7a5a' }}>📍 {garden.city}, {garden.state} {garden.zip_code}</div>}
        {garden.last_frost_date && <div style={{ fontSize: '0.78rem', color: '#5a7a5a' }}>❄️ Last frost: {garden.last_frost_date}</div>}
      </div>
    )}

    {/* Bed detail panel */}
    {selectedBed && !bedEditMode && (
      <div style={{ borderTop: '1px solid #d0e0c8', paddingTop: '0.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#3a5c37' }}>🛏 {selectedBed.name}</div>
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            <button className="btn-small btn-link" style={{ fontSize: '0.72rem' }} onClick={startBedEdit}>✎ Edit</button>
            <button style={{ background: 'none', border: 'none', color: '#9ab49a', cursor: 'pointer', fontSize: '0.85rem', padding: 0 }} onClick={() => { setSelectedBed(null); setBedEditMode(false); }}>×</button>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.2rem 0.6rem', fontSize: '0.78rem', color: '#5a7a5a' }}>
          <span>📐 {selectedBed.width_ft} × {selectedBed.height_ft} ft</span>
          {selectedBed.depth_ft && <span>↕ {selectedBed.depth_ft} ft deep</span>}
          {selectedBed.plant_count != null && <span>🌿 {selectedBed.plant_count} plants</span>}
          {(canvasBeds.find(b => b.id === selectedBed.id) ? true : false)
            ? <span style={{ color: '#3a6b35' }}>✓ On canvas</span>
            : <span style={{ color: '#9ab49a' }}>Not placed</span>}
          {selectedBed.last_weeded && <span style={{ gridColumn: '1 / -1' }}>🪴 Weeded {selectedBed.last_weeded}</span>}
        </div>
        {selectedBed.location && <div style={{ fontSize: '0.78rem', color: '#5a7a5a', marginTop: '0.25rem' }}>📍 {selectedBed.location}</div>}
        {selectedBed.description && <div style={{ fontSize: '0.78rem', color: '#5a7a5a', marginTop: '0.25rem' }}>{selectedBed.description}</div>}
        {(selectedBed.soil_ph || selectedBed.soil_notes) && (
          <div style={{ marginTop: '0.4rem', padding: '0.35rem 0.5rem', background: '#f0f7ef', borderRadius: '4px', fontSize: '0.78rem' }}>
            <div style={{ fontWeight: 600, color: '#4a6a47', marginBottom: '0.2rem' }}>Soil</div>
            {selectedBed.soil_ph && <div>pH {selectedBed.soil_ph}</div>}
            {selectedBed.soil_notes && <div style={{ color: '#5a7a5a', marginTop: '0.15rem' }}>{selectedBed.soil_notes}</div>}
            {(selectedBed.clay_pct || selectedBed.compost_pct || selectedBed.sand_pct) && (
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.2rem', color: '#7a907a' }}>
                {selectedBed.clay_pct != null && <span>Clay {selectedBed.clay_pct}%</span>}
                {selectedBed.compost_pct != null && <span>Compost {selectedBed.compost_pct}%</span>}
                {selectedBed.sand_pct != null && <span>Sand {selectedBed.sand_pct}%</span>}
              </div>
            )}
          </div>
        )}
      </div>
    )}

    {/* Bed edit form */}
    {selectedBed && bedEditMode && (
      <div style={{ borderTop: '1px solid #d0e0c8', paddingTop: '0.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#3a5c37' }}>✎ Edit Bed</div>
          <button style={{ background: 'none', border: 'none', color: '#9ab49a', cursor: 'pointer', fontSize: '0.85rem', padding: 0 }} onClick={() => setBedEditMode(false)}>✕ Cancel</button>
        </div>
        <form onSubmit={handleBedSave} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.78rem' }}>
          <label>Name <input type="text" value={bedEditForm.name} onChange={e => setBedEditForm(f => ({ ...f, name: e.target.value }))} required style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            <label style={{ flex: 1 }}>Width (ft) <input type="number" step="0.5" min="0.5" value={bedEditForm.width_ft} onChange={e => setBedEditForm(f => ({ ...f, width_ft: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
            <label style={{ flex: 1 }}>Height (ft) <input type="number" step="0.5" min="0.5" value={bedEditForm.height_ft} onChange={e => setBedEditForm(f => ({ ...f, height_ft: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          </div>
          <label>Depth (ft) <input type="number" step="0.5" min="0" value={bedEditForm.depth_ft} onChange={e => setBedEditForm(f => ({ ...f, depth_ft: e.target.value }))} placeholder="optional" style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          <label>Location <input type="text" value={bedEditForm.location} onChange={e => setBedEditForm(f => ({ ...f, location: e.target.value }))} placeholder="e.g. South fence" style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          <label>Description <textarea rows={2} value={bedEditForm.description} onChange={e => setBedEditForm(f => ({ ...f, description: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%', resize: 'vertical' }} /></label>
          <div style={{ fontWeight: 600, color: '#4a6a47', marginTop: '0.2rem' }}>Soil</div>
          <label>pH <input type="number" step="0.1" min="0" max="14" value={bedEditForm.soil_ph} onChange={e => setBedEditForm(f => ({ ...f, soil_ph: e.target.value }))} placeholder="e.g. 6.5" style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          <label>Notes <textarea rows={2} value={bedEditForm.soil_notes} onChange={e => setBedEditForm(f => ({ ...f, soil_notes: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%', resize: 'vertical' }} /></label>
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            <label style={{ flex: 1 }}>Clay % <input type="number" step="1" min="0" max="100" value={bedEditForm.clay_pct} onChange={e => setBedEditForm(f => ({ ...f, clay_pct: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
            <label style={{ flex: 1 }}>Compost % <input type="number" step="1" min="0" max="100" value={bedEditForm.compost_pct} onChange={e => setBedEditForm(f => ({ ...f, compost_pct: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
            <label style={{ flex: 1 }}>Sand % <input type="number" step="1" min="0" max="100" value={bedEditForm.sand_pct} onChange={e => setBedEditForm(f => ({ ...f, sand_pct: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          </div>
          <div style={{ fontWeight: 600, color: '#4a6a47', marginTop: '0.2rem' }}>Appearance</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <label style={{ fontSize: '0.78rem' }}>Color
              <input type="color" value={selectedBed?.color || '#e8f5e3'}
                onChange={async e => {
                  const color = e.target.value;
                  if (!selectedBed) return;
                  await api('PUT', `/api/beds/${selectedBed.id}`, { color });
                  setCanvasBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, color } : b));
                  setPaletteBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, color } : b));
                  setSelectedBed(prev => prev ? { ...prev, color } : prev);
                }}
                style={{ marginLeft: '0.3rem', width: 28, height: 22, padding: 1, border: '1px solid #c0d4be', borderRadius: 3, cursor: 'pointer' }} />
            </label>
            <label title="Upload bed background image" style={{ cursor: 'pointer', color: '#3a6b35', fontSize: '0.78rem' }}>
              🖼 Image
              <input type="file" accept="image/*" style={{ display: 'none' }} onChange={async e => {
                const file = e.target.files?.[0]; if (!file || !selectedBed) return;
                const fd = new FormData(); fd.append('image', file);
                const r = await fetch(`/api/beds/${selectedBed.id}/upload-background`, { method: 'POST', body: fd });
                const d = await r.json();
                if (d.filename) {
                  setCanvasBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, background_image: d.filename } : b));
                  setSelectedBed(prev => prev ? { ...prev, background_image: d.filename } : prev);
                }
              }} />
            </label>
            {selectedBed?.background_image && (
              <button title="Remove bed image" onClick={async () => {
                if (!selectedBed) return;
                await api('POST', `/api/beds/${selectedBed.id}/remove-background`, {});
                setCanvasBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, background_image: undefined } : b));
                setSelectedBed(prev => prev ? { ...prev, background_image: undefined } : prev);
              }} style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.78rem', padding: 0 }}>✕ Clear</button>
            )}
          </div>
          {/* Bed color swatches */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px', marginTop: '0.2rem' }}>
            {GARDEN_PALETTE.map(c => (
              <button key={c} title={c}
                style={{ width: 16, height: 16, background: c, border: selectedBed?.color === c ? '2px solid #333' : '1px solid #aaa', borderRadius: 2, cursor: 'pointer', padding: 0 }}
                onClick={async () => {
                  if (!selectedBed) return;
                  await api('PUT', `/api/beds/${selectedBed.id}`, { color: c });
                  setCanvasBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, color: c } : b));
                  setPaletteBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, color: c } : b));
                  setSelectedBed(prev => prev ? { ...prev, color: c } : prev);
                }} />
            ))}
          </div>
          {/* Bed pattern selector */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px', marginTop: '0.2rem' }}>
            {[{ key: '', label: 'No pattern' }, ...PATTERNS].map(p => (
              <button key={p.key} className={`btn-small${selectedBed?.background_pattern === p.key || (!selectedBed?.background_pattern && p.key === '') ? '' : ' btn-link'}`}
                style={{ fontSize: '0.62rem', padding: '1px 4px', background: (selectedBed?.background_pattern === p.key || (!selectedBed?.background_pattern && p.key === '')) ? '#3a6b35' : undefined, color: (selectedBed?.background_pattern === p.key || (!selectedBed?.background_pattern && p.key === '')) ? '#fff' : undefined }}
                onClick={async () => {
                  if (!selectedBed) return;
                  const pattern = p.key || null;
                  await api('PUT', `/api/beds/${selectedBed.id}`, { background_pattern: pattern });
                  setCanvasBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, background_pattern: p.key } : b));
                  setPaletteBeds(prev => prev.map(b => b.id === selectedBed.id ? { ...b, background_pattern: p.key } : b));
                  setSelectedBed(prev => prev ? { ...prev, background_pattern: p.key } : prev);
                }}>
                {p.label}
              </button>
            ))}
          </div>
          <button type="submit" className="btn-small" style={{ fontSize: '0.78rem', marginTop: '0.2rem' }}>Save</button>
        </form>
      </div>
    )}

    {/* Weather */}
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37' }}>Weather</span>
        <button className="btn-small btn-link" title="Refresh weather" style={{ fontSize: '0.8rem', padding: '1px 4px', lineHeight: 1 }} onClick={() => loadPanelData()}>↻</button>
      </div>
      {!garden?.latitude ? (
        <p className="muted" style={{ fontSize: '0.78rem' }}>No location set. <Link to={`/gardens/${gardenId}`} style={{ color: '#3a6b35' }}>Set location →</Link></p>
      ) : !w ? (
        <p className="muted" style={{ fontSize: '0.78rem' }}>Loading…</p>
      ) : w.current ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem' }}>
            <span style={{ fontSize: '1.5rem' }}>{wIcon(w.current.condition)}</span>
            <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>{Math.round(w.current.temp)}°F</span>
            <span style={{ fontSize: '0.78rem', color: '#7a907a' }}>{w.current.condition}</span>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.78rem', color: '#5a7a5a', marginBottom: '0.5rem' }}>
            <span>💧 {w.current.humidity}%</span>
            <span>💨 {Math.round(w.current.wind_speed)} mph</span>
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', overflowX: 'auto' }}>
            {w.daily?.slice(0, 7).map(day => (
              <div key={day.date} style={{ textAlign: 'center', fontSize: '0.72rem', minWidth: '30px' }}>
                <div style={{ color: '#7a907a' }}>{new Date(day.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' })}</div>
                <div>{wIcon(day.condition)}</div>
                <div style={{ fontWeight: 600 }}>{Math.round(day.high)}°</div>
                <div style={{ color: '#9ab49a' }}>{Math.round(day.low)}°</div>
                {day.precip_prob != null && <div style={{ color: '#4a80b4' }}>💧{day.precip_prob}%</div>}
              </div>
            ))}
          </div>
          <details style={{ marginTop: '0.4rem' }}>
            <summary style={{ fontSize: '0.75rem', color: '#3a6b35', cursor: 'pointer' }}>💧 Log rain as watering</summary>
            <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center', marginTop: '0.3rem', fontSize: '0.75rem', flexWrap: 'wrap' }}>
              <span style={{ color: '#7a907a' }}>Amount:</span>
              {(['light', 'moderate', 'heavy'] as const).map(a => (
                <button key={a} className={`btn-small${rainAmount === a ? '' : ' btn-link'}`}
                        style={{ fontSize: '0.68rem', padding: '1px 5px', background: rainAmount === a ? '#4a80b4' : undefined, color: rainAmount === a ? '#fff' : undefined }}
                        onClick={() => setRainAmount(a)}>{a}</button>
              ))}
              <button className="btn-small" style={{ fontSize: '0.72rem' }} onClick={handleLogRain}>
                Apply to all plants
              </button>
            </div>
          </details>
        </>
      ) : null}
    </div>

    {/* Tasks */}
    <div>
      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37', marginBottom: '0.4rem' }}>
        Tasks
        <button className="btn-small btn-link" style={{ fontSize: '0.7rem', marginLeft: '0.5rem' }} onClick={() => setRightPanelTab('calendar')}>View calendar →</button>
      </div>
      {tasks.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', marginBottom: '0.5rem' }}>
          {(tasks as {id: number; title: string; task_type?: string; due_date?: string; plant_name?: string}[]).map(t => (
            <div key={t.id} style={{ fontSize: '0.78rem', padding: '0.25rem 0.4rem', background: '#f0f5ef', borderRadius: '4px' }}>
              <div style={{ fontWeight: 600 }}>{t.task_type && t.task_type !== 'other' && <span style={{ fontSize: '0.7rem', background: '#e0eddc', padding: '1px 4px', borderRadius: '2px', marginRight: '4px' }}>{t.task_type}</span>}{t.title}</div>
              {(t.due_date || t.plant_name) && <div style={{ color: '#7a907a', fontSize: '0.72rem' }}>{t.due_date && `Due ${t.due_date}`}{t.plant_name && ` · ${t.plant_name}`}</div>}
            </div>
          ))}
        </div>
      ) : <p className="muted" style={{ fontSize: '0.78rem' }}>No pending tasks.</p>}

      <details>
        <summary style={{ fontSize: '0.78rem', color: '#3a6b35', cursor: 'pointer' }}>+ Add Task</summary>
        <form onSubmit={handleAddTask} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          <input type="text" placeholder="Task title" value={taskForm.title} onChange={e => setTaskForm(f => ({ ...f, title: e.target.value }))} required style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.2rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
          <input type="date" value={taskForm.due_date} onChange={e => setTaskForm(f => ({ ...f, due_date: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.2rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
          <button type="submit" className="btn-small" style={{ fontSize: '0.75rem' }}>Add</button>
          {taskSaved && <span className="muted" style={{ fontSize: '0.75rem' }}>{taskSaved}</span>}
        </form>
      </details>
    </div>

    {/* Plant care */}
    {carePanel && (
      <div style={{ borderTop: '1px solid #d0e0c8', paddingTop: '0.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{carePanel.plant_name}</div>
            {carePanel.scientific_name && <div style={{ fontSize: '0.78rem', color: '#7a907a', fontStyle: 'italic' }}>{carePanel.scientific_name}</div>}
            <div style={{ fontSize: '0.78rem', color: '#5a7a5a', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.2rem' }}>
              {carePanel.sunlight && <span>☀ {carePanel.sunlight}</span>}
              {carePanel.water && <span>💧 {carePanel.water}</span>}
              {carePanel.spacing_in && <span>↔ {carePanel.spacing_in}"</span>}
            </div>
          </div>
          <button className="btn-small" style={{ fontSize: '0.72rem' }} onClick={() => setCarePanel(null)}>Close</button>
        </div>
        {/* Select all like this */}
        {!carePanel.is_bed && carePanel.library_id && (() => {
          const libId = carePanel.library_id!;
          const count = canvasPlants.filter(c => c.library_id === libId).length;
          return count > 1 ? (
            <div style={{ marginBottom: '0.4rem' }}>
              <button className="btn-small btn-link" style={{ fontSize: '0.72rem' }}
                      onClick={() => setHighlightLibId(prev => prev === libId ? null : libId)}>
                {highlightLibId === libId ? '✕ Deselect all' : `◎ Select all like this (×${count})`}
              </button>
            </div>
          ) : null;
        })()}
        {/* Last care dates */}
        {!carePanel.is_bed && (carePanel.last_watered || carePanel.last_fertilized) && (
          <div style={{ fontSize: '0.75rem', color: '#5a7a5a', marginBottom: '0.4rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            {carePanel.last_watered && (
              <span>💧 {carePanel.last_watered}{carePanel.watering_amount ? ` (${carePanel.watering_amount})` : ''}</span>
            )}
            {carePanel.last_fertilized && (
              <span>🌿 {carePanel.last_fertilized}{carePanel.fertilizer_type ? ` · ${carePanel.fertilizer_type}` : ''}{carePanel.fertilizer_npk ? ` ${carePanel.fertilizer_npk}` : ''}</span>
            )}
          </div>
        )}
        <form onSubmit={handleCareSave} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <label style={{ fontSize: '0.78rem' }}>Seeded <input type="date" value={careForm.planted_date} onChange={e => setCareForm(f => ({ ...f, planted_date: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          <label style={{ fontSize: '0.78rem' }}>Transplanted <input type="date" value={careForm.transplant_date} onChange={e => setCareForm(f => ({ ...f, transplant_date: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
          <label style={{ fontSize: '0.78rem' }}>Notes <textarea rows={2} value={careForm.plant_notes} onChange={e => setCareForm(f => ({ ...f, plant_notes: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%', resize: 'vertical' }} /></label>
          {carePanel.is_bed && (
            <>
              <label style={{ fontSize: '0.78rem' }}>Watered <input type="date" value={careForm.last_watered} onChange={e => setCareForm(f => ({ ...f, last_watered: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
              <label style={{ fontSize: '0.78rem' }}>Fertilized <input type="date" value={careForm.last_fertilized} onChange={e => setCareForm(f => ({ ...f, last_fertilized: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%' }} /></label>
              <label style={{ fontSize: '0.78rem' }}>Health Notes <textarea rows={2} value={careForm.health_notes} onChange={e => setCareForm(f => ({ ...f, health_notes: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%', resize: 'vertical' }} /></label>
              <label style={{ fontSize: '0.78rem' }}>Stage
                <select value={careForm.stage} onChange={e => setCareForm(f => ({ ...f, stage: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '100%', marginTop: '0.1rem' }}>
                  <option value="seedling">Seedling 🌱</option>
                  <option value="growing">Growing 🌿</option>
                  <option value="harvesting">Harvesting 🥕</option>
                  <option value="done">Done ✓</option>
                </select>
              </label>
            </>
          )}
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <button type="submit" className="btn-small" style={{ fontSize: '0.75rem' }}>Save</button>
            {careSaved && <span className="muted" style={{ fontSize: '0.75rem' }}>Saved.</span>}
          </div>
        </form>
      </div>
    )}

    {/* Group plant instances */}
    {groupInfoPlants && (
      <div style={{ borderTop: '1px solid #d0e0c8', paddingTop: '0.75rem', marginBottom: '0.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#3a5c37' }}>
            {groupInfoPlants[0].name}
            {groupInfoPlants.length > 1 && (
              <span style={{ fontSize: '0.75rem', color: '#7a907a', fontWeight: 400, marginLeft: 6 }}>
                ({groupInfoPlants.length} plants)
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
            {groupInfoPlants[0].library_id != null && (() => {
              const libId = groupInfoPlants[0].library_id;
              const count = canvasPlants.filter(cp => cp.library_id === libId).length;
              return count > 0 ? (
                <button className="btn-small" style={{ fontSize: '0.65rem', padding: '1px 5px' }}
                  title="Highlight all instances on the canvas"
                  onClick={() => setHighlightLibId(highlightLibId === libId ? null : libId)}>
                  {highlightLibId === libId ? '✓ Selected' : `Select all (×${count})`}
                </button>
              ) : null;
            })()}
            <button className="btn-small" style={{ fontSize: '0.72rem' }}
              onClick={() => { setGroupInfoPlants(null); setLibInfo(null); setEditingPlantId(null); setLibEditMode(false); setLibImageMode(false); }}>✕</button>
          </div>
        </div>

        {/* Bulk controls — only shown for groups */}
        {groupInfoPlants.length > 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', marginBottom: '0.5rem', fontSize: '0.75rem', padding: '0.4rem 0.5rem', background: '#f0f7ef', borderRadius: 4 }}>
            {/* Status */}
            <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
              <span style={{ color: '#7a907a', minWidth: 52 }}>Status:</span>
              <select value={bulkStatusValue} onChange={e => setBulkStatusValue(e.target.value)}
                      style={{ font: 'inherit', fontSize: '0.75rem', padding: '1px 2px', border: '1px solid #c0d4be', borderRadius: 3 }}>
                <option value="planning">Planning</option>
                <option value="growing">Growing</option>
                <option value="harvested">Harvested</option>
              </select>
              <button className="btn-small" style={{ fontSize: '0.72rem' }}
                      onClick={handleBulkStatusUpdate} disabled={bulkSaving || bulkCareSaving}>
                {bulkSaving ? '…' : 'Apply'}
              </button>
            </div>
            {/* Water all */}
            <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
              <span style={{ color: '#7a907a', minWidth: 52 }}>💧 Water:</span>
              {(['light', 'moderate', 'heavy'] as const).map(a => (
                <button key={a} className={`btn-small${bulkWaterAmount === a ? '' : ' btn-link'}`}
                        style={{ fontSize: '0.65rem', padding: '1px 5px', background: bulkWaterAmount === a ? '#4a80b4' : undefined, color: bulkWaterAmount === a ? '#fff' : undefined }}
                        onClick={() => setBulkWaterAmount(a)}>{a}</button>
              ))}
              <button className="btn-small" style={{ fontSize: '0.72rem' }}
                      onClick={() => handleBulkCare('water')} disabled={bulkCareSaving || bulkSaving}>
                {bulkCareSaving ? '…' : 'Apply'}
              </button>
            </div>
            {/* Fertilize all */}
            <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ color: '#7a907a', minWidth: 52 }}>🌿 Feed:</span>
              <select value={bulkFertType} onChange={e => setBulkFertType(e.target.value)}
                      style={{ font: 'inherit', fontSize: '0.72rem', padding: '1px 2px', border: '1px solid #c0d4be', borderRadius: 3 }}>
                <option value="balanced">Balanced</option>
                <option value="nitrogen">Nitrogen</option>
                <option value="phosphorus">Phosphorus</option>
                <option value="potassium">Potassium</option>
                <option value="organic">Organic</option>
                <option value="other">Other</option>
              </select>
              <input type="text" value={bulkFertNpk} onChange={e => setBulkFertNpk(e.target.value)}
                     placeholder="N-P-K" style={{ font: 'inherit', fontSize: '0.72rem', padding: '1px 4px', border: '1px solid #c0d4be', borderRadius: 3, width: 64 }} />
              <button className="btn-small" style={{ fontSize: '0.72rem' }}
                      onClick={() => handleBulkCare('fertilize')} disabled={bulkCareSaving || bulkSaving}>
                {bulkCareSaving ? '…' : 'Apply'}
              </button>
            </div>
          </div>
        )}

        {/* Individual plant cards */}
        {groupInfoPlants.length > 1 ? (
          <details open>
            <summary style={{ cursor: 'pointer', fontSize: '0.78rem', color: '#5a7a5a', marginBottom: '0.3rem', userSelect: 'none' }}>
              {groupInfoPlants.length} plants · {summarizeStatuses(groupInfoPlants)}
            </summary>
            {groupInfoPlants.map((p, idx) => (
              <PlantCard key={p.id} p={p} idx={idx} label={`#${idx + 1}`}
                editingPlantId={editingPlantId} plantEditForm={plantEditForm} setPlantEditForm={setPlantEditForm}
                onStartEdit={startPlantEdit} onCancelEdit={() => setEditingPlantId(null)}
                onSave={handlePlantEditSave} />
            ))}
          </details>
        ) : (
          groupInfoPlants.map((p) => (
            <PlantCard key={p.id} p={p} idx={0} label={p.name}
              editingPlantId={editingPlantId} plantEditForm={plantEditForm} setPlantEditForm={setPlantEditForm}
              onStartEdit={startPlantEdit} onCancelEdit={() => setEditingPlantId(null)}
              onSave={handlePlantEditSave} />
          ))
        )}
        {plantEditSaved && <div style={{ fontSize: '0.75rem', color: '#3a6b35', marginTop: '0.2rem' }}>Saved.</div>}
      </div>
    )}

    {/* Library plant info */}
    {libInfo && (
      <div style={{ borderTop: '1px solid #d0e0c8', paddingTop: '0.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{libInfo.name}</div>
            {libInfo.scientific_name && <div style={{ fontSize: '0.78rem', color: '#7a907a', fontStyle: 'italic' }}>{libInfo.scientific_name}</div>}
            {libInfo.type && <div style={{ fontSize: '0.72rem', color: '#9ab49a' }}>{libInfo.type}</div>}
          </div>
          <div style={{ display: 'flex', gap: '0.3rem', flexShrink: 0 }}>
            <button className="btn-small" style={{ fontSize: '0.72rem' }} onClick={openLibEdit} title="Edit plant details">✏</button>
            <button className="btn-small" style={{ fontSize: '0.72rem' }} onClick={openLibImageMode} title="Manage images">🖼</button>
            <button className="btn-small" style={{ fontSize: '0.72rem' }} onClick={() => { setLibInfo(null); setLibEditMode(false); setLibImageMode(false); }}>✕</button>
          </div>
        </div>

        {/* Image section */}
        {!libImageMode ? (
          libInfo.image_filename && (
            <img src={plantImageUrl(libInfo.image_filename) ?? ''} alt={libInfo.name}
                 style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 4, marginBottom: '0.4rem', cursor: 'pointer' }}
                 onClick={openLibImageMode} title="Click to manage images" />
          )
        ) : (
          <div style={{ marginBottom: '0.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#3a5c37' }}>Images</span>
              <div style={{ display: 'flex', gap: '0.3rem' }}>
                <label className="btn-small" style={{ fontSize: '0.72rem', cursor: 'pointer' }} title="Upload new image">
                  + Upload
                  <input type="file" accept="image/*" style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) uploadLibImage(f); e.target.value = ''; }} />
                </label>
                <button className="btn-small" style={{ fontSize: '0.72rem' }} onClick={() => setLibImageMode(false)}>Done</button>
              </div>
            </div>
            {libImages.length === 0 ? (
              <p style={{ fontSize: '0.72rem', color: '#9ab49a' }}>No images yet.</p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {libImages.map(img => (
                  <div key={img.id} style={{ position: 'relative', border: img.is_primary ? '2px solid #3a6b35' : '2px solid transparent', borderRadius: 4, overflow: 'hidden', cursor: 'pointer' }}
                       title={img.is_primary ? 'Primary image' : 'Click to set as primary'}
                       onClick={() => !img.is_primary && setLibPrimaryImage(img.id)}>
                    <img src={plantImageUrl(img.filename) ?? ''} alt=""
                         style={{ width: 52, height: 52, objectFit: 'cover', display: 'block' }} />
                    {img.is_primary && <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'rgba(58,107,53,0.8)', fontSize: '0.6rem', color: '#fff', textAlign: 'center' }}>primary</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Edit form */}
        {libEditMode ? (
          <form onSubmit={handleLibEditSave} style={{ marginBottom: '0.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.3rem 0.5rem', fontSize: '0.75rem', marginBottom: '0.4rem' }}>
              <label style={{ color: '#5a7a5a' }}>
                Sunlight
                <select value={libEditForm.sunlight} onChange={e => setLibEditForm(f => ({ ...f, sunlight: e.target.value }))}
                        style={{ width: '100%', fontSize: '0.75rem', marginTop: 2, padding: '1px 2px' }}>
                  <option value="">—</option>
                  <option value="full sun">Full sun</option>
                  <option value="partial shade">Partial shade</option>
                  <option value="full shade">Full shade</option>
                </select>
              </label>
              <label style={{ color: '#5a7a5a' }}>
                Water
                <select value={libEditForm.water} onChange={e => setLibEditForm(f => ({ ...f, water: e.target.value }))}
                        style={{ width: '100%', fontSize: '0.75rem', marginTop: 2, padding: '1px 2px' }}>
                  <option value="">—</option>
                  <option value="low">Low</option>
                  <option value="moderate">Moderate</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label style={{ color: '#5a7a5a' }}>
                Spacing (in)
                <input type="number" min="1" step="1" value={libEditForm.spacing_in}
                       onChange={e => setLibEditForm(f => ({ ...f, spacing_in: e.target.value }))}
                       style={{ width: '100%', fontSize: '0.75rem', marginTop: 2, padding: '1px 2px' }} />
              </label>
              <label style={{ color: '#5a7a5a' }}>
                Germ. days
                <input type="number" min="1" step="1" value={libEditForm.days_to_germination}
                       onChange={e => setLibEditForm(f => ({ ...f, days_to_germination: e.target.value }))}
                       style={{ width: '100%', fontSize: '0.75rem', marginTop: 2, padding: '1px 2px' }} />
              </label>
              <label style={{ color: '#5a7a5a' }}>
                Harvest days
                <input type="number" min="1" step="1" value={libEditForm.days_to_harvest}
                       onChange={e => setLibEditForm(f => ({ ...f, days_to_harvest: e.target.value }))}
                       style={{ width: '100%', fontSize: '0.75rem', marginTop: 2, padding: '1px 2px' }} />
              </label>
            </div>
            <label style={{ fontSize: '0.75rem', color: '#5a7a5a', display: 'block', marginBottom: '0.3rem' }}>
              Notes
              <textarea rows={2} value={libEditForm.notes}
                        onChange={e => setLibEditForm(f => ({ ...f, notes: e.target.value }))}
                        style={{ width: '100%', fontSize: '0.75rem', marginTop: 2, padding: '2px 4px', resize: 'vertical', boxSizing: 'border-box' }} />
            </label>
            <div style={{ display: 'flex', gap: '0.3rem' }}>
              <button type="submit" className="btn-small" style={{ fontSize: '0.72rem' }}>Save</button>
              <button type="button" className="btn-small" style={{ fontSize: '0.72rem' }} onClick={() => setLibEditMode(false)}>Cancel</button>
            </div>
          </form>
        ) : (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem 0.75rem', fontSize: '0.78rem', color: '#5a7a5a', marginBottom: '0.4rem' }}>
              {libInfo.sunlight && <span>☀ {libInfo.sunlight}</span>}
              {libInfo.water && <span>💧 {libInfo.water}</span>}
              {libInfo.spacing_in && <span>↔ {libInfo.spacing_in}"</span>}
              {libInfo.days_to_germination && <span>🌱 {libInfo.days_to_germination}d germ.</span>}
              {libInfo.days_to_harvest && <span>🥕 {libInfo.days_to_harvest}d harvest</span>}
            </div>
            {libInfo.companion_plants && (
              <div style={{ fontSize: '0.75rem', marginBottom: '0.3rem' }}>
                <span style={{ fontWeight: 600, color: '#4a6a47' }}>Companions: </span>
                <span style={{ color: '#5a7a5a' }}>{libInfo.companion_plants}</span>
              </div>
            )}
            {libInfo.growing_notes && (
              <div style={{ fontSize: '0.75rem', color: '#5a7a5a', lineHeight: 1.4 }}>{libInfo.growing_notes}</div>
            )}
          </>
        )}
      </div>
    )}

  </>);
}

// ── PlantCard sub-component ────────────────────────────────────────────────────
function PlantCard({
  p, idx, label, editingPlantId, plantEditForm, setPlantEditForm,
  onStartEdit, onCancelEdit, onSave,
}: {
  p: GardenPlant;
  idx: number;
  label: string;
  editingPlantId: number | null;
  plantEditForm: { status: string; planted_date: string; transplant_date: string; expected_harvest: string; notes: string };
  setPlantEditForm: React.Dispatch<React.SetStateAction<{ status: string; planted_date: string; transplant_date: string; expected_harvest: string; notes: string }>>;
  onStartEdit: (p: GardenPlant) => void;
  onCancelEdit: () => void;
  onSave: (plantId: number, e: React.FormEvent) => Promise<void>;
}) {
  return (
    <div style={{ background: '#f0f6ef', borderRadius: 4, padding: '0.4rem 0.5rem', marginBottom: '0.3rem', fontSize: '0.78rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, color: '#3a5c37' }}>{label}</span>
        <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', color: '#5a7a5a', background: '#ddeedd', borderRadius: 3, padding: '1px 5px' }}>
            {p.status || 'planning'}
          </span>
          {editingPlantId === p.id
            ? <button className="btn-small" style={{ fontSize: '0.68rem' }} onClick={onCancelEdit}>Cancel</button>
            : <button className="btn-small" style={{ fontSize: '0.68rem' }} onClick={() => onStartEdit(p)}>Edit</button>
          }
        </div>
      </div>

      {editingPlantId !== p.id && (
        <div style={{ marginTop: '0.2rem', color: '#5a7a5a', fontSize: '0.73rem', display: 'flex', flexWrap: 'wrap', gap: '0.2rem 0.5rem' }}>
          {p.planted_date && <span>🌱 {p.planted_date}</span>}
          {p.transplant_date && <span>↳ {p.transplant_date}</span>}
          {p.expected_harvest && <span>🥕 {p.expected_harvest}</span>}
          {p.last_watered && <span>💧 {p.last_watered}{p.watering_amount ? ` (${p.watering_amount})` : ''}</span>}
          {p.last_fertilized && <span>🌿 {p.last_fertilized}{p.fertilizer_type ? ` · ${p.fertilizer_type}` : ''}{p.fertilizer_npk ? ` ${p.fertilizer_npk}` : ''}</span>}
          {p.notes && <span style={{ width: '100%', fontStyle: 'italic', color: '#7a907a' }}>{p.notes}</span>}
          {!p.planted_date && !p.transplant_date && !p.expected_harvest && !p.last_watered && !p.last_fertilized && !p.notes && (
            <span style={{ color: '#b0c8b0' }}>No dates recorded</span>
          )}
        </div>
      )}

      {editingPlantId === p.id && (
        <form onSubmit={e => onSave(p.id, e)} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label style={{ fontSize: '0.75rem', color: '#5a7a5a' }}>
            Status
            <select value={plantEditForm.status} onChange={e => setPlantEditForm(f => ({ ...f, status: e.target.value }))}
                    style={{ width: '100%', font: 'inherit', fontSize: '0.75rem', marginTop: 1, padding: '1px 2px', border: '1px solid #c0d4be', borderRadius: 3 }}>
              <option value="planning">Planning</option>
              <option value="growing">Growing</option>
              <option value="harvested">Harvested</option>
            </select>
          </label>
          <label style={{ fontSize: '0.75rem', color: '#5a7a5a' }}>
            Seeded
            <input type="date" value={plantEditForm.planted_date}
                   onChange={e => setPlantEditForm(f => ({ ...f, planted_date: e.target.value }))}
                   style={{ width: '100%', font: 'inherit', fontSize: '0.75rem', marginTop: 1, padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: 3 }} />
          </label>
          <label style={{ fontSize: '0.75rem', color: '#5a7a5a' }}>
            Transplanted
            <input type="date" value={plantEditForm.transplant_date}
                   onChange={e => setPlantEditForm(f => ({ ...f, transplant_date: e.target.value }))}
                   style={{ width: '100%', font: 'inherit', fontSize: '0.75rem', marginTop: 1, padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: 3 }} />
          </label>
          <label style={{ fontSize: '0.75rem', color: '#5a7a5a' }}>
            Exp. harvest
            <input type="date" value={plantEditForm.expected_harvest}
                   onChange={e => setPlantEditForm(f => ({ ...f, expected_harvest: e.target.value }))}
                   style={{ width: '100%', font: 'inherit', fontSize: '0.75rem', marginTop: 1, padding: '0.15rem', border: '1px solid #c0d4be', borderRadius: 3 }} />
          </label>
          <label style={{ fontSize: '0.75rem', color: '#5a7a5a' }}>
            Notes
            <textarea rows={2} value={plantEditForm.notes}
                      onChange={e => setPlantEditForm(f => ({ ...f, notes: e.target.value }))}
                      style={{ width: '100%', font: 'inherit', fontSize: '0.75rem', marginTop: 1, padding: '2px 4px', border: '1px solid #c0d4be', borderRadius: 3, resize: 'vertical', boxSizing: 'border-box' }} />
          </label>
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            <button type="submit" className="btn-small" style={{ fontSize: '0.72rem' }}>Save</button>
            <button type="button" className="btn-small" style={{ fontSize: '0.72rem' }} onClick={onCancelEdit}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}
