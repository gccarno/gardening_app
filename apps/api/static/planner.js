'use strict';

const canvas = document.getElementById('planner-canvas');
const PX = parseInt(canvas.dataset.px, 10) || 60;   // px per foot
const PX_PER_IN = PX / 12;                           // px per inch (5 at default scale)
const GARDEN_ID = canvas.dataset.gardenId;

let dragState = null;
let tileIn = 12; // current tile size in inches (default 1 ft)
let zoom = parseFloat(localStorage.getItem('plannerZoom') || '1');

// ── Shared fetch helper ────────────────────────────────────────────────────────
async function api(method, path, body) {
    return fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
    }).then(r => r.json());
}

function snap(value) { return Math.round(value / PX) * PX; }

function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Returns the span (in cells) a plant occupies at the current tile size
function plantSpan(spacingIn) {
    return Math.max(1, Math.round(spacingIn / tileIn));
}

// ── Build tile grid inside a canvas-bed element ───────────────────────────────
function buildBedGrid(bedEl) {
    const grid = bedEl.querySelector('.canvas-bed-grid');
    if (!grid) return;

    const widthFt  = parseFloat(bedEl.dataset.width);
    const heightFt = parseFloat(bedEl.dataset.height);
    const tilePx   = tileIn * PX_PER_IN;
    const cols     = Math.max(1, Math.round(widthFt  * 12 / tileIn));
    const rows     = Math.max(1, Math.round(heightFt * 12 / tileIn));

    grid.innerHTML = '';
    grid.style.gridTemplateColumns = `repeat(${cols}, ${tilePx}px)`;
    grid.style.gridTemplateRows    = `repeat(${rows}, ${tilePx}px)`;
    grid.dataset.cols = cols;
    grid.dataset.rows = rows;
    grid.classList.toggle('tiny', tilePx < 20);

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            cell.dataset.cx = c;
            cell.dataset.cy = r;
            grid.appendChild(cell);
        }
    }

    // Re-render already-placed plants
    let bpData = [];
    try { bpData = JSON.parse(bedEl.dataset.bedPlants || '[]'); } catch(e) {}
    bpData.forEach(bp => {
        if (bp.grid_x < 0 || bp.grid_y < 0) return;
        const cx = Math.floor(bp.grid_x / tileIn);
        const cy = Math.floor(bp.grid_y / tileIn);
        renderChipInGrid(grid, bp.id, cx, cy, bp.name, bp.image, bp.spacing_in || 12, bp.stage || 'seedling');
    });

    bindGridHover(grid);
}

// ── Check whether a span×span area starting at (cx,cy) is free ───────────────
function canPlace(grid, cx, cy, span) {
    const cols = parseInt(grid.dataset.cols);
    const rows = parseInt(grid.dataset.rows);
    if (cx + span > cols || cy + span > rows) return false;
    for (let r = cy; r < cy + span; r++) {
        for (let c = cx; c < cx + span; c++) {
            const cell = grid.querySelector(`[data-cx="${c}"][data-cy="${r}"]`);
            if (!cell || cell.classList.contains('cell-occupied')) return false;
        }
    }
    return true;
}

// ── Mark / unmark a span of cells as occupied ─────────────────────────────────
function setCellsOccupied(grid, cx, cy, span, occupied) {
    for (let r = cy; r < cy + span; r++) {
        for (let c = cx; c < cx + span; c++) {
            const cell = grid.querySelector(`[data-cx="${c}"][data-cy="${r}"]`);
            if (!cell) continue;
            if (occupied) cell.classList.add('cell-occupied');
            else          cell.classList.remove('cell-occupied');
        }
    }
}

// ── Highlight / un-highlight a span of drop-target cells ─────────────────────
function setDropHighlight(grid, cx, cy, span, highlight) {
    for (let r = cy; r < cy + span; r++) {
        for (let c = cx; c < cx + span; c++) {
            const cell = grid.querySelector(`[data-cx="${c}"][data-cy="${r}"]`);
            if (!cell) continue;
            if (highlight) cell.classList.add('cell-drop-target');
            else           cell.classList.remove('cell-drop-target');
        }
    }
}

// ── Render a plant chip as an absolutely-positioned element in the grid ───────
function renderChipInGrid(grid, bpId, cx, cy, name, imageFilename, spacingIn, stage) {
    const tilePx = tileIn * PX_PER_IN;
    const span   = plantSpan(spacingIn);

    setCellsOccupied(grid, cx, cy, span, true);

    const chip = document.createElement('div');
    chip.className = 'grid-plant-chip';
    chip.dataset.bpId     = bpId;
    chip.dataset.cx       = cx;
    chip.dataset.cy       = cy;
    chip.dataset.spacingIn = spacingIn;
    chip.style.left   = `${cx   * tilePx}px`;
    chip.style.top    = `${cy   * tilePx}px`;
    chip.style.width  = `${span * tilePx}px`;
    chip.style.height = `${span * tilePx}px`;

    const imgHtml = imageFilename
        ? `<img src="/static/plant_images/${imageFilename}" class="chip-img" alt="${escapeHtml(name)}">`
        : `<span class="chip-img chip-img--empty">🌱</span>`;
    const stageLabels = { seedling: '🌱', growing: '🌿', harvesting: '🥕', done: '✓' };
    const stageBadge = (stage && stage !== 'seedling')
        ? `<span class="chip-stage-badge stage-${stage}">${stageLabels[stage] || stage}</span>`
        : '';
    chip.innerHTML = `${imgHtml}<span class="chip-name">${escapeHtml(name)}</span>`
                   + stageBadge
                   + `<button class="chip-remove" title="Remove">×</button>`;

    chip.querySelector('.chip-remove').addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const result = await api('POST', `/api/bedplants/${bpId}/delete`);
        if (result.ok) {
            setCellsOccupied(grid, cx, cy, span, false);
            chip.remove();
            closePlantCarePanel();
        }
    });

    chip.addEventListener('click', (ev) => {
        if (ev.target.classList.contains('chip-remove')) return;
        openPlantCarePanel({ bpId });
        document.querySelectorAll('.grid-plant-chip.chip-active').forEach(c => c.classList.remove('chip-active'));
        chip.classList.add('chip-active');
    });

    grid.appendChild(chip);
}

// ── Visual hover feedback: highlight the plant's full span ────────────────────
function bindGridHover(grid) {
    let lastCx = -1, lastCy = -1, lastSpan = 1;

    grid.addEventListener('dragover', (e) => {
        if (!dragState || dragState.type !== 'plant') return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        grid.classList.add('drop-active');

        const tilePx = tileIn * PX_PER_IN;
        const rect   = grid.getBoundingClientRect();
        const cx     = Math.floor((e.clientX - rect.left) / zoom / tilePx);
        const cy     = Math.floor((e.clientY - rect.top)  / zoom / tilePx);
        const span   = plantSpan(dragState.spacingIn || 12);

        if (cx !== lastCx || cy !== lastCy || span !== lastSpan) {
            setDropHighlight(grid, lastCx, lastCy, lastSpan, false);
            lastCx = cx; lastCy = cy; lastSpan = span;
            if (canPlace(grid, cx, cy, span)) {
                setDropHighlight(grid, cx, cy, span, true);
            }
        }
    });

    grid.addEventListener('dragleave', (e) => {
        if (!grid.contains(e.relatedTarget)) {
            setDropHighlight(grid, lastCx, lastCy, lastSpan, false);
            grid.classList.remove('drop-active');
            lastCx = lastCy = -1;
        }
    });
}

function updateBedPlantsData(bedEl, id, name, image, spacingIn, gx, gy) {
    let list = [];
    try { list = JSON.parse(bedEl.dataset.bedPlants || '[]'); } catch(e) {}
    list.push({ id, name, image, spacing_in: spacingIn, grid_x: gx, grid_y: gy });
    bedEl.dataset.bedPlants = JSON.stringify(list);
}

// ── Tile size selector ─────────────────────────────────────────────────────────
const tileSizeSelect = document.getElementById('tile-size-select');
if (tileSizeSelect) {
    tileIn = parseInt(tileSizeSelect.value, 10);
    tileSizeSelect.addEventListener('change', () => {
        tileIn = parseInt(tileSizeSelect.value, 10);
        document.querySelectorAll('.canvas-bed').forEach(buildBedGrid);
    });
}

// Build grids for all beds already on the canvas
document.querySelectorAll('.canvas-bed').forEach(buildBedGrid);

// ── Canvas Plant Circles ───────────────────────────────────────────────────────

let activeCanvasPlantId = null;
const canvasPlantEls    = {}; // cp_id → DOM element

