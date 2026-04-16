import { useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useLibraryEntry, usePatchLibraryEntry } from '../hooks/useLibrary';

type FilterMode = 'all' | 'diff' | 'missing';

// Human-readable labels for plant library fields
const FIELD_LABELS: Record<string, string> = {
  name: 'Name', scientific_name: 'Scientific Name', type: 'Type',
  sunlight: 'Sunlight', water: 'Watering', spacing_in: 'Spacing (in)',
  days_to_germination: 'Days to Germination', days_to_harvest: 'Days to Harvest',
  difficulty: 'Difficulty', min_zone: 'Min Zone', max_zone: 'Max Zone',
  temp_min_f: 'Min Temp (°F)', temp_max_f: 'Max Temp (°F)',
  soil_ph_min: 'Soil pH Min', soil_ph_max: 'Soil pH Max', soil_type: 'Soil Type',
  notes: 'Growing Notes', family: 'Plant Family', layer: 'Garden Layer',
  edible_parts: 'Edible Parts', permapeople_description: 'Description',
  good_neighbors: 'Good Companions', bad_neighbors: 'Bad Companions',
  sow_indoor_weeks: 'Sow Indoors (weeks before frost)',
  direct_sow_offset: 'Direct Sow Offset (weeks)',
  transplant_offset: 'Transplant Offset (weeks)',
  how_to_grow: 'How to Grow', faqs: 'FAQs', nutrition: 'Nutrition',
  observations: 'Native Range / Observations', vegetable: 'Vegetable',
  edible: 'Edible', toxicity: 'Toxicity', duration: 'Life Cycle',
  ligneous_type: 'Ligneous Type', growth_habit: 'Growth Habit',
  growth_form: 'Growth Form', growth_rate: 'Growth Rate',
  nitrogen_fixation: 'Nitrogen Fixation',
  average_height_cm: 'Avg Height (cm)', maximum_height_cm: 'Max Height (cm)',
  spread_cm: 'Spread (cm)', row_spacing_cm: 'Row Spacing (cm)',
  minimum_root_depth_cm: 'Min Root Depth (cm)',
  soil_nutriments: 'Soil Nutriments', soil_salinity: 'Soil Salinity',
  atmospheric_humidity: 'Atmospheric Humidity',
  precipitation_min_mm: 'Precipitation Min (mm)', precipitation_max_mm: 'Precipitation Max (mm)',
  bloom_months: 'Bloom Months', fruit_months: 'Fruit Months', growth_months: 'Growth Months',
  flower_color: 'Flower Color', flower_conspicuous: 'Flower Conspicuous',
  foliage_color: 'Foliage Color', foliage_texture: 'Foliage Texture',
  leaf_retention: 'Leaf Retention', fruit_color: 'Fruit Color',
  fruit_conspicuous: 'Fruit Conspicuous', fruit_shape: 'Fruit Shape',
  seed_persistence: 'Seed Persistence',
  poisonous_to_pets: 'Poisonous to Pets', poisonous_to_humans: 'Poisonous to Humans',
  drought_tolerant: 'Drought Tolerant', salt_tolerant: 'Salt Tolerant',
  thorny: 'Thorny', invasive: 'Invasive', rare: 'Rare', tropical: 'Tropical',
  indoor: 'Indoor', cuisine: 'Cuisine', medicinal: 'Medicinal',
  attracts: 'Attracts', propagation_methods: 'Propagation Methods',
  harvest_season: 'Harvest Season', harvest_method: 'Harvest Method',
  fruiting_season: 'Fruiting Season', pruning_months: 'Pruning Months',
  genus: 'Genus',
};

// Fields shown in the diff (patchable, excluding identity/image)
const DIFF_FIELDS = Object.keys(FIELD_LABELS);

// Fields that hold JSON data (arrays or objects) — render as readable text
const JSON_FIELDS = new Set(['good_neighbors', 'bad_neighbors', 'how_to_grow', 'faqs',
  'nutrition', 'attracts', 'propagation_methods', 'pruning_months',
  'bloom_months', 'fruit_months', 'growth_months']);

function displayValue(field: string, val: unknown): string {
  if (val === null || val === undefined || val === '') return '';
  if (JSON_FIELDS.has(field)) {
    if (typeof val === 'string') {
      try { val = JSON.parse(val); } catch { return val as string; }
    }
    if (Array.isArray(val)) return val.join(', ');
    if (typeof val === 'object') return JSON.stringify(val, null, 2);
  }
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  return String(val);
}

function isEmpty(val: unknown): boolean {
  return val === null || val === undefined || val === '' ||
    (Array.isArray(val) && val.length === 0);
}

