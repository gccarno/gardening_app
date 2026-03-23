'use strict';

const canvas = document.getElementById('planner-canvas');
const PX = parseInt(canvas.dataset.px, 10) || 60;
const GARDEN_ID = canvas.dataset.gardenId;

let dragState = null;

// ── Shared fetch helper ────────────────────────────────────────────────────────
async function api(method, path, body) {
    return fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
    }).then(r => r.json());
}

// ── Snap to grid ──────────────────────────────────────────────────────────────
function snap(value) {
    return Math.round(value / PX) * PX;
}

// ── Create bed DOM element ────────────────────────────────────────────────────
function createBedElement(bed) {
    const div = document.createElement('div');
    div.className = 'canvas-bed';
    div.id = `canvas-bed-${bed.id}`;
    div.setAttribute('draggable', 'true');
    div.dataset.bedId = bed.id;
    div.style.left = '0px';
    div.style.top = '0px';
    div.style.width = `${bed.width_ft * PX}px`;
    div.style.height = `${bed.height_ft * PX}px`;

    const header = document.createElement('div');
    header.className = 'canvas-bed-header';
    header.textContent = bed.name;

    const plantsZone = document.createElement('div');
    plantsZone.className = 'canvas-bed-plants';
    plantsZone.dataset.bedId = bed.id;

    div.appendChild(header);
    div.appendChild(plantsZone);

    bindBedEvents(div);
    return div;
}

