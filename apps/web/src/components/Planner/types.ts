// ── Constants ─────────────────────────────────────────────────────────────────
export const PX = 60; // px per foot at zoom=1
export const PX_PER_IN = PX / 12;
export const BED_HEADER_PX = 24; // height of the bed label bar in pixels

export const GARDEN_PALETTE = [
  '#2d5a27', '#4a7c3f', '#6aaa58', '#a8d5a2', '#c8e6c9',
  '#5d4037', '#795548', '#a1887f', '#d7ccc8', '#8d6e63',
  '#f9a825', '#fbc02d', '#fff176', '#f0e68c',
  '#b3e5fc', '#81d4fa', '#4fc3f7',
  '#ffffff', '#f5f5f5', '#9e9e9e', '#424242',
];

export const PATTERNS = [
  { key: 'grass',      label: '🌿 Grass' },
  { key: 'mulch',      label: '🍂 Mulch' },
  { key: 'wood_chips', label: '🪵 Wood' },
  { key: 'straw',      label: '🌾 Straw' },
  { key: 'dirt',       label: '🟫 Dirt' },
];

// SVG data URI cursors for care tools
export const CURSOR_WATER = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g fill='%2334aadc'><rect x='3' y='12' width='14' height='10' rx='2'/><rect x='17' y='10' width='8' height='4' rx='1'/><circle cx='7' cy='26' r='2'/><circle cx='13' cy='26' r='2'/><line x1='25' y1='6' x2='29' y2='12' stroke='%2334aadc' stroke-width='2' stroke-linecap='round'/></g></svg>") 28 10, crosshair`;
export const CURSOR_FERTILIZE = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><text y='26' font-size='26'>%F0%9F%92%A9</text></svg>") 16 16, crosshair`;
export const CURSOR_WEED = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g fill='%23888' stroke='%23555' stroke-width='1'><rect x='7' y='2' width='3' height='12' rx='1'/><rect x='14' y='2' width='3' height='14' rx='1'/><rect x='21' y='2' width='3' height='12' rx='1'/><rect x='13' y='14' width='5' height='14' rx='1'/></g></svg>") 15 2, crosshair`;

// ── Helpers ───────────────────────────────────────────────────────────────────
import React from 'react';

export function patternStyle(pattern: string | null | undefined): React.CSSProperties {
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

export function snap(value: number) { return Math.round(value / PX) * PX; }
export function plantSpan(spacingIn: number, tileIn: number) { const s = Math.round((spacingIn || 12) / tileIn); return Math.max(1, isNaN(s) ? 1 : s); }

export type PlantMode = 'single' | 'block' | 'row' | 'col';

export function computePositions(
  mode: PlantMode,
  cx: number, cy: number,
  spacingIn: number, tileIn: number,
  bedWidthIn: number, bedHeightIn: number
): Array<{ grid_x: number; grid_y: number }> {
  const ox = cx * tileIn, oy = cy * tileIn;
  if (mode === 'single') return [{ grid_x: ox, grid_y: oy }];
  const out: Array<{ grid_x: number; grid_y: number }> = [];
  if (mode === 'block') {
    for (let dy = 0; dy < tileIn; dy += spacingIn)
      for (let dx = 0; dx < tileIn; dx += spacingIn)
        if (ox + dx + spacingIn <= bedWidthIn && oy + dy + spacingIn <= bedHeightIn)
          out.push({ grid_x: ox + dx, grid_y: oy + dy });
  } else if (mode === 'row') {
    for (let x = 0; x + spacingIn <= bedWidthIn; x += spacingIn)
      out.push({ grid_x: x, grid_y: oy });
  } else if (mode === 'col') {
    for (let y = 0; y + spacingIn <= bedHeightIn; y += spacingIn)
      out.push({ grid_x: ox, grid_y: y });
  }
  return out;
}

// ── API helper ────────────────────────────────────────────────────────────────
export async function api(method: string, path: string, body?: unknown) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface Bed {
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
export interface GridChip {
  id: number; grid_x: number; grid_y: number;
  plant_name: string; image_filename?: string; spacing_in: number; stage?: string;
}
export interface CanvasPlant {
  id: number; name: string; pos_x: number; pos_y: number; radius_ft: number;
  color?: string; display_mode?: string; image_filename?: string; custom_image?: string;
  svg_icon_url?: string; ai_icon_url?: string; library_id?: number; plant_id?: number; spacing_in?: number;
  status?: string;
  last_watered?: string; watering_amount?: string;
  last_fertilized?: string; fertilizer_type?: string; fertilizer_npk?: string;
}
export interface LibPlant {
  id: number; name: string; type?: string; image_filename?: string; spacing_in?: number;
}
export interface GardenPlant {
  id: number; name: string; library_id?: number; image_filename?: string;
  spacing_in?: number; status?: string; notes?: string;
  planted_date?: string; transplant_date?: string; expected_harvest?: string;
  type?: string; days_to_harvest?: number; days_to_germination?: number;
  sow_indoor_weeks?: number; direct_sow_offset?: number;
  transplant_offset?: number; temp_max_f?: number;
  last_watered?: string; watering_amount?: string;
  last_fertilized?: string; fertilizer_type?: string; fertilizer_npk?: string;
}
export interface AnnotationShape {
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
export interface DrawState {
  tool: string; el: SVGElement;
  startX: number; startY: number;
  points?: [number, number][]; lastX?: number; lastY?: number; pathLen?: number;
}
export interface CareData {
  id: number; plant_id?: number; plant_name: string; scientific_name?: string;
  sunlight?: string; water?: string; spacing_in?: number; days_to_harvest?: number;
  planted_date?: string; transplant_date?: string; last_watered?: string;
  watering_amount?: string; last_fertilized?: string; fertilizer_type?: string; fertilizer_npk?: string;
  last_harvest?: string; health_notes?: string;
  stage?: string; plant_notes?: string; is_bed: boolean;
  library_id?: number;
}
export interface LibraryInfo {
  id: number; name: string; scientific_name?: string; type?: string;
  image_filename?: string; sunlight?: string; water?: string;
  spacing_in?: number; companion_plants?: string; growing_notes?: string;
  days_to_germination?: number; days_to_harvest?: number;
}
