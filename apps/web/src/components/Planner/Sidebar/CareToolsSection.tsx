import React from 'react';

interface Props {
  careToolType: 'water' | 'fertilize' | 'weed' | null;
  setCareToolType: React.Dispatch<React.SetStateAction<'water' | 'fertilize' | 'weed' | null>>;
  waterAmount: 'light' | 'moderate' | 'heavy';
  setWaterAmount: React.Dispatch<React.SetStateAction<'light' | 'moderate' | 'heavy'>>;
  fertType: string;
  setFertType: React.Dispatch<React.SetStateAction<string>>;
  fertNpk: string;
  setFertNpk: React.Dispatch<React.SetStateAction<string>>;
}

export default function CareToolsSection({
  careToolType, setCareToolType,
  waterAmount, setWaterAmount,
  fertType, setFertType,
  fertNpk, setFertNpk,
}: Props) {
  return (
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
  );
}
