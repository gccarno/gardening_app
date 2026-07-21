"""
Tomorrow.io weather client — fallback provider for when Open-Meteo is
unreachable (it rate-limits/403s by source IP, and Render free-tier services
share egress IPs).

The free-tier key is read from TOMORROW_IO_KEY or TOMORROW_IO (process env
first, then the repo-root .env). Endpoints used:
    /v4/weather/forecast        daily forecast (~6 days)
    /v4/weather/realtime        current conditions
    /v4/weather/history/recent  past ~24h dailies (WeatherLog backfill)

Units: pass units='metric' (C, mm, wind m/s) or 'imperial' (F, inch, mph).
Fetch functions return None when no key is configured and raise
requests exceptions on HTTP/network errors — callers decide how to degrade.
"""
from __future__ import annotations

import requests

from .weather_probes import _get_key

TIMEOUT = 8
_BASE = 'https://api.tomorrow.io/v4/weather'

# tomorrow.io weatherCode → human-readable condition
CODES = {
    0: 'Unknown', 1000: 'Clear sky', 1100: 'Mainly clear', 1101: 'Partly cloudy',
    1102: 'Mostly cloudy', 1001: 'Overcast', 2000: 'Fog', 2100: 'Light fog',
    4000: 'Drizzle', 4200: 'Light rain', 4001: 'Rain', 4201: 'Heavy rain',
    5001: 'Snow flurries', 5100: 'Light snow', 5000: 'Snow', 5101: 'Heavy snow',
    6000: 'Freezing drizzle', 6200: 'Light freezing rain', 6001: 'Freezing rain',
    6201: 'Heavy freezing rain', 7102: 'Light ice pellets', 7000: 'Ice pellets',
    7101: 'Heavy ice pellets', 8000: 'Thunderstorm',
}


def get_key() -> str | None:
    return _get_key('TOMORROW_IO_KEY')


def _get(path: str, lat: float, lon: float, units: str, key: str, **extra) -> dict:
    resp = requests.get(f'{_BASE}/{path}', params={
        'location': f'{lat},{lon}', 'apikey': key, 'units': units, **extra,
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _daily_entry(day: dict) -> dict:
    v = day.get('values', {})
    return {
        'date': (day.get('time') or '')[:10],
        'temp_max': v.get('temperatureMax'),
        'temp_min': v.get('temperatureMin'),
        'precip_prob': v.get('precipitationProbabilityMax',
                             v.get('precipitationProbabilityAvg')),
        'precip_sum': v.get('rainAccumulationSum', v.get('rainAccumulationAvg')),
        'wind_max': v.get('windSpeedMax', v.get('windSpeedAvg')),
        'humidity': v.get('humidityAvg'),
        'uv': v.get('uvIndexMax'),
        'et0': v.get('evapotranspirationSum'),
        'condition': CODES.get(v.get('weatherCodeMax', v.get('weatherCodeMin')),
                               'Unknown'),
    }


def fetch_forecast_days(lat: float, lon: float, units: str = 'metric',
                        key: str | None = None) -> list[dict] | None:
    """Daily forecast, today first (~6 days on the free tier)."""
    key = key or get_key()
    if not key:
        return None
    data = _get('forecast', lat, lon, units, key, timesteps='1d')
    return [_daily_entry(d) for d in data['timelines']['daily']]


def fetch_realtime(lat: float, lon: float, units: str = 'metric',
                   key: str | None = None) -> dict | None:
    key = key or get_key()
    if not key:
        return None
    v = _get('realtime', lat, lon, units, key)['data']['values']
    return {
        'temp': v.get('temperature'),
        'humidity': v.get('humidity'),
        'precipitation': v.get('rainIntensity', v.get('precipitationIntensity')),
        'wind_speed': v.get('windSpeed'),
        'condition': CODES.get(v.get('weatherCode'), 'Unknown'),
    }


def fetch_history_days(lat: float, lon: float, units: str = 'metric',
                       key: str | None = None) -> list[dict] | None:
    """Past ~24h daily history — enough to backfill yesterday's WeatherLog."""
    key = key or get_key()
    if not key:
        return None
    data = _get('history/recent', lat, lon, units, key, timesteps='1d')
    return [_daily_entry(d) for d in data['timelines']['daily']]
