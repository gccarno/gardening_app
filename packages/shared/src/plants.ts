export interface Plant {
  id: number;
  name: string;
  type?: string;
  status?: string;
  notes?: string;
  planted_date?: string;
  transplant_date?: string;
  expected_harvest?: string;
  last_watered?: string;
  last_fertilized?: string;
  garden_id?: number;
  library_id?: number;
  image_filename?: string;
  scientific_name?: string;
  sunlight?: string;
  days_to_harvest?: number;
  days_to_germination?: number;
  sow_indoor_weeks?: number;
  direct_sow_offset?: number;
  transplant_offset?: number;
  temp_max_f?: number;
  bed_names?: string[];
  succession_label?: string;
}

export interface SuccessionGroup {
  label: string;
  plants: Plant[];
}

export interface PlantGroup {
  key: string;
  name: string;
  library_id: number | null;
  image_filename: string | null;
  type: string | null;
  plants: Plant[];
  successionGroups: SuccessionGroup[];
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

export function createPlantsApi(base: string) {
  return {
    fetchPlants: async (params?: { garden_id?: number; status?: string }): Promise<Plant[]> => {
      const q = new URLSearchParams();
      if (params?.garden_id) q.set('garden_id', String(params.garden_id));
      if (params?.status) q.set('status', params.status);
      const res = await fetch(`${base}/plants?${q}`);
      if (!res.ok) throw new Error('Failed to fetch plants');
      return res.json();
    },

    fetchPlant: async (id: number): Promise<PlantDetail> => {
      const res = await fetch(`${base}/plants/${id}`);
      if (!res.ok) throw new Error('Failed to fetch plant');
      return res.json();
    },

    createPlant: async (body: Partial<Plant> & { name: string }): Promise<Plant> => {
      const res = await fetch(`${base}/plants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to create plant');
      return res.json();
    },

    updatePlant: async (id: number, body: Partial<Plant>): Promise<Plant> => {
      const res = await fetch(`${base}/plants/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to update plant');
      return res.json();
    },

    deletePlant: async (id: number): Promise<void> => {
      const res = await fetch(`${base}/plants/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete plant');
    },

    setPlantStatus: async (id: number, status: string): Promise<Plant> => {
      const res = await fetch(`${base}/plants/${id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error('Failed to set status');
      return res.json();
    },

    bulkDeletePlants: async (ids: number[]): Promise<void> => {
      const res = await fetch(`${base}/plants/bulk-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
      });
      if (!res.ok) throw new Error('Failed to bulk delete plants');
    },

    bulkStatusPlants: async (ids: number[], status: string): Promise<void> => {
      const res = await fetch(`${base}/plants/bulk-status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, status }),
      });
      if (!res.ok) throw new Error('Failed to bulk set status');
    },

    bulkCarePlants: async (ids: number[], care: Record<string, string | null>): Promise<void> => {
      const res = await fetch(`${base}/plants/bulk-care`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, ...care }),
      });
      if (!res.ok) throw new Error('Failed to bulk update care');
    },

    fetchLibraryNames: async (): Promise<Array<{ id: number; name: string }>> => {
      const res = await fetch(`${base}/library?per_page=200`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.entries.map((e: { id: number; name: string }) => ({ id: e.id, name: e.name }));
    },
  };
}
