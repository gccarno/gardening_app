import React from 'react';
import { CanvasPlant, PX } from '../types';
import { plantImageUrl } from '../../utils/images';

interface Props {
  cp: CanvasPlant;
  careToolType: 'water' | 'fertilize' | 'weed' | null;
  careToolFlash: number | null;
  waterAmount: 'light' | 'moderate' | 'heavy';
  highlightLibId: number | null;
  onPointerDown: (e: React.PointerEvent, mode: 'move' | 'resize') => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onClick: () => void;
  onDelete: () => void;
}

export default function CanvasPlantCircle({
  cp, careToolType, careToolFlash, waterAmount, highlightLibId,
  onPointerDown, onPointerMove, onPointerUp, onClick, onDelete,
}: Props) {
  const diamPx = cp.radius_ft * PX * 2;
  const leftPx = cp.pos_x * PX - cp.radius_ft * PX;
  const topPx  = cp.pos_y * PX - cp.radius_ft * PX;
  const imgSrc = cp.custom_image
    ? `/static/canvas_plant_images/${cp.custom_image}`
    : (cp.ai_icon_url || cp.svg_icon_url || plantImageUrl(cp.image_filename));
  const isCareMode = careToolType === 'water' || careToolType === 'fertilize';

  return (
    <div
      id={`cp-${cp.id}`}
      className="canvas-plant-circle"
      style={{
        position: 'absolute', left: leftPx, top: topPx, width: diamPx, height: diamPx,
        borderRadius: '50%', background: imgSrc ? 'transparent' : (cp.color || '#5a9e54'),
        border: '2px solid rgba(0,0,0,0.15)', overflow: 'visible',
        cursor: isCareMode ? 'cell' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', userSelect: 'none',
        boxShadow: highlightLibId != null && cp.library_id === highlightLibId ? '0 0 0 3px #f5a623' : undefined,
        transition: 'box-shadow 0.2s',
      }}
      onClick={onClick}
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
      {/* Move handle */}
      <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', cursor: isCareMode ? 'cell' : 'move' }}
           onPointerDown={e => { if (isCareMode) return; onPointerDown(e, 'move'); }}
           onPointerMove={onPointerMove}
           onPointerUp={onPointerUp} />
      {/* Resize handle */}
      <div className="canvas-plant-resize-handle"
           style={{ position: 'absolute', bottom: 2, right: 2, width: 12, height: 12, background: 'rgba(255,255,255,0.7)', border: '1px solid #888', borderRadius: '50%', cursor: 'ew-resize', zIndex: 1 }}
           title="Drag to resize"
           onPointerDown={e => { e.stopPropagation(); onPointerDown(e, 'resize'); }}
           onPointerMove={onPointerMove}
           onPointerUp={onPointerUp} />
      <button className="canvas-plant-delete-btn"
              style={{ position: 'absolute', top: -6, right: -6, width: 16, height: 16, background: '#b84040', color: '#fff', border: 'none', borderRadius: '50%', fontSize: '10px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}
              onClick={e => { e.stopPropagation(); onDelete(); }}>×</button>
    </div>
  );
}
