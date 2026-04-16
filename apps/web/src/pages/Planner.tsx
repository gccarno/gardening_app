import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useGardens, useGarden } from '../hooks/useGardens';
import ChatWidget from '../components/ChatWidget';
import { plantImageUrl } from '../utils/images';
import GanttChart, { type GanttRow } from '../components/GanttChart';

// ── Constants ─────────────────────────────────────────────────────────────────
const PX = 60; // px per foot at zoom=1
const PX_PER_IN = PX / 12;
const BED_HEADER_PX = 24; // height of the bed label bar in pixels

const GARDEN_PALETTE = [
  '#2d5a27', '#4a7c3f', '#6aaa58', '#a8d5a2', '#c8e6c9',
  '#5d4037', '#795548', '#a1887f', '#d7ccc8', '#8d6e63',
  '#f9a825', '#fbc02d', '#fff176', '#f0e68c',
  '#b3e5fc', '#81d4fa', '#4fc3f7',
  '#ffffff', '#f5f5f5', '#9e9e9e', '#424242',
];

const PATTERNS = [
  { key: 'grass',      label: '🌿 Grass' },
  { key: 'mulch',      label: '🍂 Mulch' },
  { key: 'wood_chips', label: '🪵 Wood' },
  { key: 'straw',      label: '🌾 Straw' },
  { key: 'dirt',       label: '🟫 Dirt' },
];

// SVG data URI cursors for care tools
const CURSOR_WATER = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g fill='%2334aadc'><rect x='3' y='12' width='14' height='10' rx='2'/><rect x='17' y='10' width='8' height='4' rx='1'/><circle cx='7' cy='26' r='2'/><circle cx='13' cy='26' r='2'/><line x1='25' y1='6' x2='29' y2='12' stroke='%2334aadc' stroke-width='2' stroke-linecap='round'/></g></svg>") 28 10, crosshair`;
const CURSOR_FERTILIZE = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><text y='26' font-size='26'>%F0%9F%92%A9</text></svg>") 16 16, crosshair`;
const CURSOR_WEED = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g fill='%23888' stroke='%23555' stroke-width='1'><rect x='7' y='2' width='3' height='12' rx='1'/><rect x='14' y='2' width='3' height='14' rx='1'/><rect x='21' y='2' width='3' height='12' rx='1'/><rect x='13' y='14' width='5' height='14' rx='1'/></g></svg>") 15 2, crosshair`;

