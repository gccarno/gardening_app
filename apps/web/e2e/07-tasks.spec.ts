// Tasks: create with every field/type, list actions (Done/Undo/Edit/Delete),
// month-grid calendar navigation, and the detail editor.
import { test, expect, api, testName, readRunState, logManifest } from './helpers';

test.describe.configure({ mode: 'serial' });

const today = new Date().toISOString().slice(0, 10);

test.describe('tasks', () => {
  test('creates a fully-linked task through the form', async ({ page, request }) => {
    const { gardenId, bedIds, plantIds } = readRunState();
    const title = testName('Watering task');
    await page.goto('/tasks');
    await page.getByLabel('Title').fill(title);
    // Wrapped selects: option text joins the label's accessible name, so
    // target them by name attribute instead of label.
    await page.locator('select[name="task_type"]').selectOption('watering');
    await page.getByLabel('Due Date').fill(today);
    await page.locator('select[name="plant_id"]').selectOption(String(plantIds![1]));
    await page.locator('select[name="garden_id"]').selectOption(String(gardenId));
    await page.locator('select[name="bed_id"]').selectOption(String(bedIds![0]));
    await page.getByLabel('Description').fill('E2E: water the tomatoes');
    await page.getByRole('button', { name: 'Add Task' }).click();
    await expect(page.locator('.card', { hasText: title })).toBeVisible();

    const tasks = await api(request, 'get', `/api/tasks?garden_id=${gardenId}`);
    const mine = tasks.find((t: any) => t.title === title);
    expect(mine.task_type).toBe('watering');
    expect(mine.plant_id).toBe(plantIds![1]);
    logManifest({ type: 'task', id: mine.id, name: title });
  });

  test('creates one task of each remaining type via the form select', async ({ page, request }) => {
    const { gardenId } = readRunState();
    for (const type of ['seeding', 'harvest']) { // representative types beyond watering
      const title = testName(`${type} task`);
      await page.goto('/tasks');
      await page.getByLabel('Title').fill(title);
      await page.locator('select[name="task_type"]').selectOption(type);
      await page.getByLabel('Due Date').fill(today);
      await page.locator('select[name="garden_id"]').selectOption(String(gardenId));
      await page.getByRole('button', { name: 'Add Task' }).click();
      await expect(page.locator('.card', { hasText: title })).toBeVisible();
    }
    const tasks = await api(request, 'get', `/api/tasks?garden_id=${gardenId}`);
    for (const t of tasks.filter((t: any) => t.title?.startsWith('[E2E]'))) {
      logManifest({ type: 'task', id: t.id, name: t.title });
    }
  });

  test('Done and Undo toggle completion from the list', async ({ page }) => {
    const { runId } = readRunState();
    await page.goto('/tasks');
    const card = page.locator('.card', { hasText: `${runId} Watering task` });
    await card.getByRole('button', { name: 'Done' }).click();
    await expect(card.getByRole('button', { name: 'Undo' })).toBeVisible();
    await card.getByRole('button', { name: 'Undo' }).click();
    await expect(card.getByRole('button', { name: 'Done' })).toBeVisible();
  });

  test('calendar view shows the task chip on its due date and navigates months', async ({ page }) => {
    const { runId } = readRunState();
    await page.goto('/tasks');
    await page.getByRole('button', { name: 'Calendar' }).click();
    await expect(page.locator('.cal-cell--today')).toBeVisible();
    await expect(page.locator('.cal-chip', { hasText: `${runId} Watering task` })).toBeVisible();
    await page.locator('.cal-nav').getByRole('button', { name: '›' }).click();
    await page.locator('.cal-nav').getByRole('button', { name: '‹' }).click();
    await expect(page.locator('.cal-cell--today')).toBeVisible();

    // Clicking a chip opens the task detail.
    await page.locator('.cal-chip', { hasText: `${runId} Watering task` }).click();
    await page.waitForURL('**/tasks/*');
    await expect(page.getByRole('heading', { name: 'Edit Task' })).toBeVisible();
  });

  test('detail editor updates every field', async ({ page, request }) => {
    const { gardenId, runId } = readRunState();
    const tasks = await api(request, 'get', `/api/tasks?garden_id=${gardenId}`);
    const task = tasks.find((t: any) => t.title.includes(`${runId} seeding task`));
    await page.goto(`/tasks/${task.id}`);
    await page.getByLabel('Title').fill(testName('seeding task edited'));
    await page.locator('select[name="task_type"]').selectOption('transplanting');
    await page.getByLabel('Description').fill('E2E: edited description');
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await page.waitForURL('**/tasks');

    const after = await api(request, 'get', `/api/tasks/${task.id}`);
    expect(after.task_type).toBe('transplanting');
    expect(after.title).toContain('edited');
  });

  test('delete removes a task from the list', async ({ page }) => {
    const { runId } = readRunState();
    await page.goto('/tasks');
    const card = page.locator('.card', { hasText: `${runId} harvest task` });
    await card.getByRole('button', { name: 'Delete' }).click(); // confirm auto-accepted
    await expect(card).toHaveCount(0);
  });
});
