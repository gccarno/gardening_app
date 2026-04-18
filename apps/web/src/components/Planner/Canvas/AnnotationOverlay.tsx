import React, { useRef } from 'react';
import { AnnotationShape, DrawState, api } from '../types';

interface Props {
  activeTool: string | null;
  activeObjectType: string;
  strokeColor: string;
  fillColor: string;
  noFill: boolean;
  strokeWidth: number;
  dashArray: string;
  zoom: number;
  gardenId: number;
  annShapes: AnnotationShape[];
  onShapesChange: (shapes: AnnotationShape[]) => void;
}

const NS = 'http://www.w3.org/2000/svg';

function newShapeId() {
  try { return crypto.randomUUID(); } catch (_) { return Math.random().toString(36).slice(2); }
}

function distPts(ax: number, ay: number, bx: number, by: number) {
  return Math.sqrt((bx - ax) ** 2 + (by - ay) ** 2);
}

function distToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax, dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return distPts(px, py, ax, ay);
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
  return distPts(px, py, ax + t * dx, ay + t * dy);
}

function hitTestShape(shape: AnnotationShape, x: number, y: number, r = 10) {
  switch (shape.type) {
    case 'rect':
      return x >= (shape.x! - r) && x <= (shape.x! + shape.w! + r)
          && y >= (shape.y! - r) && y <= (shape.y! + shape.h! + r);
    case 'ellipse':
      return x >= (shape.cx! - shape.rx! - r) && x <= (shape.cx! + shape.rx! + r)
          && y >= (shape.cy! - shape.ry! - r) && y <= (shape.cy! + shape.ry! + r);
    case 'line':
      return distToSegment(x, y, shape.x1!, shape.y1!, shape.x2!, shape.y2!) <= r;
    case 'free': {
      const pts = shape.points!;
      for (let i = 0; i < pts.length - 1; i++)
        if (distToSegment(x, y, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) <= r) return true;
      if (pts.length === 1) return distPts(x, y, pts[0][0], pts[0][1]) <= r;
      return false;
    }
  }
  return false;
}

