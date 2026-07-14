import React, { useState, useEffect, useRef, useCallback } from 'react';
import { apiFetch } from '@garden/shared';
import { useSearchParams, Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useGardens, useGarden } from '../hooks/useGardens';
import ChatWidget from '../components/ChatWidget';
import {
  PX, BED_HEADER_PX, GARDEN_PALETTE, PATTERNS,
  CURSOR_WATER, CURSOR_FERTILIZE, CURSOR_WEED,
  patternStyle, snap, computePositions, api,
  type Bed, type GridChip, type CanvasPlant, type LibPlant, type GardenPlant,
  type AnnotationShape, type CareData, type LibraryInfo, type PlantMode,
} from '../components/Planner/types';
import { PlannerCtx } from '../components/Planner/PlannerContext';
import HelpModal from '../components/Planner/Dialogs/HelpModal';
import CareToolsSection from '../components/Planner/Sidebar/CareToolsSection';
import DrawToolsSection from '../components/Planner/Sidebar/DrawToolsSection';
import BedList from '../components/Planner/Sidebar/BedList';
import TimelineTab from '../components/Planner/RightPanel/TimelineTab';
import CalendarTab from '../components/Planner/RightPanel/CalendarTab';
import InfoTab from '../components/Planner/RightPanel/InfoTab';
import BedGrid from '../components/Planner/Canvas/BedGrid';
import CanvasPlantCircle from '../components/Planner/Canvas/CanvasPlantCircle';
import AnnotationOverlay from '../components/Planner/Canvas/AnnotationOverlay';
import PlantSearchPanel from '../components/Planner/Sidebar/PlantSearchPanel';

// ── Canvas plant grouping ─────────────────────────────────────────────────────
interface GroupedPlant {
  representative: CanvasPlant;
  count: number;
  ids: number[];
  libraryId?: number;
}

