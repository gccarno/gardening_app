"""Rain log, rainfall summary, and weather-card provider tests."""
from datetime import date, timedelta

from apps.backend.app.db.models import WeatherLog
from apps.backend.app.routers import weather as weather_router
from apps.backend.app.services.helpers import rainfall_summary


def test_log_rain_creates_entry(client, db, garden):
    r = client.post(f'/api/gardens/{garden.id}/log-rain', json={'rainfall_in': 0.5})
    assert r.status_code == 200
    data = r.json()
    assert data['rainfall_in'] == 0.5
    assert data['date'] == date.today().isoformat()

    logs = client.get(f'/api/gardens/{garden.id}/rain-log').json()
    assert len(logs) == 1
    assert logs[0]['source'] == 'manual'


def test_log_rain_upserts_same_date(client, db, garden):
    client.post(f'/api/gardens/{garden.id}/log-rain', json={'rainfall_in': 0.5})
    client.post(f'/api/gardens/{garden.id}/log-rain', json={'rainfall_in': 1.25})
    logs = db.query(WeatherLog).filter_by(garden_id=garden.id).all()
    assert len(logs) == 1
    assert logs[0].rainfall_in == 1.25


def test_log_rain_clamped(client, garden):
    r = client.post(f'/api/gardens/{garden.id}/log-rain', json={'rainfall_in': 500})
    assert r.json()['rainfall_in'] == 20.0
    r = client.post(f'/api/gardens/{garden.id}/log-rain',
                    json={'rainfall_in': -3, 'entry_date': '2026-06-01'})
    assert r.json()['rainfall_in'] == 0.0


def test_log_rain_specific_date(client, garden):
    r = client.post(f'/api/gardens/{garden.id}/log-rain',
                    json={'rainfall_in': 0.3, 'entry_date': '2026-06-15'})
    assert r.json()['date'] == '2026-06-15'


def test_rain_log_window(client, db, garden):
    db.add(WeatherLog(garden_id=garden.id, date=date.today() - timedelta(days=30),
                      rainfall_in=1.0, source='api'))
    db.add(WeatherLog(garden_id=garden.id, date=date.today() - timedelta(days=2),
                      rainfall_in=0.4, source='api'))
    db.flush()
    logs = client.get(f'/api/gardens/{garden.id}/rain-log?days=14').json()
    assert len(logs) == 1


def test_rainfall_summary(db, garden, weather_log):
    summary = rainfall_summary(db, garden.id, days=7)
    assert summary['total_in'] == 0.4
    assert summary['days_with_data'] == 1


def test_garden_weather_prefers_tomorrow_io(client, garden, monkeypatch):
    """Tomorrow.io is the primary provider — Open-Meteo must not be called
    when it succeeds."""
    weather_router._weather_cache.clear()
    monkeypatch.setattr(weather_router, '_tomorrow_io_weather',
                        lambda g: {'source': 'tomorrow.io'})
    monkeypatch.setattr(weather_router, '_open_meteo_weather',
                        lambda g: (_ for _ in ()).throw(AssertionError('should not be called')))

    r = client.get(f'/api/gardens/{garden.id}/weather')
    assert r.status_code == 200
    assert r.json()['source'] == 'tomorrow.io'


def test_garden_weather_falls_back_to_open_meteo(client, garden, monkeypatch):
    """When Tomorrow.io has no key/fails, Open-Meteo is the fallback."""
    weather_router._weather_cache.clear()
    monkeypatch.setattr(weather_router, '_tomorrow_io_weather', lambda g: None)
    monkeypatch.setattr(weather_router, '_open_meteo_weather',
                        lambda g: {'source': 'open-meteo'})

    r = client.get(f'/api/gardens/{garden.id}/weather')
    assert r.status_code == 200
    assert r.json()['source'] == 'open-meteo'


def test_garden_weather_502_when_both_providers_down(client, garden, monkeypatch):
    weather_router._weather_cache.clear()
    monkeypatch.setattr(weather_router, '_tomorrow_io_weather', lambda g: None)
    monkeypatch.setattr(weather_router, '_open_meteo_weather', lambda g: None)

    r = client.get(f'/api/gardens/{garden.id}/weather')
    assert r.status_code == 502


def test_open_meteo_weather_handles_malformed_json_body(garden, monkeypatch):
    """Regression for GARDEN-APP-BACKEND-G: Open-Meteo returned HTTP 200 with
    a non-JSON (empty) body, and resp.json() raised outside any try/except,
    producing an unhandled 500. _open_meteo_weather must degrade to None
    instead of raising."""
    import requests

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            raise requests.exceptions.JSONDecodeError('Expecting value', '', 0)

    monkeypatch.setattr(weather_router.http, 'get', lambda *a, **k: FakeResp())

    assert weather_router._open_meteo_weather(garden) is None
