import React, { useState } from 'react';

interface Task {
  id: number;
  title: string;
  task_type?: string;
  due_date?: string;
  completed?: boolean;
  plant_name?: string;
}

interface Props {
  tasks: unknown[];
  gardenId: number;
  onAddTask: (e: React.FormEvent) => void;
  taskForm: { title: string; due_date: string; description: string };
  setTaskForm: React.Dispatch<React.SetStateAction<{ title: string; due_date: string; description: string }>>;
  taskSaved: string;
}

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DAY_LABELS  = ['Su','Mo','Tu','We','Th','Fr','Sa'];
const TYPE_COLORS: Record<string, string> = {
  seeding:'#5a9e54', transplanting:'#3a8c5a', watering:'#4a80b4',
  fertilizing:'#c4942a', mulching:'#8a6a40', weeding:'#9a5a5a',
  harvest:'#d4a84b', other:'#7a907a',
};

export default function CalendarTab({ tasks, onAddTask, taskForm, setTaskForm, taskSaved }: Props) {
  const [calYear, setCalYear] = useState(() => new Date().getFullYear());
  const [calMonth, setCalMonth] = useState(() => new Date().getMonth());

  const totalDays   = new Date(calYear, calMonth + 1, 0).getDate();
  const startOffset = new Date(calYear, calMonth, 1).getDay();
  const cells: (number | null)[] = [...Array(startOffset).fill(null), ...Array.from({ length: totalDays }, (_, i) => i + 1)];
  while (cells.length % 7 !== 0) cells.push(null);

  const todayStr = new Date().toISOString().slice(0, 10);
  const allTasks = tasks as Task[];

  function prevMonth() { if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11); } else setCalMonth(m => m - 1); }
  function nextMonth() { if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0); } else setCalMonth(m => m + 1); }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <button className="btn-small btn-link" onClick={prevMonth} style={{ fontSize: '1rem', padding: '0 0.3rem' }}>‹</button>
        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37' }}>{MONTH_NAMES[calMonth]} {calYear}</span>
        <button className="btn-small btn-link" onClick={nextMonth} style={{ fontSize: '1rem', padding: '0 0.3rem' }}>›</button>
      </div>

      {/* Day headers */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1, marginBottom: 2 }}>
        {DAY_LABELS.map(d => (
          <div key={d} style={{ textAlign: 'center', fontSize: '0.62rem', color: '#9ab49a', fontWeight: 600 }}>{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1 }}>
        {cells.map((day, i) => {
          if (!day) return <div key={`e-${i}`} style={{ minHeight: 28 }} />;
          const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const isToday = dateStr === todayStr;
          const dayTasks = allTasks.filter(t => t.due_date === dateStr);
          const hasOverdue = dayTasks.some(t => !t.completed && dateStr < todayStr);
          return (
            <div key={dateStr} style={{ minHeight: 28, padding: '1px 2px', background: isToday ? '#d4edcc' : hasOverdue ? '#fce8e8' : '#f8fbf7', borderRadius: 3, border: isToday ? '1px solid #3a6b35' : '1px solid #e8f0e4', fontSize: '0.65rem' }}>
              <div style={{ fontWeight: isToday ? 700 : 400, color: isToday ? '#3a6b35' : '#5a7a5a', marginBottom: 1 }}>{day}</div>
              {dayTasks.slice(0, 3).map(t => (
                <div key={t.id}
                  title={t.title + (t.plant_name ? ' · ' + t.plant_name : '')}
                  style={{ background: t.completed ? '#c8d8c8' : (TYPE_COLORS[t.task_type ?? 'other'] ?? TYPE_COLORS.other), color: '#fff', borderRadius: 2, padding: '0 2px', marginBottom: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer', opacity: t.completed ? 0.6 : 1 }}>
                  {t.title}
                </div>
              ))}
              {dayTasks.length > 3 && <div style={{ fontSize: '0.6rem', color: '#7a907a' }}>+{dayTasks.length - 3}</div>}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: '0.62rem', color: '#7a907a' }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, background: color, borderRadius: 2 }} />{type}
          </span>
        ))}
      </div>

      {/* Add task form */}
      <details style={{ marginTop: '0.5rem' }}>
        <summary style={{ fontSize: '0.78rem', color: '#3a6b35', cursor: 'pointer' }}>+ Add Task</summary>
        <form onSubmit={onAddTask} style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          <input type="text" placeholder="Task title" value={taskForm.title} onChange={e => setTaskForm(f => ({ ...f, title: e.target.value }))} required style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.2rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
          <input type="date" value={taskForm.due_date} onChange={e => setTaskForm(f => ({ ...f, due_date: e.target.value }))} style={{ font: 'inherit', fontSize: '0.78rem', padding: '0.2rem', border: '1px solid #c0d4be', borderRadius: '3px' }} />
          <button type="submit" className="btn-small" style={{ fontSize: '0.75rem' }}>Add</button>
          {taskSaved && <span className="muted" style={{ fontSize: '0.75rem' }}>{taskSaved}</span>}
        </form>
      </details>
    </div>
  );
}