export default function PlantDiff() {
  const [searchParams] = useSearchParams();
  const aId = parseInt(searchParams.get('a') || '0');
  const bId = parseInt(searchParams.get('b') || '0');

  const { data: plantA } = useLibraryEntry(aId);
  const { data: plantB } = useLibraryEntry(bId);
  const patchA = usePatchLibraryEntry(aId);
  const patchB = usePatchLibraryEntry(bId);

  const [filter, setFilter] = useState<FilterMode>('diff');
  // Local overrides for optimistic UI: { [plantId]: { [field]: value } }
  const [overrides, setOverrides] = useState<Record<number, Record<string, unknown>>>({});
  const [copying, setCopying] = useState<string>(''); // "field:direction" being copied

  if (!aId || !bId) {
    return (
      <div style={{ padding: '2rem' }}>
        <p className="muted">Select two plants to compare. <Link to="/library">← Back to Library</Link></p>
      </div>
    );
  }

  if (!plantA || !plantB) {
    return <p className="muted" style={{ padding: '2rem' }}>Loading plants…</p>;
  }

  function getVal(plant: Record<string, unknown>, id: number, field: string): unknown {
    return overrides[id]?.[field] !== undefined ? overrides[id][field] : plant[field];
  }

  async function copyField(field: string, fromPlant: Record<string, unknown>, fromId: number, toPlantId: number) {
    const key = `${field}:${toPlantId}`;
    setCopying(key);
    const rawVal = fromPlant[field];
    // For JSON fields, serialize back to string if the API stores them as strings
    let apiVal = rawVal;
    if (JSON_FIELDS.has(field) && (Array.isArray(rawVal) || (rawVal && typeof rawVal === 'object'))) {
      apiVal = JSON.stringify(rawVal);
    }
    try {
      const patcher = toPlantId === aId ? patchA : patchB;
      await patcher.mutateAsync({ [field]: apiVal });
      setOverrides(prev => ({
        ...prev,
        [toPlantId]: { ...(prev[toPlantId] || {}), [field]: rawVal },
      }));
    } catch { /* error silently */ }
    setCopying('');
  }

  async function fillAllMissing(targetId: number, sourceId: number) {
    const target = targetId === aId ? plantA : plantB;
    const source = sourceId === aId ? plantA : plantB;
    const fields: Record<string, unknown> = {};
    for (const field of DIFF_FIELDS) {
      const tVal = getVal(target, targetId, field);
      const sVal = getVal(source, sourceId, field);
      if (isEmpty(tVal) && !isEmpty(sVal)) {
        let apiVal = sVal;
        if (JSON_FIELDS.has(field) && (Array.isArray(sVal) || (sVal && typeof sVal === 'object'))) {
          apiVal = JSON.stringify(sVal);
        }
        fields[field] = apiVal;
      }
    }
    if (!Object.keys(fields).length) return;
    const patcher = targetId === aId ? patchA : patchB;
    try {
      await patcher.mutateAsync(fields);
      const localOverride: Record<string, unknown> = {};
      for (const field of Object.keys(fields)) {
        localOverride[field] = getVal(source, sourceId, field);
      }
      setOverrides(prev => ({
        ...prev,
        [targetId]: { ...(prev[targetId] || {}), ...localOverride },
      }));
    } catch { /* ignore */ }
  }

  const rows = DIFF_FIELDS.map(field => {
    const aVal = getVal(plantA, aId, field);
    const bVal = getVal(plantB, bId, field);
    const aEmpty = isEmpty(aVal);
    const bEmpty = isEmpty(bVal);
    const differ = displayValue(field, aVal) !== displayValue(field, bVal);
    return { field, aVal, bVal, aEmpty, bEmpty, differ };
  }).filter(row => {
    if (filter === 'diff') return row.differ;
    if (filter === 'missing') return (row.aEmpty && !row.bEmpty) || (!row.aEmpty && row.bEmpty);
    return true;
  });

  const missingInA = DIFF_FIELDS.filter(f => {
    const aVal = getVal(plantA, aId, f);
    const bVal = getVal(plantB, bId, f);
    return isEmpty(aVal) && !isEmpty(bVal);
  }).length;
  const missingInB = DIFF_FIELDS.filter(f => {
    const aVal = getVal(plantA, aId, f);
    const bVal = getVal(plantB, bId, f);
    return isEmpty(bVal) && !isEmpty(aVal);
  }).length;

  return (
    <div style={{ padding: '1.5rem 2rem' }}>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/library" style={{ color: '#3a6b35', fontSize: '0.85rem' }}>← Back to Library</Link>
      </div>

      <h1 style={{ fontSize: '1.3rem', marginBottom: '0.25rem' }}>Compare Plants</h1>
      <p className="muted" style={{ marginBottom: '1.25rem', fontSize: '0.9rem' }}>
        <Link to={`/library/${aId}`} style={{ color: '#3a6b35', fontWeight: 600 }}>{plantA.name as string}</Link>
        {' '}↔{' '}
        <Link to={`/library/${bId}`} style={{ color: '#3a6b35', fontWeight: 600 }}>{plantB.name as string}</Link>
      </p>

      {/* Filter toggles */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {(['all', 'diff', 'missing'] as FilterMode[]).map(m => (
          <button
            key={m}
            onClick={() => setFilter(m)}
            style={{
              background: filter === m ? '#3a6b35' : '#f0f7ef',
              color: filter === m ? '#fff' : '#3a5c37',
              border: '1px solid #b0c8ae', borderRadius: '4px',
              padding: '0.28rem 0.65rem', cursor: 'pointer', font: 'inherit', fontSize: '0.85rem',
            }}
          >
            {m === 'all' ? 'All fields' : m === 'diff' ? 'Differences only' : 'Missing values'}
          </button>
        ))}
        <span style={{ marginLeft: '0.5rem', fontSize: '0.82rem', color: '#7a907a' }}>
          {rows.length} field{rows.length !== 1 ? 's' : ''} shown
        </span>
      </div>

      {/* Bulk fill-missing actions */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        {missingInA > 0 && (
          <button
            onClick={() => fillAllMissing(aId, bId)}
            style={{ background: '#fff8e1', border: '1px solid #f0c040', borderRadius: '4px', padding: '0.3rem 0.7rem', cursor: 'pointer', font: 'inherit', fontSize: '0.82rem', color: '#7a5800' }}
          >
            Fill {missingInA} missing in "{plantA.name as string}" from B →
          </button>
        )}
        {missingInB > 0 && (
          <button
            onClick={() => fillAllMissing(bId, aId)}
            style={{ background: '#fff8e1', border: '1px solid #f0c040', borderRadius: '4px', padding: '0.3rem 0.7rem', cursor: 'pointer', font: 'inherit', fontSize: '0.82rem', color: '#7a5800' }}
          >
            ← Fill {missingInB} missing in "{plantB.name as string}" from A
          </button>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="muted">No fields to show with current filter.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #c0d4be', background: '#f4f9f3' }}>
              <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', width: '16%', color: '#3a5c37' }}>Field</th>
              <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', width: '36%', color: '#3a5c37' }}>
                <Link to={`/library/${aId}`} style={{ color: '#3a5c37' }}>{plantA.name as string}</Link>
              </th>
              <th style={{ textAlign: 'center', padding: '0.5rem 0.4rem', width: '8%', color: '#7a907a' }}>Copy</th>
              <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', width: '36%', color: '#3a5c37' }}>
                <Link to={`/library/${bId}`} style={{ color: '#3a5c37' }}>{plantB.name as string}</Link>
              </th>
              <th style={{ width: '4%' }}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ field, aVal, bVal, aEmpty, bEmpty, differ }) => {
              const aDisplay = displayValue(field, aVal);
              const bDisplay = displayValue(field, bVal);
              const isMissing = (aEmpty && !bEmpty) || (!aEmpty && bEmpty);
              const rowBg = isMissing ? '#f0f4ff' : differ ? '#fffbe6' : undefined;
              return (
                <tr key={field} style={{ borderBottom: '1px solid #e8f0e6', background: rowBg, verticalAlign: 'top' }}>
                  <td style={{ padding: '0.45rem 0.75rem', fontWeight: 600, color: '#3a5c37', whiteSpace: 'nowrap' }}>
                    {FIELD_LABELS[field] || field}
                  </td>
                  <td style={{ padding: '0.45rem 0.75rem', color: aEmpty ? '#bbb' : undefined, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {aDisplay || <span style={{ color: '#ccc', fontStyle: 'italic' }}>—</span>}
                  </td>
                  <td style={{ padding: '0.45rem 0.2rem', textAlign: 'center', whiteSpace: 'nowrap' }}>
                    {!bEmpty && (
                      <button
                        title={`Copy "${FIELD_LABELS[field]}" from B to A`}
                        disabled={copying === `${field}:${aId}`}
                        onClick={() => copyField(field, plantB, bId, aId)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3a6b35', fontSize: '1rem', padding: '0 0.15rem' }}
                      >
                        {copying === `${field}:${aId}` ? '…' : '←'}
                      </button>
                    )}
                    {!aEmpty && (
                      <button
                        title={`Copy "${FIELD_LABELS[field]}" from A to B`}
                        disabled={copying === `${field}:${bId}`}
                        onClick={() => copyField(field, plantA, aId, bId)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3a6b35', fontSize: '1rem', padding: '0 0.15rem' }}
                      >
                        {copying === `${field}:${bId}` ? '…' : '→'}
                      </button>
                    )}
                  </td>
                  <td style={{ padding: '0.45rem 0.75rem', color: bEmpty ? '#bbb' : undefined, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {bDisplay || <span style={{ color: '#ccc', fontStyle: 'italic' }}>—</span>}
                  </td>
                  <td></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
