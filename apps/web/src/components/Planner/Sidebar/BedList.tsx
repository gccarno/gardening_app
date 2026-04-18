import React from 'react';
import { Bed } from '../types';

interface Props {
  canvasBeds: Bed[];
  paletteBeds: Bed[];
  selectedBed: Bed | null;
  addBedForm: { name: string; width_ft: string; height_ft: string };
  rightPanelOpen: boolean;
  onSelectBed: (bed: Bed) => void;
  onDeleteBed: (bedId: number, name: string) => void;
  onPaletteBedDragStart: (e: React.DragEvent, bed: Bed) => void;
  onAddBed: (e: React.FormEvent) => void;
  setAddBedForm: React.Dispatch<React.SetStateAction<{ name: string; width_ft: string; height_ft: string }>>;
}

export default function BedList({
  canvasBeds, paletteBeds, selectedBed, addBedForm,
  onSelectBed, onDeleteBed, onPaletteBedDragStart, onAddBed, setAddBedForm,
}: Props) {
  return (
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
              onClick={() => onSelectBed(b)}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</span>
            <span style={{ color: '#9ab49a', fontSize: '0.7rem', flexShrink: 0 }}>{b.width_ft}×{b.height_ft}</span>
            <button title="Focus on canvas" style={{ background: 'none', border: 'none', color: '#3a6b35', cursor: 'pointer', fontSize: '0.8rem', padding: '0 0.1rem', flexShrink: 0 }}
              onClick={e => { e.stopPropagation(); const el = document.getElementById(`canvas-bed-${b.id}`); el?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>◎</button>
            <button className="palette-delete-btn" style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.9rem', padding: '0 0.1rem', flexShrink: 0 }}
                    onClick={e => { e.stopPropagation(); onDeleteBed(b.id, b.name); }}>×</button>
          </li>
        ))}
        {/* Unplaced beds */}
        {paletteBeds.map(b => (
          <li key={b.id}
              className={`palette-item palette-bed${selectedBed?.id === b.id ? ' active' : ''}`}
              draggable
              onDragStart={e => onPaletteBedDragStart(e, b)}
              style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.4rem', background: selectedBed?.id === b.id ? '#d4edcc' : '#f0f5ef', borderRadius: '4px', fontSize: '0.8rem', cursor: 'grab', opacity: 0.75 }}
              onClick={() => onSelectBed(b)}>
            <span style={{ fontSize: '0.65rem', color: '#9ab49a', flexShrink: 0 }} title="Drag to canvas">⋮⋮</span>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.name}</span>
            <span style={{ color: '#9ab49a', fontSize: '0.7rem', flexShrink: 0 }}>{b.width_ft}×{b.height_ft}</span>
            <button className="palette-delete-btn" style={{ background: 'none', border: 'none', color: '#b84040', cursor: 'pointer', fontSize: '0.9rem', padding: '0 0.1rem', flexShrink: 0 }}
                    onClick={e => { e.stopPropagation(); onDeleteBed(b.id, b.name); }}>×</button>
          </li>
        ))}
      </ul>
      <details style={{ marginTop: '0.4rem' }}>
        <summary style={{ fontSize: '0.8rem', color: '#3a6b35', cursor: 'pointer' }}>+ Add New Bed</summary>
        <form onSubmit={onAddBed} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.3rem', fontSize: '0.8rem' }}>
          <input type="text" placeholder="Name" value={addBedForm.name} onChange={e => setAddBedForm(f => ({ ...f, name: e.target.value }))} required style={{ font: 'inherit', fontSize: '0.8rem', padding: '0.25rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            <input type="number" placeholder="W(ft)" value={addBedForm.width_ft} onChange={e => setAddBedForm(f => ({ ...f, width_ft: e.target.value }))} style={{ font: 'inherit', fontSize: '0.8rem', padding: '0.25rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '50%' }} />
            <input type="number" placeholder="H(ft)" value={addBedForm.height_ft} onChange={e => setAddBedForm(f => ({ ...f, height_ft: e.target.value }))} style={{ font: 'inherit', fontSize: '0.8rem', padding: '0.25rem', border: '1px solid #c0d4be', borderRadius: '3px', width: '50%' }} />
          </div>
          <button type="submit" className="btn-small" style={{ fontSize: '0.78rem' }}>Add Bed</button>
        </form>
      </details>
    </div>
  );
}
