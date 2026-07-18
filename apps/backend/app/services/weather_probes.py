"""
Weather-provider probes: test alternative weather APIs from wherever this
code runs (locally or on Render, via POST /api/admin/test-weather-providers).

The point is diagnosing why Open-Meteo "doesn't run well" from Render: it is
keyless and rate-limits/403s by source IP, and Render free-tier services share
egress IPs. Each probe requests the data contract the app actually needs
(daily precipitation sum, temp max/min, forecast precip probability, ET0 —
see routers/weather.py and apps/ml_service/app/watering_engine.py) and reports
which fields the provider can supply, plus latency and any error.

Key-based providers are skipped with status "no_key" until their key is set:
    OPENWEATHERMAP_API_KEY, WEATHERAPI_KEY, VISUAL_CROSSING_KEY,
    TOMORROW_IO_KEY (or TOMORROW_IO)
Keys are read from the process environment first (Render), then the repo-root
.env file (local — never rely on process env for local values on Windows).
"""
from __future__ import annotations

import logging
import os
import socket
import time
from datetime import date, datetime, timedelta, timezone

import requests

from .helpers import REPO_ROOT

log = logging.getLogger(__name__)

TIMEOUT = 8
# NWS and Met Norway require an identifying User-Agent and 403 without one.
USER_AGENT = 'gardening-app/1.0 (gccarnovale@gmail.com)'

CONTRACT_FIELDS = ('precip_sum_daily', 'temp_max', 'temp_min',
                   'precip_prob_forecast', 'et0')

# Fallback when no garden has coordinates (Philadelphia-ish).
DEFAULT_LAT, DEFAULT_LON = 40.0, -75.2


# Alternate env-var names accepted for the same key.
_KEY_ALIASES = {'TOMORROW_IO_KEY': ('TOMORROW_IO',)}


def _get_key(name: str) -> str | None:
    names = (name,) + _KEY_ALIASES.get(name, ())
    for n in names:
        val = os.environ.get(n)
        if val:
            return val
    try:
        from dotenv import dotenv_values
        values = dotenv_values(REPO_ROOT / '.env')
        for n in names:
            if values.get(n):
                return values[n]
    except Exception:
        pass
    return None


def _result(provider: str, *, status: str, http_status: int | None = None,
            error: str | None = None, sample: dict | None = None) -> dict:
    sample = sample or {}
    return {
        'provider': provider,
        'status': status,
        'http_status': http_status,
        'latency_ms': None,  # filled in by run_all_probes
        'error': error,
        'fields': {f: sample.get(f) is not None for f in CONTRACT_FIELDS},
        'sample': sample,
    }


def _idx(lst, i=0):
    return lst[i] if lst and len(lst) > i else None


# ── Probes ────────────────────────────────────────────────────────────────────
# All take (lat, lon, key); keyless probes ignore `key`. Each returns a result
# dict or raises — run_all_probes converts exceptions to status="error".