function applyCircleAppearance(el, cp) {
    const bg = el.querySelector('.circle-bg');
    const img = bg ? bg.querySelector('img') : null;
    const svgSrc = cp.svg_icon_url || null;
    if (cp.custom_image) {
        const src = `/static/canvas_plant_images/${cp.image_filename}`;
        if (img) { img.src = src; img.style.display = 'block'; }
        el.style.backgroundColor = 'transparent';
    } else if (svgSrc) {
        if (img) { img.src = svgSrc; img.style.display = 'block'; }
        el.style.backgroundColor = 'transparent';
    } else if (cp.display_mode === 'image' && cp.image_filename) {
        const src = `/static/plant_images/${cp.image_filename}`;
        if (img) { img.src = src; img.style.display = 'block'; }
        el.style.backgroundColor = 'transparent';
    } else {
        if (img) img.style.display = 'none';
        el.style.backgroundColor = cp.color || '#5a9e54';
    }
}

function renderCanvasPlant(cp) {
    const diamPx  = cp.radius_ft * PX * 2;
    const leftPx  = cp.pos_x * PX - cp.radius_ft * PX;
    const topPx   = cp.pos_y * PX - cp.radius_ft * PX;

    const el = document.createElement('div');
    el.className   = 'canvas-plant-circle';
    el.id          = `canvas-plant-${cp.id}`;
    el.dataset.cpId = cp.id;
    el.style.left   = `${leftPx}px`;
    el.style.top    = `${topPx}px`;
    el.style.width  = `${diamPx}px`;
    el.style.height = `${diamPx}px`;

    // Inner clip div for background image
    const bg = document.createElement('div');
    bg.className = 'circle-bg';
    const img = document.createElement('img');
    img.alt = cp.name || '';
    bg.appendChild(img);
    el.appendChild(bg);

    applyCircleAppearance(el, cp);

    const label = document.createElement('span');
    label.className   = 'canvas-plant-label';
    label.textContent = cp.name || '';
    el.appendChild(label);

    const handle = document.createElement('div');
    handle.className = 'canvas-plant-resize-handle';
    handle.title     = 'Drag to resize';
    el.appendChild(handle);

    const delBtn = document.createElement('button');
    delBtn.className   = 'canvas-plant-delete-btn';
    delBtn.textContent = '×';
    delBtn.title       = 'Remove from canvas';
    el.appendChild(delBtn);

    bindCanvasPlantEvents(el, cp);
    canvas.appendChild(el);
    canvasPlantEls[cp.id] = el;
}

function bindCanvasPlantEvents(el, cp) {
    let pointerMode = null; // 'move' | 'resize'
    let startX, startY, startLeft, startTop, startDiam;
    let didMove = false;

    el.addEventListener('pointerdown', (e) => {
        if (e.target.classList.contains('canvas-plant-delete-btn')) return;
        e.stopPropagation();
        e.preventDefault();
        el.setPointerCapture(e.pointerId);
        didMove = false;

        if (e.target.classList.contains('canvas-plant-resize-handle')) {
            pointerMode = 'resize';
            startX      = e.clientX;
            startDiam   = parseFloat(el.style.width);
            startLeft   = parseFloat(el.style.left);
            startTop    = parseFloat(el.style.top);
        } else {
            pointerMode = 'move';
            startX      = e.clientX;
            startY      = e.clientY;
            startLeft   = parseFloat(el.style.left);
            startTop    = parseFloat(el.style.top);
            el.classList.add('dragging');
        }
    });

    el.addEventListener('pointermove', (e) => {
        if (!pointerMode) return;
        didMove = true;
        if (pointerMode === 'move') {
            const dx = (e.clientX - startX) / zoom;
            const dy = (e.clientY - startY) / zoom;
            el.style.left = `${Math.max(0, startLeft + dx)}px`;
            el.style.top  = `${Math.max(0, startTop  + dy)}px`;
        } else {
            const dx      = (e.clientX - startX) / zoom;
            const newDiam = Math.max(PX * 0.5, startDiam + dx * 2);
            const delta   = newDiam - startDiam;
            el.style.width  = `${newDiam}px`;
            el.style.height = `${newDiam}px`;
            el.style.left   = `${startLeft - delta / 2}px`;
            el.style.top    = `${startTop  - delta / 2}px`;
        }
    });

    el.addEventListener('pointerup', async (e) => {
        if (!pointerMode) return;
        const mode = pointerMode;
        pointerMode = null;

        if (mode === 'move') {
            el.classList.remove('dragging');
            if (didMove) {
                const diam = parseFloat(el.style.width);
                const newX = (parseFloat(el.style.left) + diam / 2) / PX;
                const newY = (parseFloat(el.style.top)  + diam / 2) / PX;
                await api('POST', `/api/canvas-plants/${cp.id}/position`, { x: newX, y: newY });
                cp.pos_x = newX;
                cp.pos_y = newY;
            }
        } else if (mode === 'resize') {
            if (didMove) {
                const newDiam   = parseFloat(el.style.width);
                const newRadius = newDiam / 2 / PX;
                await api('POST', `/api/canvas-plants/${cp.id}/radius`, { radius_ft: newRadius });
                cp.radius_ft = newRadius;
                offerSpacingUpdate(cp, newRadius);
            }
        }
        didMove = false;
    });

    el.addEventListener('click', (e) => {
        if (e.target.classList.contains('canvas-plant-delete-btn')) return;
        if (e.target.classList.contains('canvas-plant-resize-handle')) return;
        if (didMove) return;
        document.querySelectorAll('.canvas-plant-circle.circle-active').forEach(c => c.classList.remove('circle-active'));
        document.querySelectorAll('.grid-plant-chip.chip-active').forEach(c => c.classList.remove('chip-active'));
        el.classList.add('circle-active');
        openCanvasPlantPanel(cp.id);
    });

    el.querySelector('.canvas-plant-delete-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        const name = cp.name || 'this plant';
        if (!confirm(`Remove "${name}" from canvas?`)) return;
        const r = await api('POST', `/api/canvas-plants/${cp.id}/delete`, {});
        if (r.ok) {
            el.remove();
            delete canvasPlantEls[cp.id];
            if (activeCanvasPlantId == cp.id) closeCanvasPlantPanel();
        }
    });
}

async function offerSpacingUpdate(cp, newRadiusFt) {
    if (!cp.library_id) return;
    const newSpacingIn = Math.round(newRadiusFt * 2 * 12);
    if (confirm(`Update default spacing for "${cp.name}" in the plant library to ${newSpacingIn}"?`)) {
        await api('POST', `/api/library/${cp.library_id}/quick-edit`, { spacing_in: newSpacingIn });
    }
}

async function openCanvasPlantPanel(cpId) {
    activeCanvasPlantId = cpId;
    try {
        const d = await fetch(`/api/canvas-plants/${cpId}`).then(r => r.json());
        // Populate the care section using existing function (no bed fields)
        populateCarePanel({
            plant_name:      d.name,
            scientific_name: d.scientific_name,
            sunlight:        d.sunlight,
            water:           d.water,
            spacing_in:      d.spacing_in,
            planted_date:    d.planted_date,
            transplant_date: d.transplant_date,
            plant_notes:     d.plant_notes,
            plant_id:        d.plant_id,
            id:              d.plant_id,
        }, false);
        // Populate lib section
        populateLibSection(d);
        // Populate appearance section
        populateAppearanceSection(d);
        // Show the new sections
        document.getElementById('rp-lib-section').style.display        = '';
        document.getElementById('rp-appearance-section').style.display = '';
    } catch (err) {
        console.error('openCanvasPlantPanel error:', err);
    }
}

function closeCanvasPlantPanel() {
    activeCanvasPlantId = null;
    const libSec  = document.getElementById('rp-lib-section');
    const appSec  = document.getElementById('rp-appearance-section');
    if (libSec)  libSec.style.display  = 'none';
    if (appSec)  appSec.style.display  = 'none';
    document.querySelectorAll('.canvas-plant-circle.circle-active').forEach(c => c.classList.remove('circle-active'));
}

function populateLibSection(d) {
    const entryId = d.library_id || '';
    document.getElementById('rp-lib-entry-id').value = entryId;

    const readonlyEl = document.getElementById('rp-lib-readonly');
    if (entryId) {
        let parts = [];
        if (d.sunlight)   parts.push(`☀ ${escapeHtml(d.sunlight)}`);
        if (d.water)      parts.push(`💧 ${escapeHtml(d.water)}`);
        if (d.spacing_in) parts.push(`↔ ${d.spacing_in}" spacing`);
        if (d.lib_notes)  parts.push(`<span style="font-size:0.7rem;">${escapeHtml(d.lib_notes.substring(0, 80))}${d.lib_notes.length > 80 ? '…' : ''}</span>`);
        readonlyEl.innerHTML = parts.join(' · ') || '<span class="rp-muted">No details.</span>';
    } else {
        readonlyEl.innerHTML = '<span class="rp-muted">No library entry linked.</span>';
    }

    document.getElementById('rp-lib-sunlight').value = d.sunlight   || '';
    document.getElementById('rp-lib-water').value    = d.water      || '';
    document.getElementById('rp-lib-spacing').value  = d.spacing_in || '';
    document.getElementById('rp-lib-notes').value    = d.lib_notes  || '';

    document.getElementById('rp-lib-form').style.display         = 'none';
    document.getElementById('rp-lib-edit-toggle').textContent    = 'Edit';
    document.getElementById('rp-lib-saved').style.display        = 'none';
    document.getElementById('rp-lib-edit-toggle').style.display  = entryId ? '' : 'none';
}

