"""Weather provider probes: parsers, no_key/error handling, admin endpoint."""
import json

import pytest
import requests

from apps.backend.app.services import weather_probes as wp


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f'HTTP {self.status_code}')
            err.response = self
            raise err


PAYLOADS = {
    'api.open-meteo.com': {'daily': {
        'time': ['2026-07-16', '2026-07-17'],
        'temperature_2m_max': [30.0, 31.0],
        'temperature_2m_min': [18.0, 19.0],
        'precipitation_probability_max': [40, 10],
        'precipitation_sum': [2.5, 0.0],
        'et0_fao_evapotranspiration': [4.2, 4.5],
    }},
    'archive-api.open-meteo.com': {'daily': {
        'time': ['2026-07-13'],
        'temperature_2m_max': [28.0],
        'temperature_2m_min': [16.0],
        'precipitation_sum': [1.1],
        'et0_fao_evapotranspiration': [3.9],
    }},
    'api.weather.gov/points': {'properties': {
        'forecast': 'https://api.weather.gov/gridpoints/PHI/49,75/forecast',
    }},
    'api.weather.gov/gridpoints': {'properties': {'periods': [
        {'isDaytime': True, 'temperature': 86,
         'startTime': '2026-07-16T06:00:00-04:00',
         'probabilityOfPrecipitation': {'value': 40}},
        {'isDaytime': False, 'temperature': 64,
         'startTime': '2026-07-16T18:00:00-04:00',
         'probabilityOfPrecipitation': {'value': 20}},
    ]}},
    'api.met.no': {'properties': {'timeseries': [
        {'time': '2026-07-16T00:00:00Z', 'data': {
            'instant': {'details': {'air_temperature': 20.0}},
            'next_1_hours': {'details': {'precipitation_amount': 0.5}}}},
        {'time': '2026-07-16T01:00:00Z', 'data': {
            'instant': {'details': {'air_temperature': 28.0}},
            'next_1_hours': {'details': {'precipitation_amount': 1.0}}}},
    ]}},
    'api.openweathermap.org': {'list': [
        {'dt_txt': '2026-07-16 00:00:00', 'main': {'temp': 22.0},
         'rain': {'3h': 1.2}, 'pop': 0.4},
        {'dt_txt': '2026-07-16 03:00:00', 'main': {'temp': 30.0}, 'pop': 0.8},
    ]},
    'api.weatherapi.com': {'forecast': {'forecastday': [
        {'date': '2026-07-16', 'day': {
            'totalprecip_mm': 3.1, 'maxtemp_c': 30.5, 'mintemp_c': 18.2,
            'daily_chance_of_rain': 70}},
    ]}},
    'weather.visualcrossing.com': {'days': [
        {'datetime': '2026-07-16', 'precip': 2.0, 'tempmax': 29.0,
         'tempmin': 17.0, 'precipprob': 55.0},
    ]},
    'api.tomorrow.io': {'timelines': {'daily': [
        {'time': '2026-07-16T11:00:00Z', 'values': {
            'rainAccumulationSum': 4.0, 'temperatureMax': 31.0,
            'temperatureMin': 19.0, 'precipitationProbabilityMax': 65,
            'evapotranspirationSum': 3.8}},
    ]}},
}


def fake_get(url, **kwargs):
    for fragment, payload in PAYLOADS.items():
        if fragment in url:
            return FakeResponse(payload)
    raise AssertionError(f'unexpected URL in test: {url}')


@pytest.fixture
def canned_http(monkeypatch):
    monkeypatch.setattr(wp.requests, 'get', fake_get)


# ── Individual parsers produce the full contract ─────────────────────────────

def test_open_meteo_forecast_parses_all_fields(canned_http):
    r = wp._probe_open_meteo_forecast(40.0, -75.2)
    assert r['status'] == 'ok'
    assert r['sample'] == {
        'date': '2026-07-16', 'precip_sum_daily': 2.5, 'temp_max': 30.0,
        'temp_min': 18.0, 'precip_prob_forecast': 40, 'et0': 4.2,
    }
    assert all(r['fields'].values())


def test_open_meteo_archive_has_no_probability(canned_http):
    r = wp._probe_open_meteo_archive(40.0, -75.2)
    assert r['status'] == 'ok'
    assert r['fields']['precip_sum_daily'] is True
    assert r['fields']['precip_prob_forecast'] is False


def test_nws_follows_points_and_converts_to_celsius(canned_http):
    r = wp._probe_nws(40.0, -75.2)
    assert r['status'] == 'ok'
    assert r['sample']['temp_max'] == 30.0   # 86F
    assert r['sample']['temp_min'] == 17.8   # 64F
    assert r['sample']['precip_prob_forecast'] == 40
    assert r['fields']['precip_sum_daily'] is False
    assert r['fields']['et0'] is False


