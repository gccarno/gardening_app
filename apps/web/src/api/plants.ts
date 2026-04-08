const BASE = '/api';

export interface Plant {
  id: number;
  name: string;
  type?: string;
  status?: string;
  notes?: string;
  planted_date?: string;
  transplant_date?: string;
  expected_harvest?: string;
  garden_id?: number;
  library_id?: number;
  image_filename?: string;
  scientific_name?: string;
  sunlight?: string;
  days_to_harvest?: number;
  bed_names?: string[];
}

export interface LibraryEntry {
  id: number;
  name: string;
  scientific_name?: string;
  type?: string;
  sunlight?: string;
  water?: string;
  spacing_in?: number;
  days_to_germination?: number;
  days_to_harvest?: number;
  min_zone?: number;
  max_zone?: number;
  temp_min_f?: number;
  temp_max_f?: number;
  soil_ph_min?: number;
  soil_ph_max?: number;
  soil_type?: string;
  notes?: string;
  family?: string;
  layer?: string;
  edible_parts?: string;
  permapeople_description?: string;
  permapeople_link?: string;
  image_filename?: string;
  difficulty?: string;
  good_neighbors?: string[];
  bad_neighbors?: string[];
  how_to_grow?: Record<string, string>;
  faqs?: Array<{ q: string; a: string }>;
  nutrition?: Record<string, unknown>;
  bloom_months?: string;
  fruit_months?: string;
  growth_months?: string;
  calendar_rows?: Array<Record<string, unknown>>;
  selected_zone?: number;
  [key: string]: unknown;
}

export interface PlantDetail extends Plant {
  bed_assignments: Array<{ bp_id: number; bed_id: number; bed_name: string; garden_name?: string }>;
  tasks: Array<{ id: number; title: string; task_type?: string; due_date?: string; completed: boolean }>;
  today: string;
  library?: LibraryEntry;
}

export async function fetchPlants(params?: { garden_id?: number; status?: string }): Promise<Plant[]> {
  const q = new URLSearchParams();
  if (params?.garden_id) q.set('garden_id', String(params.garden_id));
  if (params?.status) q.set('status', params.status);
  const res = await fetch(`${BASE}/plants?${q}`);
  if (!res.ok) throw new Error('Failed to fetch plants');
  return res.json();
}

export async function fetchPlant(id: number): Promise<PlantDetail> {
  const res = await fetch(`${BASE}/plants/${id}`);
  if (!res.ok) throw new Error('Failed to fetch plant');
  return res.json();
}

export async function createPlant(body: Partial<Plant> & { name: string }): Promise<Plant> {
  const res = await fetch(`${BASE}/plants`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create plant');
  return res.json();
}

export async function updatePlant(id: number, body: Partial<Plant>): Promise<Plant> {
  const res = await fetch(`${BASE}/plants/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to update plant');
  return res.json();
}

export async function deletePlant(id: number): Promise<void> {
  const res = await fetch(`${BASE}/plants/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete plant');
}

export async function setPlantStatus(id: number, status: string): Promise<Plant> {
  const res = await fetch(`${BASE}/plants/${id}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error('Failed to set status');
  return res.json();
}

export async function fetchLibraryNames(): Promise<Array<{ id: number; name: string }>> {
  // Fetch all names for datalist autocomplete (first page, large limit)
  const res = await fetch(`${BASE}/library?per_page=200`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.entries.map((e: { id: number; name: string }) => ({ id: e.id, name: e.name }));
}
