const BASE = '/api';

export interface Garden {
  id: number;
  name: string;
  description?: string;
  unit: string;
  zip_code?: string;
  city?: string;
  state?: string;
  latitude?: number;
  longitude?: number;
  usda_zone?: string;
  zone_temp_range?: string;
  last_frost_date?: string;
  watering_frequency_days?: number;
  water_source?: string;
  background_image?: string;
}

export interface DashboardData {
  metrics: {
    bed_count: number;
    plant_count: number;
    plants_active: number;
    task_count: number;
    overdue_tasks: number;
  };
  upcoming_tasks: Array<{
    id: number;
    title: string;
    task_type?: string;
    due_date?: string;
    plant_name?: string;
  }>;
  recent_plants: Array<{
    id: number;
    name: string;
    type?: string;
    status?: string;
  }>;
  recent_activity: Array<{
    id: number;
    title: string;
    completed_date?: string;
  }>;
  season: string;
  season_icon: string;
  hint_action: string;
  hint_text: string;
  hint_crops: string;
  frost_context?: string;
}

export async function fetchGardens(): Promise<Garden[]> {
  const res = await fetch(`${BASE}/gardens`);
  if (!res.ok) throw new Error('Failed to fetch gardens');
  return res.json();
}

export async function fetchGarden(id: number): Promise<Garden> {
  const res = await fetch(`${BASE}/gardens/${id}`);
  if (!res.ok) throw new Error('Failed to fetch garden');
  return res.json();
}

export async function createGarden(body: Partial<Garden>): Promise<Garden> {
  const res = await fetch(`${BASE}/gardens`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create garden');
  return res.json();
}

export async function updateGarden(id: number, body: Partial<Garden>): Promise<Garden> {
  const res = await fetch(`${BASE}/gardens/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to update garden');
  return res.json();
}

export async function deleteGarden(id: number): Promise<void> {
  const res = await fetch(`${BASE}/gardens/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete garden');
}

export async function fetchDashboard(gardenId?: number): Promise<DashboardData> {
  const url = gardenId
    ? `${BASE}/dashboard?garden_id=${gardenId}`
    : `${BASE}/dashboard`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch dashboard');
  return res.json();
}

export async function fetchDefaultGarden(): Promise<{ garden_id: number | null }> {
  const res = await fetch(`${BASE}/settings/default-garden`);
  if (!res.ok) throw new Error('Failed to fetch default garden');
  return res.json();
}

export async function setDefaultGarden(gardenId: number | null): Promise<void> {
  await fetch(`${BASE}/settings/default-garden`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ garden_id: gardenId }),
  });
}

export async function fetchWateringStatus(gardenId: number) {
  const res = await fetch(`${BASE}/gardens/${gardenId}/watering-status`);
  if (!res.ok) throw new Error('Failed to fetch watering status');
  return res.json();
}

export async function sendChat(body: {
  message: string;
  garden_id?: number | null;
  conversation_history: Array<{ role: string; content: string }>;
  session_id: string;
}) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Chat request failed');
  return res.json();
}
