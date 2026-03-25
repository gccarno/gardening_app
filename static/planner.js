'use strict';

const canvas = document.getElementById('planner-canvas');
const PX = parseInt(canvas.dataset.px, 10) || 60;   // px per foot
const PX_PER_IN = PX / 12;                           // px per inch (5 at default scale)
const GARDEN_ID = canvas.dataset.gardenId;

let dragState = null;
let tileIn = 12; // current tile size in inches (default 1 ft)

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
        renderChipInGrid(grid, bp.id, cx, cy, bp.name, bp.image, bp.spacing_in || 12);
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
function renderChipInGrid(grid, bpId, cx, cy, name, imageFilename, spacingIn) {
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
    chip.innerHTML = `${imgHtml}<span class="chip-name">${escapeHtml(name)}</span>`
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
        const cx     = Math.floor((e.clientX - rect.left) / tilePx);
        const cy     = Math.floor((e.clientY - rect.top)  / tilePx);
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
        const rawX = e.clientX - cr.left - dragState.offsetX + canvas.scrollLeft;
        const rawY = e.clientY - cr.top  - dragState.offsetY + canvas.scrollTop;
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

    // ── Plant drop onto a grid cell ──
    if (dragState.type === 'plant') {
        const target = document.elementFromPoint(e.clientX, e.clientY);
        const grid   = target && target.closest('.canvas-bed-grid');
        if (grid) {
            const tilePx   = tileIn * PX_PER_IN;
            const rect     = grid.getBoundingClientRect();
            const cx       = Math.floor((e.clientX - rect.left) / tilePx);
            const cy       = Math.floor((e.clientY - rect.top)  / tilePx);
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
                    renderChipInGrid(grid, result.id, cx, cy, result.plant_name, result.image_filename, sIn);
                    updateBedPlantsData(grid.closest('.canvas-bed'), result.id, result.plant_name, result.image_filename, sIn, gridX, gridY);
                    // If dragged from library (creates a new Plant), add it to the sidebar
                    if (dragState && dragState.libraryId && result.plant_id) {
                        addPlantToGardenPalette(result.plant_id, result.library_id, result.plant_name, result.image_filename, sIn);
                    }
                }
            }
        }
        dragState = null;
        return;
    }

    // ── Bed repositioning ──
    if (dragState.type === 'bed-canvas') {
        const rawX  = e.clientX - cr.left - dragState.offsetX;
        const rawY  = e.clientY - cr.top  - dragState.offsetY;
        const sx    = snap(Math.max(0, rawX));
        const sy    = snap(Math.max(0, rawY));
        const bedEl = document.getElementById(`canvas-bed-${dragState.bedId}`);
        if (bedEl) { bedEl.style.left = `${sx}px`; bedEl.style.top = `${sy}px`; }
        await api('POST', `/api/beds/${dragState.bedId}/position`, { x: sx / PX, y: sy / PX });

    // ── Bed from palette onto canvas ──
    } else if (dragState.type === 'bed-palette') {
        const sx = snap(Math.max(0, e.clientX - cr.left));
        const sy = snap(Math.max(0, e.clientY - cr.top));
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
            await api('POST', `/api/bedplants/${bpId}/care`, payload);
        } else if (plantId) {
            await api('POST', `/api/plants/${plantId}/care`, payload);
        }
        if (careSaved) {
            careSaved.style.display = '';
            setTimeout(() => { careSaved.style.display = 'none'; }, 2000);
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

(function () {
    const panel      = document.getElementById('planner-right-panel');
    const toggleBtn  = document.getElementById('right-panel-toggle');
    if (!panel || !toggleBtn) return;

    const gd = typeof GARDEN_DATA !== 'undefined' ? GARDEN_DATA : null;

    loadPanelData = function() {
        if (!gd) return;
        renderGardenInfo();
        if (gd.latitude) {
            loadWeather();
            loadTasks();
        } else {
            const noLoc = '<p class="rp-muted" style="margin-top:0.4rem;">No location set. <a href="/gardens/' + gd.id + '" style="color:#3a6b35;">Set location →</a></p>';
            const wEl = document.getElementById('rp-weather-loading');
            if (wEl) wEl.outerHTML = noLoc;
            const tEl = document.getElementById('rp-tasks-loading');
            if (tEl) tEl.outerHTML = noLoc;
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
                return `<div class="rp-task-item">
                    <div class="rp-task-title">${escapeHtml(t.title)}</div>
                    <div class="rp-task-meta">${due}${plant}</div>
                </div>`;
            }).join('');
        } catch (err) {
            if (loading) loading.style.display = 'none';
            if (list) list.innerHTML = '<p class="rp-error">Could not load tasks.</p>';
        }
    }
})();