function populateAppearanceSection(d) {
    document.getElementById('rp-appearance-cp-id').value = d.id;
    document.getElementById('rp-circle-color').value     = d.color || '#5a9e54';

    document.querySelectorAll('.rp-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === (d.display_mode || 'color'));
    });

    const previewEl = document.getElementById('rp-image-preview');
    const imgEl     = document.getElementById('rp-image-preview-img');
    const saveBtn   = document.getElementById('rp-save-image-to-library-btn');
    if (d.custom_image) {
        imgEl.src               = `/static/canvas_plant_images/${d.custom_image}`;
        previewEl.style.display = '';
    } else if (d.display_mode === 'image' && d.image_filename) {
        imgEl.src               = `/static/plant_images/${d.image_filename}`;
        previewEl.style.display = '';
    } else {
        previewEl.style.display = 'none';
    }
    if (saveBtn) saveBtn.style.display = d.library_id ? '' : 'none';
}

// Lib section toggle
document.getElementById('rp-lib-edit-toggle')?.addEventListener('click', () => {
    const form    = document.getElementById('rp-lib-form');
    const isShown = form.style.display !== 'none';
    form.style.display = isShown ? 'none' : '';
    document.getElementById('rp-lib-edit-toggle').textContent = isShown ? 'Edit' : 'Cancel';
});

document.getElementById('rp-lib-cancel')?.addEventListener('click', () => {
    document.getElementById('rp-lib-form').style.display      = 'none';
    document.getElementById('rp-lib-edit-toggle').textContent = 'Edit';
});

document.getElementById('rp-lib-form')?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const entryId = document.getElementById('rp-lib-entry-id').value;
    if (!entryId) return;
    if (!confirm('Save these changes to the shared plant library? This affects all gardens.')) return;
    const result = await api('POST', `/api/library/${entryId}/quick-edit`, {
        sunlight:   document.getElementById('rp-lib-sunlight').value || null,
        water:      document.getElementById('rp-lib-water').value    || null,
        spacing_in: parseInt(document.getElementById('rp-lib-spacing').value) || null,
        notes:      document.getElementById('rp-lib-notes').value    || null,
    });
    if (result.ok) {
        document.getElementById('rp-lib-saved').style.display        = '';
        setTimeout(() => { document.getElementById('rp-lib-saved').style.display = 'none'; }, 2000);
        document.getElementById('rp-lib-form').style.display         = 'none';
        document.getElementById('rp-lib-edit-toggle').textContent    = 'Edit';
        // Refresh readonly display
        if (activeCanvasPlantId) openCanvasPlantPanel(activeCanvasPlantId);
    }
});

// Appearance: color input
document.getElementById('rp-circle-color')?.addEventListener('input', async (e) => {
    const cpId = document.getElementById('rp-appearance-cp-id').value;
    if (!cpId) return;
    const color = e.target.value;
    const el = document.getElementById(`canvas-plant-${cpId}`);
    if (el) el.style.backgroundColor = color;
});
document.getElementById('rp-circle-color')?.addEventListener('change', async (e) => {
    const cpId = document.getElementById('rp-appearance-cp-id').value;
    if (!cpId) return;
    const color = e.target.value;
    await api('POST', `/api/canvas-plants/${cpId}/appearance`, { color, display_mode: 'color' });
    const cp = (CANVAS_PLANTS_DATA || []).find(c => String(c.id) === String(cpId));
    if (cp) { cp.color = color; cp.display_mode = 'color'; }
    document.querySelectorAll('.rp-toggle-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === 'color'));
});

// Appearance: display mode toggle
document.querySelectorAll('.rp-toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const cpId = document.getElementById('rp-appearance-cp-id').value;
        if (!cpId) return;
        const mode = btn.dataset.mode;
        document.querySelectorAll('.rp-toggle-btn').forEach(b => b.classList.toggle('active', b === btn));
        await api('POST', `/api/canvas-plants/${cpId}/appearance`, { display_mode: mode });
        const cp = (CANVAS_PLANTS_DATA || []).find(c => String(c.id) === String(cpId));
        if (cp) {
            cp.display_mode = mode;
            const el = document.getElementById(`canvas-plant-${cpId}`);
            if (el) applyCircleAppearance(el, cp);
        }
    });
});

// Appearance: image upload
document.getElementById('rp-image-upload-btn')?.addEventListener('click', () => {
    document.getElementById('rp-image-file-input').click();
});

document.getElementById('rp-image-file-input')?.addEventListener('change', async () => {
    const cpId = document.getElementById('rp-appearance-cp-id').value;
    const file = document.getElementById('rp-image-file-input').files[0];
    if (!cpId || !file) return;
    const formData = new FormData();
    formData.append('image', file);
    try {
        const resp = await fetch(`/api/canvas-plants/${cpId}/upload-image`, { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.ok) {
            const imgEl = document.getElementById('rp-image-preview-img');
            imgEl.src = data.url;
            document.getElementById('rp-image-preview').style.display = '';
            const cp = (CANVAS_PLANTS_DATA || []).find(c => String(c.id) === String(cpId));
            if (cp) {
                cp.custom_image    = data.filename;
                cp.image_filename  = data.filename;
                cp.display_mode    = 'image';
                const el = document.getElementById(`canvas-plant-${cpId}`);
                if (el) applyCircleAppearance(el, cp);
            }
            document.querySelectorAll('.rp-toggle-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === 'image'));
            const saveBtn = document.getElementById('rp-save-image-to-library-btn');
            const libId   = document.getElementById('rp-lib-entry-id').value;
            if (saveBtn && libId) saveBtn.style.display = '';
        } else {
            alert(data.error || 'Upload failed');
        }
    } catch (err) {
        console.error('Image upload error:', err);
    }
    document.getElementById('rp-image-file-input').value = '';
});

// Appearance: save image to library
document.getElementById('rp-save-image-to-library-btn')?.addEventListener('click', async () => {
    const cpId = document.getElementById('rp-appearance-cp-id').value;
    if (!cpId) return;
    if (!confirm('Save this image to the plant library? It will appear for all plants of this type.')) return;
    const result = await api('POST', `/api/canvas-plants/${cpId}/save-image-to-library`, {});
    if (result.ok) {
        const saveBtn = document.getElementById('rp-save-image-to-library-btn');
        saveBtn.textContent = 'Saved to library ✓';
        setTimeout(() => { saveBtn.textContent = 'Save to plant library?'; }, 3000);
    } else {
        alert(result.error || 'Could not save image to library');
    }
});

// Initialize circles from server data
function initCanvasPlants() {
    (CANVAS_PLANTS_DATA || []).forEach(cp => renderCanvasPlant(cp));
}
initCanvasPlants();

// ── Create a new canvas-bed element ──────────────────────────────────────────
function createBedElement(bed) {
    const div = document.createElement('div');
    div.className = 'canvas-bed';
    div.id = `canvas-bed-${bed.id}`;
    div.setAttribute('draggable', 'true');
    div.dataset.bedId  = bed.id;
    div.dataset.width  = bed.width_ft;
    div.dataset.height = bed.height_ft;
    div.dataset.bedPlants = '[]';
    div.style.left   = '0px';
    div.style.top    = '0px';
    div.style.width  = `${bed.width_ft * PX}px`;
    div.style.height = `${bed.height_ft * PX}px`;

    const header = document.createElement('div');
    header.className = 'canvas-bed-header';
    header.innerHTML = `<span class="bed-header-name">${escapeHtml(bed.name)}</span>`
        + `<button class="bed-header-delete" data-bed-id="${bed.id}" data-bed-name="${escapeHtml(bed.name)}" title="Delete bed" draggable="false">×</button>`;
    bindBedHeaderDelete(header.querySelector('.bed-header-delete'));

    const grid = document.createElement('div');
    grid.className = 'canvas-bed-grid';
    grid.dataset.bedId = bed.id;

    div.appendChild(header);
    div.appendChild(grid);
    bindBedEvents(div);
    buildBedGrid(div);
    return div;
}

// ── Bind move-drag events to a canvas bed ────────────────────────────────────
function bindBedEvents(bedEl) {
    bedEl.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('chip-remove')) {
            e.stopPropagation(); e.preventDefault(); return;
        }
        if (e.target.closest('.canvas-bed-grid')) {
            e.stopPropagation(); e.preventDefault(); return;
        }
        const rect = bedEl.getBoundingClientRect();
        dragState = {
            type: 'bed-canvas',
            bedId: bedEl.dataset.bedId,
            offsetX: e.clientX - rect.left,
            offsetY: e.clientY - rect.top,
        };
        e.dataTransfer.effectAllowed = 'move';
        setTimeout(() => bedEl.classList.add('dragging'), 0);
    });

    bedEl.addEventListener('dragend', () => bedEl.classList.remove('dragging'));
}

