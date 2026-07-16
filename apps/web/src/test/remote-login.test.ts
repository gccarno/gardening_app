// @vitest-environment node
//
// Live login tests against the deployed backend (Render by default).
// Credentials come from the repo-root .env file (USERNAME / PASSWORD) — read
// straight from the file, NOT process.env, because Windows always defines
// USERNAME as the OS account name. Skipped automatically when the file or
// keys are missing (e.g. CI).
//
// Override the target server: GARDEN_TEST_BASE_URL=http://127.0.0.1:8000
import { describe, it, expect, beforeAll } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const RENDER_URL = 'https://garden-app-wa0b.onrender.com';
const baseUrl = (process.env.GARDEN_TEST_BASE_URL ?? RENDER_URL).replace(/\/+$/, '');

function loadRootDotEnv(): Record<string, string> {
  const envPath = path.resolve(__dirname, '../../../../.env');
  if (!existsSync(envPath)) return {};
  const vars: Record<string, string> = {};
  for (const line of readFileSync(envPath, 'utf-8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*)\s*$/);
    if (m) vars[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
  return vars;
}

const env = loadRootDotEnv();
const email = env.USERNAME;
const password = env.PASSWORD;

// Render free tier spins down when idle; the first request can take ~60 s.
const COLD_START_MS = 120_000;

describe.skipIf(!email || !password)(`remote login (${baseUrl})`, () => {
  beforeAll(async () => {
    // Warm up through any cold start so the login tests measure auth, not boot.
    const deadline = Date.now() + COLD_START_MS;
    for (;;) {
      try {
        const res = await fetch(`${baseUrl}/api/health`);
        if (res.ok) return;
      } catch {
        // service still booting / unreachable — retry below
      }
      if (Date.now() > deadline) throw new Error(`${baseUrl}/api/health not up after ${COLD_START_MS} ms`);
      await new Promise(r => setTimeout(r, 3000));
    }
  }, COLD_START_MS + 10_000);

  it('logs in with .env credentials and returns a token', async () => {
    const res = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.token).toBeTruthy();
    expect(body.user.email).toBe(email);
  }, 30_000);

  it('rejects a wrong password', async () => {
    const res = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: 'definitely-wrong-password' }),
    });
    expect(res.status).toBe(401);
  }, 30_000);

  it('token works against /api/auth/me', async () => {
    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const { token } = await login.json();
    const me = await fetch(`${baseUrl}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(me.status).toBe(200);
    const body = await me.json();
    expect(body.email).toBe(email);
  }, 30_000);
});
