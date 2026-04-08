import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useGardens, useGarden } from '../hooks/useGardens';
import ChatWidget from '../components/ChatWidget';

// ── Constants ─────────────────────────────────────────────────────────────────
const PX = 60; // px per foot at zoom=1
const PX_PER_IN = PX / 12;

// ── Types ─────────────────────────────────────────────────────────────────────
interface Bed {
  id: number; name: string; width_ft: number; height_ft: number;
  pos_x?: number; pos_y?: number; garden_id?: number;
  depth_ft?: number; location?: string; description?: string;
  soil_notes?: string; soil_ph?: number;
  clay_pct?: number; compost_pct?: number; sand_pct?: number;
  plant_count?: number;
}
interface GridChip {
  id: number; grid_x: number; grid_y: number;
  plant_name: string; image_filename?: string; spacing_in: number; stage?: string;
}
interface CanvasPlant {
  id: number; name: string; pos_x: number; pos_y: number; radius_ft: number;
  color?: string; display_mode?: string; image_filename?: string; custom_image?: string;
  library_id?: number; plant_id?: number; spacing_in?: number;
}
interface LibPlant {
  id: number; name: string; type?: string; image_filename?: string; spacing_in?: number;
}
interface GardenPlant {
  id: number; name: string; library_id?: number; image_filename?: string;
  spacing_in?: number; status?: string;
  planted_date?: string; transplant_date?: string; expected_harvest?: string;
  type?: string;
}
interface AnnotationShape {
  id: string;
  type: 'rect' | 'ellipse' | 'line' | 'free';
  objectType?: string;   // 'path' | 'fence' | 'water' | 'structure' | 'hedge' | 'generic'
  stroke: string; strokeWidth: number; fill: string;
  dashArray?: string;
  x?: number; y?: number; w?: number; h?: number;
  cx?: number; cy?: number; rx?: number; ry?: number;
  x1?: number; y1?: number; x2?: number; y2?: number;
  points?: [number, number][];
}
interface DrawState {
  tool: string; el: SVGElement;
  startX: number; startY: number;
  points?: [number, number][]; lastX?: number; lastY?: number; pathLen?: number;
}

interface CareData {
  id: number; plant_id?: number; plant_name: string; scientific_name?: string;
  sunlight?: string; water?: string; spacing_in?: number; days_to_harvest?: number;
  planted_date?: string; transplant_date?: string; last_watered?: string;
  last_fertilized?: string; last_harvest?: string; health_notes?: string;
  stage?: string; plant_notes?: string; is_bed: boolean;
}

// ── API helper ────────────────────────────────────────────────────────────────
async function api(method: string, path: string, body?: unknown) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

function snap(value: number) { return Math.round(value / PX) * PX; }
function plantSpan(spacingIn: number, tileIn: number) { return Math.max(1, Math.round(spacingIn / tileIn)); }

