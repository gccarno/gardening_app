// Environment for the live E2E suite. Credentials come from the repo-root
// .env FILE (USERNAME / PASSWORD) — read from the file, never process.env,
// because Windows always defines USERNAME as the OS account name.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const REPO_ROOT = path.resolve(__dirname, '../../..');
export const ARTIFACTS_DIR = path.join(REPO_ROOT, 'tests', 'e2e', 'artifacts');
export const FIXTURES_DIR = path.join(REPO_ROOT, 'tests', 'e2e', 'fixtures');

// Every entity the suite creates is named with this prefix; teardown and
// scripts/e2e_cleanup.py match on it. Keep the three in sync.
export const E2E_PREFIX = '[E2E]';

const RENDER_URL = 'https://garden-app-wa0b.onrender.com';

function loadRootDotEnv(): Record<string, string> {
  const envPath = path.join(REPO_ROOT, '.env');
  if (!existsSync(envPath)) return {};
  const vars: Record<string, string> = {};
  for (const line of readFileSync(envPath, 'utf-8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*)\s*$/);
    if (m) vars[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
  return vars;
}

export const dotenv = loadRootDotEnv();
export const baseUrl = (
  process.env.GARDEN_TEST_BASE_URL ?? dotenv.GARDEN_TEST_BASE_URL ?? RENDER_URL
).replace(/\/+$/, '');
export const credentials = { email: dotenv.USERNAME, password: dotenv.PASSWORD };
