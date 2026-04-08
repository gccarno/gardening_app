import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTasks, useCreateTask, useToggleTask, useDeleteTask } from '../hooks/useTasks';
import { useGardens } from '../hooks/useGardens';
import { usePlants } from '../hooks/usePlants';
import { useBeds } from '../hooks/useBeds';

const TASK_TYPES = ['other','seeding','transplanting','watering','fertilizing','mulching','weeding','harvest'];

const TYPE_COLORS: Record<string, string> = {
  seeding:       '#5a9e54',
  transplanting: '#3a8c5a',
  watering:      '#4a80b4',
  fertilizing:   '#c4942a',
  mulching:      '#8a6a40',
  weeding:       '#9a5a5a',
  harvest:       '#d4a84b',
  other:         '#7a907a',
};

// ── Calendar helpers ──────────────────────────────────────────────────────────
function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}
function firstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay(); // 0=Sun
}
const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const DAY_LABELS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

export default function TaskList() {
  const { data: tasks, isLoading } = useTasks();
  const { data: gardens } = useGardens();
  const { data: plants } = usePlants();
  const { data: beds } = useBeds();
  const createMut = useCreateTask();
  const toggleMut = useToggleTask();
  const deleteMut = useDeleteTask();
  const navigate = useNavigate();

  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');

  const today = new Date();
  const [calYear, setCalYear]   = useState(today.getFullYear());
  const [calMonth, setCalMonth] = useState(today.getMonth());

  const [form, setForm] = useState({
    title: '', task_type: 'other', due_date: '',
    plant_id: '', garden_id: '', bed_id: '', description: '',
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await createMut.mutateAsync({
      title:       form.title,
      task_type:   form.task_type,
      due_date:    form.due_date || undefined,
      plant_id:    form.plant_id  ? parseInt(form.plant_id)  : undefined,
      garden_id:   form.garden_id ? parseInt(form.garden_id) : undefined,
      bed_id:      form.bed_id    ? parseInt(form.bed_id)    : undefined,
      description: form.description || undefined,
    });
    setForm({ title: '', task_type: 'other', due_date: '', plant_id: '', garden_id: '', bed_id: '', description: '' });
  }

  function prevMonth() {
    if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11); }
    else setCalMonth(m => m - 1);
  }
  function nextMonth() {
    if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0); }
    else setCalMonth(m => m + 1);
  }

  const todayStr = today.toISOString().slice(0, 10);

  // Build calendar grid
  function renderCalendar() {
    const totalDays   = daysInMonth(calYear, calMonth);
    const startOffset = firstDayOfMonth(calYear, calMonth);
    const cells: (number | null)[] = [
      ...Array(startOffset).fill(null),
      ...Array.from({ length: totalDays }, (_, i) => i + 1),
    ];
    // pad to complete last row
    while (cells.length % 7 !== 0) cells.push(null);

    return (
      <div className="cal-wrapper">
        <div className="cal-nav">
          <button className="btn-small" onClick={prevMonth}>‹</button>
          <span className="cal-month-label">{MONTH_NAMES[calMonth]} {calYear}</span>
          <button className="btn-small" onClick={nextMonth}>›</button>
        </div>
        <div className="cal-grid">
          {DAY_LABELS.map(d => (
            <div key={d} className="cal-day-header">{d}</div>
          ))}
          {cells.map((day, i) => {
            if (!day) return <div key={`empty-${i}`} className="cal-cell cal-cell--empty" />;
            const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const isToday = dateStr === todayStr;
            const dayTasks = (tasks ?? []).filter(t => t.due_date === dateStr);
            const hasOverdue = dayTasks.some(t => !t.completed && dateStr < todayStr);
            return (
              <div
                key={dateStr}
                className={[
                  'cal-cell',
                  isToday ? 'cal-cell--today' : '',
                  hasOverdue ? 'cal-cell--overdue' : '',
                ].filter(Boolean).join(' ')}
              >
                <span className="cal-day-num">{day}</span>
                {dayTasks.map(t => (
                  <button
                    key={t.id}
                    className={`cal-chip ${t.completed ? 'cal-chip--done' : ''}`}
                    style={{ background: t.completed ? '#c8d8c8' : (TYPE_COLORS[t.task_type ?? 'other'] ?? TYPE_COLORS.other) }}
                    title={t.title}
                    onClick={() => navigate(`/tasks/${t.id}`)}
                  >
                    {t.title}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <>
      <h1>Tasks</h1>

      <section>
        <h2>Add Task</h2>
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
          <label>Description <textarea name="description" rows={2} value={form.description} onChange={handleChange} /></label>
          <button type="submit" disabled={createMut.isPending}>Add Task</button>
        </form>
      </section>

      <section>
        <div className="tasks-view-header">
          <h2 style={{ margin: 0 }}>All Tasks</h2>
          <div className="tasks-view-toggle">
            <button
              className={viewMode === 'list' ? 'active' : ''}
              onClick={() => setViewMode('list')}
            >List</button>
            <button
              className={viewMode === 'calendar' ? 'active' : ''}
              onClick={() => setViewMode('calendar')}
            >Calendar</button>
          </div>
        </div>

        {isLoading && <p className="muted">Loading…</p>}

        {viewMode === 'calendar' && renderCalendar()}

        {viewMode === 'list' && (
          <>
            {tasks && tasks.length === 0 && <p className="muted">No tasks yet.</p>}
            {tasks && tasks.length > 0 && (
              <ul className="card-list">
                {tasks.map(task => (
                  <li key={task.id} className={`card ${task.completed ? 'completed' : ''}`}>
                    <div className="task-row">
                      <span>
                        <strong>{task.title}</strong>
                        {task.task_type && task.task_type !== 'other' && <span className="muted"> [{task.task_type}]</span>}
                        {task.due_date && <span className="muted"> Due {task.due_date}</span>}
                        {task.completed && task.completed_date && <span className="muted"> Done {task.completed_date}</span>}
                        {task.plant_name && <span className="muted"> — {task.plant_name}</span>}
                        {task.garden_name && <span className="muted"> — {task.garden_name}</span>}
                        {task.description && <span className="muted"> {task.description}</span>}
                      </span>
                      <span className="task-actions">
                        <Link to={`/tasks/${task.id}`} className="btn-small btn-link">Edit</Link>
                        <button
                          className="btn-small"
                          onClick={() => toggleMut.mutate(task.id)}
                        >
                          {task.completed ? 'Undo' : 'Done'}
                        </button>
                        <button
                          className="btn-small btn-danger"
                          onClick={() => { if (confirm('Delete task?')) deleteMut.mutate(task.id); }}
                        >
                          Delete
                        </button>
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </>
  );
}
