import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTask, useUpdateTask, useDeleteTask } from '../hooks/useTasks';
import { useGardens } from '../hooks/useGardens';
import { usePlants } from '../hooks/usePlants';
import { useBeds } from '../hooks/useBeds';

const TASK_TYPES = ['other','seeding','transplanting','watering','fertilizing','mulching','weeding','harvest'];

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const taskId = parseInt(id!);
  const { data: task, isLoading } = useTask(taskId);
  const { data: gardens } = useGardens();
  const { data: plants } = usePlants();
  const { data: beds } = useBeds();
  const updateMut = useUpdateTask();
  const deleteMut = useDeleteTask();

  const [form, setForm] = useState({
    title: '', task_type: 'other', due_date: '',
    plant_id: '', garden_id: '', bed_id: '', description: '',
  });

  useEffect(() => {
    if (task) {
      setForm({
        title:       task.title ?? '',
        task_type:   task.task_type ?? 'other',
        due_date:    task.due_date ?? '',
        plant_id:    task.plant_id   ? String(task.plant_id)  : '',
        garden_id:   task.garden_id  ? String(task.garden_id) : '',
        bed_id:      task.bed_id     ? String(task.bed_id)    : '',
        description: task.description ?? '',
      });
    }
  }, [task]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await updateMut.mutateAsync({
      id:          taskId,
      title:       form.title,
      task_type:   form.task_type,
      due_date:    form.due_date || undefined,
      plant_id:    form.plant_id  ? parseInt(form.plant_id)  : undefined,
      garden_id:   form.garden_id ? parseInt(form.garden_id) : undefined,
      bed_id:      form.bed_id    ? parseInt(form.bed_id)    : undefined,
      description: form.description || undefined,
    });
    nav('/tasks');
  }

  if (isLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;
  if (!task) return <p className="muted" style={{ padding: '2rem' }}>Task not found.</p>;

  return (
    <>
      <h1>{task.title}</h1>
      <h2>Edit Task</h2>
      <form onSubmit={handleSubmit} className="form">
        <label>Title <input type="text" name="title" value={form.title} onChange={handleChange} required /></label>
        <label>Type
          <select name="task_type" value={form.task_type} onChange={handleChange}>
            {TASK_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select>
        </label>
        <label>Due Date <input type="date" name="due_date" value={form.due_date} onChange={handleChange} /></label>
        <label>Plant
          <select name="plant_id" value={form.plant_id} onChange={handleChange}>
            <option value="">— None —</option>
            {plants?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label>Garden
          <select name="garden_id" value={form.garden_id} onChange={handleChange}>
            <option value="">— None —</option>
            {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
        <label>Bed
          <select name="bed_id" value={form.bed_id} onChange={handleChange}>
            <option value="">— None —</option>
            {beds?.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label>Description <textarea name="description" rows={3} value={form.description} onChange={handleChange} /></label>
        <button type="submit" disabled={updateMut.isPending}>Save Changes</button>
      </form>

      {task.completed_date && <p className="muted">Completed: {task.completed_date}</p>}

      <p><Link to="/tasks">← Back to Tasks</Link></p>
    </>
  );
}
