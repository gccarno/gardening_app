import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useLibraryEntry, useSetImagePrimary, useDeleteImage, useAddImageUrl, useUploadImage, useClonePlant } from '../hooks/useLibrary';
import { useGardens } from '../hooks/useGardens';
import { createPlant } from '../api/plants';
import { plantImageUrl } from '../utils/images';

type Tab = 'overview' | 'calendar' | 'how-to' | 'companions' | 'soil' | 'nutrition' | 'faqs';

const HOW_TO_STAGES: [string, string, string][] = [
  ['starting', '🪴', 'Starting'],
  ['seedling', '🌱', 'Seedling Stage'],
  ['vegetative', '🌿', 'Vegetative Stage'],
  ['flowering', '🌸', 'Flowering Stage'],
  ['harvest', '🌽', 'Harvest Stage'],
];

export default function LibraryDetail() {
  const { id } = useParams<{ id: string }>();
  const entryId = parseInt(id!);
  const navigate = useNavigate();
  const { data: entry, isLoading } = useLibraryEntry(entryId);
  const { data: gardens } = useGardens();
  const setPrimaryMut = useSetImagePrimary(entryId);
  const deleteImgMut = useDeleteImage(entryId);
  const addUrlMut = useAddImageUrl(entryId);
  const uploadMut = useUploadImage(entryId);
  const cloneMut = useClonePlant();

  const [tab, setTab] = useState<Tab>('overview');
  const [selectedGarden, setSelectedGarden] = useState('');
  const [addingPlant, setAddingPlant] = useState(false);
  const [plantMsg, setPlantMsg] = useState('');

  // Clone modal state
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [cloneName, setCloneName] = useState('');
  const [cloneMsg, setCloneMsg] = useState('');

  // Image panel state
  const [showImgForm, setShowImgForm] = useState(false);
  const [imgMode, setImgMode] = useState<'upload' | 'url'>('upload');
  const [imgUrl, setImgUrl] = useState('');
  const [imgSource, setImgSource] = useState('manual');
  const [imgAttribution, setImgAttribution] = useState('');
  const [imgFile, setImgFile] = useState<File | null>(null);
  const [imgMsg, setImgMsg] = useState('');
  const [previewImg, setPreviewImg] = useState<{ filename: string; attribution?: string } | null>(null);

  // Derived data
  const images = entry?.images as Array<{ id: number; filename: string; is_primary: boolean; source?: string; attribution?: string }> | undefined;
  const primaryImg = images?.find(i => i.is_primary) || images?.[0];
  const nutrition = entry?.nutrition as Record<string, unknown> | undefined;
  const faqs = entry?.faqs as Array<{ q: string; a: string }> | undefined;
  const howToGrow = entry?.how_to_grow as Record<string, string> | undefined;
  const goodNeighbors = entry?.good_neighbors as string[] | undefined;
  const badNeighbors = entry?.bad_neighbors as string[] | undefined;
  const calendarRows = entry?.calendar_rows as Array<Record<string, unknown>> | undefined;
  const selectedZone = entry?.selected_zone as number | undefined;
  const bloomMonths = entry?.bloom_months as string | undefined;
  const fruitMonths = entry?.fruit_months as string | undefined;
  const growthMonths = entry?.growth_months as string | undefined;

  const heroImg = previewImg || (primaryImg ? { filename: primaryImg.filename, attribution: primaryImg.attribution } : null);

  const availableTabs: Tab[] = ['overview', 'calendar', 'how-to', 'companions', 'soil'];
  if (nutrition) availableTabs.push('nutrition');
  if (faqs?.length) availableTabs.push('faqs');

  async function handleAddToPlanning() {
    if (!selectedGarden) return;
    setAddingPlant(true);
    try {
      await createPlant({
        name: entry!.name,
        library_id: entryId,
        garden_id: parseInt(selectedGarden),
        status: 'planning',
      });
      setPlantMsg('Added to planning!');
      setTimeout(() => setPlantMsg(''), 3000);
    } catch { setPlantMsg('Error adding plant.'); }
    setAddingPlant(false);
  }

  async function handleClone() {
    if (!cloneName.trim()) { setCloneMsg('Please enter a name.'); return; }
    setCloneMsg('Cloning…');
    try {
      const result = await cloneMut.mutateAsync({ entryId, name: cloneName.trim() });
      setShowCloneModal(false);
      navigate(`/library/${result.id}`);
    } catch { setCloneMsg('Error cloning plant.'); }
  }

  async function handleImgSubmit() {
    setImgMsg('Saving…');
    try {
      if (imgMode === 'upload') {
        if (!imgFile) { setImgMsg('Please choose a file.'); return; }
        await uploadMut.mutateAsync(imgFile);
      } else {
        if (!imgUrl) { setImgMsg('Please enter a URL.'); return; }
        await addUrlMut.mutateAsync({ url: imgUrl, source: imgSource, attribution: imgAttribution || undefined });
      }
      setImgMsg('Saved!');
      setShowImgForm(false);
      setImgUrl(''); setImgFile(null); setImgAttribution('');
    } catch { setImgMsg('Error saving image.'); }
  }

  if (isLoading) return <p className="muted" style={{ padding: '2rem' }}>Loading…</p>;
  if (!entry) return <p className="muted" style={{ padding: '2rem' }}>Entry not found.</p>;

  return (
    <>
      <div className="plant-hero">
        <div className="plant-hero-info">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
            <h1 style={{ margin: 0 }}>{entry.name}</h1>
            {entry.type && <span className={`lib-badge lib-badge--${entry.type}`}>{entry.type as string}</span>}
            {entry.difficulty && <span className={`difficulty-badge difficulty--${(entry.difficulty as string).toLowerCase()}`}>{entry.difficulty as string}</span>}
          </div>
          {entry.scientific_name && <p style={{ color: '#7a907a', fontStyle: 'italic', margin: '0 0 0.75rem' }}>{entry.scientific_name as string}</p>}

          <div className="plant-hero-stats">
            {entry.sunlight && <span className="hero-stat">☀️ {entry.sunlight as string}</span>}
            {entry.water && <span className="hero-stat">💧 {entry.water as string} water</span>}
            {entry.spacing_in && <span className="hero-stat">↔ {entry.spacing_in as number}" spacing</span>}
            {entry.days_to_harvest && <span className="hero-stat">🗓 {entry.days_to_harvest as number} days to harvest</span>}
            {entry.min_zone && entry.max_zone && <span className="hero-stat">🌍 Zones {entry.min_zone as number}–{entry.max_zone as number}</span>}
          </div>

          {entry.cloned_from_id && (
            <p style={{ fontSize: '0.82rem', color: '#7a907a', margin: '0 0 0.5rem' }}>
              Cloned from:{' '}
              <Link to={`/library/${entry.cloned_from_id as number}`} style={{ color: '#3a6b35' }}>
                {(entry.cloned_from_name as string) || `#${entry.cloned_from_id as number}`}
              </Link>
            </p>
          )}

          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <select
              value={selectedGarden}
              onChange={e => setSelectedGarden(e.target.value)}
              style={{ font: 'inherit', padding: '0.38rem 0.6rem', border: '1px solid #c0d4be', borderRadius: '4px', background: '#fbfefb' }}
            >
              <option value="">— select a garden —</option>
              {gardens?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <button onClick={handleAddToPlanning} disabled={addingPlant || !selectedGarden}>
              {addingPlant ? 'Adding…' : '+ Add to Planning'}
            </button>
            <button
              onClick={() => { setCloneName(`${entry.name as string} (Clone)`); setCloneMsg(''); setShowCloneModal(true); }}
              style={{ background: '#f0f7ef', border: '1px solid #b0c8ae', color: '#3a5c37', padding: '0.38rem 0.75rem', borderRadius: '4px', cursor: 'pointer', font: 'inherit' }}
            >
              Clone Plant
            </button>
            {plantMsg && <span className="muted">{plantMsg}</span>}
          </div>

          {showCloneModal && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#f4f9f3', border: '1px solid #c0d4be', borderRadius: '6px', maxWidth: '380px' }}>
              <p style={{ margin: '0 0 0.5rem', fontWeight: 600, fontSize: '0.9rem' }}>Clone this plant</p>
              <input
                type="text"
                value={cloneName}
                onChange={e => setCloneName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleClone(); if (e.key === 'Escape') setShowCloneModal(false); }}
                placeholder="New plant name…"
                autoFocus
                style={{ width: '100%', font: 'inherit', padding: '0.35rem 0.5rem', border: '1px solid #c0d4be', borderRadius: '4px', marginBottom: '0.4rem', boxSizing: 'border-box' }}
              />
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button onClick={handleClone} disabled={cloneMut.isPending}>
                  {cloneMut.isPending ? 'Cloning…' : 'Create Clone'}
                </button>
                <button onClick={() => setShowCloneModal(false)} style={{ background: 'none', border: '1px solid #c0d4be', padding: '0.35rem 0.6rem', borderRadius: '4px', cursor: 'pointer', font: 'inherit' }}>
                  Cancel
                </button>
              </div>
              {cloneMsg && <p style={{ fontSize: '0.8rem', margin: '0.3rem 0 0', color: '#c0392b' }}>{cloneMsg}</p>}
            </div>
          )}
        </div>

        <div className="plant-gallery" id="plant-gallery">
          <div className="plant-gallery__primary">
            {heroImg ? (
              <>
                <img src={plantImageUrl(heroImg.filename) ?? ''} alt={entry.name} className="plant-hero-img" />
                {heroImg.attribution && <p className="img-attribution">{heroImg.attribution}</p>}
              </>
            ) : (
              <div className="plant-hero-img plant-hero-img--loading" style={{ justifyContent: 'center', color: '#9ab49a' }}>No image</div>
            )}
          </div>
          <div className="plant-gallery__aside">
            <div className="plant-gallery__thumbs">
              {images?.map(img => (
                <div key={img.id} className={`gallery-thumb${img.is_primary ? ' thumb--primary' : ''}`}
                     style={{ position: 'relative', display: 'inline-block' }}>
                  <button onClick={() => setPreviewImg({ filename: img.filename, attribution: img.attribution })}
                          style={{ padding: 0, border: 'none', background: 'none' }}>
                    <img src={plantImageUrl(img.filename) ?? ''} alt="" style={{ width: '60px', height: '60px', objectFit: 'cover' }} />
                  </button>
                  <div className="thumb-menu">
                    <button className="thumb-menu-btn" onClick={() => setPrimaryMut.mutate(img.id)}>Set primary</button>
                    <button className="thumb-menu-btn thumb-menu-btn--danger"
                            onClick={() => { if (confirm('Delete this image?')) deleteImgMut.mutate(img.id); }}>Delete</button>
                  </div>
                </div>
              ))}
            </div>
            {!showImgForm ? (
              <button className="btn btn--sm" style={{ marginTop: '0.5rem' }} onClick={() => setShowImgForm(true)}>+ Add Image</button>
            ) : (
              <div style={{ marginTop: '0.6rem' }}>
                <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
                  {(['upload', 'url'] as const).map(m => (
                    <label key={m} style={{ fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <input type="radio" checked={imgMode === m} onChange={() => setImgMode(m)} /> {m === 'upload' ? 'Upload file' : 'From URL'}
                    </label>
                  ))}
                </div>
                {imgMode === 'upload' ? (
                  <input type="file" accept="image/*" style={{ fontSize: '0.8rem', width: '100%' }}
                         onChange={e => setImgFile(e.target.files?.[0] ?? null)} />
                ) : (
                  <input type="text" placeholder="https://…" value={imgUrl} onChange={e => setImgUrl(e.target.value)}
                         style={{ width: '100%', font: 'inherit', padding: '0.3rem', border: '1px solid #c0d4be', borderRadius: '4px' }} />
                )}
                <select value={imgSource} onChange={e => setImgSource(e.target.value)}
                        style={{ marginTop: '0.4rem', width: '100%', font: 'inherit', padding: '0.3rem', border: '1px solid #c0d4be', borderRadius: '4px' }}>
                  <option value="manual">Manual / unknown</option>
                  <option value="wikimedia">Wikimedia Commons</option>
                  <option value="inaturalist">iNaturalist</option>
                  <option value="openverse">OpenVerse</option>
                  <option value="pexels">Pexels</option>
                </select>
                <input type="text" placeholder="Attribution (optional)" value={imgAttribution} onChange={e => setImgAttribution(e.target.value)}
                       style={{ marginTop: '0.4rem', width: '100%', font: 'inherit', padding: '0.3rem', border: '1px solid #c0d4be', borderRadius: '4px' }} />
                <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem' }}>
                  <button className="btn btn--sm" onClick={handleImgSubmit}>Save</button>
                  <button className="btn btn--sm btn--ghost" onClick={() => { setShowImgForm(false); setImgMsg(''); }}>Cancel</button>
                </div>
                {imgMsg && <p style={{ fontSize: '0.8rem', margin: '0.3rem 0 0' }}>{imgMsg}</p>}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="plant-tabs" style={{ marginTop: '1.5rem' }}>
        {availableTabs.map(t => (
          <button key={t} className={`plant-tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'how-to' ? 'How to Grow' : t === 'faqs' ? 'FAQs' : t.charAt(0).toUpperCase() + t.slice(1).replace('-', ' ')}
          </button>
        ))}
      </div>

      {/* Overview */}
      {tab === 'overview' && (
        <section style={{ marginTop: '1.25rem' }}>
          <dl className="details">
            {entry.scientific_name && <><dt>Scientific Name</dt><dd><em>{entry.scientific_name as string}</em></dd></>}
            {entry.sunlight && <><dt>Sunlight</dt><dd>{entry.sunlight as string}</dd></>}
            {entry.water && <><dt>Watering</dt><dd>{entry.water as string}</dd></>}
            {entry.spacing_in && <><dt>Spacing</dt><dd>{entry.spacing_in as number} inches apart</dd></>}
            {entry.days_to_germination && <><dt>Germination</dt><dd>{entry.days_to_germination as number} days</dd></>}
            {entry.days_to_harvest && <><dt>Days to Harvest</dt><dd>{entry.days_to_harvest as number} days</dd></>}
            {entry.min_zone && entry.max_zone && <><dt>Hardiness Zones</dt><dd>USDA Zones {entry.min_zone as number}–{entry.max_zone as number}</dd></>}
            {entry.temp_min_f && entry.temp_max_f && <><dt>Temperature Range</dt><dd>{entry.temp_min_f as number}–{entry.temp_max_f as number}°F</dd></>}
            {entry.soil_ph_min && entry.soil_ph_max && <><dt>Soil pH</dt><dd>{entry.soil_ph_min as number}–{entry.soil_ph_max as number}</dd></>}
            {entry.soil_type && <><dt>Soil Type</dt><dd>{entry.soil_type as string}</dd></>}
            {entry.notes && <><dt>Growing Notes</dt><dd>{entry.notes as string}</dd></>}
            {entry.family && <><dt>Plant Family</dt><dd>{entry.family as string}</dd></>}
            {entry.layer && <><dt>Garden Layer</dt><dd>{entry.layer as string}</dd></>}
            {entry.edible_parts && <><dt>Edible Parts</dt><dd>{entry.edible_parts as string}</dd></>}
            {entry.permapeople_description && <><dt>Description</dt><dd>{entry.permapeople_description as string}</dd></>}
          </dl>
          {entry.permapeople_link && (
            <p style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#7a907a' }}>
              Plant data sourced from <a href={entry.permapeople_link as string} target="_blank" rel="noopener" style={{ color: '#3a6b35' }}>Permapeople.org</a> — licensed under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener" style={{ color: '#3a6b35' }}>CC BY-SA 4.0</a>
            </p>
          )}
          {(entry.observations || entry.duration || entry.growth_habit || entry.average_height_cm) && (
            <>
              <h3 style={{ margin: '1.5rem 0 0.5rem', fontSize: '1rem', color: '#3a5c37', borderTop: '1px solid #e0ead0', paddingTop: '1rem' }}>Growth &amp; Classification</h3>
              <dl className="details">
                {entry.observations && <><dt>Native Range</dt><dd>{entry.observations as string}</dd></>}
                {entry.duration && <><dt>Life Cycle</dt><dd>{entry.duration as string}</dd></>}
                {entry.growth_habit && <><dt>Growth Habit</dt><dd>{entry.growth_habit as string}</dd></>}
                {entry.average_height_cm && <><dt>Height</dt><dd>{entry.average_height_cm as number} cm avg{entry.maximum_height_cm ? ` / ${entry.maximum_height_cm as number} cm max` : ''}</dd></>}
                {entry.spread_cm && <><dt>Spread</dt><dd>{entry.spread_cm as number} cm</dd></>}
              </dl>
            </>
          )}
          {(bloomMonths || fruitMonths || growthMonths || entry.flower_color) && (
            <>
              <h3 style={{ margin: '1.5rem 0 0.5rem', fontSize: '1rem', color: '#3a5c37', borderTop: '1px solid #e0ead0', paddingTop: '1rem' }}>Seasonal Activity &amp; Appearance</h3>
              <dl className="details">
                {bloomMonths && <><dt>Bloom Months</dt><dd>{bloomMonths}</dd></>}
                {fruitMonths && <><dt>Fruit Months</dt><dd>{fruitMonths}</dd></>}
                {growthMonths && <><dt>Active Growth</dt><dd>{growthMonths}</dd></>}
                {entry.flower_color && <><dt>Flower Color</dt><dd>{(entry.flower_color as string).charAt(0).toUpperCase() + (entry.flower_color as string).slice(1)}</dd></>}
                {entry.foliage_color && <><dt>Foliage Color</dt><dd>{entry.foliage_color as string}</dd></>}
                {entry.fruit_color && <><dt>Fruit Color</dt><dd>{entry.fruit_color as string}</dd></>}
              </dl>
            </>
          )}
        </section>
      )}

      {/* Calendar */}
      {tab === 'calendar' && (
        <section style={{ marginTop: '1.25rem' }}>
          {calendarRows && calendarRows.length > 0 ? (
            <>
              <p className="muted" style={{ marginBottom: '1rem' }}>
                Dates are calculated from your region's average last spring frost.
                {selectedZone && <> <strong>Your garden is in Zone {selectedZone}.</strong></>}
              </p>
              {(() => {
                const myRow = calendarRows.find(r => r.zone === (selectedZone || 6));
                return myRow ? (
                  <div className="cal-highlight">
                    <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Zone {myRow.zone as number} — Your Schedule</h3>
                    <div className="cal-steps">
                      {!!myRow.start_indoors && <div className="cal-step cal-step--indoor"><span className="cal-step-icon">🪴</span><strong>Start Indoors</strong><span>{myRow.start_indoors as string}</span></div>}
                      {!!myRow.direct_sow && <div className="cal-step cal-step--sow"><span className="cal-step-icon">🌱</span><strong>Direct Sow</strong><span>{myRow.direct_sow as string}</span></div>}
                      {!!myRow.transplant && <div className="cal-step cal-step--transplant"><span className="cal-step-icon">🌿</span><strong>Transplant Out</strong><span>{myRow.transplant as string}</span></div>}
                      <div className="cal-step cal-step--frost"><span className="cal-step-icon">❄️</span><strong>Last Frost</strong><span>{myRow.last_frost as string}</span></div>
                      <div className="cal-step cal-step--harvest"><span className="cal-step-icon">🌽</span><strong>First Fall Frost</strong><span>{myRow.first_fall_frost as string}</span></div>
                    </div>
                  </div>
                ) : null;
              })()}
              <h3 style={{ margin: '1.5rem 0 0.75rem', fontSize: '1rem' }}>All Zones Reference</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className="lib-table">
                  <thead>
                    <tr>
                      <th>Zone</th><th>Last Spring Frost</th>
                      {!!calendarRows[0]?.start_indoors && <th>🪴 Start Indoors</th>}
                      {!!calendarRows[0]?.direct_sow && <th>🌱 Direct Sow</th>}
                      {!!calendarRows[0]?.transplant && <th>🌿 Transplant Out</th>}
                      <th>First Fall Frost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calendarRows.map(row => (
                      <tr key={row.zone as number} style={row.zone === selectedZone ? { background: '#f0f7ef', fontWeight: 600 } : undefined}>
                        <td>Zone {row.zone as number}</td>
                        <td>{row.last_frost as string}</td>
                        {row.start_indoors !== undefined && <td>{row.start_indoors as string}</td>}
                        {row.direct_sow !== undefined && <td>{row.direct_sow as string}</td>}
                        {row.transplant !== undefined && <td>{row.transplant as string}</td>}
                        <td>{row.first_fall_frost as string}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : <p className="muted">Planting calendar data not yet available for this plant.</p>}
        </section>
      )}

      {/* How to Grow */}
      {tab === 'how-to' && (
        <section style={{ marginTop: '1.25rem' }}>
          {howToGrow ? (
            <div className="howto-stages">
              {HOW_TO_STAGES.filter(([key]) => howToGrow[key]).map(([key, icon, label]) => (
                <div key={key} className="howto-stage">
                  <div className="howto-stage-icon">{icon}</div>
                  <div className="howto-stage-body">
                    <h3 className="howto-stage-title">{label}</h3>
                    <p>{howToGrow[key]}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="muted">Growing guide not yet available for this plant.</p>}
        </section>
      )}

      {/* Companions */}
      {tab === 'companions' && (
        <section style={{ marginTop: '1.25rem' }}>
          <div className="companions-grid">
            <div className="companions-col companions-col--good">
              <h3>👍 Good Neighbors</h3>
              {goodNeighbors?.length ? (
                <ul className="companion-list">{goodNeighbors.map((n, i) => <li key={i}>{n}</li>)}</ul>
              ) : <p className="muted">No data available.</p>}
            </div>
            <div className="companions-col companions-col--bad">
              <h3>👎 Bad Neighbors</h3>
              {badNeighbors?.length ? (
                <ul className="companion-list">{badNeighbors.map((n, i) => <li key={i}>{n}</li>)}</ul>
              ) : <p className="muted">No data available.</p>}
            </div>
          </div>
          <p className="muted" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
            Companion planting improves growth, deters pests, and maximizes space. Keep bad neighbors at least 3–4 ft apart when possible.
          </p>
        </section>
      )}

      {/* Soil */}
      {tab === 'soil' && (
        <section style={{ marginTop: '1.25rem' }}>
          {(entry.soil_ph_min || entry.soil_type || entry.temp_min_f) ? (
            <dl className="details">
              {entry.soil_ph_min && entry.soil_ph_max && <><dt>Soil pH</dt><dd>{entry.soil_ph_min as number}–{entry.soil_ph_max as number}</dd></>}
              {entry.soil_type && <><dt>Soil Type</dt><dd>{entry.soil_type as string}</dd></>}
              {entry.temp_min_f && entry.temp_max_f && <><dt>Growing Temp</dt><dd>{entry.temp_min_f as number}–{entry.temp_max_f as number}°F</dd></>}
              {entry.sunlight && <><dt>Sunlight</dt><dd>{entry.sunlight as string}</dd></>}
              {entry.water && <><dt>Watering</dt><dd>{entry.water as string}</dd></>}
              {entry.spacing_in && <><dt>Spacing</dt><dd>{entry.spacing_in as number} inches</dd></>}
              {entry.notes && <><dt>Growing Notes</dt><dd>{entry.notes as string}</dd></>}
            </dl>
          ) : <p className="muted">Soil and care data not yet available for this plant.</p>}
        </section>
      )}

      {/* Nutrition */}
      {tab === 'nutrition' && nutrition && (
        <section style={{ marginTop: '1.25rem' }}>
          <p className="muted" style={{ marginBottom: '1rem' }}>Per serving: <strong>{nutrition.serving_size as string}</strong></p>
          <div className="nutrition-panel">
            <div className="nutrition-facts">
              <div className="nf-header">Nutrition Facts</div>
              <div className="nf-serving">Serving size: {nutrition.serving_size as string}</div>
              <div className="nf-calories-row"><span>Calories</span><span className="nf-calories-val">{nutrition.calories as number}</span></div>
              <div className="nf-divider" />
              <div className="nf-row"><span>Protein</span><span>{nutrition.protein_g as number}g</span></div>
              <div className="nf-row"><span>Carbohydrates</span><span>{nutrition.carbs_g as number}g</span></div>
              <div className="nf-row nf-indent"><span>Dietary Fiber</span><span>{nutrition.fiber_g as number}g</span></div>
              <div className="nf-row"><span>Total Fat</span><span>{nutrition.fat_g as number}g</span></div>
              {(nutrition.vitamins as string[])?.length > 0 && (
                <>
                  <div className="nf-divider" />
                  <div className="nf-vitamins-label">Vitamins &amp; Minerals</div>
                  {(nutrition.vitamins as string[]).map((v, i) => (
                    <div key={i} className="nf-row nf-vitamin">
                      <span>{v.includes(':') ? v.split(':')[0] : v}</span>
                      <span>{v.includes(':') ? v.split(':')[1] : ''}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
            {!!nutrition.notes && (
              <div className="nutrition-notes">
                <h3 style={{ fontSize: '1rem', color: '#3a5c37', marginBottom: '0.5rem' }}>Health Benefits</h3>
                <p>{nutrition.notes as string}</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* FAQs */}
      {tab === 'faqs' && faqs && (
        <section style={{ marginTop: '1.25rem' }}>
          <div className="faq-list">
            {faqs.map((item, i) => (
              <details key={i} className="faq-item" open={i === 0}>
                <summary className="faq-q">{item.q}</summary>
                <p className="faq-a">{item.a}</p>
              </details>
            ))}
          </div>
        </section>
      )}

      <p style={{ marginTop: '2rem' }}><Link to="/library">← Back to Library</Link></p>
    </>
  );
}
