const BASE = '/api';

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

export async function fetchTasks(params?: { garden_id?: number; completed?: boolean }): Promise<Task[]> {
  const q = new URLSearchParams();
  if (params?.garden_id != null) q.set('garden_id', String(params.garden_id));
  if (params?.completed != null) q.set('completed', String(params.completed));
  const res = await fetch(`${BASE}/tasks?${q}`);
  if (!res.ok) throw new Error('Failed to fetch tasks');
  return res.json();
}

export async function fetchTask(id: number): Promise<Task> {
  const res = await fetch(`${BASE}/tasks/${id}`);
  if (!res.ok) throw new Error('Failed to fetch task');
  return res.json();
}

export async function createTask(body: Partial<Task>): Promise<Task> {
  const res = await fetch(`${BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create task');
  return res.json();
}

export async function updateTask(id: number, body: Partial<Task>): Promise<Task> {
  const res = await fetch(`${BASE}/tasks/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to update task');
  return res.json();
}

export async function toggleTaskComplete(id: number): Promise<Task> {
  const res = await fetch(`${BASE}/tasks/${id}/complete`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to toggle task');
  return res.json();
}

export async function deleteTask(id: number): Promise<void> {
  const res = await fetch(`${BASE}/tasks/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete task');
}
