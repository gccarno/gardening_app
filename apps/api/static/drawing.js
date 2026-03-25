'use strict';

// drawing.js — loaded after planner.js; shares canvas, PX, GARDEN_ID, api() globals

const svg        = document.getElementById('annotation-svg');
const tooltip    = document.getElementById('draw-tooltip');
const strokeColorInput = document.getElementById('draw-stroke-color');
const fillColorInput   = document.getElementById('draw-fill-color');
const noFillCheck      = document.getElementById('draw-no-fill');
const strokeWidthSel   = document.getElementById('draw-stroke-width');

let activeTool  = null;   // 'rect'|'ellipse'|'line'|'free'|'eraser'|null
let drawState   = null;   // in-progress: { tool, startX, startY, el, points?, pathLen? }
let shapes      = [];     // all persisted shapes for this garden
let _saveTimer  = null;

// ── Helpers ────────────────────────────────────────────────────────────────────

function newId() {
    try { return crypto.randomUUID(); } catch (_) {
        return Math.random().toString(36).slice(2) + Date.now().toString(36);
    }
}

// Canvas-local coordinates from a mouse event.
// getBoundingClientRect() returns the scaled rect; dividing by zoom converts to canvas pixels.
function canvasPoint(e) {
    const rect = canvas.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / zoom, y: (e.clientY - rect.top) / zoom };
}

function dist(ax, ay, bx, by) {
    return Math.sqrt((bx - ax) ** 2 + (by - ay) ** 2);
}

// Distance from point (px,py) to segment (ax,ay)-(bx,by)
function distToSegment(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) return dist(px, py, ax, ay);
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
    return dist(px, py, ax + t * dx, ay + t * dy);
}

// Format pixels → feet/inches string
function fmtFt(px) {
    const ft = px / PX;
    if (ft < 1) {
        const inches = Math.round(ft * 12);
        return `${inches}"`;
    }
    const wholeFt = Math.floor(ft);
    const inches  = Math.round((ft - wholeFt) * 12);
    return inches === 0 ? `${wholeFt}'` : `${wholeFt}' ${inches}"`;
}

function currentStroke()      { return strokeColorInput.value; }
function currentFill()        { return noFillCheck.checked ? 'none' : fillColorInput.value; }
function currentStrokeWidth() { return parseInt(strokeWidthSel.value, 10); }

// ── SVG rendering ─────────────────────────────────────────────────────────────

const NS = 'http://www.w3.org/2000/svg';

function applyCommon(el, shape) {
    el.setAttribute('stroke', shape.stroke);
    el.setAttribute('stroke-width', shape.strokeWidth);
    el.setAttribute('fill', shape.type === 'line' ? 'none' : (shape.fill || 'none'));
    el.id = `shape-${shape.id}`;
}

function renderShape(shape) {
    let el;
    switch (shape.type) {
        case 'rect':
            el = document.createElementNS(NS, 'rect');
            el.setAttribute('x', shape.x);
            el.setAttribute('y', shape.y);
            el.setAttribute('width',  shape.w);
            el.setAttribute('height', shape.h);
            break;
        case 'ellipse':
            el = document.createElementNS(NS, 'ellipse');
            el.setAttribute('cx', shape.cx);
            el.setAttribute('cy', shape.cy);
            el.setAttribute('rx', shape.rx);
            el.setAttribute('ry', shape.ry);
            break;
        case 'line':
            el = document.createElementNS(NS, 'line');
            el.setAttribute('x1', shape.x1);
            el.setAttribute('y1', shape.y1);
            el.setAttribute('x2', shape.x2);
            el.setAttribute('y2', shape.y2);
            break;
        case 'free':
            el = document.createElementNS(NS, 'polyline');
            el.setAttribute('points', shape.points.map(p => p.join(',')).join(' '));
            break;
        default:
            return;
    }
    applyCommon(el, shape);
    svg.appendChild(el);
}

// ── Persistence ───────────────────────────────────────────────────────────────

async function loadAnnotations() {
    try {
        const data = await api('GET', `/api/gardens/${GARDEN_ID}/annotations`);
        shapes = data.shapes || [];
        shapes.forEach(renderShape);
    } catch (_) { /* non-fatal */ }
}

function saveAnnotations() {
    clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => {
        api('POST', `/api/gardens/${GARDEN_ID}/annotations`, { shapes });
    }, 300);
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

function showTooltip(clientX, clientY, text) {
    tooltip.textContent = text;
    tooltip.style.left    = `${clientX + 16}px`;
    tooltip.style.top     = `${clientY + 16}px`;
    tooltip.style.display = 'block';
}

function hideTooltip() {
    tooltip.style.display = 'none';
}

function tooltipForRect(wPx, hPx, clientX, clientY) {
    showTooltip(clientX, clientY, `${fmtFt(Math.abs(wPx))} × ${fmtFt(Math.abs(hPx))}`);
}

