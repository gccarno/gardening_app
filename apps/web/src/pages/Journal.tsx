import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useGardens } from '../hooks/useGardens';

interface JournalEntry {
  id: number;
  garden_id: number;
  plant_id: number | null;
  entry_date: string;
  title: string;
  body: string | null;
  tags: string[];
  image_filename: string | null;
  created_at: string;
}

function useGardenId() {
  const { data: gardens } = useGardens();
  const stored = localStorage.getItem('defaultGardenId');
  const storedId = stored ? parseInt(stored, 10) : undefined;
  return gardens?.find(g => g.id === storedId)?.id ?? gardens?.[0]?.id;
}

function useJournal(gardenId?: number, page = 1) {
  return useQuery<{ total: number; page: number; entries: JournalEntry[] }>({
    queryKey: ['journal', gardenId, page],
    queryFn: () => fetch(`/api/gardens/${gardenId}/journal?page=${page}&per_page=20`).then(r => r.json()),
    enabled: !!gardenId,
  });
}

function formatDate(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function Journal() {
  const gardenId = useGardenId();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useJournal(gardenId, page);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: '',
    body: '',
    entry_date: new Date().toISOString().split('T')[0],
    tagsRaw: '',
  });
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const createMut = useMutation({
    mutationFn: () =>
      fetch(`/api/gardens/${gardenId}/journal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title,
          body: form.body || undefined,
          entry_date: form.entry_date,
          tags: form.tagsRaw ? form.tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [],
        }),
      }).then(r => r.json()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['journal', gardenId] });
      setShowForm(false);
      setForm({ title: '', body: '', entry_date: new Date().toISOString().split('T')[0], tagsRaw: '' });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      fetch(`/api/journal/${id}`, { method: 'DELETE' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['journal', gardenId] }),
  });

  if (!gardenId) return <p className="muted" style={{ padding: '2rem' }}>Select a garden first.</p>;
  if (isLoading)  return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;

  const entries = data?.entries ?? [];
  const totalPages = data ? Math.ceil(data.total / 20) : 1;

  return (
    <div style={{ padding: '1.5rem', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0 }}>Garden Journal</h1>
        <button className="btn" onClick={() => setShowForm(s => !s)}>
          {showForm ? 'Cancel' : '+ New Entry'}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <input
              className="form-input"
              placeholder="Title *"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            />
            <input
              type="date"
              className="form-input"
              value={form.entry_date}
              onChange={e => setForm(f => ({ ...f, entry_date: e.target.value }))}
            />
            <textarea
              className="form-input"
              placeholder="What happened in the garden today?"
              rows={4}
              value={form.body}
              onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
            />
            <input
              className="form-input"
              placeholder="Tags (comma-separated): harvest, disease, watering…"
              value={form.tagsRaw}
              onChange={e => setForm(f => ({ ...f, tagsRaw: e.target.value }))}
            />
            <button
              className="btn"
              disabled={!form.title || createMut.isPending}
              onClick={() => createMut.mutate()}
            >
              {createMut.isPending ? 'Saving…' : 'Save Entry'}
            </button>
          </div>
        </div>
      )}

      {entries.length === 0 ? (
        <p className="muted">No journal entries yet. Start recording your garden journey!</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          {entries.map(e => (
            <div key={e.id} className="card" style={{ padding: '0.8rem 1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span style={{ fontWeight: 600 }}>{e.title}</span>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>{formatDate(e.entry_date)}</span>
                  </div>
                  {e.tags.length > 0 && (
                    <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginTop: '0.3rem' }}>
                      {e.tags.map(tag => (
                        <span key={tag} style={{
                          background: '#e8f0e4', color: '#3a6b36', borderRadius: '4px',
                          padding: '0.1rem 0.4rem', fontSize: '0.75rem',
                        }}>{tag}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <button
                    className="btn btn--ghost"
                    style={{ fontSize: '0.78rem', padding: '0.2rem 0.5rem' }}
                    onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                  >
                    {expandedId === e.id ? 'Hide' : 'Read'}
                  </button>
                  <button
                    className="btn btn--ghost"
                    style={{ fontSize: '0.78rem', padding: '0.2rem 0.5rem', color: '#c0392b' }}
                    onClick={() => { if (confirm('Delete this entry?')) deleteMut.mutate(e.id); }}
                  >
                    ×
                  </button>
                </div>
              </div>
              {expandedId === e.id && e.body && (
                <p style={{ marginTop: '0.6rem', lineHeight: 1.55, whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                  {e.body}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginTop: '1.5rem' }}>
          <button className="btn btn--ghost" disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span className="muted" style={{ lineHeight: '2rem' }}>Page {page} of {totalPages}</span>
          <button className="btn btn--ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
