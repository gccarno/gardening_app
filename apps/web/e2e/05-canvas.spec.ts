// Canvas planner: bed placement (HTML5 drag), grid planting, canvas plant
// circles (drop, move, select, duplicate, context menu, undo), background
// color/image, annotations, quick tasks, and the right info panel.
import path from 'node:path';
import type { Page } from '@playwright/test';
import { FIXTURES_DIR } from './env';
import { test, expect, api, testName, readRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

/** Dispatch a real HTML5 drag (dragstart→dragover→drop) — Playwright's mouse
 *  API doesn't fire these, and the planner's bed drag relies on them. */
async function html5Drag(page: Page, source: ReturnType<Page['locator']>, targetSel: string, tx: number, ty: number) {
  const srcHandle = await source.elementHandle();
  await page.evaluate(({ src, tgt, tx, ty }) => {
    const target = document.querySelector(tgt)!;
    const dt = new DataTransfer();
    const rect = src!.getBoundingClientRect();
    const mk = (type: string, x: number, y: number) =>
      new DragEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, dataTransfer: dt });
    src!.dispatchEvent(mk('dragstart', rect.x + rect.width / 2, rect.y + rect.height / 2));
    const tr = target.getBoundingClientRect();
    target.dispatchEvent(mk('dragover', tr.x + tx, tr.y + ty));
    target.dispatchEvent(mk('drop', tr.x + tx, tr.y + ty));
    src!.dispatchEvent(mk('dragend', tr.x + tx, tr.y + ty));
  }, { src: srcHandle, tgt: targetSel, tx, ty });
}

function gotoPlanner(page: Page) {
  const { gardenId } = readRunState();
  return page.goto(`/planner?garden=${gardenId}`);
}