export default function AnnotationOverlay({
  activeTool, activeObjectType, strokeColor, fillColor, noFill, strokeWidth, dashArray,
  zoom, gardenId, annShapes, onShapesChange,
}: Props) {
  const svgRef      = useRef<SVGSVGElement>(null);
  const drawRef     = useRef<DrawState | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function saveAnnotations(shapes: AnnotationShape[]) {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      api('POST', `/api/gardens/${gardenId}/annotations`, { shapes });
    }, 400);
  }

  function svgPoint(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / zoom, y: (e.clientY - rect.top) / zoom };
  }

  function eraseAtPoint(x: number, y: number, currentShapes: AnnotationShape[]) {
    for (let i = currentShapes.length - 1; i >= 0; i--) {
      if (hitTestShape(currentShapes[i], x, y)) {
        const next = [...currentShapes];
        next.splice(i, 1);
        onShapesChange(next);
        saveAnnotations(next);
        return next;
      }
    }
    return currentShapes;
  }

  function handleSvgMouseDown(e: React.MouseEvent<SVGSVGElement>) {
    if (!activeTool || !svgRef.current) return;
    e.preventDefault();
    const { x, y } = svgPoint(e);

    if (activeTool === 'eraser') {
      drawRef.current = { tool: 'eraser', el: null as unknown as SVGElement, startX: x, startY: y };
      eraseAtPoint(x, y, annShapes);
      return;
    }

    const stroke = strokeColor;
    const fill   = noFill ? 'none' : fillColor;
    const sw     = strokeWidth;
    let el: SVGElement;

    switch (activeTool) {
      case 'rect':
        el = document.createElementNS(NS, 'rect');
        el.setAttribute('x', String(x)); el.setAttribute('y', String(y));
        el.setAttribute('width', '0'); el.setAttribute('height', '0');
        break;
      case 'ellipse':
        el = document.createElementNS(NS, 'ellipse');
        el.setAttribute('cx', String(x)); el.setAttribute('cy', String(y));
        el.setAttribute('rx', '0'); el.setAttribute('ry', '0');
        break;
      case 'line':
        el = document.createElementNS(NS, 'line');
        el.setAttribute('x1', String(x)); el.setAttribute('y1', String(y));
        el.setAttribute('x2', String(x)); el.setAttribute('y2', String(y));
        break;
      case 'free':
        el = document.createElementNS(NS, 'polyline');
        el.setAttribute('points', `${x},${y}`);
        break;
      default:
        return;
    }
    el.setAttribute('stroke', stroke);
    el.setAttribute('stroke-width', String(sw));
    el.setAttribute('fill', activeTool === 'line' ? 'none' : fill);
    el.setAttribute('stroke-linecap', 'round');
    el.setAttribute('stroke-linejoin', 'round');
    svgRef.current.appendChild(el);
    drawRef.current = { tool: activeTool, el, startX: x, startY: y,
      ...(activeTool === 'free' ? { points: [[x, y]], lastX: x, lastY: y, pathLen: 0 } : {}) };
  }

  function handleSvgMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const dr = drawRef.current;
    if (!dr) return;
    const { x, y } = svgPoint(e);

    if (dr.tool === 'eraser') { eraseAtPoint(x, y, annShapes); return; }
    const { el, startX, startY } = dr;

    switch (dr.tool) {
      case 'rect': {
        const rx = Math.min(startX, x), ry = Math.min(startY, y);
        el.setAttribute('x', String(rx)); el.setAttribute('y', String(ry));
        el.setAttribute('width', String(Math.abs(x - startX)));
        el.setAttribute('height', String(Math.abs(y - startY)));
        break;
      }
      case 'ellipse': {
        const cx = (startX + x) / 2, cy = (startY + y) / 2;
        el.setAttribute('cx', String(cx)); el.setAttribute('cy', String(cy));
        el.setAttribute('rx', String(Math.abs(x - startX) / 2));
        el.setAttribute('ry', String(Math.abs(y - startY) / 2));
        break;
      }
      case 'line':
        el.setAttribute('x2', String(x)); el.setAttribute('y2', String(y));
        break;
      case 'free': {
        const d = distPts(dr.lastX!, dr.lastY!, x, y);
        if (d >= 4) {
          dr.points!.push([x, y]);
          dr.pathLen = (dr.pathLen || 0) + d;
          dr.lastX = x; dr.lastY = y;
          el.setAttribute('points', dr.points!.map(p => p.join(',')).join(' '));
        }
        break;
      }
    }
  }

  function handleSvgMouseUp(e: React.MouseEvent<SVGSVGElement>) {
    const dr = drawRef.current;
    if (!dr) return;

    if (dr.tool === 'eraser') { drawRef.current = null; return; }

    const svgEl = svgRef.current;
    if (!svgEl) { drawRef.current = null; return; }

    const { el, startX, startY, tool } = dr;
    const stroke = el.getAttribute('stroke')!;
    const sw     = parseInt(el.getAttribute('stroke-width') || '2', 10);
    const fill   = el.getAttribute('fill') || 'none';
    let shape: AnnotationShape | null = null;

    switch (tool) {
      case 'rect': {
        const rw = parseFloat(el.getAttribute('width') || '0');
        const rh = parseFloat(el.getAttribute('height') || '0');
        if (rw < 2 && rh < 2) { el.remove(); drawRef.current = null; return; }
        const rx = parseFloat(el.getAttribute('x') || '0');
        const ry = parseFloat(el.getAttribute('y') || '0');
        shape = { id: newShapeId(), type: 'rect', objectType: activeObjectType, dashArray, x: rx, y: ry, w: rw, h: rh, stroke, strokeWidth: sw, fill };
        break;
      }
      case 'ellipse': {
        const rx2 = parseFloat(el.getAttribute('rx') || '0');
        const ry2 = parseFloat(el.getAttribute('ry') || '0');
        if (rx2 < 1 && ry2 < 1) { el.remove(); drawRef.current = null; return; }
        const cx = parseFloat(el.getAttribute('cx') || '0');
        const cy = parseFloat(el.getAttribute('cy') || '0');
        shape = { id: newShapeId(), type: 'ellipse', objectType: activeObjectType, dashArray, cx, cy, rx: rx2, ry: ry2, stroke, strokeWidth: sw, fill };
        break;
      }
      case 'line': {
        const x1 = parseFloat(el.getAttribute('x1') || '0'), y1 = parseFloat(el.getAttribute('y1') || '0');
        const x2 = parseFloat(el.getAttribute('x2') || '0'), y2 = parseFloat(el.getAttribute('y2') || '0');
        if (distPts(x1, y1, x2, y2) < 2) { el.remove(); drawRef.current = null; return; }
        shape = { id: newShapeId(), type: 'line', objectType: activeObjectType, dashArray, x1, y1, x2, y2, stroke, strokeWidth: sw, fill: 'none' };
        break;
      }
      case 'free': {
        if (!dr.points || dr.points.length < 2) { el.remove(); drawRef.current = null; return; }
        shape = { id: newShapeId(), type: 'free', objectType: activeObjectType, dashArray, points: dr.points, stroke, strokeWidth: sw, fill };
        break;
      }
    }

    el.remove();
    if (shape) {
      const next = [...annShapes, shape];
      onShapesChange(next);
      saveAnnotations(next);
    }
    drawRef.current = null;
  }

  return (
    <svg
      ref={svgRef}
      style={{
        position: 'absolute', left: 0, top: 0,
        width: '100%', height: '100%',
        pointerEvents: activeTool ? 'all' : 'none',
        zIndex: 15,
        cursor: activeTool === 'eraser' ? 'cell' : activeTool ? 'crosshair' : 'default',
        overflow: 'visible',
      }}
      onMouseDown={handleSvgMouseDown}
      onMouseMove={handleSvgMouseMove}
      onMouseUp={handleSvgMouseUp}
    >
      {annShapes.map(shape => {
        const common: React.SVGProps<SVGElement> = {
          stroke: shape.stroke,
          strokeWidth: shape.strokeWidth,
          fill: shape.fill,
          strokeLinecap: 'round' as const,
          strokeLinejoin: 'round' as const,
          strokeDasharray: shape.dashArray || undefined,
        };
        switch (shape.type) {
          case 'rect':   return <rect     key={shape.id} {...common as React.SVGProps<SVGRectElement>}     x={shape.x}   y={shape.y}   width={shape.w}  height={shape.h} />;
          case 'ellipse':return <ellipse  key={shape.id} {...common as React.SVGProps<SVGEllipseElement>}  cx={shape.cx} cy={shape.cy} rx={shape.rx}   ry={shape.ry} />;
          case 'line':   return <line     key={shape.id} {...common as React.SVGProps<SVGLineElement>}     x1={shape.x1} y1={shape.y1} x2={shape.x2}   y2={shape.y2} fill="none" />;
          case 'free':   return <polyline key={shape.id} {...common as React.SVGProps<SVGPolylineElement>} points={shape.points!.map(p => p.join(',')).join(' ')} />;
          default:       return null;
        }
      })}
    </svg>
  );
}
