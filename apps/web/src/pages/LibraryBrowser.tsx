import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLibrary } from '../hooks/useLibrary';
import { perenualSearch, perenualSave } from '../api/library';

const PLANT_TYPES = ['vegetable', 'herb', 'fruit', 'flower'];

export default function LibraryBrowser() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(1);

  const [compareMode, setCompareMode] = useState(false);
  const [compareIds, setCompareIds] = useState<number[]>([]);

  const [perenualQ, setPerenualQ] = useState('');
  const [perenualResults, setPerenualResults] = useState<unknown[]>([]);
  const [perenualSearching, setPerenualSearching] = useState(false);
  const [perenualMsg, setPerenualMsg] = useState('');
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());

  function toggleCompare(id: number) {
    setCompareIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= 2) return [prev[1], id]; // replace oldest
      return [...prev, id];
    });
  }

  const { data, isLoading } = useLibrary({
    q: search || undefined,
    type: typeFilter || undefined,
    page,
  });

  const entries = data?.entries ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
  }

  async function runPerenualSearch() {
    if (!perenualQ.trim()) return;
    setPerenualSearching(true);
    setPerenualMsg('');
    setPerenualResults([]);
    try {
      const data = await perenualSearch(perenualQ);
      if ((data as { error?: string }).error) {
        setPerenualMsg((data as { message?: string; error: string }).message || (data as { error: string }).error);
      } else {
        const results = (data as { results: unknown[] }).results;
        if (!results.length) setPerenualMsg('No results found.');
        else setPerenualResults(results);
      }
    } catch { setPerenualMsg('Search failed.'); }
    setPerenualSearching(false);
  }

  async function handleSave(result: unknown) {
    const r = result as { id: number; name: string };
    setSavingIds(s => new Set(s).add(r.id));
    try {
      const data = await perenualSave(result as Record<string, unknown>);
      if ((data as { ok?: boolean }).ok) {
        setPerenualResults(prev => prev.map(item =>
          (item as { id: number }).id === r.id ? { ...item as object, _saved: true, _existing: (data as { existing?: boolean }).existing } : item
        ));
      }
    } catch { /* ignore */ }
    setSavingIds(s => { const n = new Set(s); n.delete(r.id); return n; });
  }

  return (
    <>
      <h1>Plant Library</h1>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Search Perenual</h2>
        <div style={{ display: 'flex', gap: '0.5rem', maxWidth: '480px' }}>
          <input
            type="text"
            className="perenual-input"
            placeholder="e.g. basil, sunflower…"
            value={perenualQ}
            onChange={e => setPerenualQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') runPerenualSearch(); }}
          />
          <button onClick={runPerenualSearch} disabled={perenualSearching}>
            {perenualSearching ? 'Searching…' : 'Search'}
          </button>
        </div>
        {perenualMsg && <p className="muted" style={{ marginTop: '0.5rem' }}>{perenualMsg}</p>}
        {perenualResults.length > 0 && (
          <div className="perenual-results" style={{ marginTop: '0.75rem' }}>
            {perenualResults.map(result => {
              const r = result as { id: number; name: string; scientific_name?: string; image?: string; sunlight?: string; watering?: string; cycle?: string; _saved?: boolean; _existing?: boolean };
              return (
                <div key={r.id} className="perenual-card">
                  {r.image
                    ? <img src={r.image} alt={r.name} className="perenual-thumb" />
                    : <div className="perenual-thumb perenual-thumb--empty" />}
                  <div className="perenual-card-body">
                    <strong>{r.name}</strong>
                    {r.scientific_name && <span className="muted">{r.scientific_name}</span>}
                    <div className="perenual-meta">
                      {r.sunlight && <span>☀ {r.sunlight}</span>}
                      {r.watering && <span>💧 {r.watering}</span>}
                      {r.cycle && <span>↻ {r.cycle}</span>}
                    </div>
                  </div>
                  <button
                    className="btn-small perenual-save-btn"
                    disabled={savingIds.has(r.id) || r._saved}
                    onClick={() => handleSave(result)}
                  >
                    {r._saved ? (r._existing ? 'Already saved' : 'Saved!') : savingIds.has(r.id) ? 'Saving…' : 'Save to Library'}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <div className="lib-filters" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.4rem' }}>
        <button className={`lib-filter${typeFilter === '' ? ' active' : ''}`} onClick={() => { setTypeFilter(''); setPage(1); }}>
          All ({total})
        </button>
        {PLANT_TYPES.map(t => (
          <button key={t} className={`lib-filter${typeFilter === t ? ' active' : ''}`}
                  onClick={() => { setTypeFilter(t); setPage(1); }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}s
          </button>
        ))}
        <span style={{ marginLeft: 'auto' }}>
          <button
            onClick={() => { setCompareMode(m => !m); setCompareIds([]); }}
            style={{ background: compareMode ? '#3a6b35' : '#f0f7ef', color: compareMode ? '#fff' : '#3a5c37', border: '1px solid #b0c8ae', borderRadius: '4px', padding: '0.3rem 0.7rem', cursor: 'pointer', font: 'inherit', fontSize: '0.85rem' }}
          >
            {compareMode ? 'Exit Compare' : 'Compare Plants'}
          </button>
          {compareMode && compareIds.length === 2 && (
            <button
              onClick={() => navigate(`/library/diff?a=${compareIds[0]}&b=${compareIds[1]}`)}
              style={{ marginLeft: '0.4rem', background: '#3a6b35', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.3rem 0.8rem', cursor: 'pointer', font: 'inherit', fontSize: '0.85rem' }}
            >
              Diff selected →
            </button>
          )}
          {compareMode && compareIds.length < 2 && (
            <span className="muted" style={{ marginLeft: '0.5rem', fontSize: '0.82rem' }}>
              Select {2 - compareIds.length} more plant{compareIds.length === 1 ? '' : 's'}
            </span>
          )}
        </span>
      </div>

      <form onSubmit={handleSearch} style={{ maxWidth: '340px', marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search by name…"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          style={{ width: '100%', font: 'inherit', padding: '0.4rem 0.6rem', border: '1px solid #c0d4be', borderRadius: '4px', background: '#fbfefb' }}
        />
      </form>

      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <table className="lib-table">
            <thead>
              <tr>
                {compareMode && <th style={{ width: '2rem' }}></th>}
                <th>Name</th>
                <th>Type</th>
                <th>Spacing</th>
                <th>Sunlight</th>
                <th>Water</th>
                <th>Germination</th>
                <th>Days to Harvest</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => {
                const isChecked = compareIds.includes(e.id);
                return (
                  <tr key={e.id} style={isChecked ? { background: '#eef6ec' } : undefined}>
                    {compareMode && (
                      <td>
                        <input type="checkbox" checked={isChecked} onChange={() => toggleCompare(e.id)} />
                      </td>
                    )}
                    <td>
                      <Link to={`/library/${e.id}`}>{e.name}</Link>
                      {(e as { is_custom?: boolean }).is_custom && (
                        <span style={{ marginLeft: '0.4rem', fontSize: '0.7rem', background: '#d4edda', color: '#155724', borderRadius: '3px', padding: '0 0.3rem', verticalAlign: 'middle' }}>custom</span>
                      )}
                    </td>
                    <td>{e.type && <span className={`lib-badge lib-badge--${e.type}`}>{e.type}</span>}</td>
                    <td>{e.spacing_in ? `${e.spacing_in}″` : '—'}</td>
                    <td>{e.sunlight || '—'}</td>
                    <td>{e.water || '—'}</td>
                    <td>{e.days_to_germination ? `${e.days_to_germination} days` : '—'}</td>
                    <td>{e.days_to_harvest ? `${e.days_to_harvest} days` : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {pages > 1 && (
            <div className="actions" style={{ marginTop: '1rem', gap: '0.5rem' }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span className="muted">Page {page} of {pages} ({total} plants)</span>
              <button disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
          {entries.length === 0 && <p className="muted">No plants found.</p>}
        </>
      )}
    </>
  );
}
