// Teardown: delete everything the suite created, bottom-up (garden delete
// does NOT cascade), restore the previous default garden, then assert no
// [E2E] residue remains. The library clone is the one deliberate leftover —
// it has no delete endpoint; run scripts/e2e_cleanup.py --apply --sql for it.
import { E2E_PREFIX } from './env';
import { test, expect, api, readRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('teardown', () => {
  test('restores the previous default garden', async ({ request }) => {
    const { prevDefaultGardenId } = readRunState();
    if (prevDefaultGardenId) {
      await api(request, 'post', '/api/settings/default-garden', { garden_id: prevDefaultGardenId });
    }
  });

  test('deletes all garden children bottom-up via API', async ({ request }) => {
    const { gardenId } = readRunState();

    for (const cp of await api(request, 'get', `/api/gardens/${gardenId}/canvas-plants`)) {
      await api(request, 'post', `/api/canvas-plants/${cp.id}/delete`);
    }
    for (const p of await api(request, 'get', `/api/plants?garden_id=${gardenId}`)) {
      await api(request, 'delete', `/api/plants/${p.id}`); // cascades bed_plants + observations
    }
    for (const b of await api(request, 'get', `/api/beds?garden_id=${gardenId}`)) {
      await api(request, 'post', `/api/beds/${b.id}/delete`);
    }
    for (const t of await api(request, 'get', `/api/tasks?garden_id=${gardenId}`)) {
      await api(request, 'delete', `/api/tasks/${t.id}`);
    }
    const journal = await api(request, 'get', `/api/gardens/${gardenId}/journal?per_page=100`);
    for (const e of journal.entries) {
      await api(request, 'delete', `/api/journal/${e.id}`);
    }
    for (const tray of await api(request, 'get', `/api/gardens/${gardenId}/seed-room`)) {
      await api(request, 'delete', `/api/seed-room/${tray.id}`);
    }
    for (const bin of await api(request, 'get', `/api/gardens/${gardenId}/compost`)) {
      await api(request, 'delete', `/api/compost/${bin.id}`);
    }
    logManifest({ event: 'children-deleted', gardenId });
  });

  test('deletes the garden through the UI confirmation flow', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto(`/gardens/${gardenId}`);
    await page.getByRole('button', { name: 'Delete Garden' }).click(); // confirm auto-accepted
    await page.waitForURL('**/gardens');
    await expect(page.locator('.card', { hasText: readRunState().runId })).toHaveCount(0);
    logManifest({ event: 'garden-deleted', gardenId });
  });

  test('no [E2E] residue remains (library clone excepted)', async ({ request }) => {
    const gardens = await api(request, 'get', '/api/gardens');
    expect(gardens.filter((g: any) => g.name?.startsWith(E2E_PREFIX))).toHaveLength(0);

    const beds = await api(request, 'get', '/api/beds');
    expect(beds.filter((b: any) => b.name?.startsWith(E2E_PREFIX))).toHaveLength(0);

    const plants = await api(request, 'get', '/api/plants');
    expect(plants.filter((p: any) => p.name?.startsWith(E2E_PREFIX))).toHaveLength(0);

    const tasks = await api(request, 'get', '/api/tasks');
    expect(tasks.filter((t: any) => t.title?.startsWith(E2E_PREFIX))).toHaveLength(0);

    // Deliberate leftover: the library clone (no delete endpoint).
    const lib = await api(request, 'get', `/api/library?q=${encodeURIComponent(E2E_PREFIX)}`);
    for (const e of lib.entries ?? []) {
      logManifest({ event: 'residue-library-clone', id: e.id, name: e.name, action: 'run e2e_cleanup.py --apply --sql' });
    }
  });
});
