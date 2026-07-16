// Beds: create/edit/rename/delete, the 1ft mini-grid (place, care, remove),
// rotation warnings, and bed-plant observations (no web UI — API-verified).
import { test, expect, api, testName, readRunState, updateRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('beds & grid', () => {
  test('creates two beds with every form field', async ({ page, request }) => {
    const { gardenId } = readRunState();
    await page.goto('/beds');

    const bedA = testName('Bed A');
    // A wrapped <select>'s option text joins the label's accessible name, so
    // exact-match on "Garden" never resolves; scope to the form instead.
    const form = page.locator('form.form');
    await form.locator('select[name="garden_id"]').selectOption(String(gardenId));
    await form.getByLabel('Name').fill(bedA);
    await form.getByLabel('Location').fill('South fence');
    await form.getByLabel('Description').fill('Primary E2E bed');
    await form.getByLabel('Width (ft)').fill('4');
    await form.getByLabel('Height (ft)').fill('4');
    await form.getByLabel('Depth (ft)').fill('1');
    await form.getByLabel('Soil Notes').fill('Raised bed with compost mix');
    await page.getByRole('button', { name: 'Add Bed' }).click();
    await expect(page.locator('.card', { hasText: bedA })).toBeVisible();

    const bedB = testName('Bed B');
    await form.getByLabel('Name').fill(bedB);
    await form.getByLabel('Width (ft)').fill('3');
    await form.getByLabel('Height (ft)').fill('3');
    await page.getByRole('button', { name: 'Add Bed' }).click();
    await expect(page.locator('.card', { hasText: bedB })).toBeVisible();

    const beds = await api(request, 'get', `/api/beds?garden_id=${gardenId}`);
    const ids = [bedA, bedB].map(n => beds.find((b: any) => b.name === n)?.id);
    expect(ids.every(Boolean)).toBeTruthy();
    updateRunState({ bedIds: ids });
    ids.forEach((id, i) => logManifest({ type: 'bed', id, name: i === 0 ? bedA : bedB }));
  });

  test('garden filter narrows the list; rename works', async ({ page }) => {
    const { gardenId, runId } = readRunState();
    await page.goto('/beds');
    await page.locator('#garden-filter').selectOption(String(gardenId));
    const cards = page.locator('.card', { hasText: runId });
    await expect(cards).toHaveCount(2);

    const bCard = page.locator('.card', { hasText: 'Bed B' });
    await bCard.getByRole('button', { name: 'Rename' }).click();
    await bCard.locator('input[type="text"]').fill(testName('Bed B renamed'));
    await bCard.getByRole('button', { name: 'Save' }).click();
    await expect(page.locator('.card', { hasText: 'Bed B renamed' })).toBeVisible();
  });

  test('edit form saves soil profile fields', async ({ page, request }) => {
    const { bedIds } = readRunState();
    await page.goto(`/beds/${bedIds![0]}`);
    await page.getByText('Edit Bed').click();
    const form = page.locator('details form');
    await form.getByLabel('Soil pH').fill('6.5');
    await form.locator('input[placeholder="Clay %"]').fill('20');
    await form.locator('input[placeholder="Compost %"]').fill('50');
    await form.locator('input[placeholder="Sand %"]').fill('30');
    await form.getByRole('button', { name: 'Save Changes' }).click();
    await expect(page.locator('dl.details')).toContainText('6.5');
    await expect(page.locator('dl.details')).toContainText('Clay 20%');

    const bed = await api(request, 'get', `/api/beds/${bedIds![0]}`);
    expect(bed.soil_ph).toBe(6.5);
  });

  test('places a plant in the grid and triggers a rotation warning', async ({ page }) => {
    const { bedIds } = readRunState();
    await page.goto(`/beds/${bedIds![0]}`);

    // Select "Tomato" from the library sidebar and click an empty cell.
    await page.getByPlaceholder('Search library…').fill('Tomato');
    const option = page.locator('.bed-plant-select option', { hasText: 'Tomato' }).first();
    await page.locator('select.bed-plant-select').selectOption(await option.getAttribute('value') ?? '');
    await page.locator('.bed-cell.empty').first().click();
    await expect(page.locator('.bed-cell.occupied')).toHaveCount(1);

    // The rotation query is keyed on the selected plant and does not refetch
    // after placement — select a same-family plant (Pepper, also Solanaceae)
    // to trigger a fresh check against the now-occupied bed.
    await page.getByPlaceholder('Search library…').fill('Pepper');
    const pepper = page.locator('.bed-plant-select option', { hasText: 'Pepper' }).first();
    await page.locator('select.bed-plant-select').selectOption(await pepper.getAttribute('value') ?? '');
    await expect(page.getByText(/⚠️|Families in bed:/)).toBeVisible();
  });

  test('care panel saves dates and notes for the placed plant', async ({ page }) => {
    const { bedIds } = readRunState();
    await page.goto(`/beds/${bedIds![0]}`);
    await page.locator('.bed-cell.occupied').first().click();
    const panel = page.locator('.care-panel');
    await expect(panel).toBeVisible();
    await panel.getByLabel('Last Watered').fill('2026-07-14');
    await panel.getByLabel('Last Fertilized').fill('2026-07-10');
    await panel.getByLabel(/Health Notes/).fill('E2E: aphids spotted, treated with neem oil');
    await panel.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(panel.getByText('Saved.')).toBeVisible();
    await panel.getByRole('button', { name: 'Close' }).click();
  });

  test('observations + health score (API — no web UI for this yet)', async ({ request }) => {
    const { bedIds, gardenId } = readRunState();
    const grid = await api(request, 'get', `/api/beds/${bedIds![0]}/grid`);
    const bp = grid.placed[0];
    expect(bp, 'grid should still hold the placed plant').toBeTruthy();

    const obs = await api(request, 'post', `/api/bedplants/${bp.id}/observations`, {
      observation_type: 'pest_damage', severity: 2, notes: `${testName('obs')} aphids on lower leaves`,
    });
    const score = await api(request, 'get', `/api/bedplants/${bp.id}/health-score`);
    expect(score.score ?? score.health_score).toBeDefined();
    await api(request, 'delete', `/api/observations/${obs.id}`);
    void gardenId;
  });

  test('removing the plant from its cell empties the grid', async ({ page }) => {
    const { bedIds } = readRunState();
    await page.goto(`/beds/${bedIds![0]}`);
    await page.locator('.bed-cell.occupied').first().click();
    await page.locator('.care-panel').getByRole('button', { name: 'Remove Plant' }).click();
    await expect(page.locator('.bed-cell.occupied')).toHaveCount(0);
  });

  test('a throwaway bed can be deleted from the list', async ({ page, request }) => {
    const { gardenId } = readRunState();
    const name = testName('Bed C throwaway');
    await api(request, 'post', '/api/beds', { name, garden_id: gardenId, width_ft: 2, height_ft: 2 });
    await page.goto('/beds');
    const card = page.locator('.card', { hasText: name });
    await card.getByRole('button', { name: 'Delete' }).click(); // confirm() auto-accepted
    await expect(card).toHaveCount(0);
  });
});
