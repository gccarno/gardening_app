import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, configureAuth } from './http';

function stubFetch(status = 200, body: unknown = {}) {
  const mock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', mock);
  return mock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  configureAuth({ getToken: () => null });
});

describe('apiFetch', () => {
  it('sends no Authorization header when logged out', async () => {
    const mock = stubFetch();
    await apiFetch('/api/gardens');
    const init = mock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).has('Authorization')).toBe(false);
  });

  it('sends the bearer token when configured', async () => {
    const mock = stubFetch();
    configureAuth({ getToken: () => 'tok123' });
    await apiFetch('/api/gardens');
    const init = mock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok123');
  });

  it('invokes onUnauthorized on a 401 response', async () => {
    stubFetch(401);
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => 'expired', onUnauthorized });
    const res = await apiFetch('/api/gardens');
    expect(res.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it('does not invoke onUnauthorized on success', async () => {
    stubFetch(200);
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => 'good', onUnauthorized });
    await apiFetch('/api/gardens');
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
