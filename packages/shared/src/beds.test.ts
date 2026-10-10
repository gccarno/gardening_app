import { afterEach, describe, expect, it, vi } from 'vitest';
import { createBedsApi } from './beds';

const api = createBedsApi('/api');

function stubFetch(status: number, body: unknown) {
  const mock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', mock);
  return mock;
}

afterEach(() => vi.unstubAllGlobals());

describe('soil moisture check-ins', () => {
  it('lists recent check-ins for a bed', async () => {
    const mock = stubFetch(200, [{ id: 1, bed_id: 7, check_date: '2026-10-10', level: 'dry', notes: null }]);
    const rows = await api.fetchMoistureCheckins(7, 5);
    expect(mock.mock.calls[0][0]).toBe('/api/beds/7/moisture-checkins?limit=5');
    expect(rows[0].level).toBe('dry');
  });

  it('POSTs a reading with the local date', async () => {
    const mock = stubFetch(200, { id: 2, bed_id: 7, check_date: '2026-10-10', level: 'wet' });
    await api.saveMoistureCheckin(7, { level: 'wet', check_date: '2026-10-10' });
    const [url, init] = mock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/beds/7/moisture-checkins');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ level: 'wet', check_date: '2026-10-10' });
  });

  it('throws when the server rejects the reading', async () => {
    stubFetch(400, { detail: 'level must be one of dry, ok, wet' });
    await expect(api.saveMoistureCheckin(7, { level: 'ok' })).rejects.toThrow('Failed to save soil moisture check-in');
  });

  it('throws on a failed list request', async () => {
    stubFetch(500, {});
    await expect(api.fetchMoistureCheckins(7)).rejects.toThrow('Failed to fetch soil moisture check-ins');
  });
});