function computeGroups(plants: CanvasPlant[], mode: 'species' | 'row'): GroupedPlant[] {
  const buckets = new Map<string, CanvasPlant[]>();
  for (const cp of plants) {
    const key = mode === 'species'
      ? String(cp.library_id ?? cp.name)
      : String(Math.round(cp.pos_y * 2));
    buckets.set(key, [...(buckets.get(key) ?? []), cp]);
  }
  return [...buckets.values()].map(group => {
    const centX = group.reduce((s, p) => s + p.pos_x, 0) / group.length;
    const centY = group.reduce((s, p) => s + p.pos_y, 0) / group.length;
    return {
      representative: { ...group[0], pos_x: centX, pos_y: centY },
      count: group.length,
      ids: group.map(p => p.id),
      libraryId: mode === 'species' ? group[0].library_id : undefined,
    };
  });
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
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => parseInt(localStorage.getItem('plannerSidebarWidth') || '220'));
  const sidebarWidthRef = useRef<number>(parseInt(localStorage.getItem('plannerSidebarWidth') || '220'));
  const [tileIn, setTileIn] = useState(12);

  // Canvas beds (placed on canvas) and unplaced beds (sidebar)
  const [canvasBeds, setCanvasBeds] = useState<Bed[]>([]);
  const [paletteBeds, setPaletteBeds] = useState<Bed[]>([]);
  const [bedChips, setBedChips] = useState<Record<number, GridChip[]>>({});

  // Canvas plants (circles)
  const [canvasPlants, setCanvasPlants] = useState<CanvasPlant[]>([]);

  // Palette plants
  const [gardenPlants, setGardenPlants] = useState<GardenPlant[]>([]);

  // UI state
  const [plantMode, setPlantMode] = useState<PlantMode>('single');
  const [selectedPlant, setSelectedPlant] = useState<LibPlant | GardenPlant | null>(null);
  const [carePanel, setCarePanel] = useState<CareData | null>(null);
  const [rightPanelOpen, setRightPanelOpen] = useState(() => localStorage.getItem('plannerRightPanel') === 'open');
  const [rightPanelWidth, setRightPanelWidth] = useState<number>(() => parseInt(localStorage.getItem('plannerRightPanelWidth') || '280'));
  const [chatOpen, setChatOpen] = useState(false);

  // Right panel tabs
  const [rightPanelTab, setRightPanelTab] = useState<'info' | 'timeline' | 'calendar'>('info');

  // ── Care tools ────────────────────────────────────────────────────────────────
  const [careToolType, setCareToolType] = useState<'water' | 'fertilize' | 'weed' | null>(null);
  const [careToolFlash, setCareToolFlash] = useState<number | null>(null);
  const [highlightLibId, setHighlightLibId] = useState<number | null>(null);
  const [waterAmount, setWaterAmount] = useState<'light' | 'moderate' | 'heavy'>('moderate');
  const [fertType, setFertType] = useState('balanced');
  const [fertNpk, setFertNpk] = useState('');

  // ── Drawing / annotation state ──────────────────────────────────────────────
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeObjectType, setActiveObjectType] = useState<string>('generic');
  const [strokeColor, setStrokeColor] = useState('#2d5a1b');
  const [fillColor, setFillColor] = useState('#a8d5a2');
  const [noFill, setNoFill] = useState(true);
  const [strokeWidth, setStrokeWidth] = useState(2);
  const [dashArray, setDashArray] = useState('');
  const [annShapes, setAnnShapes] = useState<AnnotationShape[]>([]);

  // ── Selected bed for detail panel ──────────────────────────────────────────
  const [selectedBed, setSelectedBed] = useState<Bed | null>(null);

  const [weather, setWeather] = useState<unknown>(null);
  const [tasks, setTasks] = useState<unknown[]>([]);
  const [taskForm, setTaskForm] = useState({ title: '', due_date: '', description: '' });
  const [taskSaved, setTaskSaved] = useState('');

  const [addBedForm, setAddBedForm] = useState({ name: '', width_ft: '4', height_ft: '8' });

  // Library plant info panel (libEditMode/libImageMode are context-level; set by showGroupInfo)
  const [libInfo, setLibInfo] = useState<LibraryInfo | null>(null);
  const [libEditMode, setLibEditMode] = useState(false);
  const [libImageMode, setLibImageMode] = useState(false);

  // Group info panel
  const [groupInfoPlants, setGroupInfoPlants] = useState<GardenPlant[] | null>(null);

  // Help modal
  const [showHelp, setShowHelp] = useState(false);

  // Canvas background color + pattern (persisted on garden)
  const [canvasBgColor, setCanvasBgColor] = useState('#f0f4ef');
  const [canvasBgPattern, setCanvasBgPattern] = useState('');

  // ── Overlap + scroll-to-zoom toggles ─────────────────────────────────────────
  const [allowOverlap, setAllowOverlap] = useState<boolean>(() => localStorage.getItem('plannerAllowOverlap') === 'true');
  const [scrollToZoom, setScrollToZoom] = useState<boolean>(() => localStorage.getItem('plannerScrollToZoom') === 'true');
  const scrollToZoomRef = useRef(scrollToZoom);
  useEffect(() => { scrollToZoomRef.current = scrollToZoom; }, [scrollToZoom]);

  const [iconScale, setIconScale] = useState<number>(() => parseFloat(localStorage.getItem('plannerIconScale') || '1.0'));
  const [labelMode, setLabelMode] = useState<'hover' | 'always'>(() => (localStorage.getItem('plannerLabelMode') as 'hover' | 'always') || 'hover');
  const [groupMode, setGroupMode] = useState<'none' | 'species' | 'row'>(() => (localStorage.getItem('plannerGroupMode') as 'none' | 'species' | 'row') || 'none');
  const [highlightIds, setHighlightIds] = useState<Set<number>>(new Set());

  // ── Multi-select ──────────────────────────────────────────────────────────────
  const [selectedCanvasIds, setSelectedCanvasIds] = useState<Set<number>>(new Set());
  const [lassoRect, setLassoRect] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; plantId: number | null } | null>(null);

  const canvasRef = useRef<HTMLDivElement>(null);
  const canvasWrapperRef = useRef<HTMLDivElement>(null);
  const dragBedRef = useRef<{ bedId: number; offsetX: number; offsetY: number } | null>(null);
  const cpDragRef = useRef<{ cpId: number; mode: 'move' | 'resize'; startX: number; startY?: number; startLeft: number; startTop: number; startDiam: number; groupStart?: Array<{ id: number; left: number; top: number }> } | null>(null);
  const lassoStartRef = useRef<{ x: number; y: number } | null>(null);

  // ── Undo / redo history ───────────────────────────────────────────────────────
  type HistoryEntry = { undo: () => Promise<void>; redo: () => Promise<void> };
  const history = useRef<HistoryEntry[]>([]);
  const historyIdx = useRef(-1);

  function pushHistory(entry: HistoryEntry) {
    history.current = history.current.slice(0, historyIdx.current + 1);
    history.current.push(entry);
    historyIdx.current = history.current.length - 1;
  }

  // Clear history when garden changes
  useEffect(() => { history.current = []; historyIdx.current = -1; }, [gardenId]);

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
    setSelectedCanvasIds(new Set());
    setContextMenu(null);
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
      // Weather is best-effort: a failed fetch (502 from the backend when
      // open-meteo is unreachable) must not abort loading tasks below.
      try {
        const w = await api('GET', `/api/gardens/${gardenId}/weather`);
        setWeather(w && (w as { current?: unknown }).current ? w : null);
      } catch { setWeather(null); }
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
  useEffect(() => { localStorage.setItem('plannerIconScale', String(iconScale)); }, [iconScale]);
  useEffect(() => { localStorage.setItem('plannerLabelMode', labelMode); }, [labelMode]);
  useEffect(() => { localStorage.setItem('plannerGroupMode', groupMode); }, [groupMode]);

  // Ctrl+wheel zoom on canvas wrapper
  useEffect(() => {
    const el = canvasWrapperRef.current;
    if (!el) return;
    function onWheel(e: WheelEvent) {
      if (!e.ctrlKey && !scrollToZoomRef.current) return;
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom(prev => {
        const next = Math.max(0.3, Math.min(2, Math.round((prev + delta) * 20) / 20));
        localStorage.setItem('plannerZoom', String(next));
        return next;
      });
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

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

  function handleSidebarResize(e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sidebarWidthRef.current;
    function onMove(mv: MouseEvent) {
      const w = Math.max(160, Math.min(480, startWidth + (mv.clientX - startX)));
      setSidebarWidth(w);
      sidebarWidthRef.current = w;
    }
    function onUp() {
      localStorage.setItem('plannerSidebarWidth', String(sidebarWidthRef.current));
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
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
    const spacingIn = selectedPlant.spacing_in ?? 12;

    // Resolve library_id
    let library_id: number | undefined;
    if ('library_id' in selectedPlant) {
      library_id = (selectedPlant as GardenPlant).library_id ?? undefined;
    } else {
      library_id = selectedPlant.id;
    }

    if (plantMode === 'single') {
      const payload: Record<string, unknown> = { grid_x: cx * tileIn, grid_y: cy * tileIn, spacing_in: spacingIn };
      if (library_id) payload.library_id = library_id;
      const r = await api('POST', `/api/beds/${bedId}/grid-plant`, payload);
      if (r.ok) {
        const chip: GridChip = { id: r.id, grid_x: cx * tileIn, grid_y: cy * tileIn, plant_name: r.plant_name, image_filename: r.image_filename, spacing_in: r.spacing_in || spacingIn, stage: 'seedling' };
        setBedChips(prev => ({ ...prev, [bedId]: [...(prev[bedId] || []), chip] }));
      }
    } else {
      const bed = canvasBeds.find(b => b.id === bedId);
      if (!bed) return;
      const positions = computePositions(plantMode, cx, cy, spacingIn, tileIn, bed.width_ft * 12, bed.height_ft * 12);
      if (positions.length === 0) return;
      const payload: Record<string, unknown> = { positions, spacing_in: spacingIn };
      if (library_id) payload.library_id = library_id;
      const r = await api('POST', `/api/beds/${bedId}/grid-plant-bulk`, payload);
      if (r.ok && r.placed?.length > 0) {
        const newChips: GridChip[] = (r.placed as Array<{ id: number; grid_x: number; grid_y: number; plant_name: string; image_filename?: string; spacing_in: number }>).map(p => ({
          id: p.id, grid_x: p.grid_x, grid_y: p.grid_y,
          plant_name: p.plant_name, image_filename: p.image_filename,
          spacing_in: p.spacing_in, stage: 'seedling',
        }));
        setBedChips(prev => ({ ...prev, [bedId]: [...(prev[bedId] || []), ...newChips] }));
      }
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
      if (r.canvas_plant.plant_id) {
        const gp = await api('GET', `/api/plants?garden_id=${gardenId}`) as GardenPlant[];
        setGardenPlants(gp);
      }
      let placedId = r.canvas_plant.id as number;
      pushHistory({
        undo: async () => {
          await api('POST', `/api/canvas-plants/${placedId}/delete`, {});
          setCanvasPlants(prev => prev.filter(c => c.id !== placedId));
        },
        redo: async () => {
          const r2 = await api('POST', `/api/gardens/${gardenId}/canvas-plants`, payload);
          if (r2.ok) { placedId = r2.canvas_plant.id; setCanvasPlants(prev => [...prev, r2.canvas_plant]); }
        },
      });
    }
  }, [selectedPlant, gardenId, zoom, gardenPlants]);

  async function handleDeleteCanvasPlant(cp: CanvasPlant) {
    if (!confirm(`Remove "${cp.name}" from canvas?`)) return;
    const r = await api('POST', `/api/canvas-plants/${cp.id}/delete`, {});
    if (r.ok) {
      setCanvasPlants(prev => prev.filter(c => c.id !== cp.id));
      if (carePanel && 'plant_id' in carePanel && carePanel.plant_id === cp.plant_id) setCarePanel(null);
      const restorePayload = { pos_x: cp.pos_x, pos_y: cp.pos_y, library_id: cp.library_id, radius_ft: cp.radius_ft };
      let restoredId = -1;
      pushHistory({
        undo: async () => {
          const r2 = await api('POST', `/api/gardens/${gardenId}/canvas-plants`, restorePayload);
          if (r2.ok) { restoredId = r2.canvas_plant.id; setCanvasPlants(prev => [...prev, r2.canvas_plant]); }
        },
        redo: async () => {
          if (restoredId === -1) return;
          await api('POST', `/api/canvas-plants/${restoredId}/delete`, {});
          setCanvasPlants(prev => prev.filter(c => c.id !== restoredId));
        },
      });
    }
  }

  async function handleCanvasPlantClick(cp: CanvasPlant, e?: React.MouseEvent) {
    // Ctrl+click is handled in CanvasPlantCircle before onClick fires; this is the plain click path
    if (e && (e.ctrlKey || e.metaKey)) { toggleSelectId(cp.id); return; }
    // Clicking a non-selected plant clears selection
    if (selectedCanvasIds.size > 0) { setSelectedCanvasIds(new Set()); }
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
    if (cp.library_id) {
      const group = gardenPlants.filter(p => p.library_id === cp.library_id);
      if (group.length > 0) showGroupInfo(group);
    }
    if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); }
  }

  function handleGroupClick(group: GroupedPlant) {
    if (groupMode === 'species' && group.libraryId != null) {
      setHighlightLibId(group.libraryId);
      setHighlightIds(new Set());
    } else {
      setHighlightIds(new Set(group.ids));
      setHighlightLibId(null);
    }
  }

  async function handleDeleteGroup(ids: number[]) {
    if (!confirm(`Delete all ${ids.length} plant(s) in this group?`)) return;
    for (const id of ids) {
      await api('POST', `/api/canvas-plants/${id}/delete`, {});
    }
    setCanvasPlants(prev => prev.filter(c => !ids.includes(c.id)));
  }

  // ── Multi-select helpers ──────────────────────────────────────────────────────
  function toggleSelectId(id: number) {
    setSelectedCanvasIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleByPlantId(plantId: number) {
    const matching = canvasPlants.filter(cp => cp.plant_id === plantId).map(cp => cp.id);
    if (matching.length === 0) return;
    setSelectedCanvasIds(prev => {
      const next = new Set(prev);
      const allIn = matching.every(id => next.has(id));
      matching.forEach(id => allIn ? next.delete(id) : next.add(id));
      return next;
    });
  }

  async function handleBulkDeleteSelected() {
    const ids = [...selectedCanvasIds];
    if (ids.length === 0) return;
    if (ids.length > 5 && !confirm(`Delete ${ids.length} plants?`)) return;
    await api('POST', '/api/canvas-plants/bulk-delete', { ids });
    setCanvasPlants(prev => prev.filter(c => !selectedCanvasIds.has(c.id)));
    setSelectedCanvasIds(new Set());
    setCarePanel(null);
  }

  async function handleDuplicateSelected() {
    const plants = canvasPlants.filter(cp => selectedCanvasIds.has(cp.id));
    if (plants.length === 0) return;
    const results = await Promise.all(plants.map(cp =>
      api('POST', `/api/gardens/${gardenId}/canvas-plants`, { library_id: cp.library_id, pos_x: cp.pos_x + 0.5, pos_y: cp.pos_y + 0.5 })
    ));
    const newPlants = results.filter(r => r.ok).map((r: { canvas_plant: CanvasPlant }) => r.canvas_plant);
    if (newPlants.length > 0) {
      setCanvasPlants(prev => [...prev, ...newPlants]);
      setSelectedCanvasIds(new Set(newPlants.map((p: CanvasPlant) => p.id)));
    }
  }

  function alignSelected(axis: 'left' | 'center-h' | 'right' | 'top' | 'center-v' | 'bottom' | 'distribute-h' | 'distribute-v') {
    const plants = canvasPlants.filter(cp => selectedCanvasIds.has(cp.id));
    if (plants.length < 2) return;
    let updates: Array<{ id: number; pos_x: number; pos_y: number }> = [];
    if (axis === 'left') {
      const minX = Math.min(...plants.map(p => p.pos_x - p.radius_ft));
      updates = plants.map(p => ({ id: p.id, pos_x: minX + p.radius_ft, pos_y: p.pos_y }));
    } else if (axis === 'center-h') {
      const cx = (Math.min(...plants.map(p => p.pos_x)) + Math.max(...plants.map(p => p.pos_x))) / 2;
      updates = plants.map(p => ({ id: p.id, pos_x: cx, pos_y: p.pos_y }));
    } else if (axis === 'right') {
      const maxX = Math.max(...plants.map(p => p.pos_x + p.radius_ft));
      updates = plants.map(p => ({ id: p.id, pos_x: maxX - p.radius_ft, pos_y: p.pos_y }));
    } else if (axis === 'top') {
      const minY = Math.min(...plants.map(p => p.pos_y - p.radius_ft));
      updates = plants.map(p => ({ id: p.id, pos_x: p.pos_x, pos_y: minY + p.radius_ft }));
    } else if (axis === 'center-v') {
      const cy = (Math.min(...plants.map(p => p.pos_y)) + Math.max(...plants.map(p => p.pos_y))) / 2;
      updates = plants.map(p => ({ id: p.id, pos_x: p.pos_x, pos_y: cy }));
    } else if (axis === 'bottom') {
      const maxY = Math.max(...plants.map(p => p.pos_y + p.radius_ft));
      updates = plants.map(p => ({ id: p.id, pos_x: p.pos_x, pos_y: maxY - p.radius_ft }));
    } else if (axis === 'distribute-h') {
      const sorted = [...plants].sort((a, b) => a.pos_x - b.pos_x);
      const step = (sorted[sorted.length - 1].pos_x - sorted[0].pos_x) / (sorted.length - 1);
      updates = sorted.map((p, i) => ({ id: p.id, pos_x: sorted[0].pos_x + i * step, pos_y: p.pos_y }));
    } else if (axis === 'distribute-v') {
      const sorted = [...plants].sort((a, b) => a.pos_y - b.pos_y);
      const step = (sorted[sorted.length - 1].pos_y - sorted[0].pos_y) / (sorted.length - 1);
      updates = sorted.map((p, i) => ({ id: p.id, pos_x: p.pos_x, pos_y: sorted[0].pos_y + i * step }));
    }
    setCanvasPlants(prev => prev.map(c => { const u = updates.find(u => u.id === c.id); return u ? { ...c, pos_x: u.pos_x, pos_y: u.pos_y } : c; }));
    Promise.all(updates.map(u => api('POST', `/api/canvas-plants/${u.id}/position`, { x: u.pos_x, y: u.pos_y })));
  }

  // ── Lasso drag-select on bare canvas ─────────────────────────────────────────
  function handleCanvasPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (activeTool || e.button !== 0) return;
    const target = e.target as HTMLElement;
    if (target.closest('.canvas-plant-circle') || target.closest('.canvas-bed')) return;
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;
    const rect = canvasEl.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;
    lassoStartRef.current = { x, y };
    setLassoRect({ x1: x, y1: y, x2: x, y2: y });
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  function handleCanvasPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!lassoStartRef.current) return;
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;
    const rect = canvasEl.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;
    setLassoRect({ x1: lassoStartRef.current.x, y1: lassoStartRef.current.y, x2: x, y2: y });
  }

  function handleCanvasPointerUp() {
    if (!lassoStartRef.current || !lassoRect) { lassoStartRef.current = null; return; }
    const dragged = Math.abs(lassoRect.x2 - lassoRect.x1) > 5 / zoom || Math.abs(lassoRect.y2 - lassoRect.y1) > 5 / zoom;
    if (dragged) {
      const minX = Math.min(lassoRect.x1, lassoRect.x2);
      const maxX = Math.max(lassoRect.x1, lassoRect.x2);
      const minY = Math.min(lassoRect.y1, lassoRect.y2);
      const maxY = Math.max(lassoRect.y1, lassoRect.y2);
      const inside = canvasPlants.filter(cp => cp.pos_x >= minX && cp.pos_x <= maxX && cp.pos_y >= minY && cp.pos_y <= maxY);
      setSelectedCanvasIds(prev => { const next = new Set(prev); inside.forEach(cp => next.add(cp.id)); return next; });
    } else {
      setSelectedCanvasIds(new Set());
      setContextMenu(null);
    }
    lassoStartRef.current = null;
    setLassoRect(null);
  }

  function handleCanvasContextMenu(e: React.MouseEvent<HTMLDivElement>) {
    e.preventDefault();
    const target = e.target as HTMLElement;
    if (target.closest('.canvas-plant-circle') || target.closest('.canvas-bed')) return;
    setContextMenu({ x: e.clientX, y: e.clientY, plantId: null });
  }

  // Pointer events for canvas plant drag/resize
  function handleCpPointerDown(e: React.PointerEvent, cp: CanvasPlant, mode: 'move' | 'resize') {
    e.stopPropagation(); e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const diam = cp.radius_ft * PX * 2;
    const leftPx = cp.pos_x * PX - cp.radius_ft * PX;
    const topPx = cp.pos_y * PX - cp.radius_ft * PX;
    let groupStart: Array<{ id: number; left: number; top: number }> | undefined;
    if (mode === 'move' && selectedCanvasIds.has(cp.id)) {
      groupStart = canvasPlants
        .filter(c => selectedCanvasIds.has(c.id) && c.id !== cp.id)
        .map(c => ({ id: c.id, left: c.pos_x * PX - c.radius_ft * PX, top: c.pos_y * PX - c.radius_ft * PX }));
    }
    cpDragRef.current = { cpId: cp.id, mode, startX: e.clientX, startY: e.clientY, startLeft: leftPx, startTop: topPx, startDiam: diam, groupStart };
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
      if (ref.groupStart) {
        for (const g of ref.groupStart) {
          const el2 = document.getElementById(`cp-${g.id}`);
          if (el2) { el2.style.left = `${Math.max(0, g.left + dx)}px`; el2.style.top = `${Math.max(0, g.top + dy)}px`; }
        }
      }
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
      const oldX = cp.pos_x, oldY = cp.pos_y;
      const dxFt = newX - oldX;
      const dyFt = newY - oldY;
      // Skip history if plant didn't actually move
      if (Math.abs(dxFt) < 0.01 && Math.abs(dyFt) < 0.01) return;
      await api('POST', `/api/canvas-plants/${cp.id}/position`, { x: newX, y: newY });
      // Compute and persist group updates
      const groupUpdates = (ref.groupStart ?? []).map(g => {
        const gcp = canvasPlants.find(c => c.id === g.id);
        return gcp ? { id: g.id, newX: gcp.pos_x + dxFt, newY: gcp.pos_y + dyFt } : null;
      }).filter(Boolean) as Array<{ id: number; newX: number; newY: number }>;
      setCanvasPlants(prev => {
        let next = prev.map(c => c.id === cp.id ? { ...c, pos_x: newX, pos_y: newY } : c);
        for (const g of groupUpdates) next = next.map(c => c.id === g.id ? { ...c, pos_x: g.newX, pos_y: g.newY } : c);
        return next;
      });
      if (groupUpdates.length > 0) {
        await Promise.all(groupUpdates.map(g => api('POST', `/api/canvas-plants/${g.id}/position`, { x: g.newX, y: g.newY })));
      }
      pushHistory({
        undo: async () => {
          await api('POST', `/api/canvas-plants/${cp.id}/position`, { x: oldX, y: oldY });
          setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, pos_x: oldX, pos_y: oldY } : c));
        },
        redo: async () => {
          await api('POST', `/api/canvas-plants/${cp.id}/position`, { x: newX, y: newY });
          setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, pos_x: newX, pos_y: newY } : c));
        },
      });
    } else {
      const newRadius = newDiam / 2 / PX;
      const oldRadius = cp.radius_ft;
      if (Math.abs(newRadius - oldRadius) < 0.01) return;
      await api('POST', `/api/canvas-plants/${cp.id}/radius`, { radius_ft: newRadius });
      setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, radius_ft: newRadius } : c));
      pushHistory({
        undo: async () => {
          await api('POST', `/api/canvas-plants/${cp.id}/radius`, { radius_ft: oldRadius });
          setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, radius_ft: oldRadius } : c));
        },
        redo: async () => {
          await api('POST', `/api/canvas-plants/${cp.id}/radius`, { radius_ft: newRadius });
          setCanvasPlants(prev => prev.map(c => c.id === cp.id ? { ...c, radius_ft: newRadius } : c));
        },
      });
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

  // ── Group info panel ──────────────────────────────────────────────────────────
  async function showGroupInfo(group: GardenPlant[]) {
    setGroupInfoPlants(group);
    setCarePanel(null);
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

  function deactivateDrawTool() { setActiveTool(null); }

  function selectDrawTool(tool: string) {
    if (activeTool === tool) { deactivateDrawTool(); return; }
    setActiveTool(tool);
  }

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      if (e.key === 'Escape') {
        if (activeTool) deactivateDrawTool();
        if (careToolType) setCareToolType(null);
        setSelectedCanvasIds(new Set());
        setContextMenu(null);
      }
      if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        if (historyIdx.current >= 0) {
          history.current[historyIdx.current].undo();
          historyIdx.current--;
        }
      }
      if (e.ctrlKey && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) {
        e.preventDefault();
        if (historyIdx.current < history.current.length - 1) {
          historyIdx.current++;
          history.current[historyIdx.current].redo();
        }
      }
      if (e.ctrlKey && e.key === 'a' && !typing) {
        e.preventDefault();
        setSelectedCanvasIds(new Set(canvasPlants.map(cp => cp.id)));
      }
      if (e.ctrlKey && e.key === 'd' && !typing) {
        e.preventDefault();
        handleDuplicateSelected();
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && !typing) {
        if (selectedCanvasIds.size > 0) { e.preventDefault(); handleBulkDeleteSelected(); }
      }
      // Zoom hotkeys — only when not typing in an input
      if (!typing && !e.ctrlKey && !e.altKey) {
        if (e.key === '+' || e.key === '=') setZoom(prev => Math.min(2, Math.round((prev + 0.1) * 20) / 20));
        if (e.key === '-') setZoom(prev => Math.max(0.3, Math.round((prev - 0.1) * 20) / 20));
        if (e.key === '0') setZoom(1);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeTool, careToolType, selectedCanvasIds, canvasPlants]);

  // Dismiss context menu on outside click
  useEffect(() => {
    if (!contextMenu) return;
    function onDown() { setContextMenu(null); }
    window.addEventListener('pointerdown', onDown);
    return () => window.removeEventListener('pointerdown', onDown);
  }, [!!contextMenu]);

  if (!gardenId && gardens && gardens.length === 0) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1>Garden Planner</h1>
        <p className="muted">No gardens yet. <Link to="/gardens">Create a garden first.</Link></p>
      </div>
    );
  }

  const plannerCtxValue = {
    gardenId, garden, gardens,
    canvasBeds, setCanvasBeds,
    paletteBeds, setPaletteBeds,
    canvasPlants, setCanvasPlants,
    gardenPlants, setGardenPlants,
    selectedBed, setSelectedBed,
    carePanel, setCarePanel,
    rightPanelOpen, setRightPanelOpen,
    rightPanelTab, setRightPanelTab,
    groupInfoPlants, setGroupInfoPlants,
    libInfo, setLibInfo,
    libEditMode, setLibEditMode,
    libImageMode, setLibImageMode,
    highlightLibId, setHighlightLibId,
    weather,
    tasks, setTasks,
    taskForm, setTaskForm,
    taskSaved, setTaskSaved,
    loadPanelData,
    handleAddTask,
    showLibInfo,
    showGroupInfo,
  };

  return (
  <PlannerCtx.Provider value={plannerCtxValue}>
    <div className="planner-layout" style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }}>

      {/* ── Left Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="planner-sidebar" style={{ width: sidebarWidth, flexShrink: 0, overflowY: 'auto', borderRight: '1px solid #d0e0c8', padding: '0.75rem', background: '#f8fbf7', display: 'flex', flexDirection: 'column', gap: '0.75rem', position: 'relative' }}>
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
                await apiFetch(`/api/gardens/${gardenId}/upload-background`, { method: 'POST', body: fd });
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
        <div style={{ fontSize: '0.8rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
            <span style={{ color: '#7a907a' }}>Zoom</span>
            <span style={{ color: '#3a5c37', fontWeight: 600, fontSize: '0.75rem' }}>{zoom.toFixed(2)}×</span>
          </div>
          <input type="range" min="0.3" max="2" step="0.05" value={zoom}
            style={{ width: '100%', accentColor: '#3a6b35' }}
            onChange={e => setZoom(parseFloat(e.target.value))} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: '#9ab49a' }}>
            <span>0.3×</span><span>1×</span><span>2×</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem' }}>
            <input type="checkbox" id="scrollToZoom" checked={scrollToZoom}
              onChange={e => { setScrollToZoom(e.target.checked); localStorage.setItem('plannerScrollToZoom', String(e.target.checked)); }}
              style={{ cursor: 'pointer', accentColor: '#3a6b35', width: 12, height: 12 }} />
            <label htmlFor="scrollToZoom" style={{ fontSize: '0.68rem', color: '#7a907a', cursor: 'pointer', userSelect: 'none' }}>
              Scroll to zoom {scrollToZoom ? '' : '(Ctrl+scroll)'}
            </label>
          </div>
          <div style={{ fontSize: '0.67rem', color: '#b0c4b0', marginTop: '0.1rem' }}>+/− keys, 0 to reset</div>
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
        <CareToolsSection
          careToolType={careToolType} setCareToolType={setCareToolType}
          waterAmount={waterAmount} setWaterAmount={setWaterAmount}
          fertType={fertType} setFertType={setFertType}
          fertNpk={fertNpk} setFertNpk={setFertNpk}
        />

        {/* Draw toolbar */}
        <DrawToolsSection
          activeTool={activeTool} activeObjectType={activeObjectType}
          strokeColor={strokeColor} fillColor={fillColor}
          noFill={noFill} strokeWidth={strokeWidth} dashArray={dashArray}
          annShapesCount={annShapes.length}
          setActiveTool={setActiveTool} setActiveObjectType={setActiveObjectType}
          setStrokeColor={setStrokeColor} setFillColor={setFillColor}
          setNoFill={setNoFill} setStrokeWidth={setStrokeWidth} setDashArray={setDashArray}
          selectDrawTool={selectDrawTool} deactivateDrawTool={deactivateDrawTool}
          onClearShapes={() => { setAnnShapes([]); api('POST', `/api/gardens/${gardenId}/annotations`, { shapes: [] }); }}
        />

        {/* Beds */}
        <BedList
          canvasBeds={canvasBeds} paletteBeds={paletteBeds}
          selectedBed={selectedBed} addBedForm={addBedForm}
          rightPanelOpen={rightPanelOpen}
          onSelectBed={b => { setSelectedBed(b); if (!rightPanelOpen) { setRightPanelOpen(true); localStorage.setItem('plannerRightPanel', 'open'); } }}
          onDeleteBed={handleDeleteBed}
          onPaletteBedDragStart={handlePaletteBedDragStart}
          onAddBed={handleAddBed}
          setAddBedForm={setAddBedForm}
        />

        {/* Plant search */}
        <PlantSearchPanel
          gardenId={gardenId}
          gardenPlants={gardenPlants}
          canvasPlants={canvasPlants}
          selectedCanvasIds={selectedCanvasIds}
          selectedPlant={selectedPlant}
          setSelectedPlant={setSelectedPlant}
          showGroupInfo={showGroupInfo}
          showLibInfo={showLibInfo}
          onAddToGarden={handleAddToGarden}
          onToggleByPlantId={toggleByPlantId}
        />
        {/* Resize handle */}
        <div onMouseDown={handleSidebarResize}
          style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 5, cursor: 'col-resize', zIndex: 20, background: 'transparent' }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(58,107,53,0.25)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')} />
      </aside>

      {/* ── Canvas ───────────────────────────────────────────────────────────── */}
      <div ref={canvasWrapperRef} style={{ flex: 1, overflow: 'auto', position: 'relative', backgroundColor: canvasBgColor, backgroundImage: 'radial-gradient(circle, rgba(80,120,80,0.45) 1.5px, transparent 1.5px)', backgroundSize: `${PX * zoom}px ${PX * zoom}px` }}>
        {/* ── View controls bar ──────────────────────────────────────────────── */}
        <div style={{ position: 'sticky', top: 0, zIndex: 11, background: '#e8f2e5', borderBottom: '1px solid #b8d4b0', fontSize: '0.78rem' }}>
          <div style={{ padding: '0.25rem 0.75rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#3a5c37' }}>
              <span style={{ fontWeight: 500 }}>Icon size:</span>
              <input type="range" min="0.5" max="3" step="0.25" value={iconScale}
                style={{ width: 80, accentColor: '#3a6b35' }}
                onChange={e => setIconScale(parseFloat(e.target.value))} />
              <span style={{ color: '#7a907a', minWidth: 28 }}>{iconScale.toFixed(2)}×</span>
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ color: '#3a5c37', fontWeight: 500 }}>Labels:</span>
              {(['hover', 'always'] as const).map(m => (
                <button key={m} onClick={() => setLabelMode(m)}
                  style={{ fontSize: '0.72rem', padding: '0.1rem 0.4rem', border: '1px solid #3a6b35', borderRadius: 3, cursor: 'pointer', background: labelMode === m ? '#3a6b35' : 'transparent', color: labelMode === m ? '#fff' : '#3a6b35' }}>
                  {m === 'hover' ? 'Hover' : 'Always'}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ color: '#3a5c37', fontWeight: 500 }}>Group by:</span>
              {([{ mode: 'none', label: 'Off' }, { mode: 'species', label: 'Species' }, { mode: 'row', label: 'Row' }] as const).map(({ mode, label }) => (
                <button key={mode}
                  onClick={() => { setGroupMode(mode); if (mode === 'none') setHighlightIds(new Set()); }}
                  style={{ fontSize: '0.72rem', padding: '0.1rem 0.4rem', border: '1px solid #3a6b35', borderRadius: 3, cursor: 'pointer', background: groupMode === mode ? '#3a6b35' : 'transparent', color: groupMode === mode ? '#fff' : '#3a6b35' }}>
                  {label}
                </button>
              ))}
              {groupMode !== 'none' && (
                <span style={{ color: '#b06010', fontSize: '0.68rem' }}>(drag/care disabled)</span>
              )}
            </div>
          </div>

          {/* ── Selection toolbar (shown when plants are selected) ── */}
          {selectedCanvasIds.size > 0 && (
            <div style={{ padding: '0.25rem 0.75rem', borderTop: '1px solid #b8d4b0', background: '#d4edcc', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600, color: '#2d5a1b', fontSize: '0.8rem' }}>{selectedCanvasIds.size} plant{selectedCanvasIds.size > 1 ? 's' : ''} selected</span>
              <span style={{ color: '#9ab49a', fontSize: '0.7rem' }}>Ctrl+click to add/remove · Drag to move all</span>
              {selectedCanvasIds.size >= 2 && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                  <span style={{ color: '#3a5c37', fontSize: '0.72rem', fontWeight: 500 }}>Align:</span>
                  {([
                    { k: 'left', t: '⫿ Left' }, { k: 'center-h', t: '⊟ H-center' }, { k: 'right', t: '⫾ Right' },
                    { k: 'top', t: '⊤ Top' }, { k: 'center-v', t: '⊞ V-center' }, { k: 'bottom', t: '⊥ Bottom' },
                    { k: 'distribute-h', t: '↔ Dist-H' }, { k: 'distribute-v', t: '↕ Dist-V' },
                  ] as const).map(({ k, t }) => (
                    <button key={k} title={t} onClick={() => alignSelected(k)}
                      style={{ fontSize: '0.68rem', padding: '0.1rem 0.35rem', border: '1px solid #3a6b35', borderRadius: 3, cursor: 'pointer', background: 'transparent', color: '#3a6b35', whiteSpace: 'nowrap' }}>
                      {t}
                    </button>
                  ))}
                </span>
              )}
              <div style={{ display: 'flex', gap: '0.3rem', marginLeft: 'auto' }}>
                <button onClick={handleDuplicateSelected} title="Ctrl+D" style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', border: '1px solid #3a6b35', borderRadius: 3, cursor: 'pointer', background: '#3a6b35', color: '#fff' }}>⎘ Duplicate</button>
                <button onClick={async () => {
                  const today = new Date().toISOString().split('T')[0];
                  const plantIds = canvasPlants.filter(cp => selectedCanvasIds.has(cp.id) && cp.plant_id).map(cp => cp.plant_id!);
                  if (plantIds.length) await api('POST', '/api/plants/bulk-care', { ids: plantIds, last_watered: today, watering_amount: waterAmount });
                }} style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', border: '1px solid #5a9e54', borderRadius: 3, cursor: 'pointer', background: '#5a9e54', color: '#fff' }}>💧 Water</button>
                <button onClick={handleBulkDeleteSelected} title="Delete" style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', border: '1px solid #b84040', borderRadius: 3, cursor: 'pointer', background: '#b84040', color: '#fff' }}>🗑 Delete</button>
                <button onClick={() => setSelectedCanvasIds(new Set())} style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', border: '1px solid #888', borderRadius: 3, cursor: 'pointer', background: 'transparent', color: '#555' }}>✕ Clear</button>
              </div>
            </div>
          )}
        </div>
        {selectedPlant && (
          <div style={{ position: 'sticky', top: 0, zIndex: 10, background: '#d4edcc', padding: '0.3rem 0.75rem', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #a8d4a0', flexWrap: 'wrap' }}>
            <strong>Selected:</strong> {selectedPlant.name}
            <span style={{ color: '#7a907a' }}>— drag to canvas or click a bed cell</span>
            <div style={{ display: 'flex', gap: '0.2rem', marginLeft: '0.25rem' }}>
              {([
                { mode: 'single' as PlantMode, label: '1×1',    title: 'Single plant per click' },
                { mode: 'block'  as PlantMode, label: '⊞ Block', title: 'Fill 1 ft tile with plants at spacing' },
                { mode: 'row'    as PlantMode, label: '↔ Row',   title: 'Fill entire bed row at spacing' },
                { mode: 'col'    as PlantMode, label: '↕ Col',   title: 'Fill entire bed column at spacing' },
              ]).map(({ mode, label, title }) => (
                <button key={mode} title={title}
                  style={{ fontSize: '0.72rem', padding: '0.1rem 0.35rem', cursor: 'pointer', border: '1px solid #3a6b35', borderRadius: 3, background: plantMode === mode ? '#3a6b35' : 'transparent', color: plantMode === mode ? '#fff' : '#3a6b35' }}
                  onClick={() => setPlantMode(mode)}>
                  {label}
                </button>
              ))}
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.72rem', color: '#3a6b35', cursor: 'pointer', userSelect: 'none' }}>
              <input type="checkbox" checked={allowOverlap}
                onChange={e => { setAllowOverlap(e.target.checked); localStorage.setItem('plannerAllowOverlap', String(e.target.checked)); }}
                style={{ cursor: 'pointer', accentColor: '#3a6b35' }} />
              Allow overlap
            </label>
            <button className="btn-small" style={{ marginLeft: 'auto' }} onClick={() => { setSelectedPlant(null); setPlantMode('single'); }}>✕ Deselect</button>
          </div>
        )}
        <div
          id="planner-canvas"
          ref={canvasRef}
          style={{ position: 'relative', minWidth: '1200px', minHeight: '900px', transform: `scale(${zoom})`, transformOrigin: 'top left', width: `${100 / zoom}%`, height: `${900 / zoom}px`, backgroundImage: garden?.background_image ? `url(/static/garden_backgrounds/${garden.background_image})` : undefined, backgroundSize: garden?.background_image ? 'cover' : undefined, backgroundRepeat: garden?.background_image ? 'no-repeat' : undefined, cursor: careToolType === 'water' ? CURSOR_WATER : careToolType === 'fertilize' ? CURSOR_FERTILIZE : careToolType === 'weed' ? CURSOR_WEED : lassoRect ? 'crosshair' : undefined, ...patternStyle(canvasBgPattern) }}
          onDragOver={e => { handleCanvasDragOver(e); if (selectedPlant) e.preventDefault(); }}
          onDrop={e => {
            if (dragBedRef.current) { handleCanvasDropBed(e); return; }
            if (selectedPlant) handleCanvasDrop(e);
          }}
          onPointerDown={handleCanvasPointerDown}
          onPointerMove={handleCanvasPointerMove}
          onPointerUp={handleCanvasPointerUp}
          onContextMenu={handleCanvasContextMenu}
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
                     setSelectedBed(bed);
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
                plantMode={plantMode}
                allowOverlap={allowOverlap}
              />
            </div>
          ))}

          {/* Canvas plant circles */}
          {groupMode === 'none'
            ? canvasPlants.map(cp => (
                <CanvasPlantCircle key={cp.id} cp={cp}
                  iconScale={iconScale} labelMode={labelMode}
                  groupCount={1} isGrouped={false}
                  careToolType={careToolType} careToolFlash={careToolFlash}
                  waterAmount={waterAmount}
                  highlightLibId={highlightLibId} highlightIds={highlightIds}
                  isSelected={selectedCanvasIds.has(cp.id)}
                  onPointerDown={(e, mode) => handleCpPointerDown(e, cp, mode)}
                  onPointerMove={e => handleCpPointerMove(e, cp)}
                  onPointerUp={e => handleCpPointerUp(e, cp)}
                  onClick={e => handleCanvasPlantClick(cp, e)}
                  onDelete={() => handleDeleteCanvasPlant(cp)}
                  onToggleSelect={() => toggleSelectId(cp.id)}
                  onContextMenu={e => setContextMenu({ x: e.clientX, y: e.clientY, plantId: cp.id })}
                />
              ))
            : computeGroups(canvasPlants, groupMode).map(group => (
                <CanvasPlantCircle key={`group-${group.ids.join('-')}`}
                  cp={group.representative}
                  iconScale={iconScale} labelMode={labelMode}
                  groupCount={group.count} isGrouped={true}
                  careToolType={null} careToolFlash={null}
                  waterAmount={waterAmount}
                  highlightLibId={highlightLibId} highlightIds={highlightIds}
                  isSelected={false}
                  onPointerDown={() => {}} onPointerMove={() => {}} onPointerUp={() => {}}
                  onClick={() => handleGroupClick(group)}
                  onDelete={() => handleDeleteGroup(group.ids)}
                  onToggleSelect={() => {}}
                  onContextMenu={() => {}}
                />
              ))
          }
          {/* ── SVG annotation overlay ────────────────────────────────────────── */}
          <AnnotationOverlay
            activeTool={activeTool} activeObjectType={activeObjectType}
            strokeColor={strokeColor} fillColor={fillColor}
            noFill={noFill} strokeWidth={strokeWidth} dashArray={dashArray}
            zoom={zoom} gardenId={gardenId}
            annShapes={annShapes}
            onShapesChange={setAnnShapes}
          />

          {/* ── Lasso selection rectangle ─────────────────────────────────────── */}
          {lassoRect && (
            <div style={{
              position: 'absolute',
              left: Math.min(lassoRect.x1, lassoRect.x2),
              top: Math.min(lassoRect.y1, lassoRect.y2),
              width: Math.abs(lassoRect.x2 - lassoRect.x1),
              height: Math.abs(lassoRect.y2 - lassoRect.y1),
              border: '1.5px dashed #4CAF50',
              background: 'rgba(76,175,80,0.08)',
              pointerEvents: 'none',
              zIndex: 12,
            }} />
          )}
        </div>
      </div>

      {/* ── Right Panel toggle ────────────────────────────────────────────────── */}
      <button
        id="right-panel-toggle"
        style={{ position: 'fixed', right: rightPanelOpen ? rightPanelWidth + 4 : 0, top: '50%', transform: 'translateY(-50%)', zIndex: 20, background: '#3a5c37', color: '#fff', border: 'none', borderRadius: '4px 0 0 4px', padding: '0.75rem 0.25rem', cursor: 'pointer', writingMode: 'vertical-lr', fontSize: '0.75rem', transition: 'right 0.2s' }}
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
          right: rightPanelOpen ? rightPanelWidth + 16 : '1rem',
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
          right: rightPanelOpen ? rightPanelWidth + 16 : '1rem',
          width: 320, zIndex: 30,
          boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
          borderRadius: 8, overflow: 'hidden',
          transition: 'right 0.2s',
        }}>
          <ChatWidget gardenId={gardenId || undefined} gardenName={garden?.name} zone={garden?.usda_zone ?? undefined} />
        </div>
      )}

      {rightPanelOpen && (
        <aside className="planner-right-panel" style={{ width: rightPanelWidth, flexShrink: 0, overflowY: 'auto', borderLeft: '1px solid #d0e0c8', background: '#f8fbf7', display: 'flex', flexDirection: 'column', position: 'relative' }}>
          {/* Drag-to-resize handle */}
          <div
            style={{ position: 'absolute', left: 0, top: 0, width: 5, height: '100%', cursor: 'col-resize', zIndex: 10 }}
            onMouseDown={e => {
              e.preventDefault();
              const startX = e.clientX;
              const startWidth = rightPanelWidth;
              function onMove(ev: MouseEvent) {
                const newWidth = Math.min(600, Math.max(200, startWidth + (startX - ev.clientX)));
                setRightPanelWidth(newWidth);
              }
              function onUp(ev: MouseEvent) {
                const newWidth = Math.min(600, Math.max(200, startWidth + (startX - ev.clientX)));
                localStorage.setItem('plannerRightPanelWidth', String(newWidth));
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
              }
              document.addEventListener('mousemove', onMove);
              document.addEventListener('mouseup', onUp);
            }}
          />

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
          {rightPanelTab === 'info' && <InfoTab />}


          {/* ── Timeline tab ── */}
          {rightPanelTab === 'timeline' && (
            <TimelineTab
              gardenPlants={gardenPlants}
              lastFrostDate={garden?.last_frost_date}
              firstFrostDate={garden?.first_frost_date}
            />
          )}

          {/* ── Calendar tab ── */}
          {rightPanelTab === 'calendar' && (
            <CalendarTab
              tasks={tasks} gardenId={gardenId}
              onAddTask={handleAddTask}
              taskForm={taskForm} setTaskForm={setTaskForm}
              taskSaved={taskSaved}
            />
          )}

          </div>
        </aside>
      )}

      {/* ── Help Modal ──────────────────────────────────────────────────────── */}
      {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}

      {/* ── Context menu ────────────────────────────────────────────────────── */}
      {contextMenu && (() => {
        const cp = contextMenu.plantId != null ? canvasPlants.find(c => c.id === contextMenu.plantId) : null;
        const multiSel = selectedCanvasIds.size > 1 && contextMenu.plantId != null && selectedCanvasIds.has(contextMenu.plantId);
        const btnStyle: React.CSSProperties = { display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '0.4rem 0.75rem', cursor: 'pointer', fontSize: '0.82rem', color: '#1a3018' };
        return (
          <div
            onPointerDown={e => e.stopPropagation()}
            style={{ position: 'fixed', left: contextMenu.x, top: contextMenu.y, background: '#fff', border: '1px solid #c0d4be', borderRadius: 6, boxShadow: '0 4px 16px rgba(0,0,0,0.18)', zIndex: 9999, minWidth: 168, overflow: 'hidden', fontSize: '0.82rem' }}
          >
            {multiSel ? (
              <>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={() => { setContextMenu(null); handleDuplicateSelected(); }}>⎘ Duplicate {selectedCanvasIds.size} plants</button>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={async () => {
                    setContextMenu(null);
                    const today = new Date().toISOString().split('T')[0];
                    const ids = canvasPlants.filter(c => selectedCanvasIds.has(c.id) && c.plant_id).map(c => c.plant_id!);
                    if (ids.length) await api('POST', '/api/plants/bulk-care', { ids, last_watered: today, watering_amount: waterAmount });
                  }}>💧 Water {selectedCanvasIds.size} plants</button>
                <hr style={{ margin: '0.2rem 0', borderColor: '#e0ece0' }} />
                <button style={{ ...btnStyle, color: '#b84040' }} onMouseEnter={e => (e.currentTarget.style.background='#fff0f0')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={() => { setContextMenu(null); handleBulkDeleteSelected(); }}>🗑 Delete {selectedCanvasIds.size} plants</button>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={() => { setContextMenu(null); setSelectedCanvasIds(new Set()); }}>✕ Clear selection</button>
              </>
            ) : cp ? (
              <>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={() => { setContextMenu(null); handleCanvasPlantClick(cp); }}>ℹ Info / Care</button>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={async () => {
                    setContextMenu(null);
                    const r = await api('POST', `/api/gardens/${gardenId}/canvas-plants`, { library_id: cp.library_id, pos_x: cp.pos_x + 0.5, pos_y: cp.pos_y + 0.5 });
                    if (r.ok) setCanvasPlants(prev => [...prev, r.canvas_plant]);
                  }}>⎘ Duplicate</button>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={async () => {
                    setContextMenu(null);
                    if (!cp.plant_id) return;
                    const today = new Date().toISOString().split('T')[0];
                    await api('POST', `/api/plants/${cp.plant_id}/care`, { last_watered: today, watering_amount: waterAmount });
                    setCareToolFlash(cp.id); setTimeout(() => setCareToolFlash(null), 1200);
                  }}>💧 Water now</button>
                <hr style={{ margin: '0.2rem 0', borderColor: '#e0ece0' }} />
                <button style={{ ...btnStyle, color: '#b84040' }} onMouseEnter={e => (e.currentTarget.style.background='#fff0f0')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={() => { setContextMenu(null); handleDeleteCanvasPlant(cp); }}>🗑 Delete</button>
              </>
            ) : (
              <>
                <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                  onClick={() => { setContextMenu(null); setSelectedCanvasIds(new Set(canvasPlants.map(c => c.id))); }}>☐ Select all ({canvasPlants.length})</button>
                {selectedCanvasIds.size > 0 && (
                  <button style={btnStyle} onMouseEnter={e => (e.currentTarget.style.background='#f0f8ef')} onMouseLeave={e => (e.currentTarget.style.background='none')}
                    onClick={() => { setContextMenu(null); setSelectedCanvasIds(new Set()); }}>✕ Clear selection</button>
                )}
              </>
            )}
          </div>
        );
      })()}
    </div>
  </PlannerCtx.Provider>
  );
}
