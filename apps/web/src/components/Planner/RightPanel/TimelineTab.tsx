import React from 'react';
import GanttChart, { type GanttRow } from '../../GanttChart';
import { GardenPlant } from '../types';

interface Props {
  gardenPlants: GardenPlant[];
  lastFrostDate?: string | null;
  firstFrostDate?: string | null;
}

export default function TimelineTab({ gardenPlants, lastFrostDate, firstFrostDate }: Props) {
  const groupMap = new Map<string, GardenPlant[]>();
  for (const p of gardenPlants) {
    const key = p.library_id != null ? `lib_${p.library_id}` : `name_${p.name}`;
    if (!groupMap.has(key)) groupMap.set(key, []);
    groupMap.get(key)!.push(p);
  }
  const ganttRows: GanttRow[] = [...groupMap.values()].map(group => {
    const planted    = group.map(p => p.planted_date).filter(Boolean).sort()[0] ?? null;
    const transplant = group.map(p => p.transplant_date).filter(Boolean).sort()[0] ?? null;
    const harvest    = group.map(p => p.expected_harvest).filter(Boolean).sort().at(-1) ?? null;
    const rep = group[0];
    const status = group.some(p => p.status === 'growing') ? 'growing' : (rep.status || 'planning');
    return {
      id: rep.id,
      name: rep.name,
      count: group.length,
      status,
      planted: planted ?? null,
      harvest: harvest ?? null,
      transplant: transplant ?? null,
      germDays: rep.days_to_germination ?? null,
      daysToHarvest: rep.days_to_harvest ?? null,
      sowIndoorWeeks: rep.sow_indoor_weeks ?? null,
      directSowOffset: rep.direct_sow_offset ?? null,
      transplantOffset: rep.transplant_offset ?? null,
      tempMaxF: rep.temp_max_f ?? null,
      href: `/plants/${rep.id}`,
    };
  });

  const lastFrost = lastFrostDate ? new Date(lastFrostDate + 'T00:00:00') : null;
  const firstFallFrost = firstFrostDate ? new Date(firstFrostDate + 'T00:00:00') : null;

  return (
    <div>
      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#3a5c37', marginBottom: '0.5rem' }}>Plant Timeline</div>
      {ganttRows.length === 0 ? (
        <p className="muted" style={{ fontSize: '0.78rem' }}>No plants yet. Add plants to see the timeline.</p>
      ) : (
        <GanttChart rows={ganttRows} filter="all" lastFrost={lastFrost} firstFallFrost={firstFallFrost} />
      )}
    </div>
  );
}
