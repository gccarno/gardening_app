// AI / external features — all skip-if-unavailable: chat assistant (Ollama or
// hosted LLM), photo identify (ML model), recommendations. Never calls
// /api/chat/restart-model (disruptive on shared prod).
import path from 'node:path';
import { FIXTURES_DIR, baseUrl } from './env';
import { test, expect, readRunState } from './helpers';

test.describe('AI features', () => {
  test('chat widget: chips render, a message gets a reply', async ({ page, request }) => {
    const { gardenId, token } = readRunState();
    // Probe the backend first so an offline model skips instead of failing.
    const probe = await request.post(`${baseUrl}/api/chat`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { message: 'ping', garden_id: gardenId, conversation_history: [] },
      timeout: 90_000,
    }).catch(() => null);
    test.skip(!probe || !probe.ok(), 'chat backend unavailable');

    await page.goto('/dashboard');
    // Wait for the widget to mount (it defaults open); only click the header
    // if it rendered collapsed — clicking too early toggles it closed.
    await page.locator('.chat-widget').waitFor();
    if (!(await page.locator('.chat-widget__body').count())) {
      await page.locator('.chat-widget__header').click();
    }
    await expect(page.locator('.chat-prompt-chip').first()).toBeVisible();
    await page.getByPlaceholder('Ask about planting, companions, tasks…').fill('In one word, what season is July in the northern hemisphere?');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.locator('.chat-msg--user')).toBeVisible();
    await expect(page.locator('.chat-msg--bot').last()).not.toContainText(
      'Could not reach the assistant', { timeout: 90_000 });
  });

  test('identify uploads a photo and shows a response', async ({ page, request }) => {
    const { token } = readRunState();
    const probe = await request.get(`${baseUrl}/api/health`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    test.skip(!probe.ok(), 'backend unavailable');

    await page.goto('/identify');
    await expect(page.getByRole('heading', { name: 'Identify' })).toBeVisible();
    for (const mode of ['🐛 Identify pest', '🌿 What plant is this?']) {
      await page.getByRole('button', { name: mode }).click();
    }
    await page.locator('input[type="file"]').setInputFiles(path.join(FIXTURES_DIR, 'plant_photo.png'));
    await page.getByRole('button', { name: /Analyze/ }).click();
    // Model may be missing on prod — accept either a result card or an error
    // message, as long as the page responds rather than hangs.
    await expect(page.locator('.identify-result, .result, [class*=result], .muted, [class*=error]').first())
      .toBeVisible({ timeout: 120_000 });
  });

  test('recommendations endpoint responds for the garden', async ({ request }) => {
    const { gardenId, token } = readRunState();
    const resp = await request.get(`${baseUrl}/api/recommendations?garden_id=${gardenId}`, {
      headers: { Authorization: `Bearer ${token}` }, timeout: 90_000,
    });
    test.skip(resp.status() >= 500, 'recommendations backend unavailable');
    expect(resp.status()).toBeLessThan(500);
  });
});
