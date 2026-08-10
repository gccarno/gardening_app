// Sync relay phase 3 of 3: the web app verifies Android's mutations in its
// own UI, then tears the shared sync garden down and confirms the deletion
// propagates (the reverse-direction "garden deleted" row of the matrix).
import { test, expect, api, readRunState, logManifest } from '../helpers';

test.describe.configure({ mode: 'serial' });

test.describe('sync: verify android mutations on web', () => {
  test('garden rename from Android shows in the web list', async ({ page }) => {
    const { syncGardenId } = readRunState();
    await page.goto('/gardens');
    await expect(page.locator('.card', { hasText: '(android edited)' })).toBeVisible();
    void syncGardenId;
  });

  test('task completed on Android shows as done on web', async ({ page, request }) => {
    const { syncGardenId, runId } = readRunState();
    const tasks = await api(request, 'get', `/api/tasks?garden_id=${syncGardenId}`);
    const syncTask = tasks.find((t: any) => t.title.includes('Sync task from web'));
    expect(syncTask.completed).toBeTruthy();

    await page.goto('/tasks');
    const card = page.locator('.card', { hasText: `${runId} Sync task from web` });
    await expect(card).toHaveClass(/completed/);
    await expect(card.getByRole('button', { name: 'Undo' })).toBeVisible();
  });

  test('journal entry written on Android renders on web', async ({ page }) => {
    const { syncGardenId } = readRunState();
    // Journal page reads the default garden — point it at the sync garden.
    await page.goto('/dashboard');
    await page.locator('.garden-selector-select').selectOption(String(syncGardenId));
    await page.goto('/journal');
    await expect(page.locator('.card', { hasText: 'Android sync entry' })).toBeVisible();
  });

  test('plant watered on Android shows the care date on web', async ({ request }) => {
    const { syncGardenId } = readRunState();
    const plants = await api(request, 'get', `/api/plants?garden_id=${syncGardenId}`);
    expect(plants.some((p: any) => p.last_watered === '2026-07-16')).toBeTruthy();
  });

  test('teardown: sync garden deleted on web disappears everywhere', async ({ page, request }) => {
    const { syncGardenId, prevDefaultGardenId } = readRunState();

    for (const cp of await api(request, 'get', `/api/gardens/${syncGardenId}/canvas-plants`)) {
      await api(request, 'post', `/api/canvas-plants/${cp.id}/delete`);
    }
    for (const p of await api(request, 'get', `/api/plants?garden_id=${syncGardenId}`)) {
      await api(request, 'delete', `/api/plants/${p.id}`);
    }
    for (const b of await api(request, 'get', `/api/beds?garden_id=${syncGardenId}`)) {
      await api(request, 'post', `/api/beds/${b.id}/delete`);
    }
    for (const t of await api(request, 'get', `/api/tasks?garden_id=${syncGardenId}`)) {
      await api(request, 'delete', `/api/tasks/${t.id}`);
    }
    const journal = await api(request, 'get', `/api/gardens/${syncGardenId}/journal?per_page=100`);
    for (const e of journal.entries) await api(request, 'delete', `/api/journal/${e.id}`);
    for (const tr of await api(request, 'get', `/api/gardens/${syncGardenId}/seed-room`)) {
      await api(request, 'delete', `/api/seed-room/${tr.id}`);
    }
    for (const bin of await api(request, 'get', `/api/gardens/${syncGardenId}/compost`)) {
      await api(request, 'delete', `/api/compost/${bin.id}`);
    }
    // `null` must be restored too — skipping it leaves this garden as the
    // global default and the delete below then strands it (see 99-teardown).
    if (prevDefaultGardenId !== undefined) {
      await api(request, 'post', '/api/settings/default-garden', { garden_id: prevDefaultGardenId });
    }

    await page.goto(`/gardens/${syncGardenId}`);
    await page.getByRole('button', { name: 'Delete Garden' }).click();
    await page.waitForURL('**/gardens');
    await expect(page.locator('.card', { hasText: '(android edited)' })).toHaveCount(0);
    logManifest({ event: 'sync-garden-deleted', gardenId: syncGardenId });
  });
});
