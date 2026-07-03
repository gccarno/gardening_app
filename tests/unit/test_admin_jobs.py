"""Admin job endpoints: X-Job-Token shared-secret guard."""
import pytest

from apps.backend.app.routers import admin as admin_router


@pytest.fixture
def stub_jobs(monkeypatch):
    calls = []
    monkeypatch.setattr(admin_router, 'run_daily_weather_fetch',
                        lambda: calls.append('weather'))
    return calls


def test_no_token_configured_allows_local_use(client, monkeypatch, stub_jobs):
    monkeypatch.delenv('JOB_TOKEN', raising=False)
    r = client.post('/api/admin/run-weather-fetch')
    assert r.status_code == 200
    assert stub_jobs == ['weather']


def test_missing_token_rejected(client, monkeypatch, stub_jobs):
    monkeypatch.setenv('JOB_TOKEN', 'sekrit')
    assert client.post('/api/admin/run-weather-fetch').status_code == 401
    assert stub_jobs == []


def test_wrong_token_rejected(client, monkeypatch, stub_jobs):
    monkeypatch.setenv('JOB_TOKEN', 'sekrit')
    r = client.post('/api/admin/run-weather-fetch',
                    headers={'X-Job-Token': 'wrong'})
    assert r.status_code == 401


def test_correct_token_accepted(client, monkeypatch, stub_jobs):
    monkeypatch.setenv('JOB_TOKEN', 'sekrit')
    r = client.post('/api/admin/run-weather-fetch',
                    headers={'X-Job-Token': 'sekrit'})
    assert r.status_code == 200
    assert stub_jobs == ['weather']
