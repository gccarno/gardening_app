import React, { useState, useRef } from 'react';
import { type Bed, type GridChip, type LibPlant, type GardenPlant, type PlantMode, PX_PER_IN, computePositions, plantSpan } from '../types';
import { plantImageUrl } from '../../utils/images';

interface Props {
  bed: Bed; chips: GridChip[]; tileIn: number;
  onCellClick: (bedId: number, cx: number, cy: number) => void;
  onChipRemove: (bedId: number, chip: GridChip) => void;
  onChipClick: (chip: GridChip) => void;
  dragPlant: LibPlant | GardenPlant | null;
  zoom: number;
  plantMode: PlantMode;
}

export default function BedGrid({
  bed, chips, tileIn, onCellClick, onChipRemove, onChipClick, dragPlant, zoom, plantMode,
}: Props) {
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

  const [hoverCells, setHoverCells] = useState<Set<string> | null>(null);
  const [hoverBadCells, setHoverBadCells] = useState<Set<string> | null>(null);

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

  function updateHover(cx: number, cy: number) {
    if (!dragPlant) return;
    const spacingIn  = (dragPlant as LibPlant | GardenPlant).spacing_in ?? 12;
    const bedWidthIn  = bed.width_ft * 12;
    const bedHeightIn = bed.height_ft * 12;
    const positions  = computePositions(plantMode, cx, cy, spacingIn, tileIn, bedWidthIn, bedHeightIn);
    const valid  = new Set<string>();
    const blocked = new Set<string>();
    for (const pos of positions) {
      const tcx = Math.floor(pos.grid_x / tileIn);
      const tcy = Math.floor(pos.grid_y / tileIn);
      const span = plantSpan(spacingIn, tileIn);
      let ok = true;
      for (let r = tcy; r < tcy + span && ok; r++)
        for (let c = tcx; c < tcx + span && ok; c++)
          if (occupied.has(`${c},${r}`)) ok = false;
      if (ok) valid.add(`${tcx},${tcy}`);
      else    blocked.add(`${tcx},${tcy}`);
    }
    setHoverCells(valid);
    setHoverBadCells(blocked);
  }

  function clearHover() {
    setHoverCells(null);
    setHoverBadCells(null);
  }

  function tryPaint(cx: number, cy: number) {
    if (!dragPlant) return;
    if (plantMode === 'row' || plantMode === 'col') return;
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
        updateHover(cx, cy);
      }}
      onDragLeave={() => clearHover()}
      onDrop={e => {
        e.preventDefault(); e.stopPropagation();
        if (!dragPlant || !hoverCells) { clearHover(); return; }
        const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
        const cx = Math.floor((e.clientX - rect.left) / zoom / tilePx);
        const cy = Math.floor((e.clientY - rect.top) / zoom / tilePx);
        if (hoverCells.size > 0) onCellClick(bed.id, cx, cy);
        clearHover();
      }}
      onMouseUp={() => { stopPainting(); clearHover(); }}
      onMouseLeave={() => { stopPainting(); clearHover(); }}
    >
      {Array.from({ length: rows }, (_, y) =>
        Array.from({ length: cols }, (_, x) => {
          const isOcc = occupied.has(`${x},${y}`) || pendingOcc.current.has(`${x},${y}`);
          const inHoverOk  = hoverCells?.has(`${x},${y}`);
          const inHoverBad = hoverBadCells?.has(`${x},${y}`);
          return (
            <div key={`${x},${y}`}
                 className={`grid-cell${isOcc ? ' cell-occupied' : ''}${inHoverOk ? ' cell-drop-target' : ''}${inHoverBad ? ' cell-drop-bad' : ''}`}
                 style={{ width: tilePx, height: tilePx }}
                 onMouseDown={e => {
                   if (!dragPlant) return;
                   e.preventDefault();
                   isPainting.current = true;
                   tryPaint(x, y);
                 }}
                 onMouseEnter={() => {
                   updateHover(x, y);
                   if (!isPainting.current || !dragPlant) return;
                   tryPaint(x, y);
                 }}
            />
          );
        })
      )}
      {chips.map(chip => {
        const chipPx = Math.round((chip.spacing_in || 12) * PX_PER_IN);
        const imgSrc = chip.image_filename ? plantImageUrl(chip.image_filename) : null;
        return (
          <div
            key={chip.id}
            className="grid-plant-chip"
            style={{ position: 'absolute', left: chip.grid_x * PX_PER_IN, top: chip.grid_y * PX_PER_IN, width: chipPx, height: chipPx }}
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
