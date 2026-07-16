// Sync relay phase 1 of 3 (see scripts/run_e2e.ps1): the web app builds the
// shared sync garden and makes the "web side" of every sync-matrix mutation.
// Android (SyncVerifyAndMutateTest) verifies these on-device, mutates back,
// and sync-verify-android.spec.ts closes the loop.
import { test, expect, api, testName, readRunState, updateRunState, logManifest } from '../helpers';

test.describe.configure({ mode: 'serial' });

const today = new Date().toISOString().slice(0, 10);

test.describe('sync: web mutations', () => {
  test('creates the shared sync garden through the UI', async ({ page, request }) => {
    const name = testName('Sync Garden');
    await page.goto('/gardens');
    await page.getByLabel('Name').fill(name);
    await page.getByLabel('Description').fill('Cross-platform sync relay garden');
    await page.getByRole('button', { name: 'Create Garden' }).click();
    await expect(page.locator('.card', { hasText: name })).toBeVisible();

    const gardens = await api(request, 'get', '/api/gardens');
    const mine = gardens.find((g: any) => g.name === name);
    updateRunState({ syncGardenId: mine.id });
    logManifest({ type: 'garden', id: mine.id, name, note: 'sync relay garden' });
  });

  test('web-side mutations across the sync matrix', async ({ page, request }) => {
    const { syncGardenId } = readRunState();

    // Rename with the "(web edited)" marker Android looks for.
    await api(request, 'put', `/api/gardens/${syncGardenId}`, {
      name: `${testName('Sync Garden')} (web edited)`,
    });

    // Bed created through the UI form.
    await page.goto('/beds');
    const form = page.locator('form.form');
    await form.locator('select[name="garden_id"]').selectOption(String(syncGardenId));
    await form.getByLabel('Name').fill(testName('Sync Bed'));
    await form.getByLabel('Width (ft)').fill('4');
    await form.getByLabel('Height (ft)').fill('4');
    await page.getByRole('button', { name: 'Add Bed' }).click();
    await expect(page.locator('.card', { hasText: 'Sync Bed' })).toBeVisible();

    // Plant from the library, task, journal entry, seed tray, compost bin,
    // canvas plant, grid placement, rain log — the same calls the already-
    // verified web UI makes (05–09 specs prove the UI wiring).
    const lib = await api(request, 'get', '/api/library?q=tomato&per_page=1');
    const plant = await api(request, 'post', '/api/plants', {
      name: testName('Sync Tomato'), garden_id: syncGardenId,
      library_id: lib.entries[0].id, status: 'growing', planted_date: today,
    });
    const beds = await api(request, 'get', `/api/beds?garden_id=${syncGardenId}`);
    await api(request, 'post', `/api/beds/${beds[0].id}/grid-plant`, {
      library_id: lib.entries[0].id, grid_x: 12, grid_y: 12, spacing_in: 12,
    });
    const task = await api(request, 'post', '/api/tasks', {
      title: `${testName('Sync task from web')}`, task_type: 'watering',
      due_date: today, garden_id: syncGardenId,
    });
    await api(request, 'post', `/api/gardens/${syncGardenId}/journal`, {
      title: testName('Web sync entry'), body: 'written on web', tags: ['sync'],
    });
    await api(request, 'post', `/api/gardens/${syncGardenId}/seed-room`, {
      slot_number: 1, plant_name: testName('Sync seeds'), stage: 'sowing',
    });
    await api(request, 'post', `/api/gardens/${syncGardenId}/compost`, {
      name: testName('Sync bin'),
    });
    await api(request, 'post', `/api/gardens/${syncGardenId}/canvas-plants`, {
      library_id: lib.entries[0].id, pos_x: 2, pos_y: 2,
    });
    await api(request, 'post', `/api/gardens/${syncGardenId}/log-rain`, {
      rainfall_in: 0.3, entry_date: today,
    });

    logManifest({
      event: 'sync-web-mutations-done', gardenId: syncGardenId,
      plantId: plant.id, taskId: task.id,
    });
  });
});
