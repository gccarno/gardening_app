import { useState, useEffect, FormEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useLibraryEntry, usePatchLibraryEntry } from '../hooks/useLibrary';

type EditTab = 'core' | 'cultivation' | 'climate' | 'companions' | 'growing' | 'dimensions' | 'appearance' | 'classification' | 'properties' | 'uses';

// Fields stored as JSON arrays in the DB — displayed/edited as comma-separated strings
const JSON_ARRAY_FIELDS = new Set([
  'good_neighbors', 'bad_neighbors', 'bloom_months', 'fruit_months', 'growth_months',
  'attracts', 'propagation_methods', 'pruning_months',
]);

// Fields stored as JSON objects in the DB — displayed/edited as raw JSON text
const JSON_OBJECT_FIELDS = new Set(['how_to_grow', 'faqs', 'nutrition']);

function arrToStr(val: unknown): string {
  if (!val) return '';
  if (Array.isArray(val)) return val.join(', ');
  if (typeof val === 'string') {
    try { const p = JSON.parse(val); return Array.isArray(p) ? p.join(', ') : val; }
    catch { return val; }
  }
  return String(val);
}

function objToStr(val: unknown): string {
  if (!val) return '';
  if (typeof val === 'string') {
    try { return JSON.stringify(JSON.parse(val), null, 2); }
    catch { return val; }
  }
  try { return JSON.stringify(val, null, 2); }
  catch { return ''; }
}

function strToArr(s: string): string {
  const arr = s.split(',').map(x => x.trim()).filter(Boolean);
  return JSON.stringify(arr);
}

