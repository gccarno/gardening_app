import { apiFetch } from './http';

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

export function createLibraryApi(base: string) {
  return {
    fetchLibrary: async (params?: {
      q?: string; type?: string; page?: number; per_page?: number;
    }): Promise<LibraryListResponse> => {
      const qs = new URLSearchParams();
      if (params?.q)        qs.set('q',        params.q);
      if (params?.type && params.type !== 'all') qs.set('type', params.type);
      if (params?.page)     qs.set('page',     String(params.page));
      if (params?.per_page) qs.set('per_page', String(params.per_page));
      const res = await apiFetch(`${base}/library?${qs}`);
      if (!res.ok) throw new Error('Failed to fetch library');
      return res.json();
    },

    fetchLibraryEntry: async (id: number) => {
      const res = await apiFetch(`${base}/library/${id}`);
      if (!res.ok) throw new Error('Failed to fetch library entry');
      return res.json();
    },

    addPlantFromLibrary: async (entryId: number, gardenId: number) => {
      const res = await apiFetch(`${base}/plants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ library_id: entryId, garden_id: gardenId, name: '' }),
      });
      if (!res.ok) throw new Error('Failed to add plant');
      return res.json();
    },

    perenualSearch: async (q: string) => {
      const res = await apiFetch(`${base}/perenual/search?q=${encodeURIComponent(q)}`);
      if (!res.ok) throw new Error('Search failed');
      return res.json();
    },

    perenualSave: async (result: Record<string, unknown>) => {
      const res = await apiFetch(`${base}/perenual/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result),
      });
      if (!res.ok) throw new Error('Save failed');
      return res.json();
    },

    setImagePrimary: async (imageId: number) => {
      const res = await apiFetch(`${base}/library/images/${imageId}/set-primary`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to set primary');
      return res.json();
    },

    deleteImage: async (imageId: number) => {
      const res = await apiFetch(`${base}/library/images/${imageId}/delete`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to delete image');
      return res.json();
    },

    addImageFromUrl: async (entryId: number, body: { url: string; source?: string; attribution?: string }) => {
      const res = await apiFetch(`${base}/library/${entryId}/images/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to add image');
      return res.json();
    },

    uploadImage: async (entryId: number, file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      const res = await apiFetch(`${base}/library/${entryId}/images`, { method: 'POST', body: fd });
      if (!res.ok) throw new Error('Upload failed');
      return res.json();
    },

    quickEditLibrary: async (entryId: number, body: Record<string, unknown>) => {
      const res = await apiFetch(`${base}/library/${entryId}/quick-edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to quick-edit');
      return res.json();
    },

    clonePlant: async (entryId: number, name: string): Promise<{ id: number; name: string }> => {
      const res = await apiFetch(`${base}/library/${entryId}/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error('Failed to clone plant');
      return res.json();
    },

    patchLibraryEntry: async (entryId: number, fields: Record<string, unknown>): Promise<void> => {
      const res = await apiFetch(`${base}/library/${entryId}/patch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields),
      });
      if (!res.ok) throw new Error('Failed to patch library entry');
    },
  };
}
