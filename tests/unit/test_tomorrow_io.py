"""Tomorrow.io client: key alias, parsers, and Open-Meteo fallback wiring."""
import json
from datetime import date, timedelta

import pytest
import requests

from apps.backend.app.routers import weather as weather_router
from apps.backend.app.services import tomorrow_io
from apps.ml_service.app import watering_engine


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


FORECAST = {'timelines': {'daily': [
    {'time': '2026-07-17T11:00:00Z', 'values': {
        'temperatureMax': 31.0, 'temperatureMin': 19.0,
        'precipitationProbabilityMax': 65, 'rainAccumulationSum': 4.0,
        'windSpeedMax': 5.0, 'uvIndexMax': 7, 'weatherCodeMax': 4001,
        'evapotranspirationSum': 3.8}},
    {'time': '2026-07-18T11:00:00Z', 'values': {
        'temperatureMax': 28.0, 'temperatureMin': 17.0,
        'precipitationProbabilityMax': 10, 'rainAccumulationSum': 0.0,
        'windSpeedMax': 3.0, 'uvIndexMax': 6, 'weatherCodeMax': 1100}},
]}}

REALTIME = {'data': {'time': '2026-07-17T14:00:00Z', 'values': {
    'temperature': 27.5, 'humidity': 60, 'rainIntensity': 0.0,
    'windSpeed': 4.2, 'weatherCode': 1101}}}


def _history_payload():
    yesterday = date.today() - timedelta(days=1)
    return {'timelines': {'daily': [
        {'time': f'{yesterday.isoformat()}T11:00:00Z', 'values': {
            'temperatureMax': 88.0, 'temperatureMin': 66.0,
            'rainAccumulationSum': 0.12, 'weatherCodeMax': 1000}},
        {'time': f'{date.today().isoformat()}T11:00:00Z', 'values': {
            'temperatureMax': 90.0, 'temperatureMin': 70.0,
            'rainAccumulationSum': 0.0, 'weatherCodeMax': 1000}},
    ]}}


def tomorrow_only_get(url, **kwargs):
    """Open-Meteo unreachable, Tomorrow.io healthy."""
    if 'open-meteo' in url:
        raise requests.ConnectionError('blocked egress IP')
    if 'tomorrow.io' in url:
        if 'history/recent' in url:
            return FakeResponse(_history_payload())
        if 'realtime' in url:
            return FakeResponse(REALTIME)
        if 'forecast' in url:
            return FakeResponse(FORECAST)
    raise AssertionError(f'unexpected URL in test: {url}')


@pytest.fixture
def fallback_http(monkeypatch):
    monkeypatch.setenv('TOMORROW_IO_KEY', 'test-key')
    monkeypatch.setattr(requests, 'get', tomorrow_only_get)


# ── Key alias ────────────────────────────────────────────────────────────────

def test_get_key_accepts_unsuffixed_alias(monkeypatch):
    monkeypatch.delenv('TOMORROW_IO_KEY', raising=False)
    monkeypatch.setenv('TOMORROW_IO', 'alias-key')
    assert tomorrow_io.get_key() == 'alias-key'


def test_get_key_prefers_canonical_name(monkeypatch):
    monkeypatch.setenv('TOMORROW_IO_KEY', 'canonical')
    monkeypatch.setenv('TOMORROW_IO', 'alias')
    assert tomorrow_io.get_key() == 'canonical'


# ── Parsers ──────────────────────────────────────────────────────────────────

def test_fetch_forecast_days_parses(fallback_http):
    days = tomorrow_io.fetch_forecast_days(40.0, -75.2)
    assert days[0] == {
        'date': '2026-07-17', 'temp_max': 31.0, 'temp_min': 19.0,
        'precip_prob': 65, 'precip_sum': 4.0, 'wind_max': 5.0, 'uv': 7,
        'et0': 3.8, 'condition': 'Rain',
    }
    assert days[1]['condition'] == 'Mainly clear'


def test_fetch_realtime_parses(fallback_http):
    cur = tomorrow_io.fetch_realtime(40.0, -75.2)
    assert cur == {'temp': 27.5, 'humidity': 60, 'precipitation': 0.0,
                   'wind_speed': 4.2, 'condition': 'Partly cloudy'}


def test_fetch_functions_return_none_without_key(monkeypatch):
    monkeypatch.setattr(tomorrow_io, 'get_key', lambda: None)
    assert tomorrow_io.fetch_forecast_days(40.0, -75.2) is None
    assert tomorrow_io.fetch_realtime(40.0, -75.2) is None
    assert tomorrow_io.fetch_history_days(40.0, -75.2) is None


# ── Watering-engine forecast fallback ────────────────────────────────────────

def test_forecast_today_falls_back_to_tomorrow_io(fallback_http):
    fc = watering_engine.fetch_forecast_today(40.0, -75.2)
    assert fc == {
        'date': '2026-07-17', 'temp_max_c': 31.0,
        'wind_kmh': 18.0,  # 5.0 m/s * 3.6
        'precip_prob': 65, 'precip_mm': 4.0,
    }


def test_forecast_today_none_when_both_fail(monkeypatch):
    monkeypatch.setenv('TOMORROW_IO_KEY', 'test-key')

    def all_fail(url, **kwargs):
        raise requests.ConnectionError('down')
    monkeypatch.setattr(requests, 'get', all_fail)
    assert watering_engine.fetch_forecast_today(40.0, -75.2) is None


# ── Weather-card endpoint fallback ───────────────────────────────────────────

def test_weather_card_falls_back_to_tomorrow_io(client, garden, fallback_http,
                                                monkeypatch):
    monkeypatch.setattr(weather_router, '_weather_cache', {})
    r = client.get(f'/api/gardens/{garden.id}/weather')
    assert r.status_code == 200
    data = r.json()
    assert data['source'] == 'tomorrow.io'
    assert data['current']['temp'] == 27.5
    assert data['daily'][0]['high'] == 31.0
    assert data['daily'][0]['condition'] == 'Rain'
    assert data['frost']['last_spring'] == 'Apr 15'


def test_weather_card_502_without_key(client, garden, monkeypatch):
    monkeypatch.setattr(weather_router, '_weather_cache', {})
    monkeypatch.setattr(tomorrow_io, 'get_key', lambda: None)

    def all_fail(url, **kwargs):
        raise requests.ConnectionError('down')
    monkeypatch.setattr(requests, 'get', all_fail)
    r = client.get(f'/api/gardens/{garden.id}/weather')
    assert r.status_code == 502


# ── WeatherLog history fallback ──────────────────────────────────────────────

def test_history_fetch_falls_back_and_skips_today(db, garden, fallback_http):
    from apps.backend.app.db.models import WeatherLog

    created = weather_router._fetch_weather_for_garden(db, garden.id)
    assert created == 1  # yesterday only; today's partial day is skipped

    logs = db.query(WeatherLog).filter_by(garden_id=garden.id).all()
    assert len(logs) == 1
    assert logs[0].date == date.today() - timedelta(days=1)
    assert logs[0].rainfall_in == 0.12
    assert logs[0].temp_high_f == 88.0
    assert logs[0].source == 'api'


def test_history_fetch_reraises_without_key(db, garden, monkeypatch):
    monkeypatch.setattr(tomorrow_io, 'get_key', lambda: None)

    def all_fail(url, **kwargs):
        raise requests.ConnectionError('down')
    monkeypatch.setattr(requests, 'get', all_fail)
    with pytest.raises(requests.ConnectionError):
        weather_router._fetch_weather_for_garden(db, garden.id)
