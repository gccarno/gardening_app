const BASE = '/api';

export interface Bed {
  id: number;
  name: string;
  garden_id?: number;
  garden_name?: string;
  width_ft: number;
  height_ft: number;
  depth_ft?: number;
  location?: string;
  description?: string;
  soil_notes?: string;
  soil_ph?: number;
  clay_pct?: number;
  compost_pct?: number;
  sand_pct?: number;
  pos_x?: number;
  pos_y?: number;
  plant_count?: number;
}

export interface GridPlant {
  id: number;
  grid_x: number;
  grid_y: number;
  plant_id: number;
  plant_name: string;
  image_filename?: string;
}

export interface BedPlantDetail {
  id: number;
  plant_id: number;
  plant_name: string;
  scientific_name?: string;
  image_filename?: string;
  sunlight?: string;
  water?: string;
  spacing_in?: number;
  days_to_harvest?: number;
  last_watered?: string;
  last_fertilized?: string;
  health_notes?: string;
}

export async function fetchBeds(gardenId?: number): Promise<Bed[]> {
  const url = gardenId ? `${BASE}/beds?garden_id=${gardenId}` : `${BASE}/beds`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch beds');
  return res.json();
}

export async function fetchBed(id: number): Promise<Bed> {
  const res = await fetch(`${BASE}/beds/${id}`);
  if (!res.ok) throw new Error('Failed to fetch bed');
  return res.json();
}

export async function createBed(body: Partial<Bed> & { name: string; garden_id: number }): Promise<{ ok: boolean; bed: Bed }> {
  const res = await fetch(`${BASE}/beds`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create bed');
  return res.json();
}

export async function updateBed(id: number, body: Partial<Bed>): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/beds/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to update bed');
  return res.json();
}

export async function deleteBed(id: number): Promise<void> {
  await fetch(`${BASE}/beds/${id}/delete`, { method: 'POST' });
}

export async function fetchBedGrid(id: number): Promise<{ placed: GridPlant[] }> {
  const res = await fetch(`${BASE}/beds/${id}/grid`);
  if (!res.ok) throw new Error('Failed to fetch grid');
  return res.json();
}

export async function placePlantInGrid(bedId: number, body: { library_id: number; grid_x: number; grid_y: number }) {
  const res = await fetch(`${BASE}/beds/${bedId}/grid-plant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to place plant');
  return res.json();
}

export async function fetchBedPlant(bpId: number): Promise<BedPlantDetail> {
  const res = await fetch(`${BASE}/bedplants/${bpId}`);
  if (!res.ok) throw new Error('Failed to fetch bed plant');
  return res.json();
}

export async function saveBedPlantCare(bpId: number, body: { last_watered?: string | null; last_fertilized?: string | null; health_notes?: string | null }) {
  const res = await fetch(`${BASE}/bedplants/${bpId}/care`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to save care');
  return res.json();
}

export async function removeBedPlant(bpId: number): Promise<void> {
  await fetch(`${BASE}/bedplants/${bpId}/delete`, { method: 'POST' });
}