// ── BedGrid component ─────────────────────────────────────────────────────────
function BedGrid({
  bed, chips, tileIn, onCellClick, onChipRemove, onChipClick, dragPlant, zoom,
}: {
  bed: Bed; chips: GridChip[]; tileIn: number;
  onCellClick: (bedId: number, cx: number, cy: number) => void;
  onChipRemove: (bedId: number, chip: GridChip) => void;
  onChipClick: (chip: GridChip) => void;
  dragPlant: LibPlant | GardenPlant | null;
  zoom: number;
}) {
  const cols = Math.max(1, Math.round(bed.width_ft * 12 / tileIn));
  const rows = Math.max(1, Math.round(bed.height_ft * 12 / tileIn));
  const tilePx = tileIn * PX_PER_IN;

  const occupied = new Set<string>();
  for (const chip of chips) {
    const cx = Math.floor(chip.grid_x / tileIn);
    const cy = Math.floor(chip.grid_y / tileIn);
    const span = plantSpan(chip.spacing_in, tileIn);
    for (let r = cy; r < cy + span; r++)
      for (let c = cx; c < cx + span; c++)
        occupied.add(`${c},${r}`);
  }

  const [hover, setHover] = useState<{cx: number; cy: number; span: number; ok: boolean} | null>(null);

  function canPlace(cx: number, cy: number, span: number) {
    if (cx + span > cols || cy + span > rows) return false;
    for (let r = cy; r < cy + span; r++)
      for (let c = cx; c < cx + span; c++)
        if (occupied.has(`${c},${r}`)) return false;
    return true;
  }

  const STAGE_LABELS: Record<string, string> = { seedling: '🌱', growing: '🌿', harvesting: '🥕', done: '✓' };

  return (
    <div
      className="canvas-bed-grid"
      style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, ${tilePx}px)`, gridTemplateRows: `repeat(${rows}, ${tilePx}px)`, position: 'relative' }}
      onDragOver={e => {
        if (!dragPlant) return;
        e.preventDefault(); e.stopPropagation();
        const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
        const cx = Math.floor((e.clientX - rect.left) / zoom / tilePx);
        const cy = Math.floor((e.clientY - rect.top) / zoom / tilePx);
        const spacingIn = (dragPlant as LibPlant | GardenPlant).spacing_in ?? 12;
        const span = plantSpan(spacingIn, tileIn);
        const ok = canPlace(cx, cy, span);
        setHover({ cx, cy, span, ok });
      }}
      onDragLeave={() => setHover(null)}
      onDrop={e => {
        e.preventDefault(); e.stopPropagation();
        if (!hover || !dragPlant) { setHover(null); return; }
        if (hover.ok) onCellClick(bed.id, hover.cx, hover.cy);
        setHover(null);
      }}
      onClick={e => {
        if (!dragPlant) return;
        const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
        const cx = Math.floor((e.clientX - rect.left) / zoom / tilePx);
        const cy = Math.floor((e.clientY - rect.top) / zoom / tilePx);
        onCellClick(bed.id, cx, cy);
      }}
    >
      {Array.from({ length: rows }, (_, y) =>
        Array.from({ length: cols }, (_, x) => {
          const isOcc = occupied.has(`${x},${y}`);
          const inHover = hover && x >= hover.cx && x < hover.cx + hover.span && y >= hover.cy && y < hover.cy + hover.span;
          return (
            <div key={`${x},${y}`}
                 className={`grid-cell${isOcc ? ' cell-occupied' : ''}${inHover ? (hover!.ok ? ' cell-drop-target' : ' cell-drop-bad') : ''}`}
                 style={{ width: tilePx, height: tilePx }} />
          );
        })
      )}
      {chips.map(chip => {
        const cx = Math.floor(chip.grid_x / tileIn);
        const cy = Math.floor(chip.grid_y / tileIn);
        const span = plantSpan(chip.spacing_in, tileIn);
        const imgSrc = chip.image_filename ? `/static/plant_images/${chip.image_filename}` : null;
        return (
          <div
            key={chip.id}
            className="grid-plant-chip"
            style={{ position: 'absolute', left: cx * tilePx, top: cy * tilePx, width: span * tilePx, height: span * tilePx }}
            onClick={e => { e.stopPropagation(); onChipClick(chip); }}
          >
            {imgSrc ? (
              <img src={imgSrc} className="chip-img" alt={chip.plant_name} />
            ) : (
              <span className="chip-img chip-img--empty">🌱</span>
            )}
            <span className="chip-name">{chip.plant_name}</span>
            {chip.stage && chip.stage !== 'seedling' && (
              <span className={`chip-stage-badge stage-${chip.stage}`}>{STAGE_LABELS[chip.stage] || chip.stage}</span>
            )}
            <button className="chip-remove" onClick={e => { e.stopPropagation(); onChipRemove(bed.id, chip); }}>×</button>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Planner ──────────────────────────────────────────────────────────────
export default function Planner() {
  const [searchParams, setSearchParams] = useSearchParams();
  const gardenIdStr = searchParams.get('garden');
  const [gardenId, setGardenId] = useState(gardenIdStr ? parseInt(gardenIdStr) : 0);

  const { data: gardens } = useGardens();
  const { data: garden } = useGarden(gardenId);

  const [zoom, setZoom] = useState<number>(() => parseFloat(localStorage.getItem('plannerZoom') || '1'));
  const [tileIn, setTileIn] = useState(12);

  // Canvas beds (placed on canvas) and unplaced beds (sidebar)
  const [canvasBeds, setCanvasBeds] = useState<Bed[]>([]);
  const [paletteBeds, setPaletteBeds] = useState<Bed[]>([]);
  const [bedChips, setBedChips] = useState<Record<number, GridChip[]>>({});

  // Canvas plants (circles)
  const [canvasPlants, setCanvasPlants] = useState<CanvasPlant[]>([]);

  // Palette plants
  const [libPlants, setLibPlants] = useState<LibPlant[]>([]);
  const [gardenPlants, setGardenPlants] = useState<GardenPlant[]>([]);
  const [plantSearch, setPlantSearch] = useState('');

  // UI state
  const [selectedPlant, setSelectedPlant] = useState<LibPlant | GardenPlant | null>(null);
  const [carePanel, setCarePanel] = useState<CareData | null>(null);
  const [careSaved, setCareSaved] = useState(false);
  const [careForm, setCareForm] = useState({ planted_date: '', transplant_date: '', plant_notes: '', last_watered: '', last_fertilized: '', last_harvest: '', health_notes: '', stage: 'seedling' });
  const [rightPanelOpen, setRightPanelOpen] = useState(() => localStorage.getItem('plannerRightPanel') === 'open');
  const [chatOpen, setChatOpen] = useState(false);

  // Library search
  const [libSearch, setLibSearch] = useState('');
  const [libSearchResults, setLibSearchResults] = useState<LibPlant[]>([]);
  const [libSearchLoading, setLibSearchLoading] = useState(false);

  // Right panel tabs & task calendar
  const [rightPanelTab, setRightPanelTab] = useState<'info' | 'timeline' | 'calendar'>('info');
  const [calYear, setCalYear] = useState(() => new Date().getFullYear());
  const [calMonth, setCalMonth] = useState(() => new Date().getMonth());

  // ── Drawing / annotation state ──────────────────────────────────────────────
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeObjectType, setActiveObjectType] = useState<string>('generic');
  const [strokeColor, setStrokeColor] = useState('#2d5a1b');
  const [fillColor, setFillColor] = useState('#a8d5a2');
  const [noFill, setNoFill] = useState(true);
  const [strokeWidth, setStrokeWidth] = useState(2);
  const [dashArray, setDashArray] = useState('');
  const [annShapes, setAnnShapes] = useState<AnnotationShape[]>([]);
  const svgRef      = useRef<SVGSVGElement>(null);
  const drawRef     = useRef<DrawState | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Selected bed for detail panel ──────────────────────────────────────────
  const [selectedBed, setSelectedBed] = useState<Bed | null>(null);

  const [weather, setWeather] = useState<unknown>(null);
  const [tasks, setTasks] = useState<unknown[]>([]);
  const [taskForm, setTaskForm] = useState({ title: '', due_date: '', description: '' });
  const [taskSaved, setTaskSaved] = useState('');

  const [addBedForm, setAddBedForm] = useState({ name: '', width_ft: '4', height_ft: '8' });

  const canvasRef = useRef<HTMLDivElement>(null);
  const dragBedRef = useRef<{ bedId: number; offsetX: number; offsetY: number } | null>(null);
  const cpDragRef = useRef<{ cpId: number; mode: 'move' | 'resize'; startX: number; startY?: number; startLeft: number; startTop: number; startDiam: number } | null>(null);

  // ── Load garden data ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!gardenId) {
      if (gardens && gardens.length > 0) setGardenId(gardens[0].id);
      return;
    }
    loadGardenData();
  }, [gardenId]);

  async function loadGardenData() {
    if (!gardenId) return;
    // Fetch beds
    const bedsData = await api('GET', `/api/beds?garden_id=${gardenId}`);
    const placed: Bed[] = [], unplaced: Bed[] = [];
    for (const b of bedsData as Bed[]) {
      if (b.garden_id === gardenId) placed.push(b); // all beds belong to this garden already
      if (b.pos_x == null) unplaced.push(b); else placed.push(b);
    }
    // Since all beds have the garden_id, separate by whether they're on canvas
    const canvas: Bed[] = [], sidebar: Bed[] = [];
    for (const b of bedsData as Bed[]) {
      if (b.pos_x != null && b.pos_x >= 0) canvas.push(b);
      else sidebar.push(b);
    }
    setCanvasBeds(canvas);
    setPaletteBeds(sidebar);

    // Load grid chips for each bed
    const chipsMap: Record<number, GridChip[]> = {};
    await Promise.all((bedsData as Bed[]).map(async b => {
      const g = await api('GET', `/api/beds/${b.id}/grid`);
      chipsMap[b.id] = g.placed || [];
    }));
    setBedChips(chipsMap);

    // Canvas plants
    const cpData = await api('GET', `/api/gardens/${gardenId}/canvas-plants`);
    setCanvasPlants(cpData as CanvasPlant[]);

    // Library plants (first 100)
    const libData = await api('GET', `/api/library?per_page=100`);
    setLibPlants((libData.entries || []) as LibPlant[]);

    // Garden plants
    const gpData = await api('GET', `/api/plants?garden_id=${gardenId}`);
    setGardenPlants(gpData as GardenPlant[]);

    if (rightPanelOpen) loadPanelData();

    // Annotations
    const annData = await api('GET', `/api/gardens/${gardenId}/annotations`);
    setAnnShapes(annData.shapes || []);
  }

  async function loadPanelData() {
    if (!gardenId) return;
    if (garden?.latitude) {
      const w = await api('GET', `/api/gardens/${gardenId}/weather`);
      setWeather(w);
    }
    const t = await api('GET', `/api/gardens/${gardenId}/tasks`);
    setTasks(t as unknown[]);
  }

  useEffect(() => {
    if (rightPanelOpen && gardenId) loadPanelData();
  }, [rightPanelOpen, gardenId]);

  // Zoom persistence
  useEffect(() => {
    localStorage.setItem('plannerZoom', String(zoom));
  }, [zoom]);

  // Debounced library search
  useEffect(() => {
    if (!libSearch.trim()) { setLibSearchResults([]); return; }
    setLibSearchLoading(true);
    const timer = setTimeout(async () => {
      const data = await api('GET', `/api/library?q=${encodeURIComponent(libSearch.trim())}&per_page=50`);
      setLibSearchResults((data.entries || []) as LibPlant[]);
      setLibSearchLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [libSearch]);

  // ── Bed placement ────────────────────────────────────────────────────────────
  async function handlePlaceBed(bedId: number, sx: number, sy: number) {
    await api('POST', `/api/beds/${bedId}/position`, { x: sx / PX, y: sy / PX });
    const bed = paletteBeds.find(b => b.id === bedId);
    if (!bed) return;
    const placed = { ...bed, pos_x: sx / PX, pos_y: sy / PX };
    setCanvasBeds(prev => [...prev, placed]);
    setPaletteBeds(prev => prev.filter(b => b.id !== bedId));
  }

  async function handleMoveBed(bedId: number, sx: number, sy: number) {
    await api('POST', `/api/beds/${bedId}/position`, { x: sx / PX, y: sy / PX });
    setCanvasBeds(prev => prev.map(b => b.id === bedId ? { ...b, pos_x: sx / PX, pos_y: sy / PX } : b));
  }

  async function handleDeleteBed(bedId: number, name: string) {
    if (!confirm(`Delete bed "${name}"? This will remove all plants placed in it.`)) return;
    const r = await api('POST', `/api/beds/${bedId}/delete`);
    if (r.ok) {
      setCanvasBeds(prev => prev.filter(b => b.id !== bedId));
      setPaletteBeds(prev => prev.filter(b => b.id !== bedId));
    }
  }

  async function handleAddBed(e: React.FormEvent) {
    e.preventDefault();
    if (!gardenId) return;
    const r = await api('POST', '/api/beds', {
      name: addBedForm.name,
      width_ft: parseFloat(addBedForm.width_ft) || 4,
      height_ft: parseFloat(addBedForm.height_ft) || 8,
      garden_id: gardenId,
    });
    if (r.ok) {
      setPaletteBeds(prev => [...prev, r.bed]);
      setAddBedForm(f => ({ ...f, name: '' }));
    }
  }

  // ── Plant grid placement ──────────────────────────────────────────────────────
  async function handleCellClick(bedId: number, cx: number, cy: number) {
    if (!selectedPlant) return;
    const payload: Record<string, unknown> = {
      grid_x: cx * tileIn,
      grid_y: cy * tileIn,
      spacing_in: selectedPlant.spacing_in ?? 12,
    };
    if ('library_id' in selectedPlant && selectedPlant.library_id) payload.library_id = selectedPlant.library_id;
    else if ('id' in selectedPlant) {
      // GardenPlant
      const gp = selectedPlant as GardenPlant;
      if (gp.library_id) payload.library_id = gp.library_id;
    }
    const r = await api('POST', `/api/beds/${bedId}/grid-plant`, payload);
    if (r.ok) {
      const chip: GridChip = { id: r.id, grid_x: cx * tileIn, grid_y: cy * tileIn, plant_name: r.plant_name, image_filename: r.image_filename, spacing_in: r.spacing_in || payload.spacing_in as number, stage: 'seedling' };
      setBedChips(prev => ({ ...prev, [bedId]: [...(prev[bedId] || []), chip] }));
    }
  }

  async function handleChipRemove(bedId: number, chip: GridChip) {
    const r = await api('POST', `/api/bedplants/${chip.id}/delete`);
    if (r.ok) {
      setBedChips(prev => ({ ...prev, [bedId]: (prev[bedId] || []).filter(c => c.id !== chip.id) }));
      if (carePanel?.id === chip.id) setCarePanel(null);
    }
  }

  async function handleChipClick(chip: GridChip) {
    const d = await api('GET', `/api/bedplants/${chip.id}`);
    setCarePanel({ ...d, is_bed: true });
    setCareForm({ planted_date: d.planted_date || '', transplant_date: d.transplant_date || '', plant_notes: d.plant_notes || '', last_watered: d.last_watered || '', last_fertilized: d.last_fertilized || '', last_harvest: d.last_harvest || '', health_notes: d.health_notes || '', stage: d.stage || 'seedling' });
    setCareSaved(false);
    if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); }
  }

  // ── Canvas plant circles ──────────────────────────────────────────────────────
  const handleCanvasDrop = useCallback(async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const canvasEl = canvasRef.current;
    if (!canvasEl || !selectedPlant || !gardenId) return;
    // Check if dropped on a grid — if so, skip (grid handles it)
    const target = document.elementFromPoint(e.clientX, e.clientY);
    if (target?.closest('.canvas-bed-grid')) return;
    if (target?.closest('.canvas-bed')) return;

    const rect = canvasEl.getBoundingClientRect();
    const posX = (e.clientX - rect.left) / zoom / PX;
    const posY = (e.clientY - rect.top) / zoom / PX;
    const payload: Record<string, unknown> = { pos_x: posX, pos_y: posY };
    const lp = selectedPlant as LibPlant;
    const gp = selectedPlant as GardenPlant;
    if (lp.id && !('library_id' in selectedPlant)) payload.library_id = lp.id;
    else if (gp.library_id) payload.library_id = gp.library_id;
    const r = await api('POST', `/api/gardens/${gardenId}/canvas-plants`, payload);
    if (r.ok) {
      setCanvasPlants(prev => [...prev, r.canvas_plant]);
      if (r.canvas_plant.plant_id && !gardenPlants.find(p => p.id === r.canvas_plant.plant_id)) {
        setGardenPlants(prev => [...prev, { id: r.canvas_plant.plant_id, name: r.canvas_plant.name, library_id: r.canvas_plant.library_id, image_filename: r.canvas_plant.image_filename, spacing_in: r.canvas_plant.spacing_in }]);
      }
    }
  }, [selectedPlant, gardenId, zoom, gardenPlants]);

  async function handleDeleteCanvasPlant(cp: CanvasPlant) {
    if (!confirm(`Remove "${cp.name}" from canvas?`)) return;
    const r = await api('POST', `/api/canvas-plants/${cp.id}/delete`, {});
    if (r.ok) {
      setCanvasPlants(prev => prev.filter(c => c.id !== cp.id));
      if (carePanel && 'plant_id' in carePanel && carePanel.plant_id === cp.plant_id) setCarePanel(null);
    }
  }

  async function handleCanvasPlantClick(cp: CanvasPlant) {
    const d = await api('GET', `/api/canvas-plants/${cp.id}`);
    setCarePanel({ ...d, plant_name: d.name, is_bed: false });
    setCareForm({ planted_date: d.planted_date || '', transplant_date: d.transplant_date || '', plant_notes: d.plant_notes || '', last_watered: '', last_fertilized: '', last_harvest: '', health_notes: '', stage: 'seedling' });
    setCareSaved(false);
    if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); }
  }

  // Pointer events for canvas plant drag/resize
  function handleCpPointerDown(e: React.PointerEvent, cp: CanvasPlant, mode: 'move' | 'resize') {
    e.stopPropagation(); e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const diam = cp.radius_ft * PX * 2;
    const leftPx = cp.pos_x * PX - cp.radius_ft * PX;
    const topPx = cp.pos_y * PX - cp.radius_ft * PX;
    cpDragRef.current = { cpId: cp.id, mode, startX: e.clientX, startY: e.clientY, startLeft: leftPx, startTop: topPx, startDiam: diam };
  }

  function handleCpPointerMove(e: React.PointerEvent, cp: CanvasPlant) {
    const ref = cpDragRef.current;
    if (!ref || ref.cpId !== cp.id) return;
    e.preventDefault();
    if (ref.mode === 'move') {
      const dx = (e.clientX - ref.startX) / zoom;
      const dy = (e.clientY - ref.startY!) / zoom;
      const el = document.getElementById(`cp-${cp.id}`);
      if (el) { el.style.left = `${Math.max(0, ref.startLeft + dx)}px`; el.style.top = `${Math.max(0, ref.startTop + dy)}px`; }
    } else {
      const dx = (e.clientX - ref.startX) / zoom;
      const newDiam = Math.max(PX * 0.5, ref.startDiam + dx * 2);
      const delta = newDiam - ref.startDiam;
      const el = document.getElementById(`cp-${cp.id}`);
      if (el) { el.style.width = `${newDiam}px`; el.style.height = `${newDiam}px`; el.style.left = `${ref.startLeft - delta / 2}px`; el.style.top = `${ref.startTop - delta / 2}px`; }
    }
  }

  async function handleCpPointerUp(e: React.PointerEvent, cp: CanvasPlant) {
    const ref = cpDragRef.current;
    if (!ref || ref.cpId !== cp.id) return;
    cpDragRef.current = null;
    const el = document.getElementById(`cp-${cp.id}`);
    if (!el) return;
    const newDiam = parseFloat(el.style.width);
    const newLeft = parseFloat(el.style.left);
    const newTop = parseFloat(el.style.top);
    if (ref.mode === 'move') {
      const newX = (newLeft + newDiam / 2) / PX;
      const newY = (newTop + newDiam / 2) / PX;
      await api('POST', `/api/canvas-plants/${cp.id}/position`, { x: newX, y: newY });
      setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, pos_x: newX, pos_y: newY } : c));
    } else {
      const newRadius = newDiam / 2 / PX;
      await api('POST', `/api/canvas-plants/${cp.id}/radius`, { radius_ft: newRadius });
      setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, radius_ft: newRadius } : c));
    }
  }

  // ── Bed drag on canvas ────────────────────────────────────────────────────────
  function handleBedDragStart(e: React.DragEvent, bed: Bed) {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    dragBedRef.current = { bedId: bed.id, offsetX: e.clientX - rect.left, offsetY: e.clientY - rect.top };
    e.dataTransfer.effectAllowed = 'move';
    setTimeout(() => (e.currentTarget as HTMLElement).classList.add('dragging'), 0);
  }

  function handleBedDragEnd(e: React.DragEvent) {
    (e.currentTarget as HTMLElement).classList.remove('dragging');
  }

  async function handleCanvasDragOver(e: React.DragEvent) {
    e.preventDefault();
    const ref = dragBedRef.current;
    if (!ref) return;
    const cr = canvasRef.current!.getBoundingClientRect();
    const rawX = (e.clientX - cr.left - ref.offsetX) / zoom;
    const rawY = (e.clientY - cr.top - ref.offsetY) / zoom;
    const el = document.getElementById(`canvas-bed-${ref.bedId}`);
    if (el) { el.style.left = `${snap(Math.max(0, rawX))}px`; el.style.top = `${snap(Math.max(0, rawY))}px`; }
  }

  async function handleCanvasDropBed(e: React.DragEvent) {
    e.preventDefault();
    const ref = dragBedRef.current;
    if (!ref) return;
    const cr = canvasRef.current!.getBoundingClientRect();
    const rawX = (e.clientX - cr.left - ref.offsetX) / zoom;
    const rawY = (e.clientY - cr.top - ref.offsetY) / zoom;
    const sx = snap(Math.max(0, rawX));
    const sy = snap(Math.max(0, rawY));

    const isCanvas = canvasBeds.find(b => b.id === ref.bedId);
    if (isCanvas) {
      await handleMoveBed(ref.bedId, sx, sy);
    } else {
      // From palette
      await api('POST', `/api/beds/${ref.bedId}/assign-garden`, { garden_id: gardenId });
      await handlePlaceBed(ref.bedId, sx, sy);
    }
    dragBedRef.current = null;
  }

  function handlePaletteBedDragStart(e: React.DragEvent, bed: Bed) {
    dragBedRef.current = { bedId: bed.id, offsetX: 0, offsetY: 0 };
    e.dataTransfer.effectAllowed = 'move';
  }

  // ── Care form ─────────────────────────────────────────────────────────────────
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
    setCareSaved(true);
    setTimeout(() => setCareSaved(false), 2000);
  }

  // ── Quick task ────────────────────────────────────────────────────────────────
  async function handleAddTask(e: React.FormEvent) {
    e.preventDefault();
    if (!gardenId) return;
    const r = await api('POST', `/api/gardens/${gardenId}/quick-task`, {
      title: taskForm.title,
      due_date: taskForm.due_date || null,
      description: taskForm.description || null,
    });
    if (r.ok) {
      setTaskForm({ title: '', due_date: '', description: '' });
      setTaskSaved('Task added!');
      setTimeout(() => setTaskSaved(''), 2000);
      loadPanelData();
    }
  }

  // ── Annotation drawing ────────────────────────────────────────────────────────
  const NS = 'http://www.w3.org/2000/svg';

  function newShapeId() {
    try { return crypto.randomUUID(); } catch (_) { return Math.random().toString(36).slice(2); }
  }

  function svgPoint(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / zoom, y: (e.clientY - rect.top) / zoom };
  }

  function distPts(ax: number, ay: number, bx: number, by: number) {
    return Math.sqrt((bx - ax) ** 2 + (by - ay) ** 2);
  }

  function saveAnnotations(shapes: AnnotationShape[]) {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      api('POST', `/api/gardens/${gardenId}/annotations`, { shapes });
    }, 400);
  }

  function handleSvgMouseDown(e: React.MouseEvent<SVGSVGElement>) {
    if (!activeTool || !svgRef.current) return;
    e.preventDefault();
    const { x, y } = svgPoint(e);

    if (activeTool === 'eraser') {
      drawRef.current = { tool: 'eraser', el: null as unknown as SVGElement, startX: x, startY: y };
      eraseAtPoint(x, y);
      return;
    }

    const stroke = strokeColor;
    const fill   = noFill ? 'none' : fillColor;
    const sw     = strokeWidth;
    let el: SVGElement;

    switch (activeTool) {
      case 'rect':
        el = document.createElementNS(NS, 'rect');
        el.setAttribute('x', String(x)); el.setAttribute('y', String(y));
        el.setAttribute('width', '0'); el.setAttribute('height', '0');
        break;
      case 'ellipse':
        el = document.createElementNS(NS, 'ellipse');
        el.setAttribute('cx', String(x)); el.setAttribute('cy', String(y));
        el.setAttribute('rx', '0'); el.setAttribute('ry', '0');
        break;
      case 'line':
        el = document.createElementNS(NS, 'line');
        el.setAttribute('x1', String(x)); el.setAttribute('y1', String(y));
        el.setAttribute('x2', String(x)); el.setAttribute('y2', String(y));
        break;
      case 'free':
        el = document.createElementNS(NS, 'polyline');
        el.setAttribute('points', `${x},${y}`);
        break;
      default:
        return;
    }
    el.setAttribute('stroke', stroke);
    el.setAttribute('stroke-width', String(sw));
    el.setAttribute('fill', activeTool === 'line' ? 'none' : fill);
    el.setAttribute('stroke-linecap', 'round');
    el.setAttribute('stroke-linejoin', 'round');
    svgRef.current.appendChild(el);
    drawRef.current = { tool: activeTool, el, startX: x, startY: y,
      ...(activeTool === 'free' ? { points: [[x, y]], lastX: x, lastY: y, pathLen: 0 } : {}) };
  }

  function handleSvgMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const dr = drawRef.current;
    if (!dr) return;
    const { x, y } = svgPoint(e);

    if (dr.tool === 'eraser') { eraseAtPoint(x, y); return; }
    const { el, startX, startY } = dr;

    switch (dr.tool) {
      case 'rect': {
        const rx = Math.min(startX, x), ry = Math.min(startY, y);
        el.setAttribute('x', String(rx)); el.setAttribute('y', String(ry));
        el.setAttribute('width', String(Math.abs(x - startX)));
        el.setAttribute('height', String(Math.abs(y - startY)));
        break;
      }
      case 'ellipse': {
        const cx = (startX + x) / 2, cy = (startY + y) / 2;
        el.setAttribute('cx', String(cx)); el.setAttribute('cy', String(cy));
        el.setAttribute('rx', String(Math.abs(x - startX) / 2));
        el.setAttribute('ry', String(Math.abs(y - startY) / 2));
        break;
      }
      case 'line':
        el.setAttribute('x2', String(x)); el.setAttribute('y2', String(y));
        break;
      case 'free': {
        const d = distPts(dr.lastX!, dr.lastY!, x, y);
        if (d >= 4) {
          dr.points!.push([x, y]);
          dr.pathLen = (dr.pathLen || 0) + d;
          dr.lastX = x; dr.lastY = y;
          el.setAttribute('points', dr.points!.map(p => p.join(',')).join(' '));
        }
        break;
      }
    }
  }

  function handleSvgMouseUp(e: React.MouseEvent<SVGSVGElement>) {
    const dr = drawRef.current;
    if (!dr) return;

    if (dr.tool === 'eraser') { drawRef.current = null; return; }

    const svgEl = svgRef.current;
    if (!svgEl) { drawRef.current = null; return; }

    const { el, startX, startY, tool } = dr;
    const stroke = el.getAttribute('stroke')!;
    const sw     = parseInt(el.getAttribute('stroke-width') || '2', 10);
    const fill   = el.getAttribute('fill') || 'none';
    let shape: AnnotationShape | null = null;

    // Get end coords from element attributes
    switch (tool) {
      case 'rect': {
        const rw = parseFloat(el.getAttribute('width') || '0');
        const rh = parseFloat(el.getAttribute('height') || '0');
        if (rw < 2 && rh < 2) { el.remove(); drawRef.current = null; return; }
        const rx = parseFloat(el.getAttribute('x') || '0');
        const ry = parseFloat(el.getAttribute('y') || '0');
        shape = { id: newShapeId(), type: 'rect', objectType: activeObjectType, dashArray, x: rx, y: ry, w: rw, h: rh, stroke, strokeWidth: sw, fill };
        break;
      }
      case 'ellipse': {
        const rx2 = parseFloat(el.getAttribute('rx') || '0');
        const ry2 = parseFloat(el.getAttribute('ry') || '0');
        if (rx2 < 1 && ry2 < 1) { el.remove(); drawRef.current = null; return; }
        const cx = parseFloat(el.getAttribute('cx') || '0');
        const cy = parseFloat(el.getAttribute('cy') || '0');
        shape = { id: newShapeId(), type: 'ellipse', objectType: activeObjectType, dashArray, cx, cy, rx: rx2, ry: ry2, stroke, strokeWidth: sw, fill };
        break;
      }
      case 'line': {
        const x1 = parseFloat(el.getAttribute('x1') || '0'), y1 = parseFloat(el.getAttribute('y1') || '0');
        const x2 = parseFloat(el.getAttribute('x2') || '0'), y2 = parseFloat(el.getAttribute('y2') || '0');
        if (distPts(x1, y1, x2, y2) < 2) { el.remove(); drawRef.current = null; return; }
        shape = { id: newShapeId(), type: 'line', objectType: activeObjectType, dashArray, x1, y1, x2, y2, stroke, strokeWidth: sw, fill: 'none' };
        break;
      }
      case 'free': {
        if (!dr.points || dr.points.length < 2) { el.remove(); drawRef.current = null; return; }
        shape = { id: newShapeId(), type: 'free', objectType: activeObjectType, dashArray, points: dr.points, stroke, strokeWidth: sw, fill };
        break;
      }
    }

    el.remove(); // Remove preview; React will render the persisted one
    if (shape) {
      const next = [...annShapes, shape];
      setAnnShapes(next);
      saveAnnotations(next);
    }
    drawRef.current = null;
  }

  function eraseAtPoint(x: number, y: number) {
    setAnnShapes(prev => {
      for (let i = prev.length - 1; i >= 0; i--) {
        if (hitTestShape(prev[i], x, y)) {
          const next = [...prev];
          next.splice(i, 1);
          saveAnnotations(next);
          return next;
        }
      }
      return prev;
    });
  }

  function distToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
    const dx = bx - ax, dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) return distPts(px, py, ax, ay);
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
    return distPts(px, py, ax + t * dx, ay + t * dy);
  }

  function hitTestShape(shape: AnnotationShape, x: number, y: number, r = 10) {
    switch (shape.type) {
      case 'rect':
        return x >= (shape.x! - r) && x <= (shape.x! + shape.w! + r)
            && y >= (shape.y! - r) && y <= (shape.y! + shape.h! + r);
      case 'ellipse':
        return x >= (shape.cx! - shape.rx! - r) && x <= (shape.cx! + shape.rx! + r)
            && y >= (shape.cy! - shape.ry! - r) && y <= (shape.cy! + shape.ry! + r);
      case 'line':
        return distToSegment(x, y, shape.x1!, shape.y1!, shape.x2!, shape.y2!) <= r;
      case 'free': {
        const pts = shape.points!;
        for (let i = 0; i < pts.length - 1; i++)
          if (distToSegment(x, y, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) <= r) return true;
        if (pts.length === 1) return distPts(x, y, pts[0][0], pts[0][1]) <= r;
        return false;
      }
    }
    return false;
  }

  function deactivateDrawTool() { setActiveTool(null); }

  function selectDrawTool(tool: string) {
    if (activeTool === tool) { deactivateDrawTool(); return; }
    setActiveTool(tool);
  }

  // Escape key deactivates draw tool
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && activeTool) deactivateDrawTool(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeTool]);

  // ── Weather helper ────────────────────────────────────────────────────────────
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

  // ── Filter plants ─────────────────────────────────────────────────────────────
  const filteredLib = libSearch.trim()
    ? libSearchResults
    : libPlants.filter(p => p.name.toLowerCase().includes(plantSearch.toLowerCase()));
  const filteredGarden = gardenPlants.filter(p => p.name.toLowerCase().includes(plantSearch.toLowerCase()));

  // Group garden plants by library_id (or name fallback)
  const gardenGroups = useMemo(() => {
    const map = new Map<string, GardenPlant[]>();
    for (const p of filteredGarden) {
      const key = p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(p);
    }
    return [...map.values()];
  }, [filteredGarden]);

  const w = weather as { current?: { temp: number; condition: string; humidity: number; wind_speed: number }; daily?: { date: string; high: number; low: number; condition: string; precip_prob?: number }[]; frost?: { last_spring: string; first_fall: string } } | null;

  if (!gardenId && gardens && gardens.length === 0) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1>Garden Planner</h1>
        <p className="muted">No gardens yet. <Link to="/gardens">Create a garden first.</Link></p>
      </div>
    );
  }

  return (
    <div className="planner-layout" style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }}>

      {/* ── Left Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="planner-sidebar" style={{ width: '220px', flexShrink: 0, overflowY: 'auto', borderRight: '1px solid #d0e0c8', padding: '0.75rem', background: '#f8fbf7', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {/* Garden selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <select
            value={gardenId}
            onChange={e => { const id = parseInt(e.target.value); setGardenId(id); setSearchParams({ garden: String(id) }); }}
            style={{ flex: 1, font: 'inherit', fontWeight: 600, padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', background: '#f4f9f4' }}
          >
            {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
          {gardenId && <Link to={`/gardens/${gardenId}`} style={{ fontSize: '0.78rem', color: '#3a6b35', whiteSpace: 'nowrap' }}>✎ Edit</Link>}
        </div>

        {/* Zoom */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
          <span style={{ color: '#7a907a' }}>Zoom:</span>
          {[0.5, 0.75, 1, 1.25, 1.5].map(z => (
            <button key={z} className={`btn-small${zoom === z ? '' : ' btn-link'}`}
                    style={{ padding: '0.15rem 0.4rem', fontSize: '0.75rem' }}
                    onClick={() => setZoom(z)}>{z}×</button>
          ))}
        </div>

        {/* Tile size */}
        <div style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ color: '#7a907a', whiteSpace: 'nowrap' }}>Grid:</span>
          <select value={tileIn} onChange={e => setTileIn(parseInt(e.target.value))}
                  style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.15rem 0.3rem', border: '1px solid #c0d4be', borderRadius: '3px' }}>
            <option value="6">6" cells</option>
            <option value="12">12" cells (1 ft)</option>
            <option value="24">24" cells (2 ft)</option>
          </select>
        </div>

        {/* Draw toolbar */}
        <div>
          <div className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', marginBottom: '0.3rem' }}>Draw</div>

          {/* Object presets */}
          <div style={{ fontSize: '0.72rem', color: '#7a907a', marginBottom: '0.25rem' }}>Quick objects:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.2rem', marginBottom: '0.5rem' }}>
            {([
              { key: 'path',      label: '🛤 Path',      tool: 'free',    stroke: '#8B6914', fill: 'none',    noFill: true,  sw: 10, dash: '' },
              { key: 'fence',     label: '🚧 Fence',     tool: 'free',    stroke: '#666655', fill: 'none',    noFill: true,  sw: 4,  dash: '10,5' },
              { key: 'hedge',     label: '🌿 Hedge',     tool: 'free',    stroke: '#2d6b20', fill: 'none',    noFill: true,  sw: 12, dash: '' },
              { key: 'water',     label: '💧 Water',     tool: 'ellipse', stroke: '#2a7ab8', fill: '#a8d4f5', noFill: false, sw: 2,  dash: '' },
              { key: 'structure', label: '🏗 Structure', tool: 'rect',    stroke: '#888877', fill: '#d8d0c0', noFill: false, sw: 2,  dash: '' },
              { key: 'compost',   label: '🌱 Compost',   tool: 'rect',    stroke: '#6b4c1e', fill: '#c4a06e', noFill: false, sw: 2,  dash: '' },
            ] as const).map(p => (
              <button
                key={p.key}
                className={`btn-small${activeObjectType === p.key && activeTool ? '' : ' btn-link'}`}
                style={{ fontSize: '0.7rem', padding: '0.15rem 0.35rem', background: activeObjectType === p.key && activeTool ? '#3a6b35' : undefined, color: activeObjectType === p.key && activeTool ? '#fff' : undefined }}
                onClick={() => {
                  setActiveObjectType(p.key);
                  setActiveTool(p.tool);
                  setStrokeColor(p.stroke);
                  setFillColor(p.fill === 'none' ? '#a8d5a2' : p.fill);
                  setNoFill(p.noFill);
                  setStrokeWidth(p.sw);
                  setDashArray(p.dash);
                }}
              >{p.label}</button>
            ))}
          </div>

          {/* Basic shape tools */}
          <div style={{ fontSize: '0.72rem', color: '#7a907a', marginBottom: '0.25rem' }}>Shapes:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.2rem', marginBottom: '0.3rem' }}>
            {[
              { tool: 'rect',    label: '▭ Rect' },
              { tool: 'ellipse', label: '◯ Oval' },
              { tool: 'line',    label: '╱ Line' },
              { tool: 'free',    label: '✏ Free' },
              { tool: 'eraser',  label: '⌫ Erase' },
            ].map(({ tool, label }) => (
              <button
                key={tool}
                className={`btn-small${activeTool === tool && activeObjectType === 'generic' ? '' : ' btn-link'}`}
                style={{ fontSize: '0.72rem', padding: '0.15rem 0.4rem', background: activeTool === tool && activeObjectType === 'generic' ? '#3a6b35' : undefined, color: activeTool === tool && activeObjectType === 'generic' ? '#fff' : undefined }}
                onClick={() => { setActiveObjectType('generic'); setDashArray(''); selectDrawTool(tool); }}
              >{label}</button>
            ))}
          </div>

          {/* Style controls */}
          {activeTool && activeTool !== 'eraser' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', fontSize: '0.75rem', borderTop: '1px solid #e0ecd8', paddingTop: '0.3rem', marginTop: '0.1rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                Stroke <input type="color" value={strokeColor} onChange={e => setStrokeColor(e.target.value)} style={{ width: 32, height: 20, padding: 1, border: '1px solid #c0d4be', borderRadius: 3 }} />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <input type="checkbox" checked={noFill} onChange={e => setNoFill(e.target.checked)} /> No fill
              </label>
              {!noFill && (
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  Fill <input type="color" value={fillColor} onChange={e => setFillColor(e.target.value)} style={{ width: 32, height: 20, padding: 1, border: '1px solid #c0d4be', borderRadius: 3 }} />
                </label>
              )}
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  Width
                  <select value={strokeWidth} onChange={e => setStrokeWidth(parseInt(e.target.value))} style={{ font: 'inherit', fontSize: '0.75rem', padding: '0.1rem', border: '1px solid #c0d4be', borderRadius: 3 }}>
                    {[1, 2, 3, 5, 8, 12].map(w => <option key={w} value={w}>{w}px</option>)}
                  </select>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  Dash
                  <select value={dashArray} onChange={e => setDashArray(e.target.value)} style={{ font: 'inherit', fontSize: '0.75rem', padding: '0.1rem', border: '1px solid #c0d4be', borderRadius: 3 }}>
                    <option value="">Solid</option>
                    <option value="6,3">Dashed</option>
                    <option value="10,5">Long dash</option>
                    <option value="2,4">Dotted</option>
                    <option value="10,5,2,5">Dash-dot</option>
                  </select>
                </label>
              </div>
            </div>
          )}

          {activeTool && (
            <button className="btn-small btn-link" style={{ fontSize: '0.7rem', marginTop: '0.3rem' }}
              onClick={() => { deactivateDrawTool(); setActiveObjectType('generic'); }}>
              ✕ Stop drawing
            </button>
          )}
          {annShapes.length > 0 && (
            <button className="btn-small btn-link" style={{ fontSize: '0.72rem', marginTop: '0.2rem', color: '#b84040' }}
              onClick={() => { if (confirm('Clear all drawn shapes?')) { setAnnShapes([]); saveAnnotations([]); } }}>
              Clear all
            </button>
          )}
        </div>

        {/* Beds */}
        <div>
          <div className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', marginBottom: '0.3rem' }}>
            Beds ({canvasBeds.length + paletteBeds.length})
          </div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {/* Placed beds */}
            {canvasBeds.map(b => (
              <li key={b.id}
                  className={`palette-item palette-bed${selectedBed?.id === b.id ? ' active' : ''}`}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.4rem', background: selectedBed?.id === b.id ? '#d4edcc' : '#f0f5ef', borderRadius: '4px', fontSize: '0.8rem', cursor: 'pointer' }}
                  onClick={() => { setSelectedBed(b); if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); } }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</span>
                <span style={{ color: '#9ab49a', fontSize: '0.7rem', flexShrink: 0 }}>{b.width_ft}×{b.height_ft}</span>
                <button title="Focus on canvas" style={{ background: 'none', border: 'none', color: '#3a6b35', cursor: 'pointer', fontSize: '0.8rem', padding: '0 0.1rem', flexShrink: 0 }}
                  onClick={e => { e.stopPropagation(); const el = document.getElementById(`canvas-bed-${b.id}`); el?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>◎</button>
                <button className="palette-delete-btn" style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.9rem', padding: '0 0.1rem', flexShrink: 0 }}
                        onClick={e => { e.stopPropagation(); handleDeleteBed(b.id, b.name); }}>×</button>
              </li>
            ))}
            {/* Unplaced beds */}
            {paletteBeds.map(b => (
              <li key={b.id}
                  className={`palette-item palette-bed${selectedBed?.id === b.id ? ' active' : ''}`}
                  draggable
                  onDragStart={e => handlePaletteBedDragStart(e, b)}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.4rem', background: selectedBed?.id === b.id ? '#d4edcc' : '#f0f5ef', borderRadius: '4px', fontSize: '0.8rem', cursor: 'grab', opacity: 0.75 }}
                  onClick={() => { setSelectedBed(b); if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); } }}>
                <span style={{ fontSize: '0.65rem', color: '#9ab49a', flexShrink: 0 }} title="Drag to canvas">⋮⋮</span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</span>
                <span style={{ color: '#9ab49a', fontSize: '0.7rem', flexShrink: 0 }}>{b.width_ft}×{b.height_ft}</span>
                <button className="palette-delete-btn" style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.9rem', padding: '0 0.1rem', flexShrink: 0 }}
                        onClick={e => { e.stopPropagation(); handleDeleteBed(b.id, b.name); }}>×</button>
              </li>
            ))}
          </ul>
          <details style={{ marginTop: '0.4rem' }}>
            <summary style={{ fontSize: '0.8rem', color: '#3a6b35', cursor: 'pointer' }}>+ Add New Bed</summary>
            <form onSubmit={handleAddBed} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.3rem', fontSize: '0.8rem' }}>
              <input type="text" placeholder="Name" value={addBedForm.name} onChange={e => setAddBedForm(f => ({ ...f, name: e.target.value }))} required style={{ font: 'inherit', fontSize: '0.8rem', padding: '0.25rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
              <div style={{ display: 'flex', gap: '0.3rem' }}>
                <input type="number" placeholder="W(ft)" value={addBedForm.width_ft} onChange={e => setAddBedForm(f => ({ ...f, width_ft: e.target.value }))} style={{ font: 'inherit', fontSize: '0.8rem', padding: '0.25rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '50%' }} />
                <input type="number" placeholder="H(ft)" value={addBedForm.height_ft} onChange={e => setAddBedForm(f => ({ ...f, height_ft: e.target.value }))} style={{ font: 'inherit', fontSize: '0.8rem', padding: '0.25rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '50%' }} />
              </div>
              <button type="submit" className="btn-small" style={{ fontSize: '0.78rem' }}>Add Bed</button>
            </form>
          </details>
        </div>

        {/* Plant search */}
        <div>
          <input type="text" placeholder="Search plants…" value={plantSearch} onChange={e => setPlantSearch(e.target.value)}
                 style={{ width: '100%', font: 'inherit', fontSize: '0.8rem', padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', marginBottom: '0.4rem', boxSizing: 'border-box' }} />

          {gardenGroups.length > 0 && (
            <details open>
              <summary className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', cursor: 'pointer' }}>Plants in Garden ({filteredGarden.length})</summary>
              <ul style={{ listStyle: 'none', padding: 0, margin: '0.3rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                {gardenGroups.map(group => {
                  const rep = group[0]; // representative plant
                  const count = group.length;
                  const isSelected = selectedPlant?.id === rep.id;
                  if (count === 1) {
                    return (
                      <li key={rep.id}
                          className={`palette-item palette-plant${isSelected ? ' active' : ''}`}
                          draggable
                          onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(rep); }}
                          onClick={() => setSelectedPlant(prev => prev?.id === rep.id ? null : rep)}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: isSelected ? '#d4edcc' : '#f4f9f4', borderRadius: '4px', fontSize: '0.78rem', cursor: 'pointer' }}>
                        {rep.image_filename ? <img src={`/static/plant_images/${rep.image_filename}`} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rep.name}</span>
                        {rep.library_id && <Link to={`/library/${rep.library_id}`} style={{ fontSize: '0.7rem', color: '#7a907a' }} onClick={e => e.stopPropagation()}>ℹ</Link>}
                      </li>
                    );
                  }
                  // Multiple instances — show group with expand
                  return (
                    <li key={`grp-${rep.id}`} style={{ borderRadius: '4px', overflow: 'hidden', fontSize: '0.78rem' }}>
                      <details>
                        <summary
                          style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: '#f4f9f4', cursor: 'pointer', listStyle: 'none' }}
                          draggable
                          onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(rep); }}
                          onClick={() => setSelectedPlant(prev => prev?.id === rep.id ? null : rep)}
                        >
                          {rep.image_filename ? <img src={`/static/plant_images/${rep.image_filename}`} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rep.name}</span>
                          <span style={{ background: '#3a6b35', color: '#fff', borderRadius: '10px', padding: '0 5px', fontSize: '0.68rem', fontWeight: 700 }}>×{count}</span>
                        </summary>
                        <ul style={{ listStyle: 'none', padding: '0.2rem 0 0.2rem 0.6rem', margin: 0, display: 'flex', flexDirection: 'column', gap: '0.15rem', background: '#f0f6ef' }}>
                          {group.map((p, i) => (
                            <li key={p.id}
                                className={`palette-item palette-plant${selectedPlant?.id === p.id ? ' active' : ''}`}
                                draggable
                                onDragStart={e => { e.stopPropagation(); e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(p); }}
                                onClick={e => { e.stopPropagation(); setSelectedPlant(prev => prev?.id === p.id ? null : p); }}
                                style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.15rem 0.4rem', background: selectedPlant?.id === p.id ? '#d4edcc' : 'transparent', borderRadius: '3px', cursor: 'pointer' }}>
                              <span style={{ color: '#9ab49a', minWidth: 16 }}>#{i + 1}</span>
                              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    </li>
                  );
                })}
              </ul>
            </details>
          )}

          <details open style={{ marginTop: '0.4rem' }}>
            <summary className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', cursor: 'pointer' }}>Library Plants</summary>
            <div style={{ marginTop: '0.3rem', position: 'relative' }}>
              <input
                type="text"
                placeholder="Search 8,000+ plants…"
                value={libSearch}
                onChange={e => setLibSearch(e.target.value)}
                style={{ width: '100%', font: 'inherit', fontSize: '0.78rem', padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', boxSizing: 'border-box' }}
              />
              {libSearch && (
                <button onClick={() => setLibSearch('')}
                  style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9ab49a', fontSize: '0.9rem', padding: 0, lineHeight: 1 }}>×</button>
              )}
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0.3rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.2rem', maxHeight: '250px', overflowY: 'auto' }}>
              {libSearchLoading && <li style={{ fontSize: '0.75rem', color: '#9ab49a', padding: '0.2rem 0.4rem' }}>Searching…</li>}
              {!libSearchLoading && libSearch.trim() && filteredLib.length === 0 && (
                <li style={{ fontSize: '0.75rem', color: '#9ab49a', padding: '0.2rem 0.4rem' }}>No results for "{libSearch}"</li>
              )}
              {filteredLib.slice(0, 50).map(p => (
                <li key={p.id}
                    className={`palette-item palette-plant${selectedPlant?.id === p.id && !('library_id' in selectedPlant) ? ' active' : ''}`}
                    draggable
                    onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(p); }}
                    onClick={() => setSelectedPlant(prev => prev?.id === p.id ? null : p)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: selectedPlant?.id === p.id ? '#d4edcc' : '#f4f9f4', borderRadius: '4px', fontSize: '0.78rem', cursor: 'pointer' }}>
                  {p.image_filename ? <img src={`/static/plant_images/${p.image_filename}`} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      </aside>

      {/* ── Canvas ───────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto', position: 'relative', background: '#f0f4ef' }}>
        {selectedPlant && (
          <div style={{ position: 'sticky', top: 0, zIndex: 10, background: '#d4edcc', padding: '0.3rem 0.75rem', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #a8d4a0' }}>
            <strong>Selected:</strong> {selectedPlant.name}
            <span style={{ color: '#7a907a' }}>— drag to canvas or click a bed cell</span>
            <button className="btn-small" style={{ marginLeft: 'auto' }} onClick={() => setSelectedPlant(null)}>✕ Deselect</button>
          </div>
        )}
        <div
          id="planner-canvas"
          ref={canvasRef}
          style={{ position: 'relative', minWidth: '1200px', minHeight: '900px', transform: `scale(${zoom})`, transformOrigin: 'top left', width: `${100 / zoom}%`, height: `${900 / zoom}px` }}
          onDragOver={e => { handleCanvasDragOver(e); if (selectedPlant) e.preventDefault(); }}
          onDrop={e => {
            if (dragBedRef.current) { handleCanvasDropBed(e); return; }
            if (selectedPlant) handleCanvasDrop(e);
          }}
        >
          {/* Canvas beds */}
          {canvasBeds.map(bed => (
            <div
              key={bed.id}
              id={`canvas-bed-${bed.id}`}
              className="canvas-bed"
              draggable
              onDragStart={e => handleBedDragStart(e, bed)}
              onDragEnd={handleBedDragEnd}
              style={{ position: 'absolute', left: (bed.pos_x ?? 0) * PX, top: (bed.pos_y ?? 0) * PX, width: bed.width_ft * PX, height: bed.height_ft * PX, background: '#e8f5e3', border: '2px solid #a8c8a0', borderRadius: '4px', boxSizing: 'border-box' }}
            >
              <div className="canvas-bed-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '2px 6px', background: selectedBed?.id === bed.id ? '#a8d8a0' : '#c8e0c0', fontSize: '0.75rem', fontWeight: 600, cursor: 'grab' }}
                   onClick={e => { e.stopPropagation(); setSelectedBed(bed); if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); } }}>
                <span>{bed.name}</span>
                <button className="bed-header-delete" style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.9rem', padding: '0 0.1rem' }} draggable={false}
                        onClick={e => { e.stopPropagation(); handleDeleteBed(bed.id, bed.name); }}>×</button>
              </div>
              <BedGrid
                bed={bed}
                chips={bedChips[bed.id] || []}
                tileIn={tileIn}
                onCellClick={handleCellClick}
                onChipRemove={handleChipRemove}
                onChipClick={handleChipClick}
                dragPlant={selectedPlant}
                zoom={zoom}
              />
            </div>
          ))}

          {/* Canvas plant circles */}
          {canvasPlants.map(cp => {
            const diamPx = cp.radius_ft * PX * 2;
            const leftPx = cp.pos_x * PX - cp.radius_ft * PX;
            const topPx = cp.pos_y * PX - cp.radius_ft * PX;
            const imgSrc = cp.custom_image ? `/static/canvas_plant_images/${cp.custom_image}` : (cp.image_filename ? `/static/plant_images/${cp.image_filename}` : null);
            return (
              <div
                key={cp.id}
                id={`cp-${cp.id}`}
                className="canvas-plant-circle"
                style={{ position: 'absolute', left: leftPx, top: topPx, width: diamPx, height: diamPx, borderRadius: '50%', background: imgSrc ? 'transparent' : (cp.color || '#5a9e54'), border: '2px solid rgba(0,0,0,0.15)', overflow: 'visible', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', userSelect: 'none' }}
                onClick={() => handleCanvasPlantClick(cp)}
              >
                {imgSrc && (
                  <div className="circle-bg" style={{ position: 'absolute', inset: 0, borderRadius: '50%', overflow: 'hidden' }}>
                    <img src={imgSrc} alt={cp.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                )}
                <span className="canvas-plant-label" style={{ position: 'relative', fontSize: Math.max(9, Math.min(12, diamPx / 4)), color: imgSrc ? '#fff' : '#fff', textShadow: '0 1px 2px rgba(0,0,0,0.5)', textAlign: 'center', padding: '2px', pointerEvents: 'none', maxWidth: diamPx - 8, overflow: 'hidden', wordBreak: 'break-word' }}>
                  {cp.name}
                </span>
                {/* Move handle (the whole circle, minus resize handle) */}
                <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', cursor: 'move' }}
                     onPointerDown={e => handleCpPointerDown(e, cp, 'move')}
                     onPointerMove={e => handleCpPointerMove(e, cp)}
                     onPointerUp={e => handleCpPointerUp(e, cp)} />
                {/* Resize handle */}
                <div className="canvas-plant-resize-handle"
                     style={{ position: 'absolute', bottom: 2, right: 2, width: 12, height: 12, background: 'rgba(255,255,255,0.7)', border: '1px solid #888', borderRadius: '50%', cursor: 'ew-resize', zIndex: 1 }}
                     title="Drag to resize"
                     onPointerDown={e => { e.stopPropagation(); handleCpPointerDown(e, cp, 'resize'); }}
                     onPointerMove={e => handleCpPointerMove(e, cp)}
                     onPointerUp={e => handleCpPointerUp(e, cp)} />
                <button className="canvas-plant-delete-btn"
                        style={{ position: 'absolute', top: -6, right: -6, width: 16, height: 16, background: '#b84040', color: '#fff', border: 'none', borderRadius: '50%', fontSize: '10px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}
                        onClick={e => { e.stopPropagation(); handleDeleteCanvasPlant(cp); }}>×</button>
              </div>
            );
          })}
          {/* ── SVG annotation overlay ────────────────────────────────────────── */}
          <svg
            ref={svgRef}
            style={{
              position: 'absolute', left: 0, top: 0,
              width: '100%', height: '100%',
              pointerEvents: activeTool ? 'all' : 'none',
              zIndex: 15,
              cursor: activeTool === 'eraser' ? 'cell' : activeTool ? 'crosshair' : 'default',
              overflow: 'visible',
            }}
            onMouseDown={handleSvgMouseDown}
            onMouseMove={handleSvgMouseMove}
            onMouseUp={handleSvgMouseUp}
          >
            {annShapes.map(shape => {
              const common: React.SVGProps<SVGElement> = {
                stroke: shape.stroke,
                strokeWidth: shape.strokeWidth,
                fill: shape.fill,
                strokeLinecap: 'round' as const,
                strokeLinejoin: 'round' as const,
                strokeDasharray: shape.dashArray || undefined,
              };
              switch (shape.type) {
                case 'rect':   return <rect    key={shape.id} {...common as React.SVGProps<SVGRectElement>}     x={shape.x}   y={shape.y}   width={shape.w}  height={shape.h} />;
                case 'ellipse':return <ellipse  key={shape.id} {...common as React.SVGProps<SVGEllipseElement>}  cx={shape.cx} cy={shape.cy} rx={shape.rx}   ry={shape.ry} />;
                case 'line':   return <line     key={shape.id} {...common as React.SVGProps<SVGLineElement>}     x1={shape.x1} y1={shape.y1} x2={shape.x2}   y2={shape.y2} fill="none" />;
                case 'free':   return <polyline key={shape.id} {...common as React.SVGProps<SVGPolylineElement>} points={shape.points!.map(p => p.join(',')).join(' ')} />;
                default:       return null;
              }
            })}
          </svg>
        </div>
      </div>

      {/* ── Right Panel toggle ────────────────────────────────────────────────── */}
      <button
        id="right-panel-toggle"
        style={{ position: 'fixed', right: rightPanelOpen ? '284px' : 0, top: '50%', transform: 'translateY(-50%)', zIndex: 20, background: '#3a5c37', color: '#fff', border: 'none', borderRadius: '4px 0 0 4px', padding: '0.75rem 0.25rem', cursor: 'pointer', writingMode: 'vertical-lr', fontSize: '0.75rem', transition: 'right 0.2s' }}
        onClick={() => { const o = !rightPanelOpen; setRightPanelOpen(o); localStorage.setItem('plannerRightPanel', o ? 'open' : 'closed'); }}
      >
        {rightPanelOpen ? '›' : '‹'} Info
      </button>

      {/* ── Right Panel ──────────────────────────────────────────────────────── */}
      {/* ── Chat FAB ─────────────────────────────────────────────────────────── */}
      <button
        title="Garden Assistant"
        onClick={() => setChatOpen(o => !o)}
        style={{
          position: 'fixed', bottom: '1.5rem',
          right: rightPanelOpen ? '296px' : '1rem',
          zIndex: 30, background: chatOpen ? '#2d5229' : '#3a5c37',
          color: '#fff', border: 'none', borderRadius: '50%',
          width: 48, height: 48, fontSize: '1.3rem',
          cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          transition: 'right 0.2s',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >🤖</button>

      {chatOpen && (
        <div style={{
          position: 'fixed', bottom: '5.5rem',
          right: rightPanelOpen ? '296px' : '1rem',
          width: 320, zIndex: 30,
          boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
          borderRadius: 8, overflow: 'hidden',
          transition: 'right 0.2s',
        }}>
          <ChatWidget gardenId={gardenId || undefined} gardenName={garden?.name} zone={garden?.usda_zone ?? undefined} />
        </div>
      )}

      {rightPanelOpen && (
        <aside className="planner-right-panel" style={{ width: '280px', flexShrink: 0, overflowY: 'auto', borderLeft: '1px solid #d0e0c8', background: '#f8fbf7', display: 'flex', flexDirection: 'column' }}>

          {/* ── Tab bar ── */}
          <div style={{ display: 'flex', borderBottom: '2px solid #d0e0c8', flexShrink: 0 }}>
            {(['info', 'timeline', 'calendar'] as const).map(tab => (
              <button key={tab} onClick={() => setRightPanelTab(tab)}
                style={{ flex: 1, fontSize: '0.72rem', fontWeight: rightPanelTab === tab ? 700 : 400, padding: '0.4rem 0.2rem', background: 'transparent', border: 'none', borderBottom: rightPanelTab === tab ? '2px solid #3a6b35' : '2px solid transparent', marginBottom: '-2px', color: rightPanelTab === tab ? '#3a6b35' : '#7a907a', cursor: 'pointer', transition: 'color 0.15s' }}>
                {tab === 'info' ? 'Info' : tab === 'timeline' ? 'Timeline' : 'Calendar'}
              </button>
            ))}
          </div>

          <div style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1, overflowY: 'auto' }}>

          {/* ── Info tab ── */}
          {rightPanelTab === 'info' && (<>

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
          {selectedBed && (
            <div style={{ borderTop: '1px solid #d0e0c8', paddingTop: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#3a5c37' }}>🛏 {selectedBed.name}</div>
                <div style={{ display: 'flex', gap: '0.3rem' }}>
                  <Link to={`/beds/${selectedBed.id}`} style={{ fontSize: '0.72rem', color: '#3a6b35' }}>Edit →</Link>
                  <button style={{ background: 'none', border: 'none', color: '#9ab49a', cursor: 'pointer', fontSize: '0.85rem', padding: 0 }} onClick={() => setSelectedBed(null)}>×</button>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.2rem 0.6rem', fontSize: '0.78rem', color: '#5a7a5a' }}>
                <span>📐 {selectedBed.width_ft} × {selectedBed.height_ft} ft</span>
                {selectedBed.depth_ft && <span>↕ {selectedBed.depth_ft} ft deep</span>}
                {selectedBed.plant_count != null && <span>🌿 {selectedBed.plant_count} plants</span>}
                {(canvasBeds.find(b => b.id === selectedBed.id) ? true : false)
                  ? <span style={{ color: '#3a6b35' }}>✓ On canvas</span>
                  : <span style={{ color: '#9ab49a' }}>Not placed</span>}
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

          {/* Weather */}
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37', marginBottom: '0.4rem' }}>Weather</div>
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
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

          </>)}

          {/* ── Timeline tab ── */}
          {rightPanelTab === 'timeline' && (() => {
            const today = new Date();
            const startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            const endDate   = new Date(today.getFullYear(), today.getMonth() + 7, 0);
            const totalMs   = endDate.getTime() - startDate.getTime();

            function toPct(dateStr: string) {
              const d = new Date(dateStr + 'T12:00:00');
              return Math.max(0, Math.min(100, (d.getTime() - startDate.getTime()) / totalMs * 100));
            }

            const months: { label: string; pct: number }[] = [];
            const cur = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
            while (cur <= endDate) {
              months.push({ label: cur.toLocaleDateString('en-US', { month: 'short' }), pct: (cur.getTime() - startDate.getTime()) / totalMs * 100 });
              cur.setMonth(cur.getMonth() + 1);
            }

            const todayPct = toPct(today.toISOString().slice(0, 10));
            const plantsWithDates = gardenPlants.filter(p => p.planted_date || p.transplant_date || p.expected_harvest);

            return (
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37', marginBottom: '0.5rem' }}>Plant Timeline</div>
                <div style={{ fontSize: '0.68rem', color: '#9ab49a', marginBottom: '0.4rem' }}>
                  <span style={{ display: 'inline-block', width: 10, height: 8, background: '#4a80b4', borderRadius: 2, marginRight: 3 }} />Seeding &nbsp;
                  <span style={{ display: 'inline-block', width: 10, height: 8, background: '#5a9e54', borderRadius: 2, marginRight: 3 }} />Growing &nbsp;
                  🥕 Harvest
                </div>
                {/* Month header */}
                <div style={{ display: 'flex', marginLeft: 68, position: 'relative', height: 16, marginBottom: 4, borderBottom: '1px solid #d0e0c8' }}>
                  {months.map(m => (
                    <span key={m.label + m.pct} style={{ position: 'absolute', left: `${m.pct}%`, fontSize: '0.62rem', color: '#9ab49a', transform: 'translateX(-25%)', whiteSpace: 'nowrap' }}>{m.label}</span>
                  ))}
                  <div style={{ position: 'absolute', left: `${todayPct}%`, top: 0, bottom: 0, width: 1, background: '#e05050' }} />
                </div>
                {plantsWithDates.length === 0 ? (
                  <p className="muted" style={{ fontSize: '0.78rem' }}>No plants with dates yet. Set seeding/harvest dates in plant care.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {plantsWithDates.map(p => {
                      const seedPct   = p.planted_date    ? toPct(p.planted_date)    : null;
                      const transPct  = p.transplant_date ? toPct(p.transplant_date) : null;
                      const harvestPct = p.expected_harvest ? toPct(p.expected_harvest) : null;

                      const seedEnd = transPct ?? (seedPct !== null ? Math.min(100, seedPct + 12) : null);
                      const growStart = transPct ?? seedPct;

                      return (
                        <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 4, minHeight: 20 }}>
                          <div title={p.name} style={{ width: 64, fontSize: '0.68rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#3a5c37', flexShrink: 0, textAlign: 'right', paddingRight: 4 }}>{p.name}</div>
                          <div style={{ flex: 1, position: 'relative', height: 12, background: '#edf4eb', borderRadius: 3, overflow: 'visible' }}>
                            {/* Seeding bar */}
                            {seedPct !== null && seedEnd !== null && (
                              <div title={`Seeded: ${p.planted_date}${p.transplant_date ? ' → ' + p.transplant_date : ''}`}
                                style={{ position: 'absolute', left: `${seedPct}%`, width: `${Math.max(1, seedEnd - seedPct)}%`, height: '100%', background: '#4a80b4', borderRadius: 2, opacity: 0.85 }} />
                            )}
                            {/* Growing bar */}
                            {growStart !== null && harvestPct !== null && harvestPct > growStart && (
                              <div title={`Growing → harvest: ${p.expected_harvest}`}
                                style={{ position: 'absolute', left: `${growStart}%`, width: `${Math.max(1, harvestPct - growStart)}%`, height: '100%', background: '#5a9e54', borderRadius: 2, opacity: 0.85 }} />
                            )}
                            {/* Harvest marker */}
                            {harvestPct !== null && (
                              <div title={`Expected harvest: ${p.expected_harvest}`}
                                style={{ position: 'absolute', left: `${harvestPct}%`, top: -3, transform: 'translateX(-50%)', fontSize: '0.75rem', lineHeight: 1, zIndex: 2, pointerEvents: 'none' }}>🥕</div>
                            )}
                            {/* Today line */}
                            <div style={{ position: 'absolute', left: `${todayPct}%`, top: -2, bottom: -2, width: 1, background: '#e05050', zIndex: 1 }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
                {gardenPlants.length > 0 && plantsWithDates.length < gardenPlants.length && (
                  <p style={{ fontSize: '0.72rem', color: '#9ab49a', marginTop: '0.5rem' }}>
                    {gardenPlants.length - plantsWithDates.length} plant(s) have no dates set.
                  </p>
                )}
              </div>
            );
          })()}

          {/* ── Calendar tab ── */}
          {rightPanelTab === 'calendar' && (() => {
            const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            const DAY_LABELS  = ['Su','Mo','Tu','We','Th','Fr','Sa'];
            const TYPE_COLORS: Record<string, string> = {
              seeding:'#5a9e54', transplanting:'#3a8c5a', watering:'#4a80b4',
              fertilizing:'#c4942a', mulching:'#8a6a40', weeding:'#9a5a5a',
              harvest:'#d4a84b', other:'#7a907a',
            };

            const totalDays   = new Date(calYear, calMonth + 1, 0).getDate();
            const startOffset = new Date(calYear, calMonth, 1).getDay();
            const cells: (number | null)[] = [...Array(startOffset).fill(null), ...Array.from({ length: totalDays }, (_, i) => i + 1)];
            while (cells.length % 7 !== 0) cells.push(null);

            const todayStr = new Date().toISOString().slice(0, 10);
            const allTasks = tasks as {id: number; title: string; task_type?: string; due_date?: string; completed?: boolean; plant_name?: string}[];

            function prevMonth() { if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11); } else setCalMonth(m => m - 1); }
            function nextMonth() { if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0); } else setCalMonth(m => m + 1); }

            return (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <button className="btn-small btn-link" onClick={prevMonth} style={{ fontSize: '1rem', padding: '0 0.3rem' }}>‹</button>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37' }}>{MONTH_NAMES[calMonth]} {calYear}</span>
                  <button className="btn-small btn-link" onClick={nextMonth} style={{ fontSize: '1rem', padding: '0 0.3rem' }}>›</button>
                </div>

                {/* Day headers */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1, marginBottom: 2 }}>
                  {DAY_LABELS.map(d => (
                    <div key={d} style={{ textAlign: 'center', fontSize: '0.62rem', color: '#9ab49a', fontWeight: 600 }}>{d}</div>
                  ))}
                </div>

                {/* Calendar grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1 }}>
                  {cells.map((day, i) => {
                    if (!day) return <div key={`e-${i}`} style={{ minHeight: 28 }} />;
                    const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                    const isToday = dateStr === todayStr;
                    const dayTasks = allTasks.filter(t => t.due_date === dateStr);
                    const hasOverdue = dayTasks.some(t => !t.completed && dateStr < todayStr);
                    return (
                      <div key={dateStr} style={{ minHeight: 28, padding: '1px 2px', background: isToday ? '#d4edcc' : hasOverdue ? '#fce8e8' : '#f8fbf7', borderRadius: 3, border: isToday ? '1px solid #3a6b35' : '1px solid #e8f0e4', fontSize: '0.65rem' }}>
                        <div style={{ fontWeight: isToday ? 700 : 400, color: isToday ? '#3a6b35' : '#5a7a5a', marginBottom: 1 }}>{day}</div>
                        {dayTasks.slice(0, 3).map(t => (
                          <div key={t.id}
                            title={t.title + (t.plant_name ? ' · ' + t.plant_name : '')}
                            style={{ background: t.completed ? '#c8d8c8' : (TYPE_COLORS[t.task_type ?? 'other'] ?? TYPE_COLORS.other), color: '#fff', borderRadius: 2, padding: '0 2px', marginBottom: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer', opacity: t.completed ? 0.6 : 1 }}>
                            {t.title}
                          </div>
                        ))}
                        {dayTasks.length > 3 && <div style={{ fontSize: '0.6rem', color: '#7a907a' }}>+{dayTasks.length - 3}</div>}
                      </div>
                    );
                  })}
                </div>

                {/* Legend */}
                <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                  {Object.entries(TYPE_COLORS).map(([type, color]) => (
                    <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: '0.62rem', color: '#7a907a' }}>
                      <span style={{ display: 'inline-block', width: 8, height: 8, background: color, borderRadius: 2 }} />{type}
                    </span>
                  ))}
                </div>

                {/* Add task form */}
                <details style={{ marginTop: '0.5rem' }}>
                  <summary style={{ fontSize: '0.78rem', color: '#3a6b35', cursor: 'pointer' }}>+ Add Task</summary>
                  <form onSubmit={handleAddTask} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    <input type="text" placeholder="Task title" value={taskForm.title} onChange={e => setTaskForm(f => ({ ...f, title: e.target.value }))} required style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.2rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
                    <input type="date" value={taskForm.due_date} onChange={e => setTaskForm(f => ({ ...f, due_date: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.2rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
                    <button type="submit" className="btn-small" style={{ fontSize: '0.75rem' }}>Add</button>
                    {taskSaved && <span className="muted" style={{ fontSize: '0.75rem' }}>{taskSaved}</span>}
                  </form>
                </details>
              </div>
            );
          })()}

          </div>
        </aside>
      )}
    </div>
  );
}
