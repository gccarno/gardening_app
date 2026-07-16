// Plant library: browse/search/filter/paginate, compare & diff, detail tabs,
// clone (the [E2E] sandbox entry), full edit, images, add-to-planning, and
// Perenual search (external — never saves).
// NOTE: cloned entries have no delete endpoint; scripts/e2e_cleanup.py --sql
// removes them. The clone is named with the [E2E] prefix for that reason.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { FIXTURES_DIR } from './env';
import { test, expect, api, testName, readRunState, updateRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('plant library', () => {
  test('browse: filters, search, and pagination', async ({ page }) => {
    await page.goto('/library');
    await expect(page.locator('.lib-table tbody tr').first()).toBeVisible();

    await page.getByRole('button', { name: 'Vegetables' }).click();
    await expect(page.locator('.lib-table tbody tr').first()).toBeVisible();

    await page.getByRole('button', { name: /^All \(/ }).click();
    // Pagination controls only render past one page (a small local library
    // fits on one page; prod has ~200).
    const next = page.getByRole('button', { name: 'Next →' });
    if (await next.count()) {
      await next.click();
      await expect(page.getByText(/Page 2 of/)).toBeVisible();
      await page.getByRole('button', { name: '← Prev' }).click();
    }

    await page.getByPlaceholder('Search by name…').fill('tomato');
    await expect(page.locator('.lib-table tbody tr').first()).toContainText(/tomato/i);
  });

  test('compare mode diffs two plants', async ({ page }) => {
    await page.goto('/library');
    await expect(page.locator('.lib-table tbody tr').nth(1)).toBeVisible(); // need ≥2 rows
    await page.getByRole('button', { name: 'Compare Plants' }).click();
    await page.locator('.lib-table tbody tr input[type="checkbox"]').nth(0).check();
    await page.locator('.lib-table tbody tr input[type="checkbox"]').nth(1).check();
    await page.getByRole('button', { name: 'Diff selected →' }).click();
    await page.waitForURL('**/library/diff**');
    await expect(page.locator('table, .diff, h1').first()).toBeVisible();
  });

  test('detail page shows hero stats and all info tabs', async ({ page, request }) => {
    const lib = await api(request, 'get', '/api/library?q=tomato&per_page=1');
    const entry = lib.entries[0];
    await page.goto(`/library/${entry.id}`);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(entry.name);
    for (const t of ['Calendar', 'How to Grow', 'Companions', 'Soil', 'Overview']) {
      const btn = page.getByRole('button', { name: t, exact: true });
      if (await btn.count()) {
        await btn.click();
        await expect(page.locator('section').first()).toBeVisible();
      }
    }
  });

  test('clones a plant into the [E2E] sandbox entry', async ({ page, request }) => {
    const lib = await api(request, 'get', '/api/library?q=tomato&per_page=1');
    await page.goto(`/library/${lib.entries[0].id}`);
    await page.getByRole('button', { name: 'Clone Plant' }).click();
    const cloneName = testName('Tomato Clone');
    await page.getByPlaceholder('New plant name…').fill(cloneName);
    await page.getByRole('button', { name: 'Create Clone' }).click();

    let cloneId = 0;
    await expect(async () => {
      const found = await api(request, 'get', `/api/library?q=${encodeURIComponent(cloneName)}`);
      expect(found.entries.length).toBe(1);
      cloneId = found.entries[0].id;
    }).toPass({ timeout: 15_000 });
    updateRunState({ libraryCloneId: cloneId });
    logManifest({ type: 'library_clone', id: cloneId, name: cloneName, note: 'no API delete — cleanup via --sql' });

    await page.goto(`/library/${cloneId}`);
    await expect(page.getByText('Cloned from:')).toBeVisible();
    await expect(page.getByText('custom').or(page.getByRole('heading', { name: new RegExp('Tomato Clone') }))).toBeVisible();
  });

  test('full 10-tab editor patches the clone', async ({ page, request }) => {
    const { libraryCloneId } = readRunState();
    await page.goto(`/library/${libraryCloneId}/edit`);
    // Walk all 10 tabs (each must render), ending on Cultivation for the edit.
    for (const tab of ['Core', 'Climate', 'Companions', 'Growing Info', 'Dimensions',
                       'Appearance', 'Classification', 'Properties', 'Uses', 'Cultivation']) {
      await page.getByRole('button', { name: tab, exact: true }).click();
    }
    const spacing = page.getByLabel('Spacing (inches)');
    await expect(spacing).toBeVisible();
    await spacing.fill('18');
    await page.getByRole('button', { name: /Save Changes/ }).click();
    await expect(page.getByRole('button', { name: 'Saved!' })).toBeVisible();

    const entry = await api(request, 'get', `/api/library/${libraryCloneId}`);
    expect(entry.spacing_in).toBe(18);
  });

  test('image upload, set-primary, delete — on the clone only', async ({ page, request }) => {
    const { libraryCloneId } = readRunState();
    await page.goto(`/library/${libraryCloneId}`);
    await page.getByRole('button', { name: '+ Add Image' }).click();
    // Image dedupe is GLOBAL by file hash: identical bytes ever uploaded to
    // any entry get reattached there instead. Salt the PNG with the run ID
    // (bytes after IEND keep it valid) so every run's upload is unique.
    const salted = Buffer.concat([
      readFileSync(path.join(FIXTURES_DIR, 'plant_photo.png')),
      Buffer.from(readRunState().runId),
    ]);
    await page.locator('input[type="file"]').setInputFiles({
      name: 'plant_photo.png', mimeType: 'image/png', buffer: salted,
    });
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    // On success the form (and its "Saved!" note) unmounts — the API check
    // below is the real assertion.
    let imageId = 0;
    await expect(async () => {
      const imgs = await api(request, 'get', `/api/library/${libraryCloneId}/images`);
      expect(imgs.length).toBeGreaterThan(0);
      imageId = imgs[imgs.length - 1].id;
    }).toPass({ timeout: 15_000 });
    logManifest({ type: 'library_image', id: imageId });

    await api(request, 'post', `/api/library/images/${imageId}/set-primary`);
    await api(request, 'post', `/api/library/images/${imageId}/delete`);
    const after = await api(request, 'get', `/api/library/${libraryCloneId}/images`);
    expect(after.some((i: any) => i.id === imageId)).toBeFalsy();
  });

  test('add-to-planning from the detail page creates a garden plant', async ({ page, request }) => {
    const { gardenId, libraryCloneId } = readRunState();
    await page.goto(`/library/${libraryCloneId}`);
    await page.locator('select').first().selectOption(String(gardenId));
    await page.getByRole('button', { name: '+ Add to Planning' }).click();
    await expect(async () => {
      const plants = await api(request, 'get', `/api/plants?garden_id=${gardenId}`);
      const mine = plants.find((p: any) => p.library_id === libraryCloneId);
      expect(mine).toBeTruthy();
      logManifest({ type: 'plant', id: mine.id, name: mine.name });
    }).toPass({ timeout: 15_000 });
  });

  test('Perenual search responds (external — result list or a message, never save)', async ({ page }) => {
    await page.goto('/library');
    await page.getByPlaceholder('e.g. basil, sunflower…').fill('basil');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    // Either result cards or an error/empty message — the UI must respond.
    await expect(page.locator('.perenual-card, section .muted').first())
      .toBeVisible({ timeout: 60_000 });
    // Deliberately no "Save to Library" click: it creates undeletable rows on prod.
  });
});