// ── Helpers ───────────────────────────────────────────────────────────────────
function patternStyle(pattern: string | null | undefined): React.CSSProperties {
  if (!pattern) return {};
  const p: Record<string, React.CSSProperties> = {
    grass: {
      backgroundImage: `repeating-linear-gradient(45deg, #4a7c3f 0px, #4a7c3f 2px, transparent 2px, transparent 8px), repeating-linear-gradient(-45deg, #6aaa58 0px, #6aaa58 2px, transparent 2px, transparent 8px)`,
      backgroundSize: '10px 10px',
    },
    mulch: {
      backgroundImage: `repeating-linear-gradient(30deg, #795548 0px, #795548 3px, transparent 3px, transparent 12px), repeating-linear-gradient(150deg, #5d4037 0px, #5d4037 2px, transparent 2px, transparent 10px)`,
      backgroundSize: '14px 14px',
    },
    wood_chips: {
      backgroundImage: `repeating-linear-gradient(0deg, #a1887f 0px, #a1887f 2px, #d7ccc8 2px, #d7ccc8 8px)`,
      backgroundSize: '12px 10px',
    },
    straw: {
      backgroundImage: `repeating-linear-gradient(15deg, #f9a825 0px, #f9a825 1px, transparent 1px, transparent 7px), repeating-linear-gradient(-15deg, #fbc02d 0px, #fbc02d 1px, transparent 1px, transparent 9px)`,
      backgroundSize: '10px 8px',
    },
    dirt: {
      backgroundImage: `radial-gradient(circle, #795548 1px, transparent 1px)`,
      backgroundSize: '8px 8px',
    },
  };
  return p[pattern] ?? {};
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface Bed {
  id: number; name: string; width_ft: number; height_ft: number;
  pos_x?: number; pos_y?: number; garden_id?: number;
  depth_ft?: number; location?: string; description?: string;
  soil_notes?: string; soil_ph?: number;
  clay_pct?: number; compost_pct?: number; sand_pct?: number;
  plant_count?: number;
  color?: string;
  background_image?: string;
  background_pattern?: string;
  last_weeded?: string;
}
interface GridChip {
  id: number; grid_x: number; grid_y: number;
  plant_name: string; image_filename?: string; spacing_in: number; stage?: string;
}
interface CanvasPlant {
  id: number; name: string; pos_x: number; pos_y: number; radius_ft: number;
  color?: string; display_mode?: string; image_filename?: string; custom_image?: string;
  svg_icon_url?: string; ai_icon_url?: string; library_id?: number; plant_id?: number; spacing_in?: number;
  status?: string;
  last_watered?: string; watering_amount?: string;
  last_fertilized?: string; fertilizer_type?: string; fertilizer_npk?: string;
}
interface LibPlant {
  id: number; name: string; type?: string; image_filename?: string; spacing_in?: number;
}
interface GardenPlant {
  id: number; name: string; library_id?: number; image_filename?: string;
  spacing_in?: number; status?: string; notes?: string;
  planted_date?: string; transplant_date?: string; expected_harvest?: string;
  type?: string; days_to_harvest?: number; days_to_germination?: number;
  sow_indoor_weeks?: number; direct_sow_offset?: number;
  transplant_offset?: number; temp_max_f?: number;
  last_watered?: string; watering_amount?: string;
  last_fertilized?: string; fertilizer_type?: string; fertilizer_npk?: string;
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
  watering_amount?: string; last_fertilized?: string; fertilizer_type?: string; fertilizer_npk?: string;
  last_harvest?: string; health_notes?: string;
  stage?: string; plant_notes?: string; is_bed: boolean;
  library_id?: number;
}
interface LibraryInfo {
  id: number; name: string; scientific_name?: string; type?: string;
  image_filename?: string; sunlight?: string; water?: string;
  spacing_in?: number; companion_plants?: string; growing_notes?: string;
  days_to_germination?: number; days_to_harvest?: number;
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
function plantSpan(spacingIn: number, tileIn: number) { const s = Math.round((spacingIn || 12) / tileIn); return Math.max(1, isNaN(s) ? 1 : s); }

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

  // Paint mode refs — cleared when dragPlant changes or mouse released
  const isPainting = useRef(false);
  const paintedKeys = useRef(new Set<string>());
  const pendingOcc = useRef(new Set<string>());

  function canPlace(cx: number, cy: number, span: number) {
    if (cx + span > cols || cy + span > rows) return false;
    for (let r = cy; r < cy + span; r++)
      for (let c = cx; c < cx + span; c++)
        if (occupied.has(`${c},${r}`) || pendingOcc.current.has(`${c},${r}`)) return false;
    return true;
  }

  function tryPaint(cx: number, cy: number) {
    if (!dragPlant) return;
    const key = `${cx},${cy}`;
    if (paintedKeys.current.has(key)) return;
    paintedKeys.current.add(key);
    const span = plantSpan((dragPlant as LibPlant | GardenPlant).spacing_in ?? 12, tileIn);
    if (!canPlace(cx, cy, span)) return;
    for (let r = cy; r < cy + span; r++)
      for (let c = cx; c < cx + span; c++)
        pendingOcc.current.add(`${c},${r}`);
    onCellClick(bed.id, cx, cy);
  }

  function stopPainting() {
    isPainting.current = false;
    paintedKeys.current.clear();
    pendingOcc.current.clear();
  }

  const STAGE_LABELS: Record<string, string> = { seedling: '🌱', growing: '🌿', harvesting: '🥕', done: '✓' };

  return (
    <div
      className="canvas-bed-grid"
      style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, ${tilePx}px)`, gridTemplateRows: `repeat(${rows}, ${tilePx}px)`, position: 'relative', backgroundImage: 'radial-gradient(circle, rgba(80,120,80,0.45) 1.5px, transparent 1.5px)', backgroundSize: `${tilePx}px ${tilePx}px`, userSelect: 'none' }}
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
      onMouseUp={() => stopPainting()}
      onMouseLeave={() => stopPainting()}
    >
      {Array.from({ length: rows }, (_, y) =>
        Array.from({ length: cols }, (_, x) => {
          const isOcc = occupied.has(`${x},${y}`) || pendingOcc.current.has(`${x},${y}`);
          const inHover = hover && x >= hover.cx && x < hover.cx + hover.span && y >= hover.cy && y < hover.cy + hover.span;
          return (
            <div key={`${x},${y}`}
                 className={`grid-cell${isOcc ? ' cell-occupied' : ''}${inHover ? (hover!.ok ? ' cell-drop-target' : ' cell-drop-bad') : ''}`}
                 style={{ width: tilePx, height: tilePx }}
                 onMouseDown={e => {
                   if (!dragPlant) return;
                   e.preventDefault();
                   isPainting.current = true;
                   tryPaint(x, y);
                 }}
                 onMouseEnter={() => {
                   if (!isPainting.current || !dragPlant) return;
                   tryPaint(x, y);
                 }}
            />
          );
        })
      )}
      {chips.map(chip => {
        const cx = Math.floor(chip.grid_x / tileIn);
        const cy = Math.floor(chip.grid_y / tileIn);
        const chipPx = Math.round((chip.spacing_in || 12) * PX_PER_IN);
        const imgSrc = chip.image_filename ? plantImageUrl(chip.image_filename) : null;
        return (
          <div
            key={chip.id}
            className="grid-plant-chip"
            style={{ position: 'absolute', left: cx * tilePx, top: cy * tilePx, width: chipPx, height: chipPx }}
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

  const queryClient = useQueryClient();
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

  // ── Care tools ────────────────────────────────────────────────────────────────
  const [careToolType, setCareToolType] = useState<'water' | 'fertilize' | 'weed' | null>(null);
  const [careToolFlash, setCareToolFlash] = useState<number | null>(null);
  const [highlightLibId, setHighlightLibId] = useState<number | null>(null);
  const [waterAmount, setWaterAmount] = useState<'light' | 'moderate' | 'heavy'>('moderate');
  const [fertType, setFertType] = useState('balanced');
  const [fertNpk, setFertNpk] = useState('');
  // Bulk care state for info tab
  const [bulkWaterAmount, setBulkWaterAmount] = useState<'light' | 'moderate' | 'heavy'>('moderate');
  const [bulkFertType, setBulkFertType] = useState('balanced');
  const [bulkFertNpk, setBulkFertNpk] = useState('');
  const [bulkCareSaving, setBulkCareSaving] = useState(false);
  // Rain logging
  const [rainAmount, setRainAmount] = useState<'light' | 'moderate' | 'heavy'>('moderate');

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

  // Library plant info panel
  const [libInfo, setLibInfo] = useState<LibraryInfo | null>(null);
  const [libImageMode, setLibImageMode] = useState(false);
  const [libImages, setLibImages] = useState<{id: number; filename: string; is_primary: boolean; source: string}[]>([]);
  const [libEditMode, setLibEditMode] = useState(false);
  const [libEditForm, setLibEditForm] = useState<{sunlight: string; water: string; spacing_in: string; days_to_germination: string; days_to_harvest: string; notes: string}>({ sunlight: '', water: '', spacing_in: '', days_to_germination: '', days_to_harvest: '', notes: '' });

  // Group info panel
  const [groupInfoPlants, setGroupInfoPlants] = useState<GardenPlant[] | null>(null);
  const [editingPlantId, setEditingPlantId] = useState<number | null>(null);
  const [plantEditForm, setPlantEditForm] = useState<{ status: string; planted_date: string; transplant_date: string; expected_harvest: string; notes: string }>({ status: 'planning', planted_date: '', transplant_date: '', expected_harvest: '', notes: '' });
  const [plantEditSaved, setPlantEditSaved] = useState(false);
  const [bulkStatusValue, setBulkStatusValue] = useState<string>('growing');
  const [bulkSaving, setBulkSaving] = useState(false);

  // Bed inline editing
  const [bedEditMode, setBedEditMode] = useState(false);
  const [bedEditForm, setBedEditForm] = useState({ name: '', width_ft: '', height_ft: '', depth_ft: '', location: '', description: '', soil_notes: '', soil_ph: '', clay_pct: '', compost_pct: '', sand_pct: '' });

  // Help modal
  const [showHelp, setShowHelp] = useState(false);

  // Canvas background color + pattern (persisted on garden)
  const [canvasBgColor, setCanvasBgColor] = useState('#f0f4ef');
  const [canvasBgPattern, setCanvasBgPattern] = useState('');

  const canvasRef = useRef<HTMLDivElement>(null);
  const dragBedRef = useRef<{ bedId: number; offsetX: number; offsetY: number } | null>(null);
  const cpDragRef = useRef<{ cpId: number; mode: 'move' | 'resize'; startX: number; startY?: number; startLeft: number; startTop: number; startDiam: number } | null>(null);

  // ── Sync canvas background color + pattern from garden data ─────────────────
  useEffect(() => {
    if (garden?.background_color) setCanvasBgColor(garden.background_color);
    else setCanvasBgColor('#f0f4ef');
    setCanvasBgPattern(garden?.background_pattern || '');
  }, [garden?.background_color, garden?.background_pattern]);

  // ── Load garden data ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!gardenId) {
      if (gardens && gardens.length > 0) setGardenId(gardens[0].id);
      return;
    }
    loadGardenData();
  }, [gardenId]);

  function classifyBeds(beds: Bed[]): { canvas: Bed[]; palette: Bed[] } {
    const canvas: Bed[] = [], palette: Bed[] = [];
    for (const b of beds) {
      if (b.pos_x != null && b.pos_x >= 0) canvas.push(b);
      else palette.push(b);
    }
    return { canvas, palette };
  }

  async function loadGridChips(beds: Bed[]) {
    const t0 = performance.now();
    const chipsMap: Record<number, GridChip[]> = {};
    await Promise.all(beds.map(async b => {
      const t1 = performance.now();
      const g = await api('GET', `/api/beds/${b.id}/grid`);
      console.debug(`[planner] grid bed ${b.id} (${b.name}): ${(performance.now() - t1).toFixed(0)}ms`);
      chipsMap[b.id] = g.placed || [];
    }));
    setBedChips(chipsMap);
    console.info(`[planner] phase2 all grids (${beds.length} beds): ${(performance.now() - t0).toFixed(0)}ms`);
  }

  async function loadGardenData() {
    if (!gardenId) return;
    const t0 = performance.now();

    // ── Fire all 4 requests in parallel ──
    const t_beds = performance.now();
    const bedsPromise = api('GET', `/api/beds?garden_id=${gardenId}`)
      .then(d => { console.debug(`[planner] beds: ${(performance.now() - t_beds).toFixed(0)}ms`); return d; });
    const t_cp = performance.now();
    const cpPromise   = api('GET', `/api/gardens/${gardenId}/canvas-plants`)
      .then(d => { console.debug(`[planner] canvas-plants: ${(performance.now() - t_cp).toFixed(0)}ms`); return d; });
    const t_gp = performance.now();
    const gpPromise   = api('GET', `/api/plants?garden_id=${gardenId}`)
      .then(d => { console.debug(`[planner] garden-plants: ${(performance.now() - t_gp).toFixed(0)}ms`); return d; });
    const t_ann = performance.now();
    const annPromise  = api('GET', `/api/gardens/${gardenId}/annotations`)
      .then(d => { console.debug(`[planner] annotations: ${(performance.now() - t_ann).toFixed(0)}ms`); return d; });

    // ── Render beds as soon as they arrive (don't wait for cp/gp/ann) ──
    const bedsData = await bedsPromise;
    const { canvas: cb, palette: pb } = classifyBeds(bedsData as Bed[]);
    setCanvasBeds(cb);
    setPaletteBeds(pb);

    // ── Start Phase 2 grid loads immediately (canvas beds are visible) ──
    loadGridChips(bedsData as Bed[]);

    // ── Apply remaining data as it arrives ──
    const [cpData, gpData, annData] = await Promise.all([cpPromise, gpPromise, annPromise]);
    setCanvasPlants(cpData as CanvasPlant[]);
    setGardenPlants(gpData as GardenPlant[]);
    setAnnShapes((annData as any).shapes || []);

    console.info(`[planner] phase1 complete: ${(performance.now() - t0).toFixed(0)}ms`);
    if (rightPanelOpen) loadPanelData();
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

  // ── Add library plant to garden without placing on canvas ────────────────────
  async function handleAddToGarden(p: LibPlant) {
    if (!gardenId) return;
    await api('POST', '/api/plants', { name: p.name, library_id: p.id, garden_id: gardenId, status: 'planning' });
    const gp = await api('GET', `/api/plants?garden_id=${gardenId}`);
    setGardenPlants(gp as GardenPlant[]);
  }

  // ── Plant grid placement ──────────────────────────────────────────────────────
  async function handleCellClick(bedId: number, cx: number, cy: number) {
    if (!selectedPlant) return;
    const payload: Record<string, unknown> = {
      grid_x: cx * tileIn,
      grid_y: cy * tileIn,
      spacing_in: selectedPlant.spacing_in ?? 12,
    };
    if ('library_id' in selectedPlant) {
      // GardenPlant — has an explicit library_id field
      const gp = selectedPlant as GardenPlant;
      if (gp.library_id) payload.library_id = gp.library_id;
    } else {
      // LibPlant — its own .id IS the library entry id
      payload.library_id = selectedPlant.id;
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
    // Care tool shortcuts — record care without opening panel
    if (careToolType === 'water' || careToolType === 'fertilize') {
      if (!cp.plant_id) return;
      const today = new Date().toISOString().split('T')[0];
      const careBody = careToolType === 'water'
        ? { last_watered: today, watering_amount: waterAmount }
        : { last_fertilized: today, fertilizer_type: fertType, ...(fertNpk ? { fertilizer_npk: fertNpk } : {}) };
      await api('POST', `/api/plants/${cp.plant_id}/care`, careBody);
      const updated = await api('GET', `/api/gardens/${gardenId}/canvas-plants`);
      setCanvasPlants(updated);
      setCareToolFlash(cp.id);
      setTimeout(() => setCareToolFlash(null), 1200);
      return;
    }
    // Normal click: open care panel + show matching group info
    const d = await api('GET', `/api/canvas-plants/${cp.id}`);
    setCarePanel({ ...d, plant_name: d.name, is_bed: false });
    setCareForm({ planted_date: d.planted_date || '', transplant_date: d.transplant_date || '', plant_notes: d.plant_notes || '', last_watered: '', last_fertilized: '', last_harvest: '', health_notes: '', stage: 'seedling' });
    setCareSaved(false);
    if (cp.library_id) {
      const group = gardenGroups.find(g => g[0].library_id === cp.library_id);
      if (group) showGroupInfo(group);
    }
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

  // ── Library plant info ────────────────────────────────────────────────────────
  async function showLibInfo(libraryId: number) {
    const d = await api('GET', `/api/library/${libraryId}`);
    setLibInfo({
      id: d.id, name: d.name, scientific_name: d.scientific_name,
      type: d.type, image_filename: d.image_filename, sunlight: d.sunlight,
      water: d.water, spacing_in: d.spacing_in,
      companion_plants: d.companion_plants, growing_notes: d.growing_notes,
      days_to_germination: d.days_to_germination, days_to_harvest: d.days_to_harvest,
    });
    setLibImageMode(false);
    setLibEditMode(false);
    setRightPanelTab('info');
    if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); }
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

  // ── Group info panel ──────────────────────────────────────────────────────────
  async function showGroupInfo(group: GardenPlant[]) {
    setGroupInfoPlants(group);
    setCarePanel(null);
    setEditingPlantId(null);
    setPlantEditSaved(false);
    const rep = group[0];
    if (rep.library_id) {
      await showLibInfo(rep.library_id);
    } else {
      setLibInfo(null);
      setLibEditMode(false);
      setLibImageMode(false);
    }
    setRightPanelTab('info');
    if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); }
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

  function summarizeStatuses(plants: GardenPlant[]) {
    const counts: Record<string, number> = {};
    for (const p of plants) {
      const s = p.status || 'planning';
      counts[s] = (counts[s] || 0) + 1;
    }
    return Object.entries(counts).map(([s, n]) => `${s} ×${n}`).join(', ');
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

  // ── Bed inline edit ───────────────────────────────────────────────────────────
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
      // PUT /api/beds/{id} returns the bed object directly
      const updated: Bed = { ...selectedBed, ...r };
      setSelectedBed(updated);
      setCanvasBeds(prev => prev.map(b => b.id === updated.id ? updated : b));
      setPaletteBeds(prev => prev.map(b => b.id === updated.id ? updated : b));
      setBedEditMode(false);
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

  // Escape key deactivates draw tool and care tools
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (activeTool) deactivateDrawTool();
        if (careToolType) setCareToolType(null);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeTool, careToolType]);

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
          <button title="Help" onClick={() => setShowHelp(true)} style={{ background: 'none', border: '1px solid #c0d4be', borderRadius: '50%', width: 22, height: 22, cursor: 'pointer', color: '#3a6b35', fontSize: '0.75rem', fontWeight: 700, padding: 0, flexShrink: 0, lineHeight: 1 }}>?</button>
        </div>

        {/* Canvas background */}
        <div style={{ fontSize: '0.78rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
            <span style={{ color: '#7a907a', whiteSpace: 'nowrap' }}>Canvas:</span>
            <input type="color" value={canvasBgColor}
              onChange={e => setCanvasBgColor(e.target.value)}
              onBlur={async () => { if (gardenId) await api('PUT', `/api/gardens/${gardenId}`, { background_color: canvasBgColor }); }}
              style={{ width: 28, height: 22, padding: 1, border: '1px solid #c0d4be', borderRadius: 3, cursor: 'pointer' }} title="Canvas background color" />
            <label title="Upload canvas background image" style={{ cursor: 'pointer', color: '#3a6b35', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
              🖼
              <input type="file" accept="image/*" style={{ display: 'none' }} onChange={async e => {
                const file = e.target.files?.[0]; if (!file || !gardenId) return;
                const fd = new FormData(); fd.append('image', file);
                await fetch(`/api/gardens/${gardenId}/upload-background`, { method: 'POST', body: fd });
                queryClient.invalidateQueries({ queryKey: ['gardens', gardenId] });
              }} />
            </label>
            {garden?.background_image && (
              <button title="Remove canvas image" onClick={async () => { await api('POST', `/api/gardens/${gardenId}/remove-background`, {}); queryClient.invalidateQueries({ queryKey: ['gardens', gardenId] }); }}
                style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.8rem', padding: 0 }}>✕</button>
            )}
          </div>
          {/* Color swatches */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px', marginBottom: '0.25rem' }}>
            {GARDEN_PALETTE.map(c => (
              <button key={c} title={c}
                style={{ width: 16, height: 16, background: c, border: canvasBgColor === c ? '2px solid #333' : '1px solid #aaa', borderRadius: 2, cursor: 'pointer', padding: 0 }}
                onClick={async () => { setCanvasBgColor(c); if (gardenId) await api('PUT', `/api/gardens/${gardenId}`, { background_color: c }); }} />
            ))}
          </div>
          {/* Pattern selector */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px' }}>
            {[{ key: '', label: 'None' }, ...PATTERNS].map(p => (
              <button key={p.key} className={`btn-small${canvasBgPattern === p.key ? '' : ' btn-link'}`}
                style={{ fontSize: '0.62rem', padding: '1px 4px', background: canvasBgPattern === p.key ? '#3a6b35' : undefined, color: canvasBgPattern === p.key ? '#fff' : undefined }}
                onClick={async () => { setCanvasBgPattern(p.key); if (gardenId) await api('PUT', `/api/gardens/${gardenId}`, { background_pattern: p.key || null }); }}>
                {p.label}
              </button>
            ))}
          </div>
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

        {/* Care tools */}
        <div>
          <div className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', marginBottom: '0.3rem' }}>Care</div>
          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.25rem' }}>
            {([
              { key: 'water',     label: '💧 Water',     tip: 'Click a plant to record watering today' },
              { key: 'fertilize', label: '🌿 Fertilize', tip: 'Click a plant to record fertilizing today' },
              { key: 'weed',      label: '🪴 Weed',      tip: 'Click a bed header to record weeding today' },
            ] as const).map(({ key, label, tip }) => (
              <button key={key} title={tip}
                      className={`btn-small${careToolType === key ? '' : ' btn-link'}`}
                      style={{ fontSize: '0.7rem', padding: '0.15rem 0.35rem', background: careToolType === key ? '#3a6b35' : undefined, color: careToolType === key ? '#fff' : undefined }}
                      onClick={() => setCareToolType(prev => prev === key ? null : key)}>
                {label}
              </button>
            ))}
          </div>
          {careToolType === 'water' && (
            <div style={{ fontSize: '0.7rem', color: '#7a907a', marginBottom: '0.25rem' }}>
              <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center', marginBottom: '0.2rem' }}>
                <span>Amount:</span>
                {(['light', 'moderate', 'heavy'] as const).map(a => (
                  <button key={a} className={`btn-small${waterAmount === a ? '' : ' btn-link'}`}
                          style={{ fontSize: '0.65rem', padding: '1px 4px', background: waterAmount === a ? '#4a80b4' : undefined, color: waterAmount === a ? '#fff' : undefined }}
                          onClick={() => setWaterAmount(a)}>{a}</button>
                ))}
              </div>
              <span style={{ color: '#aaa' }}>Click a plant · Esc to cancel</span>
            </div>
          )}
          {careToolType === 'fertilize' && (
            <div style={{ fontSize: '0.7rem', color: '#7a907a', marginBottom: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                <span>Type:</span>
                <select value={fertType} onChange={e => setFertType(e.target.value)}
                        style={{ font: 'inherit', fontSize: '0.7rem', padding: '1px 2px', border: '1px solid #c0d4be', borderRadius: 3 }}>
                  <option value="balanced">Balanced</option>
                  <option value="nitrogen">Nitrogen-heavy</option>
                  <option value="phosphorus">Phosphorus</option>
                  <option value="potassium">Potassium</option>
                  <option value="organic">Organic</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                <span>N-P-K:</span>
                <input type="text" value={fertNpk} onChange={e => setFertNpk(e.target.value)}
                       placeholder="e.g. 10-10-10" style={{ font: 'inherit', fontSize: '0.7rem', padding: '1px 4px', border: '1px solid #c0d4be', borderRadius: 3, width: 90 }} />
              </div>
              <span style={{ color: '#aaa' }}>Click a plant · Esc to cancel</span>
            </div>
          )}
          {careToolType === 'weed' && (
            <div style={{ fontSize: '0.7rem', color: '#aaa', marginBottom: '0.25rem' }}>Click a bed header · Esc to cancel</div>
          )}
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
                  onClick={() => { setSelectedBed(b); setBedEditMode(false); if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); } }}>
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
                  onClick={() => { setSelectedBed(b); setBedEditMode(false); if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); } }}>
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
                        {rep.image_filename ? <img src={plantImageUrl(rep.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rep.name}</span>
                        <button title="Plant info" onClick={e => { e.stopPropagation(); showGroupInfo(group); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a907a', fontSize: '0.75rem', padding: '0 1px', flexShrink: 0 }}>ℹ</button>
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
                          {rep.image_filename ? <img src={plantImageUrl(rep.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rep.name}</span>
                          <span style={{ background: '#3a6b35', color: '#fff', borderRadius: '10px', padding: '0 5px', fontSize: '0.68rem', fontWeight: 700 }}>×{count}</span>
                          <button title="Plant info" onClick={e => { e.stopPropagation(); showGroupInfo(group); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a907a', fontSize: '0.75rem', padding: '0 1px', flexShrink: 0 }}>ℹ</button>
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

          <details open style={{ marginTop: '0.4rem' }} onToggle={e => {
            if ((e.currentTarget as HTMLDetailsElement).open && libPlants.length === 0 && !libSearch.trim()) {
              api('GET', '/api/library?per_page=100').then(d => setLibPlants((d.entries || []) as LibPlant[]));
            }
          }}>
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
                  {p.image_filename ? <img src={plantImageUrl(p.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                  <button title="Add to garden (no canvas)" onClick={e => { e.stopPropagation(); handleAddToGarden(p); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3a6b35', fontSize: '0.85rem', padding: '0 1px', flexShrink: 0, fontWeight: 700, lineHeight: 1 }}>+</button>
                  <button title="Plant info" onClick={e => { e.stopPropagation(); showLibInfo(p.id); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a907a', fontSize: '0.75rem', padding: '0 1px', flexShrink: 0 }}>ℹ</button>
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
          style={{ position: 'relative', minWidth: '1200px', minHeight: '900px', transform: `scale(${zoom})`, transformOrigin: 'top left', width: `${100 / zoom}%`, height: `${900 / zoom}px`, backgroundColor: canvasBgColor, backgroundImage: garden?.background_image ? `url(/static/garden_backgrounds/${garden.background_image}), radial-gradient(circle, rgba(80,120,80,0.45) 1.5px, transparent 1.5px)` : 'radial-gradient(circle, rgba(80,120,80,0.45) 1.5px, transparent 1.5px)', backgroundSize: garden?.background_image ? `cover, ${PX}px ${PX}px` : `${PX}px ${PX}px`, backgroundRepeat: garden?.background_image ? 'no-repeat, repeat' : 'repeat', cursor: careToolType === 'water' ? CURSOR_WATER : careToolType === 'fertilize' ? CURSOR_FERTILIZE : careToolType === 'weed' ? CURSOR_WEED : undefined, ...patternStyle(canvasBgPattern) }}
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
              style={{ position: 'absolute', left: (bed.pos_x ?? 0) * PX, top: (bed.pos_y ?? 0) * PX, width: bed.width_ft * PX, height: bed.height_ft * PX + BED_HEADER_PX, background: bed.color || '#e8f5e3', backgroundImage: bed.background_image ? `url(/static/bed_images/${bed.background_image})` : undefined, backgroundSize: 'cover', backgroundRepeat: 'no-repeat', border: '2px solid #a8c8a0', borderRadius: '4px', boxSizing: 'border-box', ...(!bed.background_image ? patternStyle(bed.background_pattern) : {}) }}
            >
              <div className="canvas-bed-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '2px 6px', background: careToolFlash === -(bed.id) ? '#b8e8a0' : selectedBed?.id === bed.id ? '#a8d8a0' : '#c8e0c0', fontSize: '0.75rem', fontWeight: 600, cursor: careToolType === 'weed' ? 'pointer' : 'grab' }}
                   onClick={e => {
                     e.stopPropagation();
                     if (careToolType === 'weed') {
                       const today = new Date().toISOString().split('T')[0];
                       api('PUT', `/api/beds/${bed.id}`, { last_weeded: today }).then(() => {
                         setCanvasBeds(prev => prev.map(b => b.id === bed.id ? { ...b, last_weeded: today } : b));
                         setPaletteBeds(prev => prev.map(b => b.id === bed.id ? { ...b, last_weeded: today } : b));
                         setSelectedBed(prev => prev?.id === bed.id ? { ...prev, last_weeded: today } : prev);
                       });
                       setCareToolFlash(-(bed.id));
                       setTimeout(() => setCareToolFlash(null), 1200);
                       return;
                     }
                     setSelectedBed(bed); setBedEditMode(false);
                     if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); }
                   }}>
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
            const imgSrc = cp.custom_image ? `/static/canvas_plant_images/${cp.custom_image}` : (cp.ai_icon_url || cp.svg_icon_url || plantImageUrl(cp.image_filename));
            return (
              <div
                key={cp.id}
                id={`cp-${cp.id}`}
                className="canvas-plant-circle"
                style={{
                  position: 'absolute', left: leftPx, top: topPx, width: diamPx, height: diamPx,
                  borderRadius: '50%', background: imgSrc ? 'transparent' : (cp.color || '#5a9e54'),
                  border: '2px solid rgba(0,0,0,0.15)', overflow: 'visible',
                  cursor: (careToolType === 'water' || careToolType === 'fertilize') ? 'cell' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', userSelect: 'none',
                  boxShadow: highlightLibId != null && cp.library_id === highlightLibId ? '0 0 0 3px #f5a623' : undefined,
                  transition: 'box-shadow 0.2s',
                }}
                onClick={() => handleCanvasPlantClick(cp)}
              >
                {imgSrc && (
                  <div className="circle-bg" style={{ position: 'absolute', inset: 0, borderRadius: '50%', overflow: 'hidden' }}>
                    <img src={imgSrc} alt={cp.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                )}
                <span className="canvas-plant-label" style={{ position: 'relative', fontSize: Math.max(9, Math.min(12, diamPx / 4)), color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,0.5)', textAlign: 'center', padding: '2px', pointerEvents: 'none', maxWidth: diamPx - 8, overflow: 'hidden', wordBreak: 'break-word' }}>
                  {cp.name}
                </span>
                {/* Care action flash overlay */}
                {careToolFlash === cp.id && (
                  <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'rgba(255,255,255,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: Math.max(14, diamPx / 3), pointerEvents: 'none', zIndex: 3 }}>
                    {careToolType === 'fertilize' ? '🌿' : waterAmount === 'light' ? '💧' : waterAmount === 'heavy' ? '💧💧💧' : '💧💧'}
                  </div>
                )}
                {/* Move handle (the whole circle, minus resize handle) */}
                <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', cursor: (careToolType === 'water' || careToolType === 'fertilize') ? 'cell' : 'move' }}
                     onPointerDown={e => { if (careToolType === 'water' || careToolType === 'fertilize') return; handleCpPointerDown(e, cp, 'move'); }}
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

              {/* Individual plant cards — collapsible when group has multiple */}
              {groupInfoPlants.length > 1 ? (
                <details open>
                  <summary style={{ cursor: 'pointer', fontSize: '0.78rem', color: '#5a7a5a', marginBottom: '0.3rem', userSelect: 'none' }}>
                    {groupInfoPlants.length} plants · {summarizeStatuses(groupInfoPlants)}
                  </summary>
                  {groupInfoPlants.map((p, idx) => (
                    <div key={p.id} style={{ background: '#f0f6ef', borderRadius: 4, padding: '0.4rem 0.5rem', marginBottom: '0.3rem', fontSize: '0.78rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, color: '#3a5c37' }}>#{idx + 1}</span>
                        <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.7rem', color: '#5a7a5a', background: '#ddeedd', borderRadius: 3, padding: '1px 5px' }}>
                            {p.status || 'planning'}
                          </span>
                          {editingPlantId === p.id
                            ? <button className="btn-small" style={{ fontSize: '0.68rem' }} onClick={() => setEditingPlantId(null)}>Cancel</button>
                            : <button className="btn-small" style={{ fontSize: '0.68rem' }} onClick={() => startPlantEdit(p)}>Edit</button>
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
                        <form onSubmit={e => handlePlantEditSave(p.id, e)} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
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
                            <button type="button" className="btn-small" style={{ fontSize: '0.72rem' }} onClick={() => setEditingPlantId(null)}>Cancel</button>
                          </div>
                        </form>
                      )}
                    </div>
                  ))}
                </details>
              ) : (
                groupInfoPlants.map((p) => (
                  <div key={p.id} style={{ background: '#f0f6ef', borderRadius: 4, padding: '0.4rem 0.5rem', marginBottom: '0.3rem', fontSize: '0.78rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, color: '#3a5c37' }}>{p.name}</span>
                      <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.7rem', color: '#5a7a5a', background: '#ddeedd', borderRadius: 3, padding: '1px 5px' }}>
                          {p.status || 'planning'}
                        </span>
                        {editingPlantId === p.id
                          ? <button className="btn-small" style={{ fontSize: '0.68rem' }} onClick={() => setEditingPlantId(null)}>Cancel</button>
                          : <button className="btn-small" style={{ fontSize: '0.68rem' }} onClick={() => startPlantEdit(p)}>Edit</button>
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
                      <form onSubmit={e => handlePlantEditSave(p.id, e)} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
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
                          <button type="button" className="btn-small" style={{ fontSize: '0.72rem' }} onClick={() => setEditingPlantId(null)}>Cancel</button>
                        </div>
                      </form>
                    )}
                  </div>
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

          </>)}

          {/* ── Timeline tab ── */}
          {rightPanelTab === 'timeline' && (() => {
            const groupMap = new Map<string, GardenPlant[]>();
            for (const p of gardenPlants) {
              const key = p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`;
              if (!groupMap.has(key)) groupMap.set(key, []);
              groupMap.get(key)!.push(p);
            }
            const ganttRows: GanttRow[] = [...groupMap.values()].map(group => {
              const planted    = group.map(p => p.planted_date).filter(Boolean).sort()[0] ?? null;
              const transplant = group.map(p => p.transplant_date).filter(Boolean).sort()[0] ?? null;
              const harvest    = group.map(p => p.expected_harvest).filter(Boolean).sort().at(-1) ?? null;
              const rep = group[0];
              // Determine status: if any are growing treat as growing
              const status = group.some(p => p.status === 'growing') ? 'growing' : (rep.status || 'planning');
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

            const lastFrost = garden?.last_frost_date ? new Date(garden.last_frost_date + 'T00:00:00') : null;
            const firstFallFrost = garden?.first_frost_date ? new Date(garden.first_frost_date + 'T00:00:00') : null;

            return (
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37', marginBottom: '0.5rem' }}>Plant Timeline</div>
                {ganttRows.length === 0 ? (
                  <p className="muted" style={{ fontSize: '0.78rem' }}>No plants yet. Add plants to see the timeline.</p>
                ) : (
                  <GanttChart rows={ganttRows} filter="all" lastFrost={lastFrost} firstFallFrost={firstFallFrost} />
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

      {/* ── Help Modal ──────────────────────────────────────────────────────── */}
      {showHelp && (
        <div onClick={() => setShowHelp(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={e => e.stopPropagation()} style={{ background: '#fff', borderRadius: 8, padding: '1.5rem', maxWidth: 420, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)', position: 'relative', maxHeight: '80vh', overflowY: 'auto' }}>
            <button onClick={() => setShowHelp(false)} style={{ position: 'absolute', top: 10, right: 12, background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: '#7a907a', lineHeight: 1 }}>×</button>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#3a5c37', marginBottom: '1rem' }}>Garden Planner Help</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem', fontSize: '0.82rem', color: '#3a5c37' }}>
              <div><strong>Placing beds</strong><br />Drag a bed from the sidebar onto the canvas. Placed beds can be dragged to reposition. Unplaced beds show a ⋮⋮ handle.</div>
              <div><strong>Planting on canvas (circles)</strong><br />Select a plant from Library Plants, then drag it onto the canvas. A coloured circle appears — drag to move, drag the bottom-right corner to resize.</div>
              <div><strong>Planting in a bed grid</strong><br />Select a plant, then click any empty grid cell inside a bed. Spacing determines how many cells the plant occupies.</div>
              <div><strong>Plant care & dates</strong><br />Click a plant circle or grid chip to open the Info panel. Set Seeded, Transplanted, and harvest dates there — they appear on the Timeline.</div>
              <div><strong>Timeline tab</strong><br />Shows each unique plant as one row. Multiple instances of the same plant are merged and labelled with a count badge (×N).</div>
              <div><strong>Calendar tab</strong><br />Displays tasks for this garden by month. Use "+ Add Task" to schedule reminders.</div>
              <div><strong>Drawing tools</strong><br />Use Quick objects (Path, Fence, etc.) or the shape tools to annotate your garden. Style controls appear when a tool is active.</div>
              <div><strong>Add plant to list (no canvas)</strong><br />Click the <strong>+</strong> button next to any Library Plant to add it to "Plants in Garden" without placing it on the canvas. Useful for tracking plants not yet placed.</div>
              <div><strong>Canvas & bed colours</strong><br />Use the Canvas colour swatch in the sidebar to change the background colour. Upload a background image with the 🖼 button. To change a bed's colour or image, select the bed and click "✎ Edit Bed" in the right panel.</div>
              <div><strong>Zoom</strong><br />Use the 0.5×–1.5× zoom buttons in the sidebar. The canvas size adjusts automatically.</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