def test_met_norway_aggregates_hourly(canned_http):
    r = wp._probe_met_norway(40.0, -75.2)
    assert r['status'] == 'ok'
    assert r['sample']['precip_sum_daily'] == 1.5
    assert r['sample']['temp_max'] == 28.0
    assert r['sample']['temp_min'] == 20.0


def test_openweathermap_aggregates_3h_slots(canned_http):
    r = wp._probe_openweathermap(40.0, -75.2, 'k')
    assert r['status'] == 'ok'
    assert r['sample']['precip_sum_daily'] == 1.2
    assert r['sample']['temp_max'] == 30.0
    assert r['sample']['precip_prob_forecast'] == 80


def test_weatherapi_parses_day(canned_http):
    r = wp._probe_weatherapi(40.0, -75.2, 'k')
    assert r['sample']['precip_sum_daily'] == 3.1
    assert r['sample']['precip_prob_forecast'] == 70


def test_visual_crossing_parses_day(canned_http):
    r = wp._probe_visual_crossing(40.0, -75.2, 'k')
    assert r['sample']['temp_max'] == 29.0
    assert r['fields']['et0'] is False  # not in canned payload


def test_tomorrow_io_reports_et0(canned_http):
    r = wp._probe_tomorrow_io(40.0, -75.2, 'k')
    assert r['sample']['et0'] == 3.8
    assert all(r['fields'].values())


# ── run_all_probes: no_key and error isolation ────────────────────────────────

def test_run_all_probes_no_key_and_errors_dont_crash(monkeypatch):
    monkeypatch.setattr(wp, '_get_key', lambda name: None)
    monkeypatch.setattr(wp, '_egress_ip', lambda: '1.2.3.4')

    def failing_get(url, **kwargs):
        if 'open-meteo' in url:
            raise requests.ConnectionError('boom')
        return fake_get(url, **kwargs)
    monkeypatch.setattr(wp.requests, 'get', failing_get)

    report = wp.run_all_probes(40.0, -75.2)
    by_name = {r['provider']: r for r in report['results']}

    assert len(report['results']) == len(wp.PROBES)
    assert report['egress_ip'] == '1.2.3.4'
    # keyless providers that fail -> error, not a crash
    assert by_name['open-meteo-forecast']['status'] == 'error'
    assert 'boom' in by_name['open-meteo-forecast']['error']
    # keyless providers that work -> ok
    assert by_name['nws']['status'] == 'ok'
    assert by_name['met-norway']['status'] == 'ok'
    # key-based providers without keys -> no_key
    for name in ('openweathermap', 'weatherapi', 'visual-crossing', 'tomorrow-io'):
        assert by_name[name]['status'] == 'no_key'
        assert 'not set' in by_name[name]['error']


def test_run_all_probes_captures_http_status(monkeypatch):
    monkeypatch.setattr(wp, '_get_key', lambda name: None)
    monkeypatch.setattr(wp, '_egress_ip', lambda: None)
    monkeypatch.setattr(wp.requests, 'get',
                        lambda url, **kw: FakeResponse({}, status_code=403))

    report = wp.run_all_probes(40.0, -75.2)
    forecast = report['results'][0]
    assert forecast['status'] == 'error'
    assert forecast['http_status'] == 403


def test_get_key_prefers_process_env(monkeypatch):
    monkeypatch.setenv('WEATHERAPI_KEY', 'from-env')
    assert wp._get_key('WEATHERAPI_KEY') == 'from-env'


# ── Admin endpoint: token guard + delegation ─────────────────────────────────

def test_endpoint_rejects_bad_token(client, monkeypatch):
    monkeypatch.setenv('JOB_TOKEN', 'sekrit')
    r = client.post('/api/admin/test-weather-providers',
                    headers={'X-Job-Token': 'wrong'})
    assert r.status_code == 401


def test_endpoint_runs_probes_with_token(client, monkeypatch):
    monkeypatch.setenv('JOB_TOKEN', 'sekrit')
    monkeypatch.setattr(
        'apps.backend.app.services.weather_probes.run_all_probes',
        lambda lat, lon: {'lat': lat, 'lon': lon, 'results': []})
    r = client.post('/api/admin/test-weather-providers?lat=40.0&lon=-75.2',
                    headers={'X-Job-Token': 'sekrit'})
    assert r.status_code == 200
    assert r.json() == {'lat': 40.0, 'lon': -75.2, 'results': []}
