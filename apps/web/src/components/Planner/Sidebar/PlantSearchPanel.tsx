import React, { useState, useEffect, useMemo } from 'react';
import { type LibPlant, type GardenPlant, api } from '../types';
import { plantImageUrl } from '../../utils/images';

interface Props {
  gardenId: number;
  gardenPlants: GardenPlant[];
  selectedPlant: LibPlant | GardenPlant | null;
  setSelectedPlant: React.Dispatch<React.SetStateAction<LibPlant | GardenPlant | null>>;
  showGroupInfo: (group: GardenPlant[]) => Promise<void>;
  showLibInfo: (libraryId: number) => Promise<void>;
  onAddToGarden: (p: LibPlant) => Promise<void>;
}

export default function PlantSearchPanel({
  gardenId, gardenPlants, selectedPlant, setSelectedPlant, showGroupInfo, showLibInfo, onAddToGarden,
}: Props) {
  const [libPlants, setLibPlants] = useState<LibPlant[]>([]);
  const [plantSearch, setPlantSearch] = useState('');
  const [libSearch, setLibSearch] = useState('');
  const [libSearchResults, setLibSearchResults] = useState<LibPlant[]>([]);
  const [libSearchLoading, setLibSearchLoading] = useState(false);
  const [favorites, setFavorites] = useState<LibPlant[]>(() => {
    try { return JSON.parse(localStorage.getItem('plantFavorites') || '[]'); } catch { return []; }
  });

  // Debounced library search
  useEffect(() => {
    if (!libSearch.trim()) { setLibSearchResults([]); return; }
    setLibSearchLoading(true);
    const timer = setTimeout(async () => {
      const data = await api('GET', `/api/library?q=${encodeURIComponent(libSearch.trim())}&per_page=50`);
      setLibSearchResults((data.entries || []) as LibPlant[]);
      setLibSearchLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [libSearch]);

  function toggleFavorite(plant: LibPlant, e: React.MouseEvent) {
    e.stopPropagation();
    setFavorites(prev => {
      const next = prev.some(p => p.id === plant.id)
        ? prev.filter(p => p.id !== plant.id)
        : [...prev, plant];
      localStorage.setItem('plantFavorites', JSON.stringify(next));
      return next;
    });
  }

  async function handleAddToGarden(p: LibPlant) {
    await onAddToGarden(p);
  }

  const filteredGarden = gardenPlants.filter(p => p.name.toLowerCase().includes(plantSearch.toLowerCase()));
  const filteredLib = libSearch.trim() ? libSearchResults : libPlants.filter(p => p.name.toLowerCase().includes(plantSearch.toLowerCase()));

  const gardenGroups = useMemo(() => {
    const map = new Map<string, GardenPlant[]>();
    for (const p of filteredGarden) {
      const key = p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(p);
    }
    return [...map.values()];
  }, [filteredGarden]);

  return (
    <div>
      <input type="text" placeholder="Search plants…" value={plantSearch} onChange={e => setPlantSearch(e.target.value)}
             style={{ width: '100%', font: 'inherit', fontSize: '0.8rem', padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', marginBottom: '0.4rem', boxSizing: 'border-box' }} />

      {gardenGroups.length > 0 && (
        <details open>
          <summary className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', cursor: 'pointer' }}>Plants in Garden ({filteredGarden.length})</summary>
          <ul style={{ listStyle: 'none', padding: 0, margin: '0.3rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
            {gardenGroups.map(group => {
              const rep = group[0];
              const count = group.length;
              const isSelected = selectedPlant?.id === rep.id;
              if (count === 1) {
                return (
                  <li key={rep.id}
                      className={`palette-item palette-plant${isSelected ? ' active' : ''}`}
                      draggable
                      onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(rep); }}
                      onClick={() => setSelectedPlant(prev => prev?.id === rep.id ? null : rep)}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: isSelected ? '#d4edcc' : '#f4f9f4', borderRadius: '4px', fontSize: '0.78rem', cursor: 'pointer' }}>
                    {rep.image_filename ? <img src={plantImageUrl(rep.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rep.name}</span>
                    <button title="Plant info" onClick={e => { e.stopPropagation(); showGroupInfo(group); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a907a', fontSize: '0.75rem', padding: '0 1px', flexShrink: 0 }}>ℹ</button>
                  </li>
                );
              }
              return (
                <li key={`grp-${rep.id}`} style={{ borderRadius: '4px', overflow: 'hidden', fontSize: '0.78rem' }}>
                  <details>
                    <summary
                      style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: '#f4f9f4', cursor: 'pointer', listStyle: 'none' }}
                      draggable
                      onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(rep); }}
                      onClick={() => setSelectedPlant(prev => prev?.id === rep.id ? null : rep)}
                    >
                      {rep.image_filename ? <img src={plantImageUrl(rep.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rep.name}</span>
                      <span style={{ background: '#3a6b35', color: '#fff', borderRadius: '10px', padding: '0 5px', fontSize: '0.68rem', fontWeight: 700 }}>×{count}</span>
                      <button title="Plant info" onClick={e => { e.stopPropagation(); showGroupInfo(group); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a907a', fontSize: '0.75rem', padding: '0 1px', flexShrink: 0 }}>ℹ</button>
                    </summary>
                    <ul style={{ listStyle: 'none', padding: '0.2rem 0 0.2rem 0.6rem', margin: 0, display: 'flex', flexDirection: 'column', gap: '0.15rem', background: '#f0f6ef' }}>
                      {group.map((p, i) => (
                        <li key={p.id}
                            className={`palette-item palette-plant${selectedPlant?.id === p.id ? ' active' : ''}`}
                            draggable
                            onDragStart={e => { e.stopPropagation(); e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(p); }}
                            onClick={e => { e.stopPropagation(); setSelectedPlant(prev => prev?.id === p.id ? null : p); }}
                            style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.15rem 0.4rem', background: selectedPlant?.id === p.id ? '#d4edcc' : 'transparent', borderRadius: '3px', cursor: 'pointer' }}>
                          <span style={{ color: '#9ab49a', minWidth: 16 }}>#{i + 1}</span>
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                </li>
              );
            })}
          </ul>
        </details>
      )}

      <details open style={{ marginTop: '0.4rem' }} onToggle={e => {
        if ((e.currentTarget as HTMLDetailsElement).open && libPlants.length === 0 && !libSearch.trim()) {
          api('GET', '/api/library?per_page=100').then(d => setLibPlants((d.entries || []) as LibPlant[]));
        }
      }}>
        <summary className="sidebar-label" style={{ fontWeight: 600, fontSize: '0.8rem', color: '#3a5c37', cursor: 'pointer' }}>Library Plants</summary>

        {favorites.length > 0 && (
          <details open style={{ marginTop: '0.3rem' }}>
            <summary style={{ fontSize: '0.75rem', fontWeight: 600, color: '#b8860b', cursor: 'pointer', padding: '0.1rem 0' }}>⭐ Favorites ({favorites.length})</summary>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0.2rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              {favorites.map(p => (
                <li key={p.id}
                    className={`palette-item palette-plant${selectedPlant?.id === p.id && !('library_id' in selectedPlant) ? ' active' : ''}`}
                    draggable
                    onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(p); }}
                    onClick={() => setSelectedPlant(prev => prev?.id === p.id ? null : p)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: selectedPlant?.id === p.id ? '#d4edcc' : '#fffbf0', borderRadius: '4px', fontSize: '0.78rem', cursor: 'pointer' }}>
                  {p.image_filename ? <img src={plantImageUrl(p.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                  <button title="Remove from favorites" onClick={e => toggleFavorite(p, e)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#b8860b', fontSize: '0.8rem', padding: '0 1px', flexShrink: 0 }}>⭐</button>
                  <button title="Add to garden" onClick={e => { e.stopPropagation(); handleAddToGarden(p); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3a6b35', fontSize: '0.85rem', padding: '0 1px', flexShrink: 0, fontWeight: 700, lineHeight: 1 }}>+</button>
                </li>
              ))}
            </ul>
          </details>
        )}

        <div style={{ marginTop: '0.3rem', position: 'relative' }}>
          <input
            type="text"
            placeholder="Search 8,000+ plants…"
            value={libSearch}
            onChange={e => setLibSearch(e.target.value)}
            style={{ width: '100%', font: 'inherit', fontSize: '0.78rem', padding: '0.25rem 0.4rem', border: '1px solid #c0d4be', borderRadius: '4px', boxSizing: 'border-box' }}
          />
          {libSearch && (
            <button onClick={() => setLibSearch('')}
              style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9ab49a', fontSize: '0.9rem', padding: 0, lineHeight: 1 }}>×</button>
          )}
        </div>
        <ul style={{ listStyle: 'none', padding: 0, margin: '0.3rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.2rem', maxHeight: '250px', overflowY: 'auto' }}>
          {libSearchLoading && <li style={{ fontSize: '0.75rem', color: '#9ab49a', padding: '0.2rem 0.4rem' }}>Searching…</li>}
          {!libSearchLoading && libSearch.trim() && filteredLib.length === 0 && (
            <li style={{ fontSize: '0.75rem', color: '#9ab49a', padding: '0.2rem 0.4rem' }}>No results for "{libSearch}"</li>
          )}
          {filteredLib.slice(0, 50).map(p => (
            <li key={p.id}
                className={`palette-item palette-plant${selectedPlant?.id === p.id && !('library_id' in selectedPlant) ? ' active' : ''}`}
                draggable
                onDragStart={e => { e.dataTransfer.effectAllowed = 'copy'; setSelectedPlant(p); }}
                onClick={() => setSelectedPlant(prev => prev?.id === p.id ? null : p)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.2rem 0.4rem', background: selectedPlant?.id === p.id ? '#d4edcc' : '#f4f9f4', borderRadius: '4px', fontSize: '0.78rem', cursor: 'pointer' }}>
              {p.image_filename ? <img src={plantImageUrl(p.image_filename) ?? ''} alt="" style={{ width: 20, height: 20, objectFit: 'cover', borderRadius: '50%' }} /> : <span>🌱</span>}
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
              <button title={favorites.some(f => f.id === p.id) ? 'Remove from favorites' : 'Add to favorites'} onClick={e => toggleFavorite(p, e)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: favorites.some(f => f.id === p.id) ? '#b8860b' : '#c0c0c0', fontSize: '0.8rem', padding: '0 1px', flexShrink: 0 }}>⭐</button>
              <button title="Add to garden (no canvas)" onClick={e => { e.stopPropagation(); handleAddToGarden(p); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3a6b35', fontSize: '0.85rem', padding: '0 1px', flexShrink: 0, fontWeight: 700, lineHeight: 1 }}>+</button>
              <button title="Plant info" onClick={e => { e.stopPropagation(); showLibInfo(p.id); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7a907a', fontSize: '0.75rem', padding: '0 1px', flexShrink: 0 }}>ℹ</button>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
