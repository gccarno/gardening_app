import React from 'react';
import { AnnotationShape } from '../types';

interface Props {
  activeTool: string | null;
  activeObjectType: string;
  strokeColor: string;
  fillColor: string;
  noFill: boolean;
  strokeWidth: number;
  dashArray: string;
  annShapesCount: number;
  setActiveTool: React.Dispatch<React.SetStateAction<string | null>>;
  setActiveObjectType: React.Dispatch<React.SetStateAction<string>>;
  setStrokeColor: React.Dispatch<React.SetStateAction<string>>;
  setFillColor: React.Dispatch<React.SetStateAction<string>>;
  setNoFill: React.Dispatch<React.SetStateAction<boolean>>;
  setStrokeWidth: React.Dispatch<React.SetStateAction<number>>;
  setDashArray: React.Dispatch<React.SetStateAction<string>>;
  selectDrawTool: (tool: string) => void;
  deactivateDrawTool: () => void;
  onClearShapes: () => void;
}

export default function DrawToolsSection({
  activeTool, activeObjectType,
  strokeColor, fillColor, noFill, strokeWidth, dashArray,
  annShapesCount,
  setActiveTool, setActiveObjectType,
  setStrokeColor, setFillColor, setNoFill, setStrokeWidth, setDashArray,
  selectDrawTool, deactivateDrawTool,
  onClearShapes,
}: Props) {
  return (
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
      {annShapesCount > 0 && (
        <button className="btn-small btn-link" style={{ fontSize: '0.72rem', marginTop: '0.2rem', color: '#b84040' }}
          onClick={() => { if (confirm('Clear all drawn shapes?')) onClearShapes(); }}>
          Clear all
        </button>
      )}
    </div>
  );
}
