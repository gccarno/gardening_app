import { apiFetch } from './http';

export interface Task {
  id: number;
  title: string;
  description?: string;
  task_type?: string;
  due_date?: string;
  completed: boolean;
  completed_date?: string;
  plant_id?: number;
  garden_id?: number;
  bed_id?: number;
  plant_name?: string;
  garden_name?: string;
  bed_name?: string;
}

export function createTasksApi(base: string) {
  return {
    fetchTasks: async (params?: { garden_id?: number; completed?: boolean }): Promise<Task[]> => {
      const q = new URLSearchParams();
      if (params?.garden_id != null) q.set('garden_id', String(params.garden_id));
      if (params?.completed != null) q.set('completed', String(params.completed));
      const res = await apiFetch(`${base}/tasks?${q}`);
      if (!res.ok) throw new Error('Failed to fetch tasks');
      return res.json();
    },

    fetchTask: async (id: number): Promise<Task> => {
      const res = await apiFetch(`${base}/tasks/${id}`);
      if (!res.ok) throw new Error('Failed to fetch task');
      return res.json();
    },

    createTask: async (body: Partial<Task>): Promise<Task> => {
      const res = await apiFetch(`${base}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to create task');
      return res.json();
    },

    updateTask: async (id: number, body: Partial<Task>): Promise<Task> => {
      const res = await apiFetch(`${base}/tasks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to update task');
      return res.json();
    },

    toggleTaskComplete: async (id: number): Promise<Task> => {
      const res = await apiFetch(`${base}/tasks/${id}/complete`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to toggle task');
      return res.json();
    },

    deleteTask: async (id: number): Promise<void> => {
      const res = await apiFetch(`${base}/tasks/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete task');
    },
  };
}
