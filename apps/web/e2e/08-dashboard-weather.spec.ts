// Dashboard: default-garden selector, metric tiles, weather/watering/season
// cards, tip of the day, rain logging, and the content columns.
import { test, expect, api, readRunState, updateRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('dashboard & weather', () => {
  test('selecting the E2E garden sets it as default (restored at teardown)', async ({ page, request }) => {
    const { gardenId } = readRunState();
    // Remember the previous default so 99-teardown can put it back.
    const prev = await api(request, 'get', '/api/settings/default-garden');
    updateRunState({ prevDefaultGardenId: prev?.garden_id ?? null });

    await page.goto('/dashboard');
    await page.locator('.garden-selector-select').selectOption(String(gardenId));
    await expect(async () => {
      const now = await api(request, 'get', '/api/settings/default-garden');
      expect(now?.garden_id).toBe(gardenId);
    }).toPass({ timeout: 10_000 });
  });

  test('metric tiles match the dashboard API', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await page.goto('/dashboard');
    await page.locator('.garden-selector-select').selectOption(String(gardenId));
    const dash = await api(request, 'get', `/api/dashboard?garden_id=${gardenId}`);
    const nums = page.locator('.metric-card__num');
    await expect(nums.nth(0)).toHaveText(String(dash.metrics.bed_count));
    await expect(nums.nth(1)).toHaveText(String(dash.metrics.plant_count));
    await expect(nums.nth(3)).toHaveText(String(dash.metrics.task_count));
  });

  test('info cards render: season always; weather/tip best-effort', async ({ page }) => {
    const { gardenId } = readRunState();
    await page.goto('/dashboard');
    await page.locator('.garden-selector-select').selectOption(String(gardenId));
    await expect(page.locator('.season-card')).toBeVisible();
    // Weather (external open-meteo) and Tip (ChromaDB RAG) may be unavailable:
    // the card must render either content or its graceful fallback text.
    await expect(page.locator('.tip-of-day-card .info-card__body').getByText(/.+/)).toBeVisible();
    const weatherCard = page.locator('#weather-card');
    if (await weatherCard.count()) {
      await expect(weatherCard.getByText(/°F|Weather unavailable|Loading/)).toBeVisible({ timeout: 30_000 });
    }
    await expect(page.locator('#watering-card .info-card__body').getByText(/.+/)).toBeVisible();
  });

  test('rain log slider records rainfall', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await page.goto('/dashboard');
    await page.locator('.garden-selector-select').selectOption(String(gardenId));
    const card = page.locator('#rain-log-card');
    await card.locator('input[type="range"]').fill('0.75');
    await expect(card.getByText('0.75 in')).toBeVisible();
    await card.getByRole('button', { name: 'Log Rain' }).click();
    await expect(card.getByText('✓ Saved')).toBeVisible();

    const log = await api(request, 'get', `/api/gardens/${gardenId}/rain-log`);
    const entries = Array.isArray(log) ? log : log.entries;
    expect(entries.some((e: any) => Math.abs((e.rainfall_in ?? 0) - 0.75) < 0.001)).toBeTruthy();
    logManifest({ type: 'weather_log', note: 'rain 0.75in — no delete endpoint, cleanup via --sql orphan sweep' });
  });

  test('watering-status endpoint feeds the card', async ({ request }) => {
    const { gardenId } = readRunState();
    const status = await api(request, 'get', `/api/gardens/${gardenId}/watering-status`);
    expect(status).toHaveProperty('beds');
  });

  test('upcoming tasks column lists the E2E watering task', async ({ page }) => {
    const { gardenId, runId } = readRunState();
    await page.goto('/dashboard');
    await page.locator('.garden-selector-select').selectOption(String(gardenId));
    await expect(page.locator('.dash-col', { hasText: 'Upcoming Tasks' })
      .getByText(new RegExp(runId)).first()).toBeVisible();
  });

  test('nav tiles route correctly', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('.nav-tile', { hasText: 'Seed Room' }).click();
    await page.waitForURL('**/seed-room');
    await page.goBack();
    await page.locator('.nav-tile', { hasText: 'Compost' }).click();
    await page.waitForURL('**/compost');
  });
});
