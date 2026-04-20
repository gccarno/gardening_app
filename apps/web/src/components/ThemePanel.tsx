import { useState, useEffect } from 'react';

interface Theme {
  primary: string;
  bg: string;
  radius: 'default' | 'rounded' | 'pill';
}

const DEFAULTS: Theme = {
  primary: '#3a6b35',
  bg: '#f6f9f4',
  radius: 'default',
};

const RADIUS_VALUES = {
  default: { sm: '8px', md: '12px', lg: '16px' },
  rounded: { sm: '12px', md: '18px', lg: '24px' },
  pill:    { sm: '20px', md: '28px', lg: '36px' },
};

const PRESETS = [
  '#3a6b35',
  '#2e7d32',
  '#1565c0',
  '#6a1b9a',
  '#ad1457',
  '#e65100',
  '#4e342e',
  '#37474f',
];

function hexToRgb(hex: string) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return { r, g, b };
}

function darken(hex: string, factor = 0.8): string {
  const { r, g, b } = hexToRgb(hex);
  const d = (v: number) => Math.round(v * factor).toString(16).padStart(2,'0');
  return `#${d(r)}${d(g)}${d(b)}`;
}

function lighten(hex: string): string {
  const { r, g, b } = hexToRgb(hex);
  const l = (v: number) => Math.round(v + (255 - v) * 0.88).toString(16).padStart(2,'0');
  return `#${l(r)}${l(g)}${l(b)}`;
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.style.setProperty('--clr-primary', theme.primary);
  root.style.setProperty('--clr-primary-dark', darken(theme.primary));
  root.style.setProperty('--clr-primary-light', lighten(theme.primary));
  root.style.setProperty('--clr-bg', theme.bg);
  const r = RADIUS_VALUES[theme.radius];
  root.style.setProperty('--radius-sm', r.sm);
  root.style.setProperty('--radius-md', r.md);
  root.style.setProperty('--radius-lg', r.lg);
}

export function loadSavedTheme() {
  try {
    const raw = localStorage.getItem('garden-theme');
    if (raw) {
      const t: Theme = { ...DEFAULTS, ...JSON.parse(raw) };
      applyTheme(t);
    }
  } catch {}
}

export default function ThemePanel({ onClose }: { onClose: () => void }) {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const raw = localStorage.getItem('garden-theme');
      if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
    } catch {}
    return { ...DEFAULTS };
  });

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem('garden-theme', JSON.stringify(theme));
  }, [theme]);

  function set<K extends keyof Theme>(key: K, value: Theme[K]) {
    setTheme(prev => ({ ...prev, [key]: value }));
  }

  function reset() {
    setTheme({ ...DEFAULTS });
    localStorage.removeItem('garden-theme');
  }

  return (
    <div className="theme-panel">
      <div className="theme-panel__title">Theme</div>

      <div className="theme-panel__row">
        <span className="theme-panel__label">Primary color</span>
        <div className="theme-panel__color-row">
          <div className="theme-panel__swatch-grid">
            {PRESETS.map(color => (
              <button
                key={color}
                className={`theme-swatch${theme.primary === color ? ' active' : ''}`}
                style={{ background: color }}
                title={color}
                onClick={() => set('primary', color)}
              />
            ))}
          </div>
          <input
            type="color"
            className="theme-panel__color-input"
            value={theme.primary}
            onChange={e => set('primary', e.target.value)}
            title="Custom color"
          />
        </div>
      </div>

      <div className="theme-panel__row">
        <span className="theme-panel__label">Background</span>
        <div className="theme-panel__color-row">
          {['#f6f9f4','#fafaf8','#f8f4f0','#f4f6fa','#1a1f1a'].map(color => (
            <button
              key={color}
              className={`theme-swatch${theme.bg === color ? ' active' : ''}`}
              style={{ background: color, border: color === '#fafaf8' ? '1px solid #ddd' : undefined }}
              title={color}
              onClick={() => set('bg', color)}
            />
          ))}
          <input
            type="color"
            className="theme-panel__color-input"
            value={theme.bg}
            onChange={e => set('bg', e.target.value)}
            title="Custom background"
          />
        </div>
      </div>

      <div className="theme-panel__row">
        <span className="theme-panel__label">Corner style</span>
        <div className="theme-panel__radius-btns">
          {(['default', 'rounded', 'pill'] as const).map(r => (
            <button
              key={r}
              className={`theme-radius-btn${theme.radius === r ? ' active' : ''}`}
              onClick={() => set('radius', r)}
            >
              {r === 'default' ? 'Soft' : r === 'rounded' ? 'Round' : 'Pill'}
            </button>
          ))}
        </div>
      </div>

      <div className="theme-panel__footer">
        <button className="theme-panel__reset" onClick={reset}>Reset defaults</button>
      </div>
    </div>
  );
}
