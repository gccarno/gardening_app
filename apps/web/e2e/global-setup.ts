// Global setup: warm the Render service through any cold start, log in via
// the API, and write both the Playwright storage state (so specs start
// authenticated) and the run state file (run ID + token shared across specs).
import { request } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
import { baseUrl, credentials } from './env';
import { readRunState, writeRunState } from './helpers';

const COLD_START_MS = 120_000;

export default async function globalSetup(): Promise<void> {
  if (!credentials.email || !credentials.password) {
    throw new Error('USERNAME/PASSWORD missing from repo-root .env — the live E2E suite needs them');
  }

  const ctx = await request.newContext();
  try {
    // Render free tier spins down when idle; poll /api/health until it's up.
    const deadline = Date.now() + COLD_START_MS;
    for (;;) {
      try {
        const res = await ctx.get(`${baseUrl}/api/health`, { timeout: 15_000 });
        if (res.ok()) break;
      } catch { /* still booting */ }
      if (Date.now() > deadline) {
        throw new Error(`${baseUrl}/api/health not up after ${COLD_START_MS} ms`);
      }
      await new Promise(r => setTimeout(r, 3000));
    }

    const login = await ctx.post(`${baseUrl}/api/auth/login`, {
      data: { email: credentials.email, password: credentials.password },
    });
    if (!login.ok()) {
      throw new Error(`login failed: ${login.status()} ${await login.text()}`);
    }
    const { token, user } = await login.json();

    // E2E_KEEP_RUN=1 (set by the sync-relay orchestrator between phases)
    // keeps the existing run ID and state; only the token is refreshed.
    let runId = 'e2e-' + new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    if (process.env.E2E_KEEP_RUN) {
      try {
        const prev = readRunState();
        runId = prev.runId;
        writeRunState({ ...prev, token });
      } catch {
        writeRunState({ runId, token });
      }
    } else {
      writeRunState({ runId, token });
    }

    // Seed the browser with the same localStorage keys AuthContext.tsx uses.
    const stateDir = path.resolve(__dirname, '../.playwright');
    mkdirSync(stateDir, { recursive: true });
    writeFileSync(path.join(stateDir, 'auth-state.json'), JSON.stringify({
      cookies: [],
      origins: [{
        origin: baseUrl,
        localStorage: [
          { name: 'garden_auth_token', value: token },
          { name: 'garden_auth_user', value: JSON.stringify(user) },
        ],
      }],
    }, null, 2));
    console.log(`E2E run ${runId} against ${baseUrl} as ${user.email}`);
  } finally {
    await ctx.dispose();
  }
}