// ── Canvas: dragover ──────────────────────────────────────────────────────────
canvas.addEventListener('dragover', (e) => {
    if (!dragState) return;
    e.preventDefault();

    if (dragState.type === 'plant') {
        e.dataTransfer.dropEffect = 'copy';
        return;
    }

    e.dataTransfer.dropEffect = 'move';

    if (dragState.type === 'bed-canvas') {
        const cr   = canvas.getBoundingClientRect();
        const rawX = (e.clientX - cr.left - dragState.offsetX) / zoom;
        const rawY = (e.clientY - cr.top  - dragState.offsetY) / zoom;
        const bedEl = document.getElementById(`canvas-bed-${dragState.bedId}`);
        if (bedEl) {
            bedEl.style.left = `${snap(Math.max(0, rawX))}px`;
            bedEl.style.top  = `${snap(Math.max(0, rawY))}px`;
        }
    }
});

// ── Canvas: drop ──────────────────────────────────────────────────────────────
canvas.addEventListener('drop', async (e) => {
    e.preventDefault();
    if (!dragState) return;
    const cr = canvas.getBoundingClientRect();

    // ── Plant drop onto a grid cell or bare canvas ──
    if (dragState.type === 'plant') {
        const target  = document.elementFromPoint(e.clientX, e.clientY);
        const grid    = target && target.closest('.canvas-bed-grid');
        const bedEl   = target && target.closest('.canvas-bed');
        if (grid) {
            const tilePx   = tileIn * PX_PER_IN;
            const rect     = grid.getBoundingClientRect();
            const cx       = Math.floor((e.clientX - rect.left) / zoom / tilePx);
            const cy       = Math.floor((e.clientY - rect.top)  / zoom / tilePx);
            const spacingIn = dragState.spacingIn || 12;
            const span     = plantSpan(spacingIn);

            // Clear hover highlight
            setDropHighlight(grid, cx, cy, span, false);
            grid.classList.remove('drop-active');

            if (canPlace(grid, cx, cy, span)) {
                const bedId = grid.dataset.bedId;
                const gridX = cx * tileIn;
                const gridY = cy * tileIn;
                const payload = { bed_id: bedId, grid_x: gridX, grid_y: gridY, spacing_in: spacingIn };
                if (dragState.libraryId) payload.library_id = dragState.libraryId;
                else if (dragState.plantId) payload.plant_id = dragState.plantId;

                const result = await api('POST', `/api/beds/${bedId}/grid-plant`, payload);
                if (result.ok) {
                    const sIn = result.spacing_in || spacingIn;
                    renderChipInGrid(grid, result.id, cx, cy, result.plant_name, result.image_filename, sIn, 'seedling');
                    updateBedPlantsData(grid.closest('.canvas-bed'), result.id, result.plant_name, result.image_filename, sIn, gridX, gridY);
                    // If dragged from library (creates a new Plant), add it to the sidebar
                    if (dragState && dragState.libraryId && result.plant_id) {
                        addPlantToGardenPalette(result.plant_id, result.library_id, result.plant_name, result.image_filename, sIn);
                    }
                }
            }
        } else if (!bedEl) {
            // Dropped on bare canvas — create a free-placed circle
            const posX = (e.clientX - cr.left) / zoom / PX;
            const posY = (e.clientY - cr.top)  / zoom / PX;
            const result = await api('POST', `/api/gardens/${GARDEN_ID}/canvas-plants`, {
                library_id: dragState.libraryId || null,
                plant_id:   dragState.plantId   || null,
                pos_x: posX,
                pos_y: posY,
            });
            if (result.ok) {
                renderCanvasPlant(result.canvas_plant);
                if (dragState.libraryId && result.canvas_plant.plant_id) {
                    addPlantToGardenPalette(
                        result.canvas_plant.plant_id,
                        result.canvas_plant.library_id,
                        result.canvas_plant.name,
                        result.canvas_plant.image_filename,
                        result.canvas_plant.spacing_in || 12
                    );
                }
            }
        }
        dragState = null;
        return;
    }

    // ── Bed repositioning ──
    if (dragState.type === 'bed-canvas') {
        const rawX  = (e.clientX - cr.left - dragState.offsetX) / zoom;
        const rawY  = (e.clientY - cr.top  - dragState.offsetY) / zoom;
        const sx    = snap(Math.max(0, rawX));
        const sy    = snap(Math.max(0, rawY));
        const bedEl = document.getElementById(`canvas-bed-${dragState.bedId}`);
        if (bedEl) { bedEl.style.left = `${sx}px`; bedEl.style.top = `${sy}px`; }
        await api('POST', `/api/beds/${dragState.bedId}/position`, { x: sx / PX, y: sy / PX });

    // ── Bed from palette onto canvas ──
    } else if (dragState.type === 'bed-palette') {
        const sx = snap(Math.max(0, (e.clientX - cr.left) / zoom));
        const sy = snap(Math.max(0, (e.clientY - cr.top)  / zoom));
        await api('POST', `/api/beds/${dragState.bedId}/assign-garden`, { garden_id: GARDEN_ID });
        await api('POST', `/api/beds/${dragState.bedId}/position`, { x: sx / PX, y: sy / PX });

        const bedEl = createBedElement({
            id: dragState.bedId, name: dragState.name,
            width_ft: dragState.width, height_ft: dragState.height,
        });
        bedEl.style.left = `${sx}px`;
        bedEl.style.top  = `${sy}px`;
        canvas.appendChild(bedEl);

        const paletteItem = document.querySelector(`#palette-beds .palette-bed[data-bed-id="${dragState.bedId}"]`);
        if (paletteItem) paletteItem.remove();
    }

    dragState = null;
});

// ── Plant palette drag start ──────────────────────────────────────────────────
function bindPalettePlantDrag(el) {
    el.addEventListener('dragstart', (e) => {
        e.stopPropagation();
        dragState = {
            type:      'plant',
            libraryId: el.dataset.libraryId || null,
            plantId:   el.dataset.plantId   || null,
            name:      el.dataset.name,
            image:     el.dataset.image,
            spacingIn: parseInt(el.dataset.spacing) || 12,
        };
        e.dataTransfer.effectAllowed = 'copy';
    });
    if (el.tagName === 'SUMMARY') {
        el.addEventListener('click', (e) => { if (dragState) e.preventDefault(); });
    }
}
document.querySelectorAll('.palette-plant').forEach(bindPalettePlantDrag);

// ── Add a newly-created plant to the "Plants in this Garden" sidebar ──────────
function addPlantToGardenPalette(plantId, libraryId, name, imageFilename, spacingIn) {
    // Find or create the palette list
    let list = document.getElementById('palette-garden-plants');
    if (!list) {
        // No plants yet — the template rendered a <p> instead of a <ul>
        const section = document.querySelector('.sidebar-section details');
        if (!section) return;
        const noMsg = section.querySelector('p.muted');
        list = document.createElement('ul');
        list.className = 'palette-list';
        list.id = 'palette-garden-plants';
        list.style.marginTop = '0.4rem';
        if (noMsg) noMsg.replaceWith(list);
        else section.appendChild(list);
        // Re-attach the event-delegation delete handler for this new list
        list.addEventListener('click', gardenPlantDeleteHandler);
    }

    const imgHtml = imageFilename
        ? `<img src="/static/plant_images/${imageFilename}" class="palette-plant-img" alt="${escapeHtml(name)}">`
        : `<span class="palette-plant-img palette-plant-img--empty">🌱</span>`;
    const infoHref = libraryId
        ? `/library/${libraryId}?back=${encodeURIComponent(window.location.pathname)}`
        : null;
    const infoBtn = infoHref
        ? `<a class="palette-info-btn" href="${infoHref}" title="View plant info" draggable="false">ℹ</a>`
        : '';

    const li = document.createElement('li');
    li.className = 'palette-item palette-plant';
    li.setAttribute('draggable', 'true');
    li.dataset.plantId   = plantId;
    li.dataset.libraryId = libraryId || '';
    li.dataset.name      = name;
    li.dataset.image     = imageFilename || '';
    li.dataset.spacing   = spacingIn;
    li.innerHTML = `${imgHtml}<span class="palette-plant-name">${escapeHtml(name)}</span>`
                 + `<span class="palette-type">Unplaced</span>`
                 + infoBtn
                 + `<button class="palette-delete-btn" data-plant-id="${plantId}" title="Delete plant" draggable="false">×</button>`;
    bindPalettePlantDrag(li);
    list.appendChild(li);
}

// ── Bed palette drag start ────────────────────────────────────────────────────
document.querySelectorAll('.palette-bed').forEach(el => {
    el.addEventListener('dragstart', (e) => {
        dragState = {
            type: 'bed-palette',
            bedId:  el.dataset.bedId,
            width:  parseFloat(el.dataset.width),
            height: parseFloat(el.dataset.height),
            name:   el.dataset.name,
        };
        e.dataTransfer.effectAllowed = 'move';
    });
});

