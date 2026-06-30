import React, { useState } from 'react';
import { CanvasPlant, PX } from '../types';
import { plantImageUrl } from '../../../utils/images';

interface Props {
  cp: CanvasPlant;
  iconScale: number;
  labelMode: 'hover' | 'always';
  groupCount: number;
  isGrouped: boolean;
  careToolType: 'water' | 'fertilize' | 'weed' | null;
  careToolFlash: number | null;
  waterAmount: 'light' | 'moderate' | 'heavy';
  highlightLibId: number | null;
  highlightIds: Set<number>;
  isSelected: boolean;
  onPointerDown: (e: React.PointerEvent, mode: 'move' | 'resize') => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onClick: (e: React.MouseEvent) => void;
  onDelete: () => void;
  onToggleSelect: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

export default function CanvasPlantCircle({
  cp, iconScale, labelMode, groupCount, isGrouped,
  careToolType, careToolFlash, waterAmount,
  highlightLibId, highlightIds,
  isSelected,
  onPointerDown, onPointerMove, onPointerUp, onClick, onDelete,
  onToggleSelect, onContextMenu,
}: Props) {
  const [isHovered, setIsHovered] = useState(false);
  const scaledRadius = cp.radius_ft * iconScale;
  const diamPx = scaledRadius * PX * 2;
  const leftPx = cp.pos_x * PX - scaledRadius * PX;
  const topPx  = cp.pos_y * PX - scaledRadius * PX;
  const imgSrc = cp.custom_image
    ? `/static/canvas_plant_images/${cp.custom_image}`
    : (cp.ai_icon_url || cp.svg_icon_url || plantImageUrl(cp.image_filename));
  const isCareMode = careToolType === 'water' || careToolType === 'fertilize';
  const isHighlighted =
    (highlightLibId != null && cp.library_id === highlightLibId) ||
    (highlightIds.size > 0 && highlightIds.has(cp.id));

  let ringStyle: string | undefined;
  if (isSelected) ringStyle = '0 0 0 3px #4CAF50, 0 0 0 5px rgba(76,175,80,0.25)';
  else if (isHighlighted) ringStyle = '0 0 0 3px #f5a623';

  return (
    <div
      id={`cp-${cp.id}`}
      className="canvas-plant-circle"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'absolute', left: leftPx, top: topPx, width: diamPx, height: diamPx,
        borderRadius: '50%', background: imgSrc ? 'transparent' : (cp.color || '#5a9e54'),
        border: isSelected ? '2px solid #4CAF50' : '2px solid rgba(0,0,0,0.15)',
        overflow: 'visible',
        cursor: isCareMode ? 'cell' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', userSelect: 'none',
        boxShadow: ringStyle,
        outline: isGrouped ? '2px dashed rgba(58,92,55,0.5)' : undefined,
        outlineOffset: isGrouped ? 3 : undefined,
        transition: 'box-shadow 0.15s',
      }}
      onClick={e => {
        if (e.ctrlKey || e.metaKey) { e.stopPropagation(); onToggleSelect(); return; }
        onClick(e);
      }}
      onContextMenu={e => { e.preventDefault(); e.stopPropagation(); onContextMenu(e); }}
    >
      {imgSrc && (
        <div className="circle-bg" style={{ position: 'absolute', inset: 0, borderRadius: '50%', overflow: 'hidden' }}>
          <img src={imgSrc} alt={cp.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      )}

      {/* Selection checkmark */}
      {isSelected && (
        <div style={{
          position: 'absolute', top: -6, left: -6, width: 16, height: 16,
          background: '#4CAF50', borderRadius: '50%', border: '1.5px solid #fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, color: '#fff', fontWeight: 700, zIndex: 4, pointerEvents: 'none',
        }}>✓</div>
      )}

      {/* Floating tooltip — always appears on hover */}
      {isHovered && (
        <div style={{
          position: 'absolute', bottom: 'calc(100% + 6px)', left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(30,50,28,0.92)', color: '#fff',
          fontSize: '0.72rem', padding: '3px 7px', borderRadius: 4,
          whiteSpace: 'nowrap', pointerEvents: 'none', zIndex: 100,
          boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
        }}>
          {cp.name}
          {groupCount > 1 && <span style={{ color: '#a0e090', marginLeft: 4 }}>×{groupCount}</span>}
        </div>
      )}

      {/* Count badge for groups */}
      {groupCount > 1 && (
        <div style={{
          position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)',
          background: '#3a5c37', color: '#fff', fontSize: '0.65rem', fontWeight: 700,
          padding: '1px 5px', borderRadius: 8, border: '1.5px solid #fff',
          pointerEvents: 'none', zIndex: 3, whiteSpace: 'nowrap', lineHeight: '1.4',
        }}>
          ×{groupCount}
        </div>
      )}

      <span className="canvas-plant-label" style={{
        position: 'relative', fontSize: Math.max(9, Math.min(12, diamPx / 4)),
        color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,0.5)', textAlign: 'center',
        padding: '2px', pointerEvents: 'none', maxWidth: diamPx - 8,
        overflow: 'hidden', wordBreak: 'break-word',
        opacity: labelMode === 'always' ? 1 : (isHovered ? 1 : 0),
        transition: 'opacity 0.15s',
      }}>
        {cp.name}
      </span>

      {/* Care action flash overlay */}
      {careToolFlash === cp.id && (
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'rgba(255,255,255,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: Math.max(14, diamPx / 3), pointerEvents: 'none', zIndex: 3 }}>
          {careToolType === 'fertilize' ? '🌿' : waterAmount === 'light' ? '💧' : waterAmount === 'heavy' ? '💧💧💧' : '💧💧'}
        </div>
      )}

      {/* Move handle — hidden in group mode */}
      {!isGrouped && (
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', cursor: isCareMode ? 'cell' : 'move' }}
             onPointerDown={e => { if (isCareMode || e.ctrlKey || e.metaKey) return; onPointerDown(e, 'move'); }}
             onPointerMove={onPointerMove}
             onPointerUp={onPointerUp} />
      )}

      {/* Resize handle — hidden in group mode */}
      {!isGrouped && (
        <div className="canvas-plant-resize-handle"
             style={{ position: 'absolute', bottom: 2, right: 2, width: 12, height: 12, background: 'rgba(255,255,255,0.7)', border: '1px solid #888', borderRadius: '50%', cursor: 'ew-resize', zIndex: 1 }}
             title="Drag to resize"
             onPointerDown={e => { e.stopPropagation(); onPointerDown(e, 'resize'); }}
             onPointerMove={onPointerMove}
             onPointerUp={onPointerUp} />
      )}

      <button className="canvas-plant-delete-btn"
              style={{ position: 'absolute', top: -6, right: -6, width: 16, height: 16, background: '#b84040', color: '#fff', border: 'none', borderRadius: '50%', fontSize: '10px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}
              onClick={e => { e.stopPropagation(); onDelete(); }}>×</button>
    </div>
  );
}