function tooltipForLength(px, clientX, clientY) {
    showTooltip(clientX, clientY, fmtFt(px));
}

// ── Eraser ────────────────────────────────────────────────────────────────────

function hitTest(shape, x, y, r) {
    switch (shape.type) {
        case 'rect':
            return x >= shape.x - r && x <= shape.x + shape.w + r
                && y >= shape.y - r && y <= shape.y + shape.h + r;
        case 'ellipse':
            return x >= shape.cx - shape.rx - r && x <= shape.cx + shape.rx + r
                && y >= shape.cy - shape.ry - r && y <= shape.cy + shape.ry + r;
        case 'line':
            return distToSegment(x, y, shape.x1, shape.y1, shape.x2, shape.y2) <= r;
        case 'free': {
            const pts = shape.points;
            for (let i = 0; i < pts.length - 1; i++) {
                if (distToSegment(x, y, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) <= r)
                    return true;
            }
            // Single point case
            if (pts.length === 1 && dist(x, y, pts[0][0], pts[0][1]) <= r) return true;
            return false;
        }
    }
    return false;
}

function eraseAtPoint(x, y) {
    for (let i = shapes.length - 1; i >= 0; i--) {
        if (hitTest(shapes[i], x, y, 10)) {
            const el = document.getElementById(`shape-${shapes[i].id}`);
            if (el) el.remove();
            shapes.splice(i, 1);
            saveAnnotations();
            return; // remove one shape per sample
        }
    }
}

// ── Tool activation / deactivation ───────────────────────────────────────────

function deactivateTool() {
    // Cancel any in-progress draw
    if (drawState && drawState.el) drawState.el.remove();
    drawState   = null;
    activeTool  = null;
    svg.style.pointerEvents = 'none';
    canvas.classList.remove('draw-mode');
    delete canvas.dataset.tool;
    document.querySelectorAll('.draw-tool-btn').forEach(b => b.classList.remove('active'));
    hideTooltip();
}

// ── Mouse event handlers ──────────────────────────────────────────────────────

function handleMouseDown(e) {
    if (!activeTool) return;
    e.preventDefault();
    const { x, y } = canvasPoint(e);

    if (activeTool === 'eraser') {
        drawState = { tool: 'eraser' };
        eraseAtPoint(x, y);
        return;
    }

    const stroke = currentStroke();
    const fill   = currentFill();
    const sw     = currentStrokeWidth();
    let el;

    switch (activeTool) {
        case 'rect':
            el = document.createElementNS(NS, 'rect');
            el.setAttribute('x', x); el.setAttribute('y', y);
            el.setAttribute('width', 0); el.setAttribute('height', 0);
            el.setAttribute('stroke', stroke);
            el.setAttribute('stroke-width', sw);
            el.setAttribute('fill', fill);
            svg.appendChild(el);
            drawState = { tool: 'rect', startX: x, startY: y, el };
            break;

        case 'ellipse':
            el = document.createElementNS(NS, 'ellipse');
            el.setAttribute('cx', x); el.setAttribute('cy', y);
            el.setAttribute('rx', 0); el.setAttribute('ry', 0);
            el.setAttribute('stroke', stroke);
            el.setAttribute('stroke-width', sw);
            el.setAttribute('fill', fill);
            svg.appendChild(el);
            drawState = { tool: 'ellipse', startX: x, startY: y, el };
            break;

        case 'line':
            el = document.createElementNS(NS, 'line');
            el.setAttribute('x1', x); el.setAttribute('y1', y);
            el.setAttribute('x2', x); el.setAttribute('y2', y);
            el.setAttribute('stroke', stroke);
            el.setAttribute('stroke-width', sw);
            el.setAttribute('fill', 'none');
            svg.appendChild(el);
            drawState = { tool: 'line', startX: x, startY: y, el };
            break;

        case 'free':
            el = document.createElementNS(NS, 'polyline');
            el.setAttribute('points', `${x},${y}`);
            el.setAttribute('stroke', stroke);
            el.setAttribute('stroke-width', sw);
            el.setAttribute('fill', fill);
            svg.appendChild(el);
            drawState = { tool: 'free', startX: x, startY: y, el,
                          points: [[x, y]], pathLen: 0,
                          lastX: x, lastY: y };
            break;
    }
}

