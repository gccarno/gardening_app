// Builds THE run garden through the UI and exercises everything clickable on
// the Gardens list + Garden detail pages. Later specs reuse gardenId from the
// run state; 99-teardown deletes it all.
import { test, expect, api, testName, updateRunState, readRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('garden build', () => {
  test('creates the run garden with every form field', async ({ page, request }) => {
    await page.goto('/gardens');
    const name = testName('Garden');
    await page.getByLabel('Name').fill(name);
    await page.getByLabel('Description').fill(`E2E suite garden — run ${readRunState().runId}`);
    await page.getByLabel('Unit').selectOption('ft');
    await page.getByLabel(/ZIP Code/).fill('10001');
    await page.getByRole('button', { name: 'Create Garden' }).click();

    // The new card appears in the list.
    const card = page.locator('.card', { hasText: name });
    await expect(card).toBeVisible();

    // Resolve the id for the rest of the suite (and the manifest).
    const gardens = await api(request, 'get', '/api/gardens');
    const mine = gardens.find((g: any) => g.name === name);
    expect(mine, 'created garden should be listed by the API').toBeTruthy();
    updateRunState({ gardenId: mine.id });
    logManifest({ type: 'garden', id: mine.id, name });
  });

  test('rename works from the list (and keeps the [E2E] prefix)', async ({ page }) => {
    const { gardenId } = readRunState();
    const renamed = testName('Garden renamed');
    await page.goto('/gardens');
    const card = page.locator('.card', { hasText: readRunState().runId }).first();
    await card.getByRole('button', { name: 'Rename' }).click();
    await card.locator('input[type="text"]').fill(renamed);
    await card.getByRole('button', { name: 'Save' }).click();
    await expect(page.locator('.card', { hasText: renamed })).toBeVisible();
    // Put the canonical name back so later specs can match on it.
    await api(page.request, 'put', `/api/gardens/${gardenId}`, { name: testName('Garden') });
  });

  test('ZIP lookup derived location and zone (best effort on prod)', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto(`/gardens/${gardenId}`);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('[E2E]');
    // External ZIP/NOAA lookups can fail on prod — soft-assert so the build
    // continues, but the failure is still reported.
    await expect.soft(page.locator('.location-header')).toContainText('New York');
    await expect.soft(page.locator('.zone-badge').first()).toBeVisible();
  });

  test('edit form updates every editable field', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto(`/gardens/${gardenId}`);
    await page.getByText('Edit Garden').click(); // <details> summary
    const form = page.locator('details form');
    await form.getByLabel('Description').fill('Updated by the E2E edit test');
    await form.getByLabel('Last Frost Date').fill('2026-04-15');
    await form.getByLabel('Water Every (days)').fill('5');
    await form.getByLabel('Water Source').selectOption('drip');
    await form.getByRole('button', { name: 'Save Changes' }).click();

    await page.reload();
    const detail = await api(page.request, 'get', `/api/gardens/${gardenId}`);
    expect(detail.description).toBe('Updated by the E2E edit test');
    expect(detail.watering_frequency_days).toBe(5);
    expect(detail.water_source).toBe('drip');
    expect(detail.last_frost_date).toBe('2026-04-15');
  });

  test('bulk care buttons record care and report a count', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto(`/gardens/${gardenId}`);
    for (const label of ['Water All', 'Fertilize All', 'Mulch All']) {
      await page.getByRole('button', { name: label }).click();
      await expect(page.getByText(/plant\(s\)\. Task recorded\.|Updating…/)).toBeVisible();
    }
  });

  test('fetch weather history responds (skip-friendly: external API)', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto(`/gardens/${gardenId}`);
    const btn = page.getByRole('button', { name: 'Fetch Weather History' });
    if (!(await btn.isVisible())) test.skip(true, 'garden has no coordinates (ZIP lookup failed)');
    await btn.click();
    // Either "Saved N days..." or an error string — the button must respond.
    await expect(page.locator('section', { hasText: 'Rainfall' }).locator('.muted').last())
      .not.toHaveText('', { timeout: 60_000 });
  });

  test('sharing section lists the owner', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto(`/gardens/${gardenId}`);
    const sharing = page.locator('section', { has: page.getByRole('heading', { name: 'Sharing' }) });
    await expect(sharing.locator('.member-row .badge').first()).toHaveText('owner');
    // Invite flow needs a second real account — not exercised against prod.
  });
});
