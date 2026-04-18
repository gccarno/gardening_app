import { Link } from 'react-router-dom';

function parseDate(s: string | null | undefined): Date | null {
  return s ? new Date(s + 'T00:00:00') : null;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d); r.setDate(r.getDate() + n); return r;
}
function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }
function fmtDate(d: Date) { return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }

export interface GanttRow {
  id: number;
  name: string;
  count?: number;       // grouped instance count
  status: string;
  planted: string | null;
  harvest: string | null;
  transplant: string | null;
  germDays: number | null;
  daysToHarvest: number | null;
  sowIndoorWeeks: number | null;
  directSowOffset: number | null;
  transplantOffset: number | null;
  tempMaxF: number | null;
  href?: string;        // link target; if omitted, label is plain text
}

export default function GanttChart({
  rows,
  filter,
  lastFrost,
  firstFallFrost,
}: {
  rows: GanttRow[];
  filter: string;
  lastFrost: Date | null;
  firstFallFrost: Date | null;
}) {
  const today = new Date();
  const year = today.getFullYear();
  const viewMin = new Date(year, 0, 1);
  const viewMax = new Date(year + 1, 0, 1);
  const span = viewMax.getTime() - viewMin.getTime();
  const pct = (d: Date) => clamp((d.getTime() - viewMin.getTime()) / span * 100, 0, 100);
  const todayPct = pct(today);

  const months = Array.from({ length: 12 }, (_, m) => ({
    label: new Date(year, m, 1).toLocaleDateString('en-US', { month: 'short' }),
    p: pct(new Date(year, m, 1)),
  }));

  function normToYear(d: Date): Date {
    return new Date(year, d.getMonth(), d.getDate());
  }
  const frost = lastFrost ? normToYear(lastFrost) : null;
  const fallFrost = firstFallFrost ? normToYear(firstFallFrost) : null;
  const frostPct = frost ? pct(frost) : null;
  const fallFrostPct = fallFrost ? pct(fallFrost) : null;

  const filtered = rows
    .filter(p => filter === 'all' || p.status === filter)
    .sort((a, b) => {
      if (a.status !== b.status) return a.status === 'growing' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  const groups: { status: string; items: GanttRow[] }[] = [];
  for (const row of filtered) {
    const last = groups[groups.length - 1];
    if (last?.status === row.status) last.items.push(row);
    else groups.push({ status: row.status, items: [row] });
  }

  const chartHeight = filtered.length * 36 + groups.length * 32 + 40;

  return (
    <div className="gantt-chart">
      <div className="gantt-inner">
        {/* Month header */}
        <div className="gantt-header">
          <div className="gantt-header__spacer" />
          <div className="gantt-header__months" style={{ position: 'relative', flex: 1, height: '24px' }}>
            {months.map(mk => (
              <div key={mk.label} className="gantt-header__month-label" style={{ left: mk.p + '%' }}>{mk.label}</div>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="gantt-legend">
          <span><span className="gantt-swatch gantt-swatch--indoor" />Indoors</span>
          <span><span className="gantt-swatch gantt-swatch--grow" />Growing</span>
          <span><span className="gantt-swatch gantt-swatch--fall" />Fall Planting</span>
          <span><span className="gantt-swatch gantt-swatch--harvest" />Harvest</span>
          <span><span className="gantt-swatch gantt-swatch--today" />Today</span>
          {frostPct !== null && <span style={{ color: '#3a8c5a', fontSize: '0.78rem' }}>❄ Spring Frost</span>}
          {fallFrostPct !== null && <span style={{ color: '#c07820', fontSize: '0.78rem' }}>🍂 Fall Frost</span>}
        </div>

        {/* Chart body */}
        <div style={{ position: 'relative' }}>
          {/* Global frost lines */}
          {frostPct !== null && (
            <div className="gantt-frost-line gantt-frost-line--spring"
                 style={{ left: frostPct + '%', height: chartHeight + 'px' }}
                 title={`Last Spring Frost: ${fmtDate(frost!)}`}>
              <span className="gantt-frost-label">❄ {fmtDate(frost!)}</span>
            </div>
          )}
          {fallFrostPct !== null && (
            <div className="gantt-frost-line gantt-frost-line--fall"
                 style={{ left: fallFrostPct + '%', height: chartHeight + 'px' }}
                 title={`First Fall Frost: ${fmtDate(fallFrost!)}`}>
              <span className="gantt-frost-label gantt-frost-label--fall">🍂 {fmtDate(fallFrost!)}</span>
            </div>
          )}

          {groups.map(g => (
            <div key={g.status}>
              <div className={`gantt-section-header gantt-section-header--${g.status}`}>
                {g.status === 'growing' ? 'Growing' : 'Planning'}
              </div>
              {g.items.map(p => {
                // Ideal dates from frost + library offsets
                const idealStartIndoors = frost && p.sowIndoorWeeks != null
                  ? addDays(frost, -p.sowIndoorWeeks * 7) : null;
                const idealDirectSow = frost && p.directSowOffset != null
                  ? addDays(frost, p.directSowOffset * 7) : null;
                const idealTransplant = frost && p.transplantOffset != null
                  ? addDays(frost, p.transplantOffset * 7) : null;

                const planted = parseDate(p.planted);
                const harvest = parseDate(p.harvest);
                const transplant = parseDate(p.transplant);

                const barStart = planted ?? idealStartIndoors ?? idealDirectSow ?? null;
                if (!barStart) return null;

                const germEnd = p.germDays ? addDays(barStart, p.germDays) : null;
                const growStart = transplant ?? idealTransplant ?? germEnd ?? barStart;
                let effectiveHarvest = harvest;
                if (!effectiveHarvest && p.daysToHarvest) {
                  effectiveHarvest = addDays(growStart, p.daysToHarvest);
                }
                const growEnd = effectiveHarvest ?? today;
                const planSuffix = p.status === 'planning' ? '-planning' : '';

                // Cool season fall window
                const isCoolSeason = p.tempMaxF != null && p.tempMaxF <= 75;
                let fallSowStart: Date | null = null;
                let fallSowEnd: Date | null = null;
                if (isCoolSeason && fallFrost && p.daysToHarvest) {
                  const totalDays = p.daysToHarvest + (p.germDays ?? 0);
                  fallSowStart = addDays(fallFrost, -totalDays);
                  fallSowEnd = addDays(fallFrost, -(p.germDays ?? 0));
                }

                const indoorEnd = transplant ?? idealTransplant;
                const indoorWidth = indoorEnd
                  ? Math.max(pct(indoorEnd) - pct(barStart), 0.5)
                  : germEnd
                    ? Math.max(pct(germEnd) - pct(barStart), 0.5)
                    : null;
                const growWidth = Math.max(pct(growEnd) - pct(growStart), 0.5);

                const labelContent = (
                  <>
                    {p.href ? <Link to={p.href}>{p.name}</Link> : p.name}
                    {(p.count ?? 1) > 1 && (
                      <span style={{ background: '#3a6b35', color: '#fff', borderRadius: '8px', padding: '0 4px', fontSize: '0.65rem', marginLeft: '3px', verticalAlign: 'middle' }}>×{p.count}</span>
                    )}
                  </>
                );

                return (
                  <div key={p.id} className={`gantt-row gantt-row--${p.status}`}>
                    <div className="gantt-label" title={p.name}>{labelContent}</div>
                    <div className="gantt-bar-area" style={{ position: 'relative' }}>
                      {months.map(mk => <div key={mk.label} className="gantt-grid-line" style={{ left: mk.p + '%' }} />)}

                      {/* Indoor / germination bar */}
                      {indoorWidth !== null && (
                        <div className={`gantt-bar ${indoorEnd ? 'gantt-bar--indoor' : 'gantt-bar--germ'}`}
                             style={{ left: pct(barStart) + '%', width: indoorWidth + '%' }}
                             title={indoorEnd
                               ? `Start Indoors: ${fmtDate(barStart)} → ${fmtDate(indoorEnd)} (${p.germDays ?? '?'} days germ)`
                               : `Germination: ${p.germDays} days`}>
                          {indoorWidth > 4 && p.germDays && (
                            <span className="gantt-bar-label">{p.germDays}d</span>
                          )}
                        </div>
                      )}

                      {/* Growing bar */}
                      <div className={`gantt-bar gantt-bar--growing${planSuffix}`}
                           style={{ left: pct(growStart) + '%', width: growWidth + '%' }}
                           title={effectiveHarvest
                             ? `Growing → Harvest: ${fmtDate(effectiveHarvest)}${harvest ? '' : ' (est.)'}`
                             : 'Growing (no harvest date)'}>
                        {growWidth > 6 && p.daysToHarvest && (
                          <span className="gantt-bar-label">{p.daysToHarvest}d</span>
                        )}
                      </div>

                      {/* Harvest marker */}
                      {effectiveHarvest && (
                        <div className="gantt-harvest-marker" style={{ left: pct(effectiveHarvest) + '%' }}
                             title={`Harvest: ${fmtDate(effectiveHarvest)}${harvest ? '' : ' (est.)'}`} />
                      )}

                      {/* Fall window bar */}
                      {fallSowStart && fallSowEnd && (
                        <div className="gantt-bar gantt-bar--fall"
                             style={{ left: pct(fallSowStart) + '%', width: Math.max(pct(fallSowEnd) - pct(fallSowStart), 0.5) + '%' }}
                             title={`Fall planting: sow ${fmtDate(fallSowStart)}, harvest before ${fmtDate(fallFrost!)}`}>
                          {Math.max(pct(fallSowEnd) - pct(fallSowStart), 0) > 4 && p.daysToHarvest && (
                            <span className="gantt-bar-label">{p.daysToHarvest}d</span>
                          )}
                        </div>
                      )}

                      {/* Milestone markers */}
                      {idealStartIndoors && (
                        <div className="gantt-milestone gantt-milestone--indoor"
                             style={{ left: pct(idealStartIndoors) + '%' }}
                             title={`🪴 Start Indoors: ${fmtDate(idealStartIndoors)}`} />
                      )}
                      {idealDirectSow && (
                        <div className="gantt-milestone gantt-milestone--sow"
                             style={{ left: pct(idealDirectSow) + '%' }}
                             title={`🌱 Direct Sow: ${fmtDate(idealDirectSow)}`} />
                      )}
                      {idealTransplant && (
                        <div className="gantt-milestone gantt-milestone--transplant"
                             style={{ left: pct(idealTransplant) + '%' }}
                             title={`🌿 Transplant Out: ${fmtDate(idealTransplant)}`} />
                      )}

                      {todayPct > 0 && todayPct < 100 && (
                        <div className="gantt-today-line" style={{ left: todayPct + '%' }} />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