// ── Add Bed form ──────────────────────────────────────────────────────────────
const addBedForm = document.getElementById('add-bed-form');
if (addBedForm) {
    addBedForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data   = Object.fromEntries(new FormData(addBedForm));
        const result = await api('POST', '/api/beds', {
            name:      data.name,
            width_ft:  parseFloat(data.width_ft)  || 4,
            height_ft: parseFloat(data.height_ft) || 8,
            garden_id: GARDEN_ID,
        });

        if (result.ok) {
            const bed = result.bed;
            const li  = document.createElement('li');
            li.className = 'palette-item palette-bed';
            li.setAttribute('draggable', 'true');
            li.dataset.bedId  = bed.id;
            li.dataset.width  = bed.width_ft;
            li.dataset.height = bed.height_ft;
            li.dataset.name   = bed.name;
            li.innerHTML = `${escapeHtml(bed.name)} <span class="palette-size">${bed.width_ft}×${bed.height_ft}</span>`;
            li.addEventListener('dragstart', () => {
                dragState = { type: 'bed-palette', bedId: bed.id, width: bed.width_ft, height: bed.height_ft, name: bed.name };
            });
            document.getElementById('palette-beds').appendChild(li);
            addBedForm.reset();
            addBedForm.closest('details').removeAttribute('open');
        }
    });
}

// ── Delete bed from sidebar palette ──────────────────────────────────────────
document.getElementById('palette-beds')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('.palette-delete-btn[data-bed-id]');
    if (!btn) return;
    e.stopPropagation();
    const bedId   = btn.dataset.bedId;
    const bedName = btn.dataset.bedName || 'this bed';
    if (!confirm(`Delete bed "${bedName}"? This will remove all plants placed in it.`)) return;
    const result = await api('POST', `/api/beds/${bedId}/delete`);
    if (result.ok) btn.closest('li').remove();
});

// ── Delete bed from canvas header ─────────────────────────────────────────────
function bindBedHeaderDelete(btn) {
    btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const bedId   = btn.dataset.bedId;
        const bedName = btn.dataset.bedName || 'this bed';
        if (!confirm(`Delete bed "${bedName}"? This will remove all plants placed in it.`)) return;
        const result = await api('POST', `/api/beds/${bedId}/delete`);
        if (result.ok) {
            document.getElementById(`canvas-bed-${bedId}`)?.remove();
        }
    });
}

// Bind to all template-rendered bed header delete buttons on load
document.querySelectorAll('.bed-header-delete').forEach(bindBedHeaderDelete);

// ── Delete garden plant from sidebar ─────────────────────────────────────────
async function gardenPlantDeleteHandler(e) {
    const btn = e.target.closest('.palette-delete-btn');
    if (!btn) return;
    e.stopPropagation();
    const plantId = btn.dataset.plantId;
    const name = btn.closest('.palette-item, summary')?.querySelector('.palette-plant-name')?.textContent?.trim() || 'this plant';
    if (!confirm(`Delete "${name}" from this garden?`)) return;

    const result = await api('POST', `/api/plants/${plantId}/delete`);
    if (result.ok) {
        const li = btn.closest('li');
        const groupDetails = li.closest('details');
        if (groupDetails) {
            const remaining = groupDetails.querySelectorAll('.palette-instance');
            if (remaining.length <= 1) {
                groupDetails.closest('.palette-group')?.remove();
            } else {
                li.remove();
            }
        } else {
            li.remove();
        }
    }
}
document.getElementById('palette-garden-plants')?.addEventListener('click', gardenPlantDeleteHandler);

// ── Plant search filter ───────────────────────────────────────────────────────
const plantSearch = document.getElementById('plant-search');
if (plantSearch) {
    plantSearch.addEventListener('input', () => {
        const q = plantSearch.value.toLowerCase();
        document.querySelectorAll('#palette-plants .palette-plant').forEach(el => {
            el.style.display = el.dataset.name.toLowerCase().includes(q) ? '' : 'none';
        });
    });
}

// ── Plant Care Panel ──────────────────────────────────────────────────────────
const careSec      = document.getElementById('rp-plant-care-section');
const careNameEl   = document.getElementById('rp-care-name');
const careMetaEl   = document.getElementById('rp-care-meta');
const careBpId     = document.getElementById('rp-care-bp-id');
const carePlantId  = document.getElementById('rp-care-plant-id');
const careSeeded   = document.getElementById('rp-care-seeded');
const careTransp   = document.getElementById('rp-care-transplanted');
const careWatered  = document.getElementById('rp-care-watered');
const careFertEl   = document.getElementById('rp-care-fertilized');
const careHarvest  = document.getElementById('rp-care-harvested');
const careNotes    = document.getElementById('rp-care-notes');
const careHealth   = document.getElementById('rp-care-health');
const careForm     = document.getElementById('rp-care-form');
const careSaved    = document.getElementById('rp-care-saved');

function closePlantCarePanel() {
    if (careSec) careSec.style.display = 'none';
    document.querySelectorAll('.grid-plant-chip.chip-active').forEach(c => c.classList.remove('chip-active'));
    closeCanvasPlantPanel();
}

function populateCarePanel(d, hasBed) {
    careNameEl.textContent = d.plant_name || d.name || '';
    let meta = [];
    if (d.scientific_name) meta.push(`<em>${escapeHtml(d.scientific_name)}</em>`);
    if (d.sunlight)        meta.push(`☀ ${escapeHtml(d.sunlight)}`);
    if (d.water)           meta.push(`💧 ${escapeHtml(d.water)}`);
    if (d.spacing_in)      meta.push(`↔ ${d.spacing_in}" spacing`);
    careMetaEl.innerHTML = meta.join(' · ');

    careSeeded.value  = d.planted_date    || '';
    careTransp.value  = d.transplant_date || '';
    careNotes.value   = d.plant_notes     || '';

    // Bed-specific fields
    document.querySelectorAll('.rp-bed-field').forEach(el => {
        el.style.display = hasBed ? '' : 'none';
    });
    if (hasBed) {
        careWatered.value = d.last_watered    || '';
        careFertEl.value  = d.last_fertilized || '';
        careHarvest.value = d.last_harvest    || '';
        careHealth.value  = d.health_notes    || '';
        const stageEl = document.getElementById('rp-care-stage');
        if (stageEl) stageEl.value = d.stage || 'seedling';
    }

    careBpId.value    = d.bp_id    || d.id    || '';
    carePlantId.value = d.plant_id || d.id    || '';
    careSec.style.display = '';

    // Ensure right panel is open
    const panel = document.getElementById('planner-right-panel');
    const btn   = document.getElementById('right-panel-toggle');
    if (panel && !panel.classList.contains('open')) {
        panel.classList.add('open');
        if (btn) btn.classList.add('active');
        localStorage.setItem('plannerRightPanel', 'open');
        if (typeof loadPanelData === 'function') loadPanelData();
    }
}

async function openPlantCarePanel({ bpId, plantId }) {
    try {
        let d;
        if (bpId) {
            d = await fetch(`/api/bedplants/${bpId}`).then(r => r.json());
            populateCarePanel(d, true);
        } else {
            d = await fetch(`/api/plants/${plantId}/detail`).then(r => r.json());
            const hasBed = !!d.bp_id;
            // If plant is in a bed, use the full bedplant endpoint for care fields
            if (hasBed) {
                const full = await fetch(`/api/bedplants/${d.bp_id}`).then(r => r.json());
                populateCarePanel(full, true);
            } else {
                populateCarePanel(d, false);
            }
        }
    } catch (e) {
        console.error('openPlantCarePanel error:', e);
    }
}

// Care form submit
if (careForm) {
    careForm.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const bpId    = careBpId.value;
        const plantId = carePlantId.value;
        const payload = {
            planted_date:    careSeeded.value  || null,
            transplant_date: careTransp.value  || null,
            plant_notes:     careNotes.value   || null,
        };
        const hasBed = document.querySelector('.rp-bed-field')?.style.display !== 'none';
        if (hasBed && bpId) {
            payload.last_watered    = careWatered.value || null;
            payload.last_fertilized = careFertEl.value  || null;
            payload.last_harvest    = careHarvest.value || null;
            payload.health_notes    = careHealth.value  || null;
            const stageEl = document.getElementById('rp-care-stage');
            if (stageEl) payload.stage = stageEl.value || null;
            await api('POST', `/api/bedplants/${bpId}/care`, payload);
        } else if (plantId) {
            await api('POST', `/api/plants/${plantId}/care`, payload);
        }
        if (careSaved) {
            careSaved.style.display = '';
            setTimeout(() => { careSaved.style.display = 'none'; }, 2000);
        }
        // Update stage badge on the active chip
        if (hasBed && bpId && payload.stage) {
            const chip = document.querySelector(`.grid-plant-chip[data-bp-id="${bpId}"]`);
            if (chip) {
                let badge = chip.querySelector('.chip-stage-badge');
                const stageLabels = { seedling: '🌱', growing: '🌿', harvesting: '🥕', done: '✓' };
                if (payload.stage === 'seedling') {
                    badge?.remove();
                } else {
                    if (!badge) { badge = document.createElement('span'); chip.appendChild(badge); }
                    badge.className = `chip-stage-badge stage-${payload.stage}`;
                    badge.textContent = stageLabels[payload.stage] || payload.stage;
                }
            }
        }
    });
}