def _probe_open_meteo_forecast(lat, lon, key=None):
    resp = requests.get('https://api.open-meteo.com/v1/forecast', params={
        'latitude': lat, 'longitude': lon,
        'daily': ('temperature_2m_max,temperature_2m_min,'
                  'precipitation_probability_max,precipitation_sum,'
                  'et0_fao_evapotranspiration'),
        'temperature_unit': 'celsius', 'precipitation_unit': 'mm',
        'forecast_days': 2, 'timezone': 'auto',
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    d = resp.json().get('daily', {})
    return _result('open-meteo-forecast', status='ok', http_status=resp.status_code, sample={
        'date': _idx(d.get('time')),
        'precip_sum_daily': _idx(d.get('precipitation_sum')),
        'temp_max': _idx(d.get('temperature_2m_max')),
        'temp_min': _idx(d.get('temperature_2m_min')),
        'precip_prob_forecast': _idx(d.get('precipitation_probability_max')),
        'et0': _idx(d.get('et0_fao_evapotranspiration')),
    })


def _probe_open_meteo_archive(lat, lon, key=None):
    # The archive host is what the nightly WeatherLog fetch uses — it can
    # rate-limit independently of the forecast host.
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=2)
    resp = requests.get('https://archive-api.open-meteo.com/v1/archive', params={
        'latitude': lat, 'longitude': lon,
        'start_date': start.isoformat(), 'end_date': end.isoformat(),
        'daily': ('precipitation_sum,temperature_2m_max,temperature_2m_min,'
                  'et0_fao_evapotranspiration'),
        'temperature_unit': 'celsius', 'precipitation_unit': 'mm',
        'timezone': 'auto',
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    d = resp.json().get('daily', {})
    return _result('open-meteo-archive', status='ok', http_status=resp.status_code, sample={
        'date': _idx(d.get('time')),
        'precip_sum_daily': _idx(d.get('precipitation_sum')),
        'temp_max': _idx(d.get('temperature_2m_max')),
        'temp_min': _idx(d.get('temperature_2m_min')),
        'precip_prob_forecast': None,  # archive is history, no probabilities
        'et0': _idx(d.get('et0_fao_evapotranspiration')),
    })


def _probe_nws(lat, lon, key=None):
    """api.weather.gov — keyless, US-only, mandatory User-Agent."""
    headers = {'User-Agent': USER_AGENT}
    r1 = requests.get(f'https://api.weather.gov/points/{lat:.4f},{lon:.4f}',
                      headers=headers, timeout=TIMEOUT)
    r1.raise_for_status()
    forecast_url = r1.json()['properties']['forecast']
    r2 = requests.get(forecast_url, headers=headers, timeout=TIMEOUT)
    r2.raise_for_status()
    periods = r2.json()['properties']['periods']
    day = next((p for p in periods if p.get('isDaytime')), None)
    night = next((p for p in periods if not p.get('isDaytime')), None)
    if day is None and night is None:
        raise ValueError('no forecast periods returned')

    def f_to_c(f):
        return round((f - 32) * 5 / 9, 1) if f is not None else None

    first = day or night
    return _result('nws', status='ok', http_status=r2.status_code, sample={
        'date': (first.get('startTime') or '')[:10],
        # Daily QPF needs the separate gridpoints endpoint; the standard
        # forecast has no precip totals and NWS has no ET0.
        'precip_sum_daily': None,
        'temp_max': f_to_c(day.get('temperature')) if day else None,
        'temp_min': f_to_c(night.get('temperature')) if night else None,
        'precip_prob_forecast': ((first.get('probabilityOfPrecipitation') or {})
                                 .get('value')),
        'et0': None,
    })


def _probe_met_norway(lat, lon, key=None):
    """api.met.no locationforecast — keyless, global, mandatory User-Agent."""
    resp = requests.get(
        'https://api.met.no/weatherapi/locationforecast/2.0/compact',
        params={'lat': round(lat, 4), 'lon': round(lon, 4)},
        headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    series = resp.json()['properties']['timeseries'][:24]  # ~first 24h, hourly
    if not series:
        raise ValueError('empty timeseries')
    temps = [s['data']['instant']['details'].get('air_temperature')
             for s in series]
    temps = [t for t in temps if t is not None]
    precip, got_precip = 0.0, False
    for s in series:
        det = (s['data'].get('next_1_hours') or {}).get('details') or {}
        if 'precipitation_amount' in det:
            precip += det['precipitation_amount']
            got_precip = True
    return _result('met-norway', status='ok', http_status=resp.status_code, sample={
        'date': series[0]['time'][:10],
        'precip_sum_daily': round(precip, 2) if got_precip else None,
        'temp_max': max(temps) if temps else None,
        'temp_min': min(temps) if temps else None,
        'precip_prob_forecast': None,  # compact variant has no probabilities
        'et0': None,
    })


def _probe_openweathermap(lat, lon, key):
    resp = requests.get('https://api.openweathermap.org/data/2.5/forecast',
                        params={'lat': lat, 'lon': lon, 'appid': key,
                                'units': 'metric'}, timeout=TIMEOUT)
    resp.raise_for_status()
    items = resp.json().get('list', [])[:8]  # 3-hourly → first 24h
    if not items:
        raise ValueError('empty forecast list')
    temps = [i.get('main', {}).get('temp') for i in items]
    temps = [t for t in temps if t is not None]
    precip = sum((i.get('rain') or {}).get('3h', 0) for i in items)
    pops = [i.get('pop') for i in items if i.get('pop') is not None]
    return _result('openweathermap', status='ok', http_status=resp.status_code, sample={
        'date': (items[0].get('dt_txt') or '')[:10],
        'precip_sum_daily': round(precip, 2),
        'temp_max': max(temps) if temps else None,
        'temp_min': min(temps) if temps else None,
        'precip_prob_forecast': round(max(pops) * 100) if pops else None,
        'et0': None,
    })


def _probe_weatherapi(lat, lon, key):
    resp = requests.get('https://api.weatherapi.com/v1/forecast.json',
                        params={'key': key, 'q': f'{lat},{lon}', 'days': 1},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    fc_day = resp.json()['forecast']['forecastday'][0]
    d = fc_day.get('day', {})
    return _result('weatherapi', status='ok', http_status=resp.status_code, sample={
        'date': fc_day.get('date'),
        'precip_sum_daily': d.get('totalprecip_mm'),
        'temp_max': d.get('maxtemp_c'),
        'temp_min': d.get('mintemp_c'),
        'precip_prob_forecast': d.get('daily_chance_of_rain'),
        'et0': None,
    })


def _probe_visual_crossing(lat, lon, key):
    resp = requests.get(
        'https://weather.visualcrossing.com/VisualCrossingWebServices'
        f'/rest/services/timeline/{lat},{lon}',
        params={'key': key, 'unitGroup': 'metric', 'include': 'days',
                'contentType': 'json'}, timeout=TIMEOUT)
    resp.raise_for_status()
    day = resp.json()['days'][0]
    return _result('visual-crossing', status='ok', http_status=resp.status_code, sample={
        'date': day.get('datetime'),
        'precip_sum_daily': day.get('precip'),
        'temp_max': day.get('tempmax'),
        'temp_min': day.get('tempmin'),
        'precip_prob_forecast': day.get('precipprob'),
        'et0': day.get('et0'),  # present on some plans only
    })


def _probe_tomorrow_io(lat, lon, key):
    resp = requests.get('https://api.tomorrow.io/v4/weather/forecast',
                        params={'location': f'{lat},{lon}', 'apikey': key,
                                'timesteps': '1d', 'units': 'metric'},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    day = resp.json()['timelines']['daily'][0]
    v = day.get('values', {})
    precip_prob = v.get('precipitationProbabilityMax',
                        v.get('precipitationProbabilityAvg'))
    return _result('tomorrow-io', status='ok', http_status=resp.status_code, sample={
        'date': (day.get('time') or '')[:10],
        'precip_sum_daily': v.get('rainAccumulationSum',
                                  v.get('rainAccumulationAvg')),
        'temp_max': v.get('temperatureMax'),
        'temp_min': v.get('temperatureMin'),
        'precip_prob_forecast': precip_prob,
        'et0': v.get('evapotranspirationSum'),  # tomorrow.io actually has ET
    })


PROBES: list[tuple[str, callable, str | None]] = [
    ('open-meteo-forecast', _probe_open_meteo_forecast, None),
    ('open-meteo-archive', _probe_open_meteo_archive, None),
    ('nws', _probe_nws, None),
    ('met-norway', _probe_met_norway, None),
    ('openweathermap', _probe_openweathermap, 'OPENWEATHERMAP_API_KEY'),
    ('weatherapi', _probe_weatherapi, 'WEATHERAPI_KEY'),
    ('visual-crossing', _probe_visual_crossing, 'VISUAL_CROSSING_KEY'),
    ('tomorrow-io', _probe_tomorrow_io, 'TOMORROW_IO_KEY'),
]


def _egress_ip() -> str | None:
    """Record the actual outbound IP — the shared-IP theory hinges on it."""
    try:
        return requests.get('https://api.ipify.org', timeout=5).text.strip()
    except Exception:
        return None


def _default_coords() -> tuple[float, float]:
    try:
        from ..db.models import Garden
        from ..db.session import SessionLocal
        db = SessionLocal()
        try:
            g = (db.query(Garden)
                 .filter(Garden.latitude.isnot(None),
                         Garden.longitude.isnot(None))
                 .first())
            if g:
                return g.latitude, g.longitude
        finally:
            db.close()
    except Exception:
        log.warning('[weather-probes] could not read garden coords, using default')
    return DEFAULT_LAT, DEFAULT_LON


def run_all_probes(lat: float | None = None, lon: float | None = None) -> dict:
    if lat is None or lon is None:
        lat, lon = _default_coords()
    results = []
    for name, fn, key_var in PROBES:
        key = _get_key(key_var) if key_var else None
        if key_var and not key:
            results.append(_result(name, status='no_key',
                                   error=f'{key_var} not set'))
            continue
        start = time.monotonic()
        try:
            res = fn(lat, lon, key)
        except requests.RequestException as e:
            http_status = getattr(getattr(e, 'response', None), 'status_code', None)
            res = _result(name, status='error', http_status=http_status,
                          error=str(e))
        except Exception as e:
            res = _result(name, status='error',
                          error=f'{type(e).__name__}: {e}')
        res['latency_ms'] = int((time.monotonic() - start) * 1000)
        log.info('[weather-probes] %s: %s (%s ms)', name, res['status'],
                 res['latency_ms'])
        results.append(res)
    return {
        'ran_from': socket.gethostname(),
        'egress_ip': _egress_ip(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'lat': lat,
        'lon': lon,
        'results': results,
    }