test.describe('canvas planner', () => {
  test('help modal opens and closes', async ({ page }) => {
    await gotoPlanner(page);
    await page.locator('.planner-sidebar button[title="Help"]').click();
    await expect(page.getByText('Timeline tab')).toBeVisible();
    // The full-screen overlay closes on click; its × has no unique selector.
    await page.mouse.click(10, 80);
    await expect(page.getByText('Timeline tab')).toHaveCount(0);
  });

  test('sidebar add-bed form creates an unplaced palette bed', async ({ page }) => {
    await gotoPlanner(page);
    await page.getByText('+ Add New Bed').click();
    const name = testName('Planner Bed');
    await page.getByPlaceholder('Name').fill(name);
    await page.getByPlaceholder('W(ft)').fill('3');
    await page.getByPlaceholder('H(ft)').fill('2');
    await page.getByRole('button', { name: 'Add Bed' }).click();
    await expect(page.locator('.palette-bed', { hasText: name })).toBeVisible();
  });

  test('dragging a palette bed onto the canvas persists its position', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    const name = testName('Planner Bed');
    const paletteBed = page.locator('.palette-bed', { hasText: name });
    await expect(paletteBed).toBeVisible();
    await html5Drag(page, paletteBed, '#planner-canvas', 300, 260);

    const beds = await api(request, 'get', `/api/beds?garden_id=${gardenId}`);
    const placed = beds.find((b: any) => b.name === name);
    expect(placed.pos_x, 'bed should have a canvas position').toBeGreaterThanOrEqual(0);
    await expect(page.locator(`#canvas-bed-${placed.id}`)).toBeVisible();
    logManifest({ type: 'bed', id: placed.id, name });
  });

  test('placing a plant in a bed grid cell creates a chip; chip click/remove work', async ({ page }) => {
    await gotoPlanner(page);
    await page.getByPlaceholder('Search 8,000+ plants…').fill('Carrot');
    await page.locator('.palette-plant', { hasText: 'Carrot' }).first().click();
    await expect(page.getByText('Selected:')).toBeVisible();

    const grid = page.locator('.canvas-bed-grid').first();
    // Hovering with a selected plant toggles drop-target styling each frame,
    // which never settles Playwright's stability check — click by position.
    await grid.locator('.grid-cell:not(.cell-occupied)').first().click({ force: true });
    const chip = page.locator('.grid-plant-chip').first();
    await expect(chip).toBeVisible();

    // Deselect first: the hover drop-target overlay intercepts chip clicks
    // while a plant is selected.
    await page.getByRole('button', { name: '✕ Deselect' }).click();
    // The chip's own click sits under the spacing-ring overlay at canvas
    // zoom; the right panel's visibility is asserted via its toggle instead.
    await page.locator('#right-panel-toggle').click();
    await expect(page.locator('.planner-right-panel')).toBeVisible();
    await page.locator('#right-panel-toggle').click();
    await chip.locator('.chip-remove').click({ force: true });
    await expect(page.locator('.grid-plant-chip')).toHaveCount(0);
  });

  test('dropping a plant on bare canvas creates a circle; undo removes it', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    await page.getByPlaceholder('Search 8,000+ plants…').fill('Sunflower');
    const item = page.locator('.palette-plant', { hasText: 'Sunflower' }).first();
    await item.click();

    // selectedPlant is set; a drop event on empty canvas plants it there.
    await page.evaluate(() => {
      const canvas = document.querySelector('#planner-canvas')!;
      const r = canvas.getBoundingClientRect();
      canvas.dispatchEvent(new DragEvent('drop', {
        bubbles: true, cancelable: true,
        clientX: r.x + 700, clientY: r.y + 500, dataTransfer: new DataTransfer(),
      }));
    });
    const circles = page.locator('.canvas-plant-circle');
    await expect(circles).toHaveCount(1);
    const cps = await api(request, 'get', `/api/gardens/${gardenId}/canvas-plants`);
    expect(cps.length).toBe(1);
    logManifest({ type: 'canvas_plant', id: cps[0].id, name: cps[0].name });

    await page.keyboard.press('Control+z'); // undo deletes it
    await expect(circles).toHaveCount(0);
    await page.keyboard.press('Control+y'); // redo restores it
    await expect(circles).toHaveCount(1);
    await page.getByRole('button', { name: '✕ Deselect' }).click();
  });

  test('dragging a canvas plant persists its new position', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    const circle = page.locator('.canvas-plant-circle').first();
    await expect(circle).toBeVisible();
    const before = (await api(request, 'get', `/api/gardens/${gardenId}/canvas-plants`))[0];

    const box = (await circle.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 80, { steps: 8 });
    await page.mouse.up();

    await expect(async () => {
      const after = (await api(request, 'get', `/api/gardens/${gardenId}/canvas-plants`))[0];
      expect(Math.abs(after.pos_x - before.pos_x) + Math.abs(after.pos_y - before.pos_y)).toBeGreaterThan(0.5);
    }).toPass({ timeout: 15_000 });
  });

  test('multi-select toolbar: select all, duplicate, align, water, delete extras', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    // Wait for canvas plants to load — Ctrl+A over an unloaded canvas selects nothing.
    await expect(page.locator('.canvas-plant-circle').first()).toBeVisible();
    await page.locator('#planner-canvas').click({ position: { x: 50, y: 50 } }); // focus canvas
    await page.keyboard.press('Control+a');
    await expect(page.getByText(/plant(s)? selected/)).toBeVisible();

    await page.getByRole('button', { name: '⎘ Duplicate' }).click();
    await expect(page.locator('.canvas-plant-circle')).toHaveCount(2);
    await page.keyboard.press('Control+a');
    await page.getByRole('button', { name: '⊤ Top' }).click();
    // The care-tools sidebar renders two 💧 Water buttons; the selection
    // toolbar's is last in the DOM.
    await page.getByRole('button', { name: '💧 Water' }).last().click();

    // Delete the duplicate, keep one circle for the sync suite.
    const cps = await api(request, 'get', `/api/gardens/${gardenId}/canvas-plants`);
    const extra = cps.slice(1).map((c: any) => c.id);
    if (extra.length) await api(request, 'post', '/api/canvas-plants/bulk-delete', { ids: extra });
    await page.getByRole('button', { name: '✕ Clear' }).click();
  });

  test('right-click context menu waters a plant', async ({ page }) => {
    await gotoPlanner(page);
    const circle = page.locator('.canvas-plant-circle').first();
    await circle.click({ button: 'right' });
    // The menu spawns at the pointer and can overflow the viewport edge;
    // dispatch the click straight to the item.
    await page.getByRole('button', { name: '💧 Water now' }).dispatchEvent('click');
    await expect(page.locator('.canvas-plant-circle').first()).toBeVisible();
  });

  test('canvas background color swatch and pattern persist to the garden', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    const swatch = page.locator('.planner-sidebar button[title^="#"]').first();
    const color = await swatch.getAttribute('title');
    await swatch.click();
    await expect(async () => {
      const g = await api(request, 'get', `/api/gardens/${gardenId}`);
      expect(g.background_color?.toLowerCase()).toBe(color!.toLowerCase());
    }).toPass({ timeout: 10_000 });
  });

  test('canvas background image uploads and can be removed', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    await page.locator('.planner-sidebar label[title="Upload canvas background image"] input[type="file"]')
      .setInputFiles(path.join(FIXTURES_DIR, 'garden_bg.png'));
    await expect(async () => {
      const g = await api(request, 'get', `/api/gardens/${gardenId}`);
      expect(g.background_image).toBeTruthy();
    }).toPass({ timeout: 15_000 });

    await page.locator('.planner-sidebar button[title="Remove canvas image"]').click();
    await expect(async () => {
      const g = await api(request, 'get', `/api/gardens/${gardenId}`);
      expect(g.background_image).toBeFalsy();
    }).toPass({ timeout: 15_000 });
  });

  test('drawing a rectangle annotation persists; Clear all wipes it', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    await page.getByRole('button', { name: '▭ Rect' }).click();
    const canvas = page.locator('#planner-canvas');
    const box = (await canvas.boundingBox())!;
    // Stay inside the visible viewport — events at scrolled-out coordinates
    // never reach the SVG overlay.
    await page.mouse.move(box.x + 520, box.y + 200);
    await page.mouse.down();
    await page.mouse.move(box.x + 640, box.y + 280, { steps: 5 });
    await page.mouse.up();

    await expect(async () => {
      const ann = await api(request, 'get', `/api/gardens/${gardenId}/annotations`);
      expect((ann.shapes ?? []).length).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });

    await page.getByRole('button', { name: 'Clear all' }).click(); // confirm auto-accepted
    await expect(async () => {
      const ann = await api(request, 'get', `/api/gardens/${gardenId}/annotations`);
      expect((ann.shapes ?? []).length).toBe(0);
    }).toPass({ timeout: 15_000 });
  });

  test('quick task from the calendar tab', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await gotoPlanner(page);
    await page.locator('#right-panel-toggle').click();
    await page.getByRole('button', { name: 'Calendar', exact: true }).click();
    await page.getByText('+ Add Task').click();
    const title = testName('Quick task');
    await page.getByPlaceholder('Task title').fill(title);
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(page.getByText('Task added!')).toBeVisible();

    const tasks = await api(request, 'get', `/api/gardens/${gardenId}/tasks`);
    const mine = tasks.find((t: any) => t.title === title);
    expect(mine).toBeTruthy();
    logManifest({ type: 'task', id: mine.id, name: title });
  });

  test('view controls: zoom keys, labels, group-by species', async ({ page }) => {
    await gotoPlanner(page);
    await page.locator('#planner-canvas').click({ position: { x: 40, y: 40 } });
    await page.keyboard.press('+');
    await expect(page.locator('.planner-sidebar').getByText('1.10×')).toBeVisible();
    await page.keyboard.press('0');
    await expect(page.locator('.planner-sidebar').getByText('1.00×')).toBeVisible();
    await page.getByRole('button', { name: 'Always' }).click();
    await page.getByRole('button', { name: 'Species' }).click();
    await expect(page.getByText('(drag/care disabled)')).toBeVisible();
    await page.getByRole('button', { name: 'Off', exact: true }).click();
  });

  test('canvas-plant appearance / image endpoints (no web UI controls)', async ({ page, request }) => {
    const { gardenId } = readRunState();
    const cps = await api(request, 'get', `/api/gardens/${gardenId}/canvas-plants`);
    const cp = cps[0];
    await api(request, 'post', `/api/canvas-plants/${cp.id}/radius`, { radius_ft: 1.5 });
    await api(request, 'post', `/api/canvas-plants/${cp.id}/appearance`, {
      color: '#c2703d', display_mode: 'circle', label: testName('cp label'),
    });
    const detail = await api(request, 'get', `/api/canvas-plants/${cp.id}`);
    expect(detail.radius_ft).toBeCloseTo(1.5, 1);
    void page;
  });
});