// Close button
document.getElementById('rp-care-close')?.addEventListener('click', closePlantCarePanel);

// Sidebar "Plants in this Garden" — click plant to open care panel
document.getElementById('palette-garden-plants')?.addEventListener('click', (ev) => {
    // Don't fire on delete button or info link
    if (ev.target.closest('button, a')) return;
    const item = ev.target.closest('.palette-plant');
    if (!item) return;
    const plantId = item.dataset.plantId;
    if (!plantId) return;
    openPlantCarePanel({ plantId });
});

// ── Right Info Panel ──────────────────────────────────────────────────────────
let loadPanelData = () => {}; // set below; allows plant care panel to trigger it
let refreshTasks  = () => {}; // set below; used by add-task modal

(function () {
    const panel      = document.getElementById('planner-right-panel');
    const toggleBtn  = document.getElementById('right-panel-toggle');
    if (!panel || !toggleBtn) return;

    const gd = typeof GARDEN_DATA !== 'undefined' ? GARDEN_DATA : null;

    loadPanelData = function() {
        if (!gd) return;
        renderGardenInfo();
        loadTasks();
        if (gd.latitude) {
            loadWeather();
        } else {
            const noLoc = '<p class="rp-muted" style="margin-top:0.4rem;">No location set. <a href="/gardens/' + gd.id + '" style="color:#3a6b35;">Set location →</a></p>';
            const wEl = document.getElementById('rp-weather-loading');
            if (wEl) wEl.outerHTML = noLoc;
        }
    };

    let panelDataLoaded = false;

    // Restore panel state
    if (localStorage.getItem('plannerRightPanel') === 'open') {
        panel.classList.add('open');
        toggleBtn.classList.add('active');
        loadPanelData();
        panelDataLoaded = true;
    }

    toggleBtn.addEventListener('click', () => {
        const opening = !panel.classList.contains('open');
        panel.classList.toggle('open', opening);
        toggleBtn.classList.toggle('active', opening);
        localStorage.setItem('plannerRightPanel', opening ? 'open' : 'closed');
        if (opening && !panelDataLoaded) { loadPanelData(); panelDataLoaded = true; }
    });

    // Condition string → icon emoji
    function conditionIcon(str) {
        const s = (str || '').toLowerCase();
        if (s.includes('thunder'))  return '⛈️';
        if (s.includes('snow') || s.includes('blizzard')) return '❄️';
        if (s.includes('sleet') || s.includes('freezing')) return '🌨️';
        if (s.includes('heavy rain') || s.includes('shower')) return '🌦️';
        if (s.includes('rain') || s.includes('drizzle')) return '🌧️';
        if (s.includes('fog') || s.includes('mist') || s.includes('haze')) return '🌫️';
        if (s.includes('overcast')) return '☁️';
        if (s.includes('cloud') || s.includes('partly')) return '🌤️';
        if (s.includes('clear') || s.includes('sunny')) return '☀️';
        return '🌡️';
    }

    function fmtDate(iso) {
        if (!iso) return '';
        const d = new Date(iso + 'T00:00:00');
        return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    }

    function dayAbbr(iso) {
        const d = new Date(iso + 'T00:00:00');
        return d.toLocaleDateString('en-US', { weekday: 'short' });
    }

    function renderGardenInfo() {
        if (!gd) return;
        const el = document.getElementById('rp-garden-info');
        if (!el) return;
        let html = '';
        if (gd.usda_zone) html += `<div class="rp-zone-badge">Zone ${escapeHtml(gd.usda_zone)}</div>`;
        if (gd.zone_temp_range) html += `<div class="rp-info-row"><span class="rp-info-label">Winter low</span>${escapeHtml(gd.zone_temp_range)}</div>`;
        const location = [gd.city, gd.state].filter(Boolean).join(', ') + (gd.zip_code ? ' ' + gd.zip_code : '');
        if (location.trim()) html += `<div class="rp-info-row"><span class="rp-info-label">Location</span>${escapeHtml(location)}</div>`;
        html += `<div class="rp-info-row"><span class="rp-info-label">Unit</span>${escapeHtml(gd.unit)}</div>`;
        if (gd.last_frost_date) html += `<div class="rp-info-row"><span class="rp-info-label">Last frost</span>${escapeHtml(gd.last_frost_date)}</div>`;
        if (gd.rainfall_7d && gd.rainfall_7d.days_with_data > 0) {
            html += `<div class="rp-info-row"><span class="rp-info-label">7-day rain</span>${gd.rainfall_7d.total_in}"</div>`;
        }
        html += `<div style="margin-top:0.4rem;"><a href="/gardens/${gd.id}" style="font-size:0.78rem;color:#3a6b35;">✎ Edit garden →</a></div>`;
        el.innerHTML = html;
    }

    async function loadWeather() {
        const loading = document.getElementById('rp-weather-loading');
        const content = document.getElementById('rp-weather-content');
        const errEl   = document.getElementById('rp-weather-error');
        if (!content) return;
        try {
            const data = await fetch(`/api/gardens/${gd.id}/weather`).then(r => r.json());
            if (data.error) throw new Error(data.error === 'no_location' ? 'No location set' : data.error);
            const c = data.current;
            const f = data.frost;
            let html = `<div class="rp-current">
                <span class="rp-current-icon">${conditionIcon(c.condition)}</span>
                <span class="rp-current-temp">${Math.round(c.temp)}°F</span>
                <span class="rp-current-details">${escapeHtml(c.condition)}<br>${c.humidity}% · ${Math.round(c.wind_speed)} mph</span>
            </div>`;
            if (f && f.last_spring !== 'unknown') {
                html += `<div class="rp-frost-row">🌱 Last frost: ${escapeHtml(f.last_spring)} &nbsp; 🍂 First fall: ${escapeHtml(f.first_fall)}</div>`;
            }
            html += '<div class="rp-forecast">';
            (data.daily || []).forEach(day => {
                html += `<div class="rp-forecast-day">
                    <span class="rp-day-name">${dayAbbr(day.date)}</span>
                    <span class="rp-day-icon">${conditionIcon(day.condition)}</span>
                    <span class="rp-day-hi">${Math.round(day.high)}°</span>
                    <span class="rp-day-lo">${Math.round(day.low)}°</span>
                    ${day.precip_prob != null ? `<span class="rp-day-rain">💧${day.precip_prob}%</span>` : ''}
                </div>`;
            });
            html += '</div>';
            content.innerHTML = html;
            if (loading) loading.style.display = 'none';
            content.style.display = '';
        } catch (err) {
            if (loading) loading.style.display = 'none';
            if (errEl) { errEl.textContent = 'Weather unavailable: ' + err.message; errEl.style.display = ''; }
        }
    }

    refreshTasks = function() { loadTasks(); };

    async function loadTasks() {
        const loading = document.getElementById('rp-tasks-loading');
        const list    = document.getElementById('rp-tasks-list');
        if (!list) return;
        try {
            const tasks = await fetch(`/api/gardens/${gd.id}/tasks`).then(r => r.json());
            if (loading) loading.style.display = 'none';
            if (!tasks.length) {
                list.innerHTML = '<p class="rp-muted">No pending tasks.</p>';
                return;
            }
            list.innerHTML = tasks.map(t => {
                const due = t.due_date ? `Due ${fmtDate(t.due_date)}` : '';
                const plant = t.plant_name ? ` · ${escapeHtml(t.plant_name)}` : '';
                const typeTag = (t.task_type && t.task_type !== 'other')
                    ? `<span style="font-size:0.72rem;background:#e8f5e8;padding:1px 5px;border-radius:3px;margin-right:4px;">${escapeHtml(t.task_type)}</span>`
                    : '';
                return `<div class="rp-task-item">
                    <div class="rp-task-title">${typeTag}${escapeHtml(t.title)}</div>
                    <div class="rp-task-meta">${due}${plant}</div>
                </div>`;
            }).join('');
        } catch (err) {
            if (loading) loading.style.display = 'none';
            if (list) list.innerHTML = '<p class="rp-error">Could not load tasks.</p>';
        }
    }
})();

