import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '@garden/shared';

type Mode = 'identify' | 'health' | 'disease' | 'pest';

interface Candidate {
  name: string | null;
  scientific_name: string | null;
  confidence: number | null;
  library_match: { library_id: number; library_name: string; image_filename: string | null } | null;
}

interface IdentifyResult {
  mode: Mode;
  candidates: Candidate[];
  diagnosis: string | null;
  care_advice: string | null;
}

const MODE_LABELS: Record<Mode, { label: string; hint: string }> = {
  identify: { label: '🌿 What plant is this?', hint: 'Identify a plant from a photo' },
  health:   { label: '🩺 Health check',        hint: 'Assess overall plant health' },
  disease:  { label: '🦠 Diagnose disease',    hint: 'Spots, blight, mildew, rot…' },
  pest:     { label: '🐛 Identify pest',       hint: 'Insects and animal damage' },
};

export default function Identify() {
  const [mode, setMode] = useState<Mode>('identify');
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<IdentifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = (f: File | null) => {
    setResult(null);
    setError(null);
    setFile(f);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append('image', file);
      form.append('mode', mode);
      const res = await apiFetch('/api/identify', { method: 'POST', body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? 'Identification failed');
      }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Identification failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>Identify</h1>
      <p className="muted">
        Snap or upload a photo — get a species ID, health check, or pest/disease diagnosis.
      </p>

      <div className="identify-modes">
        {(Object.keys(MODE_LABELS) as Mode[]).map(m => (
          <button key={m}
                  className={`identify-mode ${mode === m ? 'identify-mode--active' : ''}`}
                  onClick={() => setMode(m)} title={MODE_LABELS[m].hint}>
            {MODE_LABELS[m].label}
          </button>
        ))}
      </div>

      <div className="identify-drop card"
           onClick={() => inputRef.current?.click()}
           onDragOver={e => e.preventDefault()}
           onDrop={e => { e.preventDefault(); onFile(e.dataTransfer.files[0] ?? null); }}>
        {preview
          ? <img src={preview} alt="Selected plant" className="identify-preview" />
          : <p className="muted">Click to choose a photo, or drag one here</p>}
        <input ref={inputRef} type="file" accept="image/*" capture="environment" hidden
               onChange={e => onFile(e.target.files?.[0] ?? null)} />
      </div>

      <div className="actions">
        <button className="btn-primary" disabled={!file || busy} onClick={submit}>
          {busy ? 'Analyzing…' : 'Analyze photo'}
        </button>
      </div>

      {error && <p className="form-error">{error}</p>}

      {result && (
        <section className="identify-results">
          {result.candidates.length > 0 && (
            <ul className="card-list">
              {result.candidates.map((c, i) => (
                <li key={i} className="card identify-candidate">
                  <div>
                    <strong>{c.name ?? 'Unknown'}</strong>
                    {c.scientific_name && <em className="muted"> — {c.scientific_name}</em>}
                    {typeof c.confidence === 'number' && (
                      <span className="badge" style={{ marginLeft: '0.5rem' }}>
                        {Math.round(c.confidence * 100)}%
                      </span>
                    )}
                  </div>
                  {c.library_match && (
                    <Link to={`/library/${c.library_match.library_id}`} className="btn-small btn-link">
                      View in library →
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
          {result.diagnosis && (
            <div className="card">
              <h2>Assessment</h2>
              <p>{result.diagnosis}</p>
            </div>
          )}
          {result.care_advice && (
            <div className="card">
              <h2>What to do</h2>
              <p>{result.care_advice}</p>
            </div>
          )}
        </section>
      )}
    </>
  );
}
