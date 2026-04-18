import React from 'react';

export default function HelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: '#fff', borderRadius: 8, padding: '1.5rem', maxWidth: 420, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)', position: 'relative', maxHeight: '80vh', overflowY: 'auto' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 10, right: 12, background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: '#7a907a', lineHeight: 1 }}>×</button>
        <div style={{ fontWeight: 700, fontSize: '1rem', color: '#3a5c37', marginBottom: '1rem' }}>Garden Planner Help</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem', fontSize: '0.82rem', color: '#3a5c37' }}>
          <div><strong>Placing beds</strong><br />Drag a bed from the sidebar onto the canvas. Placed beds can be dragged to reposition. Unplaced beds show a ⋮⋮ handle.</div>
          <div><strong>Planting on canvas (circles)</strong><br />Select a plant from Library Plants, then drag it onto the canvas. A coloured circle appears — drag to move, drag the bottom-right corner to resize.</div>
          <div><strong>Planting in a bed grid</strong><br />Select a plant, then click any empty grid cell inside a bed. Spacing determines how many cells the plant occupies.</div>
          <div><strong>Plant care &amp; dates</strong><br />Click a plant circle or grid chip to open the Info panel. Set Seeded, Transplanted, and harvest dates there — they appear on the Timeline.</div>
          <div><strong>Timeline tab</strong><br />Shows each unique plant as one row. Multiple instances of the same plant are merged and labelled with a count badge (×N).</div>
          <div><strong>Calendar tab</strong><br />Displays tasks for this garden by month. Use "+ Add Task" to schedule reminders.</div>
          <div><strong>Drawing tools</strong><br />Use Quick objects (Path, Fence, etc.) or the shape tools to annotate your garden. Style controls appear when a tool is active.</div>
          <div><strong>Add plant to list (no canvas)</strong><br />Click the <strong>+</strong> button next to any Library Plant to add it to "Plants in Garden" without placing it on the canvas. Useful for tracking plants not yet placed.</div>
          <div><strong>Canvas &amp; bed colours</strong><br />Use the Canvas colour swatch in the sidebar to change the background colour. Upload a background image with the 🖼 button. To change a bed's colour or image, select the bed and click "✎ Edit Bed" in the right panel.</div>
          <div><strong>Zoom</strong><br />Use the 0.5×–1.5× zoom buttons in the sidebar. The canvas size adjusts automatically.</div>
        </div>
      </div>
    </div>
  );
}