// ── Add Task Modal ────────────────────────────────────────────────────────────
(function () {
    const modal     = document.getElementById('add-task-modal');
    const openBtn   = document.getElementById('add-task-btn');
    const closeBtn  = document.getElementById('add-task-modal-close');
    const form      = document.getElementById('add-task-form');
    const savedMsg  = document.getElementById('add-task-saved');
    if (!modal || !openBtn) return;

    function openModal() {
        modal.style.display = 'flex';
        document.getElementById('add-task-title').value = '';
        document.getElementById('add-task-due').value   = '';
        document.getElementById('add-task-desc').value  = '';
        if (savedMsg) savedMsg.style.display = 'none';
    }
    function closeModal() { modal.style.display = 'none'; }

    openBtn.addEventListener('click', openModal);
    closeBtn?.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    async function submitTask(payload) {
        const resp = await api('POST', `/api/gardens/${GARDEN_ID}/quick-task`, payload);
        return resp;
    }

    // Preset buttons
    document.getElementById('task-preset-grid')?.addEventListener('click', async (e) => {
        const btn = e.target.closest('.task-preset-btn');
        if (!btn) return;
        const origText = btn.textContent;
        btn.classList.add('preset-loading');
        btn.textContent = origText + ' …';
        try {
            const result = await submitTask({ task_type: btn.dataset.type });
            if (result.ok) {
                refreshTasks();
                closeModal();
            }
        } finally {
            btn.classList.remove('preset-loading');
            btn.textContent = origText;
        }
    });

    // Custom task form
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title   = document.getElementById('add-task-title').value.trim();
        const dueRaw  = document.getElementById('add-task-due').value;
        const desc    = document.getElementById('add-task-desc').value.trim();
        if (!title) return;
        const payload = { task_type: 'other', title };
        if (dueRaw)  payload.due_date = dueRaw;
        if (desc)    payload.description = desc;
        const result = await submitTask(payload);
        if (result.ok) {
            if (savedMsg) { savedMsg.style.display = ''; setTimeout(() => { savedMsg.style.display = 'none'; }, 1500); }
            refreshTasks();
            form.reset();
        }
    });
})();

// ── Zoom ──────────────────────────────────────────────────────────────────────
const ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25, 1.5, 2.0];
const CANVAS_NATURAL_W = 2400;
const CANVAS_NATURAL_H = 1800;

function applyZoom(newZoom) {
    zoom = Math.min(2.0, Math.max(0.25, newZoom));
    canvas.style.transform       = `scale(${zoom})`;
    canvas.style.transformOrigin = 'top left';

    const sizer = document.getElementById('canvas-sizer');
    if (sizer) {
        sizer.style.width  = `${CANVAS_NATURAL_W * zoom}px`;
        sizer.style.height = `${CANVAS_NATURAL_H * zoom}px`;
    }

    const display = document.getElementById('zoom-display');
    if (display) display.textContent = `${Math.round(zoom * 100)}%`;

    updateScaleBar();
    localStorage.setItem('plannerZoom', zoom);
}

function updateScaleBar() {
    const fill  = document.getElementById('scale-bar-fill');
    const label = document.getElementById('scale-bar-label');
    if (!fill || !label) return;

    // Find a "nice" distance that renders near 100 viewport px
    const niceDistances = [0.5, 1, 2, 4, 5, 10, 15, 20, 30, 50];
    const targetFt = 100 / (PX * zoom);
    const niceFt   = niceDistances.find(d => d >= targetFt) || niceDistances[niceDistances.length - 1];
    const barPx    = niceFt * PX * zoom;

    fill.style.width = `${barPx}px`;
    if (niceFt < 1) {
        label.textContent = `${Math.round(niceFt * 12)}"`;
    } else {
        label.textContent = `${niceFt} ft`;
    }
}

(function initZoom() {
    const zoomIn  = document.getElementById('zoom-in-btn');
    const zoomOut = document.getElementById('zoom-out-btn');

    if (zoomIn) {
        zoomIn.addEventListener('click', () => {
            const idx = ZOOM_STEPS.findIndex(z => z > zoom);
            if (idx !== -1) applyZoom(ZOOM_STEPS[idx]);
        });
    }
    if (zoomOut) {
        zoomOut.addEventListener('click', () => {
            const reversed = [...ZOOM_STEPS].reverse();
            const step = reversed.find(z => z < zoom);
            if (step !== undefined) applyZoom(step);
        });
    }

    // Ctrl+scroll wheel zoom
    const wrap = document.querySelector('.planner-canvas-wrap');
    if (wrap) {
        wrap.addEventListener('wheel', (e) => {
            if (!e.ctrlKey) return;
            e.preventDefault();
            if (e.deltaY < 0) {
                const idx = ZOOM_STEPS.findIndex(z => z > zoom);
                if (idx !== -1) applyZoom(ZOOM_STEPS[idx]);
            } else {
                const reversed = [...ZOOM_STEPS].reverse();
                const step = reversed.find(z => z < zoom);
                if (step !== undefined) applyZoom(step);
            }
        }, { passive: false });
    }

    applyZoom(zoom); // apply saved zoom on load
})();

// ── Navigate / Select mode ────────────────────────────────────────────────────
let canvasMode = localStorage.getItem('plannerCanvasMode') || 'select';
const canvasWrap = document.querySelector('.planner-canvas-wrap');
const modeSelectBtn   = document.getElementById('mode-select-btn');
const modeNavigateBtn = document.getElementById('mode-navigate-btn');

function setCanvasMode(mode) {
    canvasMode = mode;
    // Persist non-draw modes so the preferred mode is restored on next load
    if (mode === 'select' || mode === 'navigate') {
        localStorage.setItem('plannerCanvasMode', mode);
    }
    // When switching to select or navigate, deactivate any active draw tool
    if (mode !== 'draw') {
        // Guard: deactivateTool is defined in drawing.js which loads after this file
        if (typeof deactivateTool === 'function' &&
            typeof activeTool !== 'undefined' && activeTool) {
            deactivateTool();
        }
    }
    if (mode === 'navigate') {
        canvasWrap && canvasWrap.classList.add('navigate-mode');
        modeNavigateBtn && modeNavigateBtn.classList.add('active');
        modeSelectBtn   && modeSelectBtn.classList.remove('active');
    } else if (mode === 'select') {
        canvasWrap && canvasWrap.classList.remove('navigate-mode');
        modeSelectBtn   && modeSelectBtn.classList.add('active');
        modeNavigateBtn && modeNavigateBtn.classList.remove('active');
    } else {
        // 'draw' mode: neither mode button is active, no panning
        canvasWrap && canvasWrap.classList.remove('navigate-mode');
        modeSelectBtn   && modeSelectBtn.classList.remove('active');
        modeNavigateBtn && modeNavigateBtn.classList.remove('active');
    }
}

// Navigate: pan on mousedown+drag on canvas background
if (canvasWrap) {
    let panStart = null;

    canvasWrap.addEventListener('mousedown', (e) => {
        if (canvasMode !== 'navigate') return;
        // Only pan if clicking on background (not on a bed/chip/circle)
        if (e.target.closest('.canvas-bed, .canvas-plant-circle, .grid-plant-chip')) return;
        panStart = { x: e.clientX, y: e.clientY, sl: canvasWrap.scrollLeft, st: canvasWrap.scrollTop };
        canvasWrap.classList.add('panning');
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!panStart) return;
        const dx = e.clientX - panStart.x;
        const dy = e.clientY - panStart.y;
        canvasWrap.scrollLeft = panStart.sl - dx;
        canvasWrap.scrollTop  = panStart.st - dy;
    });

    window.addEventListener('mouseup', () => {
        if (!panStart) return;
        panStart = null;
        canvasWrap.classList.remove('panning');
    });
}

modeSelectBtn?.addEventListener('click', () => setCanvasMode('select'));
modeNavigateBtn?.addEventListener('click', () => setCanvasMode('navigate'));
setCanvasMode(canvasMode); // apply on load

// ── Multi-select plants ───────────────────────────────────────────────────────
// Each entry: { type: 'chip'|'circle', id: bpId|cpId, el: element }
const selectedPlants = new Map(); // key = 'chip-<bpId>' or 'circle-<cpId>'

function togglePlantSelection(key, entry) {
    if (selectedPlants.has(key)) {
        selectedPlants.delete(key);
        entry.el.classList.remove('chip-multi-selected', 'circle-multi-selected');
    } else {
        selectedPlants.set(key, entry);
        if (entry.type === 'chip') {
            entry.el.classList.add('chip-multi-selected');
            entry.el.classList.remove('chip-active');
        } else {
            entry.el.classList.add('circle-multi-selected');
            entry.el.classList.remove('circle-active');
        }
    }
    updateSelectionUI();
}

function clearSelection() {
    selectedPlants.forEach(entry => {
        entry.el.classList.remove('chip-multi-selected', 'circle-multi-selected');
    });
    selectedPlants.clear();
    const cb = document.getElementById('select-all-plants');
    if (cb) cb.checked = false;
    updateSelectionUI();
}

function selectAllPlants() {
    clearSelection();
    document.querySelectorAll('.grid-plant-chip').forEach(chip => {
        const bpId = chip.dataset.bpId;
        if (!bpId) return;
        const key = `chip-${bpId}`;
        selectedPlants.set(key, { type: 'chip', id: bpId, el: chip });
        chip.classList.add('chip-multi-selected');
        chip.classList.remove('chip-active');
    });
    document.querySelectorAll('.canvas-plant-circle').forEach(circle => {
        const cpId = circle.dataset.cpId;
        if (!cpId) return;
        const key = `circle-${cpId}`;
        selectedPlants.set(key, { type: 'circle', id: cpId, el: circle });
        circle.classList.add('circle-multi-selected');
        circle.classList.remove('circle-active');
    });
    const cb = document.getElementById('select-all-plants');
    if (cb) cb.checked = true;
    updateSelectionUI();
}

