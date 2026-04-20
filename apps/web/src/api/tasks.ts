import { createTasksApi } from '@garden/shared';
export type { Task } from '@garden/shared';

export const {
  fetchTasks, fetchTask, createTask, updateTask, toggleTaskComplete, deleteTask,
} = createTasksApi('/api');
