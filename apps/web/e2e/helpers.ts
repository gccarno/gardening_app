// Shared fixtures for the live E2E suite: run state passed between serial
// spec files, the JSONL manifest of everything created (the backtracking
// record if teardown fails — see tests/e2e/README.md), and an authenticated
// API request helper for setup/verification steps.
import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { ARTIFACTS_DIR, E2E_PREFIX, baseUrl } from './env';

export { expect, E2E_PREFIX };

const RUN_FILE = path.join(ARTIFACTS_DIR, 'current-run.json');

export interface RunState {
  runId: string;
  token: string;
  // IDs the build specs create and later specs (and teardown) reuse.
  gardenId?: number;
  bedIds?: number[];
  plantIds?: number[];
  libraryCloneId?: number;
  syncGardenId?: number;
  prevDefaultGardenId?: number | null;
  [key: string]: unknown;
}

export function readRunState(): RunState {
  return JSON.parse(readFileSync(RUN_FILE, 'utf-8'));
}

export function writeRunState(state: RunState): void {
  mkdirSync(ARTIFACTS_DIR, { recursive: true });
  writeFileSync(RUN_FILE, JSON.stringify(state, null, 2));
}

export function updateRunState(patch: Partial<RunState>): RunState {
  const state = { ...readRunState(), ...patch };
  writeRunState(state);
  return state;
}

/** Append one created/mutated entity to the run's JSONL manifest. */
export function logManifest(entry: Record<string, unknown>): void {
  const { runId } = readRunState();
  mkdirSync(ARTIFACTS_DIR, { recursive: true });
  appendFileSync(
    path.join(ARTIFACTS_DIR, `${runId}.jsonl`),
    JSON.stringify({ ts: new Date().toISOString(), platform: 'web', ...entry }) + '\n',
  );
}

/** Test name for an entity: `[E2E] <runId> <label>`. */
export function testName(label: string): string {
  return `${E2E_PREFIX} ${readRunState().runId} ${label}`;
}

// Render's free instance restarts under memory pressure mid-run (on 2026-07-27
// it did so while ChromaDB lazily downloaded a 79 MB ONNX model), and every
// request in that window returns 502. A single unlucky call used to abort
// teardown and strand [E2E] rows in the production database, so treat the
// gateway codes as transient and give the instance time to come back.
// Retrying the mutating verbs is safe here: these codes come from Render's
// proxy when no healthy instance accepted the request, so the write never ran.
const TRANSIENT_STATUSES = [502, 503, 504];
const RETRY_DELAYS_MS = [2_000, 5_000, 10_000, 15_000];

/** Authenticated JSON call against the live API (setup + verification). */
export async function api(
  request: APIRequestContext,
  method: 'get' | 'post' | 'put' | 'delete',
  apiPath: string,
  data?: unknown,
): Promise<any> {
  const { token } = readRunState();
  const send = () => request[method](`${baseUrl}${apiPath}`, {
    headers: { Authorization: `Bearer ${token}` },
    ...(data !== undefined ? { data } : {}),
  });

  let resp = await send();
  for (const delay of RETRY_DELAYS_MS) {
    if (!TRANSIENT_STATUSES.includes(resp.status())) break;
    logManifest({
      event: 'api-retry', method, path: apiPath, status: resp.status(), delay,
    });
    await new Promise(r => setTimeout(r, delay));
    resp = await send();
  }
  expect(resp.ok(), `${method.toUpperCase()} ${apiPath} -> ${resp.status()}`).toBeTruthy();
  const body = await resp.text();
  const parsed = body ? JSON.parse(body) : null;
  if (method !== 'get' && parsed && typeof parsed === 'object' && 'id' in parsed) {
    logManifest({ via: 'api', method, path: apiPath, id: parsed.id });
  }
  return parsed;
}

/**
 * Suite-wide page fixture:
 *  - auto-accepts confirm() dialogs (delete buttons) and logs them,
 *  - records every mutating API response (id when present) to the manifest,
 *    so even UI-driven creates leave a paper trail for cleanup.
 */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, use) => {
    page.on('dialog', dialog => {
      logManifest({ event: 'dialog', message: dialog.message() });
      dialog.accept().catch(() => {});
    });
    page.on('response', async resp => {
      const req = resp.request();
      const url = new URL(resp.url());
      if (!url.pathname.startsWith('/api/') || req.method() === 'GET') return;
      const entry: Record<string, unknown> = {
        via: 'ui', method: req.method(), path: url.pathname, status: resp.status(),
      };
      try {
        const body = await resp.json();
        if (body && typeof body === 'object' && 'id' in body) entry.id = body.id;
      } catch { /* non-JSON response */ }
      logManifest(entry);
    });
    await use(page);
  },
});