// ── Bind drag events to a canvas bed ─────────────────────────────────────────
function bindBedEvents(bedEl) {
    bedEl.addEventListener('dragstart', (e) => {
        // Don't start bed drag if the event target is a chip-remove button
        if (e.target.classList.contains('chip-remove')) {
            e.stopPropagation();
            e.preventDefault();
            return;
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

    bedEl.addEventListener('dragend', () => {
        bedEl.classList.remove('dragging');
    });
}

// ── Canvas: dragover (live preview + drop) ────────────────────────────────────
canvas.addEventListener('dragover', (e) => {
    if (!dragState) return;
    if (dragState.type === 'bed-canvas' || dragState.type === 'bed-palette') {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        if (dragState.type === 'bed-canvas') {
            const canvasRect = canvas.getBoundingClientRect();
            const rawX = e.clientX - canvasRect.left - dragState.offsetX + canvas.scrollLeft;
            const rawY = e.clientY - canvasRect.top - dragState.offsetY + canvas.scrollTop;
            const snappedX = snap(Math.max(0, rawX));
            const snappedY = snap(Math.max(0, rawY));
            const bedEl = document.getElementById(`canvas-bed-${dragState.bedId}`);
            if (bedEl) {
                bedEl.style.left = `${snappedX}px`;
                bedEl.style.top = `${snappedY}px`;
            }
        }
    }
});

canvas.addEventListener('drop', async (e) => {
    e.preventDefault();
    if (!dragState) return;

    const canvasRect = canvas.getBoundingClientRect();

    if (dragState.type === 'bed-canvas') {
        const rawX = e.clientX - canvasRect.left - dragState.offsetX;
        const rawY = e.clientY - canvasRect.top - dragState.offsetY;
        const snappedX = snap(Math.max(0, rawX));
        const snappedY = snap(Math.max(0, rawY));

        const bedEl = document.getElementById(`canvas-bed-${dragState.bedId}`);
        if (bedEl) {
            bedEl.style.left = `${snappedX}px`;
            bedEl.style.top = `${snappedY}px`;
        }

        await api('POST', `/api/beds/${dragState.bedId}/position`, {
            x: snappedX / PX,
            y: snappedY / PX,
        });

    } else if (dragState.type === 'bed-palette') {
        // Place bed from sidebar onto canvas
        const rawX = e.clientX - canvasRect.left;
        const rawY = e.clientY - canvasRect.top;
        const snappedX = snap(Math.max(0, rawX));
        const snappedY = snap(Math.max(0, rawY));

        await api('POST', `/api/beds/${dragState.bedId}/assign-garden`, { garden_id: GARDEN_ID });
        await api('POST', `/api/beds/${dragState.bedId}/position`, {
            x: snappedX / PX,
            y: snappedY / PX,
        });

        // Create and inject bed element
        const bedEl = createBedElement({
            id: dragState.bedId,
            name: dragState.name,
            width_ft: dragState.width,
            height_ft: dragState.height,
        });
        bedEl.style.left = `${snappedX}px`;
        bedEl.style.top = `${snappedY}px`;
        canvas.appendChild(bedEl);

        // Remove from sidebar palette
        const paletteItem = document.querySelector(`#palette-beds .palette-bed[data-bed-id="${dragState.bedId}"]`);
        if (paletteItem) paletteItem.remove();
    }

    dragState = null;
});

// ── Plant palette drag start ──────────────────────────────────────────────────
document.querySelectorAll('.palette-plant').forEach(el => {
    el.addEventListener('dragstart', (e) => {
        dragState = {
            type: 'plant',
            plantId: el.dataset.plantId,
            name: el.dataset.name,
        };
        e.dataTransfer.effectAllowed = 'copy';
    });
});

// ── Bed palette drag start ────────────────────────────────────────────────────
document.querySelectorAll('.palette-bed').forEach(el => {
    el.addEventListener('dragstart', (e) => {
        dragState = {
            type: 'bed-palette',
            bedId: el.dataset.bedId,
            width: parseFloat(el.dataset.width),
            height: parseFloat(el.dataset.height),
            name: el.dataset.name,
        };
        e.dataTransfer.effectAllowed = 'move';
    });
});

// ── Bed plant drop zones ──────────────────────────────────────────────────────
function bindPlantDropZone(zone) {
    zone.addEventListener('dragover', (e) => {
        if (dragState && dragState.type === 'plant') {
            e.preventDefault();
            e.stopPropagation();
            e.dataTransfer.dropEffect = 'copy';
            zone.classList.add('drop-active');
        }
    });

    zone.addEventListener('dragleave', (e) => {
        // Only remove class if leaving to outside the zone
        if (!zone.contains(e.relatedTarget)) {
            zone.classList.remove('drop-active');
        }
    });

    zone.addEventListener('drop', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove('drop-active');

        if (!dragState || dragState.type !== 'plant') return;

        const bedId = zone.dataset.bedId;
        const result = await api('POST', '/api/bedplants', {
            bed_id: bedId,
            plant_id: dragState.plantId,
        });

        if (result.ok) {
            appendChip(zone, dragState.name, result.id);
        }

        dragState = null;
    });
}

function appendChip(zone, name, bpId) {
    const chip = document.createElement('span');
    chip.className = 'plant-chip';
    chip.dataset.bpId = bpId;
    chip.innerHTML = `${escapeHtml(name)} <button class="chip-remove" data-bp-id="${bpId}" title="Remove">×</button>`;
    zone.appendChild(chip);
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Bind to existing zones
document.querySelectorAll('.canvas-bed-plants').forEach(bindPlantDropZone);

// ── Chip remove (event delegation on canvas) ──────────────────────────────────
canvas.addEventListener('click', async (e) => {
    const btn = e.target.closest('.chip-remove');
    if (!btn) return;

    const bpId = btn.dataset.bpId;
    const result = await api('POST', `/api/bedplants/${bpId}/delete`);
    if (result.ok) {
        const chip = btn.closest('.plant-chip');
        if (chip) chip.remove();
    }
});

// ── Add Bed form ──────────────────────────────────────────────────────────────
const addBedForm = document.getElementById('add-bed-form');
if (addBedForm) {
    addBedForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(addBedForm));
        const result = await api('POST', '/api/beds', {
            name: data.name,
            width_ft: parseFloat(data.width_ft) || 4,
            height_ft: parseFloat(data.height_ft) || 8,
            garden_id: GARDEN_ID,
        });

        if (result.ok) {
            // Place at origin first
            await api('POST', `/api/beds/${result.bed.id}/position`, { x: 0, y: 0 });

            const bedEl = createBedElement(result.bed);
            canvas.appendChild(bedEl);
            bindPlantDropZone(bedEl.querySelector('.canvas-bed-plants'));

            addBedForm.reset();
            // Close the <details> element
            addBedForm.closest('details').removeAttribute('open');
        }
    });
}

// ── Bind plant drop zones for dynamically added beds ─────────────────────────
// (already called inline in createBedElement → bindPlantDropZone)
