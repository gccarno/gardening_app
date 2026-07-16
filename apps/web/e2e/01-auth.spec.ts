// Login page UI: real form interactions (global setup already proved the API
// login works — this spec proves the page wiring does).
import { credentials, baseUrl } from './env';
import { test, expect } from './helpers';

// Start signed out: this spec exercises the login form itself.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe('auth', () => {
  test('rejects a wrong password with an error message', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(credentials.email!);
    // getByLabel('Password') also matches the aria-labelled Show/Hide toggle.
    await page.locator('.password-field input').fill('definitely-wrong-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.locator('.form-error')).toBeVisible();
    expect(new URL(page.url()).pathname).toBe('/login');
  });

  test('password visibility toggle works', async ({ page }) => {
    await page.goto('/login');
    const pw = page.locator('.password-field input');
    await pw.fill('secret123');
    await expect(pw).toHaveAttribute('type', 'password');
    await page.getByRole('button', { name: 'Show' }).click();
    await expect(pw).toHaveAttribute('type', 'text');
    await page.getByRole('button', { name: 'Hide' }).click();
    await expect(pw).toHaveAttribute('type', 'password');
  });

  test('register toggle only shows when registration is open', async ({ page, request }) => {
    const resp = await request.get(`${baseUrl}/api/auth/registration-open`);
    const { open } = await resp.json();
    await page.goto('/login');
    const toggle = page.getByRole('button', { name: /create an account/i });
    if (open) {
      await expect(toggle).toBeVisible(); // never click it: registering on prod is forbidden
    } else {
      await expect(toggle).toHaveCount(0);
    }
  });

  test('signs in through the form and signs out again', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(credentials.email!);
    await page.locator('.password-field input').fill(credentials.password!);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard');
    await expect(page.locator('nav .logout-btn')).toBeVisible();

    await page.locator('nav .logout-btn').click();
    await page.waitForURL('**/login');
    // Token cleared: a protected page bounces back to /login.
    await page.goto('/gardens');
    await page.waitForURL('**/login');
  });
});
