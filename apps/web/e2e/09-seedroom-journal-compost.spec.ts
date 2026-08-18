// Seed Room (24-slot shelf + stage advancement), Journal (entries, tags,
// pagination), Compost (bins, materials, stage cycle). All three pages read
// the default garden, which spec 08 pointed at the E2E garden.
import { test, expect, api, testName, readRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

const today = new Date().toISOString().slice(0, 10);

test.describe('seed room', () => {
  test('adds a seed to slot 1 and advances it through every stage', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await page.goto('/seed-room');
    await expect(page.locator('.seed-slot')).toHaveCount(24);

    await page.locator('.seed-slot--empty').first().click();
    await page.getByPlaceholder('Plant name *').fill(testName('Pepper seeds'));
    await page.locator('.modal-box input[type="date"]').fill(today);
    await page.getByPlaceholder('Notes (optional)').fill('E2E tray');
    await page.getByRole('button', { name: 'Add Seed' }).click();

    const filled = page.locator('.seed-slot--filled', { hasText: 'Pepper seeds' });
    await expect(filled).toBeVisible();
    const trays = await api(request, 'get', `/api/gardens/${gardenId}/seed-room`);
    logManifest({ type: 'seed_tray', id: trays[0].id, name: trays[0].plant_name });

    // sowing → germinating → seedling → hardening → ready
    for (const stage of ['germinating', 'seedling', 'hardening', 'ready']) {
      await filled.getByRole('button', { name: 'Advance →' }).click();
      await expect(filled.locator('.seed-slot__stage')).toHaveText(stage);
    }
    await expect(filled.getByRole('button', { name: 'Advance →' })).toHaveCount(0);
  });

  test('removes the tray from its slot', async ({ page }) => {
    await page.goto('/seed-room');
    const filled = page.locator('.seed-slot--filled', { hasText: 'Pepper seeds' });
    await filled.locator('.seed-slot__remove').click();
    await expect(page.locator('.seed-slot--filled')).toHaveCount(0);
  });
});

test.describe('journal', () => {
  test('creates an entry with tags and reads it back', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await page.goto('/journal');
    await page.getByRole('button', { name: '+ New Entry' }).click();
    const title = testName('First harvest');
    await page.getByPlaceholder('Title *').fill(title);
    await page.getByPlaceholder('What happened in the garden today?').fill('E2E: picked the first tomato of the season.');
    await page.getByPlaceholder(/Tags \(comma-separated\)/).fill('harvest, tomato');
    await page.getByRole('button', { name: 'Save Entry' }).click();

    const card = page.locator('.card', { hasText: title });
    await expect(card).toBeVisible();
    await expect(card.getByText('harvest', { exact: true })).toBeVisible(); // the tag chip
    await card.getByRole('button', { name: 'Read' }).click();
    await expect(card.getByText(/first tomato/)).toBeVisible();

    const data = await api(request, 'get', `/api/gardens/${gardenId}/journal`);
    logManifest({ type: 'journal', id: data.entries[0].id, name: title });
  });

  test('pagination appears past 20 entries (bulk-created via API)', async ({ page, request }) => {
    const { gardenId } = readRunState();
    for (let i = 1; i <= 21; i++) {
      const e = await api(request, 'post', `/api/gardens/${gardenId}/journal`, {
        title: testName(`bulk entry ${i}`), body: 'pagination filler',
      });
      logManifest({ type: 'journal', id: e.id });
    }
    await page.goto('/journal');
    await expect(page.getByText(/Page 1 of 2/)).toBeVisible();
    await page.getByRole('button', { name: 'Next →' }).click();
    await expect(page.getByText(/Page 2 of 2/)).toBeVisible();
    await page.getByRole('button', { name: '← Prev' }).click();
  });

  test('deletes an entry', async ({ page, request }) => {
    const { gardenId } = readRunState();
    const before = (await api(request, 'get', `/api/gardens/${gardenId}/journal`)).total;
    await page.goto('/journal');
    const card = page.locator('.card', { hasText: 'bulk entry' }).first();
    await card.getByRole('button', { name: '×' }).click(); // confirm auto-accepted
    await expect(async () => {
      const after = (await api(request, 'get', `/api/gardens/${gardenId}/journal`)).total;
      expect(after).toBe(before - 1);
    }).toPass({ timeout: 15_000 });
  });
});

test.describe('compost', () => {
  test('creates a bin, logs materials, advances through every stage', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await page.goto('/compost');
    await page.getByRole('button', { name: /New Bin|\+/ }).first().click();
    const name = testName('Back pile');
    await page.getByPlaceholder(/Bin name/).fill(name);
    await page.getByRole('button', { name: /Create|Add/ }).last().click();

    const bin = page.locator('.card', { hasText: name });
    await expect(bin).toBeVisible();
    const bins = await api(request, 'get', `/api/gardens/${gardenId}/compost`);
    logManifest({ type: 'compost_bin', id: bins[0].id, name });

    await bin.getByRole('button', { name: '+ Add material' }).click();
    await page.getByPlaceholder(/Material \(e\.g\./).fill('kitchen scraps');
    await page.getByPlaceholder('lbs (optional)').fill('5');
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(bin.getByText('kitchen scraps')).toBeVisible();

    // building → active → curing → ready
    for (const stage of ['active', 'curing', 'ready']) {
      await bin.getByRole('button', { name: 'Advance to next stage →' }).click();
      await expect(bin.getByText(stage, { exact: true })).toBeVisible();
    }
    await expect(bin.getByRole('button', { name: 'Advance to next stage →' })).toHaveCount(0);
  });
});