function updateSelectionUI() {
    const count = selectedPlants.size;
    const badge = document.getElementById('selection-count-badge');
    const bulkSec = document.getElementById('rp-bulk-care-section');
    const careSec2 = document.getElementById('rp-plant-care-section');
    const countEl = document.getElementById('bulk-count');

    if (badge) {
        if (count >= 2) {
            badge.textContent = `${count} selected`;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }

    if (count >= 2) {
        if (bulkSec) bulkSec.style.display = '';
        if (careSec2) careSec2.style.display = 'none';
        if (countEl) countEl.textContent = count;
        // Ensure right panel is open
        const panel = document.getElementById('planner-right-panel');
        const btn   = document.getElementById('right-panel-toggle');
        if (panel && !panel.classList.contains('open')) {
            panel.classList.add('open');
            if (btn) btn.classList.add('active');
            localStorage.setItem('plannerRightPanel', 'open');
            if (typeof loadPanelData === 'function') loadPanelData();
        }
    } else {
        if (bulkSec) bulkSec.style.display = 'none';
        // Only restore careSec if count went to 0 (not 1 — single selection handles its own display)
        if (count === 0 && careSec2) {
            // leave as-is; closePlantCarePanel will hide if needed
        }
    }
}

// Capture-phase handler: Ctrl+click for multi-select, and block plant clicks in navigate mode
canvas.addEventListener('click', (e) => {
    // In navigate mode: block all clicks on plant elements (no care panel opening)
    if (canvasMode === 'navigate') {
        if (e.target.closest('.grid-plant-chip, .canvas-plant-circle')) {
            if (!e.target.classList.contains('chip-remove') &&
                !e.target.classList.contains('canvas-plant-delete-btn')) {
                e.stopPropagation();
            }
        }
        return;
    }

    // Ctrl+click on a chip → multi-select
    if (e.ctrlKey || e.metaKey) {
        const chip = e.target.closest('.grid-plant-chip');
        if (chip && !e.target.classList.contains('chip-remove')) {
            e.stopPropagation();
            const bpId = chip.dataset.bpId;
            if (bpId) togglePlantSelection(`chip-${bpId}`, { type: 'chip', id: bpId, el: chip });
            return;
        }
        const circle = e.target.closest('.canvas-plant-circle');
        if (circle &&
            !e.target.classList.contains('canvas-plant-delete-btn') &&
            !e.target.classList.contains('canvas-plant-resize-handle')) {
            e.stopPropagation();
            const cpId = circle.dataset.cpId;
            if (cpId) togglePlantSelection(`circle-${cpId}`, { type: 'circle', id: cpId, el: circle });
            return;
        }
    }
}, true);

// Deselect all when clicking empty canvas background (not Ctrl)
canvas.addEventListener('click', (e) => {
    if (e.ctrlKey || e.metaKey) return;
    if (selectedPlants.size === 0) return;
    const isPlantEl = e.target.closest('.grid-plant-chip, .canvas-plant-circle, .canvas-bed-header');
    if (!isPlantEl) clearSelection();
});

// Select-all checkbox
document.getElementById('select-all-plants')?.addEventListener('change', (e) => {
    if (e.target.checked) selectAllPlants();
    else clearSelection();
});

// Bulk close button
document.getElementById('rp-bulk-close')?.addEventListener('click', () => {
    clearSelection();
    closePlantCarePanel();
});

// Bulk quick buttons
document.getElementById('bulk-mark-watered-btn')?.addEventListener('click', () => {
    const today = new Date().toISOString().slice(0, 10);
    const el = document.getElementById('bulk-watered');
    if (el) el.value = today;
});

document.getElementById('bulk-mark-growing-btn')?.addEventListener('click', () => {
    const today = new Date().toISOString().slice(0, 10);
    const transplantEl = document.getElementById('bulk-transplant');
    const stageEl = document.getElementById('bulk-stage');
    if (transplantEl) transplantEl.value = today;
    if (stageEl) stageEl.value = 'growing';
});

// Bulk form submit
document.getElementById('rp-bulk-form')?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const chipIds = [];
    selectedPlants.forEach((entry) => {
        if (entry.type === 'chip') chipIds.push(parseInt(entry.id));
    });
    if (!chipIds.length) {
        alert('No bed plants selected. Canvas circle plants do not support bulk care updates yet.');
        return;
    }
    const payload = { ids: chipIds };
    const watered     = document.getElementById('bulk-watered').value;
    const fertilized  = document.getElementById('bulk-fertilized').value;
    const seeded      = document.getElementById('bulk-seeded').value;
    const transplant  = document.getElementById('bulk-transplant').value;
    const notes       = document.getElementById('bulk-notes').value;
    const stage       = document.getElementById('bulk-stage').value;
    if (watered)    payload.last_watered    = watered;
    if (fertilized) payload.last_fertilized = fertilized;
    if (seeded)     payload.planted_date    = seeded;
    if (transplant) payload.transplant_date = transplant;
    if (notes)      payload.plant_notes     = notes;
    if (stage)      payload.stage           = stage;
    const result = await api('POST', '/api/bedplants/bulk-care', payload);
    if (result.ok) {
        const savedEl = document.getElementById('bulk-saved');
        if (savedEl) {
            savedEl.textContent = `Saved ✓ (${result.updated} updated)`;
            savedEl.style.display = '';
            setTimeout(() => { savedEl.style.display = 'none'; }, 2500);
        }
        // Update stage badges on updated chips
        if (stage) {
            selectedPlants.forEach(entry => {
                if (entry.type !== 'chip') return;
                let badge = entry.el.querySelector('.chip-stage-badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'chip-stage-badge';
                    entry.el.appendChild(badge);
                }
                const labels = { seedling: '🌱', growing: '🌿', harvesting: '🥕', done: '✓' };
                badge.textContent = labels[stage] || stage;
                badge.className = `chip-stage-badge stage-${stage}`;
            });
        }
        // Clear date fields after save
        ['bulk-watered','bulk-fertilized','bulk-seeded','bulk-transplant','bulk-notes'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        document.getElementById('bulk-stage').value = '';
    }
});

// Add stage badge when opening individual care panel
const _origPopulateCarePanel = populateCarePanel;
// (stage badge is rendered at chip creation time via renderChipInGrid;
//  we update it live when bulk stage changes above)

// ── Help modal ────────────────────────────────────────────────────────────────
function openHelpModal() {
    const modal = document.getElementById('help-modal');
    if (modal) modal.style.display = 'flex';
}
function closeHelpModal() {
    const modal = document.getElementById('help-modal');
    if (modal) modal.style.display = 'none';
}

document.getElementById('btn-help')?.addEventListener('click', openHelpModal);
document.getElementById('help-modal-close')?.addEventListener('click', closeHelpModal);
document.getElementById('help-modal-close-btn')?.addEventListener('click', closeHelpModal);
document.getElementById('help-modal')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('help-modal')) closeHelpModal();
});

// ── Hotkeys ───────────────────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    // Skip if focus is in an input/textarea/select
    const tag = document.activeElement?.tagName?.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

    // Ctrl+A: select all
    if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault();
        selectAllPlants();
        return;
    }

    // Ctrl combos — don't override other Ctrl shortcuts
    if (e.ctrlKey || e.metaKey) return;

    switch (e.key) {
        case '+':
        case '=': {
            e.preventDefault();
            const idx = ZOOM_STEPS.findIndex(z => z > zoom);
            if (idx !== -1) applyZoom(ZOOM_STEPS[idx]);
            break;
        }
        case '-': {
            e.preventDefault();
            const reversed = [...ZOOM_STEPS].reverse();
            const step = reversed.find(z => z < zoom);
            if (step !== undefined) applyZoom(step);
            break;
        }
        case '0': {
            e.preventDefault();
            applyZoom(1.0);
            break;
        }
        case 'Escape': {
            e.preventDefault();
            clearSelection();
            closePlantCarePanel();
            closeHelpModal();
            break;
        }
        case 'Delete':
        case 'Backspace': {
            if (selectedPlants.size === 0) break;
            e.preventDefault();
            const count = selectedPlants.size;
            if (!confirm(`Delete ${count} selected plant(s)? This cannot be undone.`)) break;
            const toDelete = [...selectedPlants.values()];
            clearSelection();
            Promise.all(toDelete.map(async entry => {
                if (entry.type === 'chip') {
                    const r = await api('POST', `/api/bedplants/${entry.id}/delete`);
                    if (r.ok) entry.el.remove();
                } else {
                    const r = await api('POST', `/api/canvas-plants/${entry.id}/delete`, {});
                    if (r.ok) { entry.el.remove(); delete canvasPlantEls[entry.id]; }
                }
            }));
            break;
        }
        case 'n':
        case 'N':
            e.preventDefault();
            setCanvasMode('navigate');
            break;
        case 's':
        case 'S':
            e.preventDefault();
            setCanvasMode('select');
            break;
        case 'h':
        case 'H':
            e.preventDefault();
            openHelpModal();
            break;
    }
});