function handleMouseMove(e) {
    if (!drawState) return;
    const { x, y } = canvasPoint(e);

    if (drawState.tool === 'eraser') {
        eraseAtPoint(x, y);
        return;
    }

    const { el, startX, startY } = drawState;

    switch (drawState.tool) {
        case 'rect': {
            const rx = Math.min(startX, x), ry = Math.min(startY, y);
            const rw = Math.abs(x - startX), rh = Math.abs(y - startY);
            el.setAttribute('x', rx); el.setAttribute('y', ry);
            el.setAttribute('width', rw); el.setAttribute('height', rh);
            tooltipForRect(rw, rh, e.clientX, e.clientY);
            break;
        }
        case 'ellipse': {
            const cx = (startX + x) / 2, cy = (startY + y) / 2;
            const rx = Math.abs(x - startX) / 2, ry = Math.abs(y - startY) / 2;
            el.setAttribute('cx', cx); el.setAttribute('cy', cy);
            el.setAttribute('rx', rx); el.setAttribute('ry', ry);
            tooltipForRect(rx * 2, ry * 2, e.clientX, e.clientY);
            break;
        }
        case 'line': {
            el.setAttribute('x2', x); el.setAttribute('y2', y);
            tooltipForLength(dist(startX, startY, x, y), e.clientX, e.clientY);
            break;
        }
        case 'free': {
            const d = dist(drawState.lastX, drawState.lastY, x, y);
            if (d >= 4) {
                drawState.points.push([x, y]);
                drawState.pathLen += d;
                drawState.lastX = x;
                drawState.lastY = y;
                el.setAttribute('points', drawState.points.map(p => p.join(',')).join(' '));
                tooltipForLength(drawState.pathLen, e.clientX, e.clientY);
            }
            break;
        }
    }
}

function handleMouseUp(e) {
    if (!drawState) return;

    if (drawState.tool === 'eraser') {
        drawState = null;
        return;
    }

    const { x, y } = canvasPoint(e);
    const { el, startX, startY, tool } = drawState;
    const stroke = el.getAttribute('stroke');
    const sw     = parseInt(el.getAttribute('stroke-width'), 10);
    const fill   = el.getAttribute('fill');
    let shape;

    switch (tool) {
        case 'rect': {
            const rx = Math.min(startX, x), ry = Math.min(startY, y);
            const rw = Math.abs(x - startX),  rh = Math.abs(y - startY);
            if (rw < 2 && rh < 2) { el.remove(); drawState = null; hideTooltip(); return; }
            shape = { id: newId(), type: 'rect', x: rx, y: ry, w: rw, h: rh,
                      stroke, strokeWidth: sw, fill };
            break;
        }
        case 'ellipse': {
            const cx = (startX + x) / 2, cy = (startY + y) / 2;
            const rx = Math.abs(x - startX) / 2, ry = Math.abs(y - startY) / 2;
            if (rx < 1 && ry < 1) { el.remove(); drawState = null; hideTooltip(); return; }
            shape = { id: newId(), type: 'ellipse', cx, cy, rx, ry,
                      stroke, strokeWidth: sw, fill };
            break;
        }
        case 'line': {
            if (dist(startX, startY, x, y) < 2) { el.remove(); drawState = null; hideTooltip(); return; }
            shape = { id: newId(), type: 'line', x1: startX, y1: startY, x2: x, y2: y,
                      stroke, strokeWidth: sw, fill: 'none' };
            break;
        }
        case 'free': {
            if (drawState.points.length < 2) { el.remove(); drawState = null; hideTooltip(); return; }
            shape = { id: newId(), type: 'free', points: drawState.points,
                      stroke, strokeWidth: sw, fill };
            break;
        }
    }

    // Replace preview element with a properly-id'd permanent element
    el.remove();
    shapes.push(shape);
    renderShape(shape);
    saveAnnotations();

    drawState = null;
    hideTooltip();
}

// ── Initialization ────────────────────────────────────────────────────────────

loadAnnotations();

// Tool button clicks
document.querySelectorAll('.draw-tool-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tool = btn.dataset.tool;
        if (activeTool === tool) {
            // Toggle off: deactivate and restore select mode
            deactivateTool();
            setCanvasMode('select');
            return;
        }
        // Cancel any in-progress draw before switching tools
        if (drawState && drawState.el) drawState.el.remove();
        drawState  = null;
        // Switch planner to 'draw' mode: clears select/navigate button highlights, disables panning
        setCanvasMode('draw');
        activeTool = tool;
        document.querySelectorAll('.draw-tool-btn').forEach(b =>
            b.classList.toggle('active', b === btn));
        svg.style.pointerEvents = 'all';
        canvas.classList.add('draw-mode');
        canvas.dataset.tool = tool;
    });
});

// Escape deactivates draw tool and restores select mode
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && activeTool) {
        deactivateTool();
        setCanvasMode('select');
    }
});

// SVG mouse events
svg.addEventListener('mousedown', handleMouseDown);
svg.addEventListener('mousemove', handleMouseMove);
svg.addEventListener('mouseup',   handleMouseUp);
// Safety net: mouseup outside SVG still finalises the shape
document.addEventListener('mouseup', handleMouseUp);
