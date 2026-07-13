// Regression test: the planner's api() helper must go through apiFetch so
// every request carries the bearer token. A bare fetch() here caused 401s on
// all planner data (beds, canvas plants, annotations, tasks, weather).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { configureAuth } from '@garden/shared';
import { api } from './types';

afterEach(() => {
  vi.unstubAllGlobals();
  configureAuth({ getToken: () => null });
});

function stubFetch() {
  const mock = vi.fn(async (..._args: Parameters<typeof fetch>) =>
    new Response('{}', { status: 200 }));
  vi.stubGlobal('fetch', mock);
  return mock;
}

describe('planner api()', () => {
  it('sends the Authorization header when a token is configured', async () => {
    const mock = stubFetch();
    configureAuth({ getToken: () => 'tok123' });

    await api('GET', '/api/beds?garden_id=1');

    const init = mock.mock.calls[0][1]!;
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok123');
  });

  it('still sends Content-Type for JSON bodies', async () => {
    const mock = stubFetch();
    configureAuth({ getToken: () => 'tok123' });

    await api('POST', '/api/beds', { name: 'New bed' });

    const init = mock.mock.calls[0][1]!;
    const headers = new Headers(init.headers);
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('Authorization')).toBe('Bearer tok123');
    expect(init.body).toBe(JSON.stringify({ name: 'New bed' }));
  });
});
