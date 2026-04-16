const BASE = '/api';

export interface LibraryListEntry {
  id: number;
  name: string;
  type?: string;
  spacing_in?: number;
  sunlight?: string;
  water?: string;
  days_to_germination?: number;
  days_to_harvest?: number;
  image_filename?: string;
  difficulty?: string;
  min_zone?: number;
  max_zone?: number;
}

export interface LibraryListResponse {
  total: number;
  page: number;
  per_page: number;
  pages: number;
  entries: LibraryListEntry[];
}

export async function fetchLibrary(params?: {
  q?: string; type?: string; page?: number; per_page?: number;
}): Promise<LibraryListResponse> {
  const qs = new URLSearchParams();
  if (params?.q)        qs.set('q',        params.q);
  if (params?.type && params.type !== 'all') qs.set('type', params.type);
  if (params?.page)     qs.set('page',     String(params.page));
  if (params?.per_page) qs.set('per_page', String(params.per_page));
  const res = await fetch(`${BASE}/library?${qs}`);
  if (!res.ok) throw new Error('Failed to fetch library');
  return res.json();
}

export async function fetchLibraryEntry(id: number) {
  const res = await fetch(`${BASE}/library/${id}`);
  if (!res.ok) throw new Error('Failed to fetch library entry');
  return res.json();
}

export async function addPlantFromLibrary(entryId: number, gardenId: number) {
  const res = await fetch(`${BASE}/plants`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ library_id: entryId, garden_id: gardenId, name: '' }),
  });
  if (!res.ok) throw new Error('Failed to add plant');
  return res.json();
}

export async function perenualSearch(q: string) {
  const res = await fetch(`${BASE}/perenual/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function perenualSave(result: Record<string, unknown>) {
  const res = await fetch(`${BASE}/perenual/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result),
  });
  if (!res.ok) throw new Error('Save failed');
  return res.json();
}

export async function setImagePrimary(imageId: number) {
  const res = await fetch(`${BASE}/library/images/${imageId}/set-primary`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to set primary');
  return res.json();
}

export async function deleteImage(imageId: number) {
  const res = await fetch(`${BASE}/library/images/${imageId}/delete`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to delete image');
  return res.json();
}

export async function addImageFromUrl(entryId: number, body: { url: string; source?: string; attribution?: string }) {
  const res = await fetch(`${BASE}/library/${entryId}/images/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to add image');
  return res.json();
}

export async function uploadImage(entryId: number, file: File) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${BASE}/library/${entryId}/images`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

export async function quickEditLibrary(entryId: number, body: Record<string, unknown>) {
  const res = await fetch(`${BASE}/library/${entryId}/quick-edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to quick-edit');
  return res.json();
}

export async function clonePlant(entryId: number, name: string): Promise<{ id: number; name: string }> {
  const res = await fetch(`${BASE}/library/${entryId}/clone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error('Failed to clone plant');
  return res.json();
}

export async function patchLibraryEntry(entryId: number, fields: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${BASE}/library/${entryId}/patch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  });
  if (!res.ok) throw new Error('Failed to patch library entry');
}
