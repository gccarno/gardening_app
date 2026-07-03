import { afterEach, describe, expect, it, vi } from 'vitest';
import { createGardensApi } from './gardens';

const api = createGardensApi('/api');

function stubFetch(status: number, body: unknown) {
  const mock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', mock);
  return mock;
}

afterEach(() => vi.unstubAllGlobals());

describe('createGardensApi', () => {
  it('fetches gardens from the right URL', async () => {
    const mock = stubFetch(200, [{ id: 1, name: 'Backyard', unit: 'ft' }]);
    const gardens = await api.fetchGardens();
    expect(mock.mock.calls[0][0]).toBe('/api/gardens');
    expect(gardens[0].name).toBe('Backyard');
  });

  it('throws on a failed list request', async () => {
    stubFetch(500, { detail: 'boom' });
    await expect(api.fetchGardens()).rejects.toThrow('Failed to fetch gardens');
  });

  it('POSTs new gardens as JSON', async () => {
    const mock = stubFetch(200, { id: 2, name: 'Front', unit: 'ft' });
    await api.createGarden({ name: 'Front' });
    const [url, init] = mock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/gardens');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ name: 'Front' });
  });

  it('parses watering status', async () => {
    stubFetch(200, {
      garden_id: 1, date: '2026-07-03', has_weather_data: true,
      forecast_today: null,
      beds: [{ bed_id: 1, bed_name: 'A', urgency_score: 55, label: 'water_today',
               deficit_mm: 12, days_since_watered: 4, kc: 1.0, mm_day: 4.5,
               plants: ['Tomato'], recommendation: 'Water today' }],
    });
    const status = await api.fetchWateringStatus(1);
    expect(status.beds[0].label).toBe('water_today');
  });
});