export default function LibraryEdit() {
  const { id } = useParams<{ id: string }>();
  const entryId = parseInt(id!);
  const navigate = useNavigate();
  const { data: entry, isLoading } = useLibraryEntry(entryId);
  const patchMut = usePatchLibraryEntry(entryId);

  const [tab, setTab] = useState<EditTab>('core');
  const [form, setForm] = useState<Record<string, string | boolean>>({});
  const [err, setErr] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!entry) return;
    const initial: Record<string, string | boolean> = {};
    for (const [k, v] of Object.entries(entry)) {
      if (JSON_ARRAY_FIELDS.has(k)) {
        initial[k] = arrToStr(v);
      } else if (JSON_OBJECT_FIELDS.has(k)) {
        initial[k] = objToStr(v);
      } else if (typeof v === 'boolean') {
        initial[k] = v;
      } else if (v === null || v === undefined) {
        initial[k] = '';
      } else if (typeof v === 'object') {
        // skip complex nested objects we don't edit (calendar_rows, images, etc.)
      } else {
        initial[k] = String(v);
      }
    }
    setForm(initial);
  }, [entry]);

  function set(field: string, value: string | boolean) {
    setForm(f => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErr('');
    const patch: Record<string, unknown> = {};

    for (const [k, v] of Object.entries(form)) {
      if (JSON_ARRAY_FIELDS.has(k)) {
        patch[k] = strToArr(v as string);
      } else if (JSON_OBJECT_FIELDS.has(k)) {
        const s = (v as string).trim();
        if (!s) { patch[k] = null; continue; }
        try { JSON.parse(s); patch[k] = s; }
        catch { setErr(`Invalid JSON in "${k}" — fix the JSON before saving.`); return; }
      } else if (typeof v === 'boolean') {
        patch[k] = v;
      } else {
        const s = (v as string).trim();
        patch[k] = s === '' ? null : s;
      }
    }

    // Remove non-patchable keys that may have come from the entry
    const NON_PATCHABLE = new Set([
      'id', 'perenual_id', 'trefle_id', 'permapeople_id', 'usda_fdc_id', 'openfarm_id',
      'openfarm_slug', 'trefle_slug', 'permapeople_link', 'cloned_from_id', 'is_custom',
      'cloned_from_name', 'images', 'calendar_rows', 'selected_zone',
    ]);
    for (const k of NON_PATCHABLE) delete patch[k];

    try {
      await patchMut.mutateAsync(patch);
      setSaved(true);
      setTimeout(() => navigate(`/library/${entryId}`), 800);
    } catch {
      setErr('Save failed. Check the console for details.');
    }
  }

  if (isLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;
  if (!entry) return <p className="muted" style={{ padding: '2rem' }}>Entry not found.</p>;

  const tabs: { id: EditTab; label: string }[] = [
    { id: 'core', label: 'Core' },
    { id: 'cultivation', label: 'Cultivation' },
    { id: 'climate', label: 'Climate' },
    { id: 'companions', label: 'Companions' },
    { id: 'growing', label: 'Growing Info' },
    { id: 'dimensions', label: 'Dimensions' },
    { id: 'appearance', label: 'Appearance' },
    { id: 'classification', label: 'Classification' },
    { id: 'properties', label: 'Properties' },
    { id: 'uses', label: 'Uses' },
  ];

  const str = (k: string) => (form[k] as string) ?? '';
  const bool = (k: string) => (form[k] as boolean) ?? false;

  const textInput = (field: string, label: string, type: 'text' | 'number' = 'text') => (
    <label key={field} style={fieldStyle}>
      <span style={labelStyle}>{label}</span>
      <input
        type={type}
        value={str(field)}
        onChange={e => set(field, e.target.value)}
        style={inputStyle}
      />
    </label>
  );

  const textArea = (field: string, label: string, rows = 4) => (
    <label key={field} style={{ ...fieldStyle, alignItems: 'flex-start' }}>
      <span style={{ ...labelStyle, paddingTop: '0.3rem' }}>{label}</span>
      <textarea
        value={str(field)}
        onChange={e => set(field, e.target.value)}
        rows={rows}
        style={{ ...inputStyle, resize: 'vertical', fontFamily: field.startsWith('{') || JSON_OBJECT_FIELDS.has(field) ? 'monospace' : 'inherit' }}
      />
    </label>
  );

  const jsonArea = (field: string, label: string, rows = 6) => (
    <label key={field} style={{ ...fieldStyle, alignItems: 'flex-start' }}>
      <span style={{ ...labelStyle, paddingTop: '0.3rem' }}>{label}</span>
      <textarea
        value={str(field)}
        onChange={e => set(field, e.target.value)}
        rows={rows}
        spellCheck={false}
        style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace', fontSize: '0.82rem' }}
      />
    </label>
  );

  const checkBox = (field: string, label: string) => (
    <label key={field} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', minWidth: '180px' }}>
      <input
        type="checkbox"
        checked={bool(field)}
        onChange={e => set(field, e.target.checked)}
        style={{ width: '16px', height: '16px', accentColor: '#3a6b35' }}
      />
      <span style={{ fontSize: '0.9rem' }}>{label}</span>
    </label>
  );

  const selectInput = (field: string, label: string, options: string[]) => (
    <label key={field} style={fieldStyle}>
      <span style={labelStyle}>{label}</span>
      <select value={str(field)} onChange={e => set(field, e.target.value)} style={inputStyle}>
        <option value="">— none —</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );

  const commaField = (field: string, label: string) => (
    <label key={field} style={{ ...fieldStyle, alignItems: 'flex-start' }}>
      <span style={{ ...labelStyle, paddingTop: '0.3rem' }}>{label}</span>
      <textarea
        value={str(field)}
        onChange={e => set(field, e.target.value)}
        rows={3}
        placeholder="Comma-separated values…"
        style={{ ...inputStyle, resize: 'vertical' }}
      />
    </label>
  );

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <Link to={`/library/${entryId}`} style={{ color: '#7a907a', textDecoration: 'none', fontSize: '0.9rem' }}>
          ← Back to {entry.name as string}
        </Link>
        <h1 style={{ margin: 0, fontSize: '1.4rem' }}>Edit: {entry.name as string}</h1>
      </div>

      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '1.25rem', borderBottom: '2px solid #e8f0e7', paddingBottom: '0.5rem' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            style={{
              background: tab === t.id ? '#3a6b35' : '#f0f7ef',
              color: tab === t.id ? '#fff' : '#3a5c37',
              border: '1px solid',
              borderColor: tab === t.id ? '#3a6b35' : '#b0c8ae',
              padding: '0.35rem 0.75rem',
              borderRadius: '4px',
              cursor: 'pointer',
              font: 'inherit',
              fontSize: '0.85rem',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

          {tab === 'core' && <>
            {textInput('name', 'Name')}
            {textInput('scientific_name', 'Scientific Name')}
            {selectInput('type', 'Type', ['vegetable', 'herb', 'fruit', 'flower'])}
            {selectInput('difficulty', 'Difficulty', ['Easy', 'Medium', 'Hard'])}
            {textArea('notes', 'Notes', 5)}
            {textInput('image_filename', 'Image Filename')}
          </>}

          {tab === 'cultivation' && <>
            {textInput('sunlight', 'Sunlight')}
            {textInput('water', 'Water')}
            {textInput('spacing_in', 'Spacing (inches)', 'number')}
            {textInput('days_to_germination', 'Days to Germination', 'number')}
            {textInput('days_to_harvest', 'Days to Harvest', 'number')}
            {textInput('sow_indoor_weeks', 'Sow Indoors (weeks before last frost)', 'number')}
            {textInput('direct_sow_offset', 'Direct Sow Offset (weeks from last frost)', 'number')}
            {textInput('transplant_offset', 'Transplant Offset (weeks after last frost)', 'number')}
            {textInput('harvest_season', 'Harvest Season')}
            {textInput('harvest_method', 'Harvest Method')}
            {textInput('fruiting_season', 'Fruiting Season')}
          </>}

          {tab === 'climate' && <>
            {textInput('min_zone', 'Min USDA Zone', 'number')}
            {textInput('max_zone', 'Max USDA Zone', 'number')}
            {textInput('temp_min_f', 'Min Temperature (°F)', 'number')}
            {textInput('temp_max_f', 'Max Temperature (°F)', 'number')}
            {textInput('soil_ph_min', 'Soil pH Min', 'number')}
            {textInput('soil_ph_max', 'Soil pH Max', 'number')}
            {textInput('soil_type', 'Soil Type')}
            {textInput('soil_nutriments', 'Soil Nutriments (0–10)', 'number')}
            {textInput('soil_salinity', 'Soil Salinity (0–10)', 'number')}
            {textInput('atmospheric_humidity', 'Atmospheric Humidity (0–10)', 'number')}
            {textInput('precipitation_min_mm', 'Precipitation Min (mm)', 'number')}
            {textInput('precipitation_max_mm', 'Precipitation Max (mm)', 'number')}
          </>}

          {tab === 'companions' && <>
            <p className="muted" style={{ margin: 0 }}>Enter plant names separated by commas.</p>
            {commaField('good_neighbors', 'Good Neighbors')}
            {commaField('bad_neighbors', 'Bad Neighbors')}
          </>}

          {tab === 'growing' && <>
            <p className="muted" style={{ margin: 0 }}>Edit as raw JSON. Leave blank to clear.</p>
            {jsonArea('how_to_grow', 'How to Grow', 10)}
            {jsonArea('faqs', 'FAQs', 10)}
            {jsonArea('nutrition', 'Nutrition', 8)}
          </>}

          {tab === 'dimensions' && <>
            {textInput('average_height_cm', 'Average Height (cm)', 'number')}
            {textInput('maximum_height_cm', 'Maximum Height (cm)', 'number')}
            {textInput('spread_cm', 'Spread (cm)', 'number')}
            {textInput('row_spacing_cm', 'Row Spacing (cm)', 'number')}
            {textInput('minimum_root_depth_cm', 'Min Root Depth (cm)', 'number')}
          </>}

          {tab === 'appearance' && <>
            {textInput('flower_color', 'Flower Color')}
            {textInput('foliage_color', 'Foliage Color')}
            {textInput('foliage_texture', 'Foliage Texture')}
            {textInput('fruit_color', 'Fruit Color')}
            {textInput('fruit_shape', 'Fruit Shape')}
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', padding: '0.5rem 0' }}>
              {checkBox('flower_conspicuous', 'Flower Conspicuous')}
              {checkBox('fruit_conspicuous', 'Fruit Conspicuous')}
              {checkBox('leaf_retention', 'Leaf Retention')}
              {checkBox('seed_persistence', 'Seed Persistence')}
            </div>
            <p className="muted" style={{ margin: '0.25rem 0 0' }}>Month lists — comma-separated (e.g. jan, feb, mar)</p>
            {commaField('bloom_months', 'Bloom Months')}
            {commaField('fruit_months', 'Fruit Months')}
            {commaField('growth_months', 'Growth Months')}
          </>}

          {tab === 'classification' && <>
            {textInput('genus', 'Genus')}
            {textInput('family', 'Family')}
            {textInput('layer', 'Layer')}
            {textInput('duration', 'Duration')}
            {textInput('ligneous_type', 'Ligneous Type')}
            {textInput('growth_habit', 'Growth Habit')}
            {textInput('growth_form', 'Growth Form')}
            {textInput('growth_rate', 'Growth Rate')}
            {textInput('toxicity', 'Toxicity')}
            {textInput('edible_parts', 'Edible Parts')}
            {textInput('nitrogen_fixation', 'Nitrogen Fixation')}
            {textArea('permapeople_description', 'Permapeople Description', 4)}
            {textArea('observations', 'Observations / Native Range', 3)}
          </>}

          {tab === 'properties' && <>
            <div style={{ display: 'flex', gap: '1rem 2rem', flexWrap: 'wrap', padding: '0.25rem 0' }}>
              {checkBox('edible', 'Edible')}
              {checkBox('vegetable', 'Vegetable')}
              {checkBox('cuisine', 'Cuisine')}
              {checkBox('medicinal', 'Medicinal')}
              {checkBox('drought_tolerant', 'Drought Tolerant')}
              {checkBox('salt_tolerant', 'Salt Tolerant')}
              {checkBox('thorny', 'Thorny')}
              {checkBox('invasive', 'Invasive')}
              {checkBox('rare', 'Rare')}
              {checkBox('tropical', 'Tropical')}
              {checkBox('indoor', 'Indoor')}
              {checkBox('poisonous_to_pets', 'Poisonous to Pets')}
              {checkBox('poisonous_to_humans', 'Poisonous to Humans')}
            </div>
          </>}

          {tab === 'uses' && <>
            <p className="muted" style={{ margin: 0 }}>Comma-separated values.</p>
            {commaField('attracts', 'Attracts (pollinators, birds, etc.)')}
            {commaField('propagation_methods', 'Propagation Methods')}
            {commaField('pruning_months', 'Pruning Months')}
          </>}
        </div>

        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button type="submit" disabled={patchMut.isPending || saved}>
            {saved ? 'Saved!' : patchMut.isPending ? 'Saving…' : 'Save Changes'}
          </button>
          <Link
            to={`/library/${entryId}`}
            style={{ color: '#7a907a', textDecoration: 'none', fontSize: '0.9rem' }}
          >
            Cancel
          </Link>
          {err && <span style={{ color: '#c0392b', fontSize: '0.88rem' }}>{err}</span>}
        </div>
      </form>
    </div>
  );
}

const fieldStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.75rem',
};

const labelStyle: React.CSSProperties = {
  minWidth: '220px',
  fontSize: '0.88rem',
  color: '#4a6a47',
  fontWeight: 500,
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  font: 'inherit',
  fontSize: '0.9rem',
  padding: '0.38rem 0.5rem',
  border: '1px solid #c0d4be',
  borderRadius: '4px',
  background: '#fbfefb',
};
