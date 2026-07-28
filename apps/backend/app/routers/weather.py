"""
Weather routes: fetch Open-Meteo forecast, fetch/store historical weather, watering status.
"""
import logging
import time
from datetime import date, timedelta
from typing import Optional

import requests as http
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sentry_sdk.crons import monitor
from sqlalchemy.orm import Session

from ..db.models import Garden, User, WeatherLog
from ..db.session import SessionLocal, get_db
from ..services.auth import get_current_user, require_garden
from ..services.helpers import FROST_DATES, REPO_ROOT, WMO, get_or_404, rainfall_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api', tags=['weather'])

_weather_cache: dict[int, tuple[float, dict]] = {}  # garden_id -> (timestamp, data)
_WEATHER_CACHE_TTL = 600  # 10 minutes


def _frost_info(garden: Garden) -> dict:
    # Use real frost dates from DB if available; fall back to static zone lookup.
    if garden.last_frost_date or garden.first_frost_date:
        last_spring = garden.last_frost_date.strftime('%b %d') if garden.last_frost_date else 'unknown'
        first_fall  = garden.first_frost_date.strftime('%b %d') if garden.first_frost_date else 'unknown'
    else:
        zone_num = ''.join(filter(str.isdigit, garden.usda_zone or ''))
        last_spring, first_fall = FROST_DATES.get(zone_num, ('unknown', 'unknown'))
    return {
        'last_spring':  last_spring,
        'first_fall':   first_fall,
        'frost_free':   garden.frost_free,
        'station_name': garden.frost_station_name,
        'station_distance_km': garden.frost_station_distance_km,
    }


def _tomorrow_io_weather(garden: Garden) -> Optional[dict]:
    """Build the weather-card payload from Tomorrow.io when Open-Meteo fails."""
    from ..services import tomorrow_io
    if not tomorrow_io.get_key():
        return None
    try:
        days_raw = tomorrow_io.fetch_forecast_days(
            garden.latitude, garden.longitude, units='imperial')
        current = tomorrow_io.fetch_realtime(
            garden.latitude, garden.longitude, units='imperial')
    except Exception as e:
        logger.warning('[weather] tomorrow.io fallback failed for garden %d: %s',
                       garden.id, e)
        return None
    return {
        'current': {
            'temp':          current['temp'],
            'humidity':      current['humidity'],
            'precipitation': current['precipitation'],
            'wind_speed':    current['wind_speed'],
            'condition':     current['condition'],
        },
        'daily': [{
            'date':        d['date'],
            'high':        d['temp_max'],
            'low':         d['temp_min'],
            'precip_prob': d['precip_prob'],
            'uv':          d['uv'],
            'condition':   d['condition'],
        } for d in days_raw],
        'frost': _frost_info(garden),
        'source': 'tomorrow.io',
    }


@router.get('/gardens/{garden_id}/weather')
def api_garden_weather(garden_id: int,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    garden = require_garden(db, user, garden_id, 'viewer')
    cached = _weather_cache.get(garden_id)
    if cached and time.time() - cached[0] < _WEATHER_CACHE_TTL:
        return cached[1]
    if not garden.latitude or not garden.longitude:
        raise HTTPException(status_code=404, detail='no_location')
    try:
        resp = http.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude':  garden.latitude,
            'longitude': garden.longitude,
            'current':   'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m',
            'daily':     'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,uv_index_max',
            'temperature_unit': 'fahrenheit',
            'wind_speed_unit':  'mph',
            'precipitation_unit': 'inch',
            'forecast_days': 7,
            'timezone': 'auto',
        }, timeout=8)
        resp.raise_for_status()
    except http.exceptions.RequestException as e:
        logger.warning('[weather] open-meteo forecast failed for garden %d: %s',
                       garden_id, e)
        if cached:  # serve stale data rather than an error
            return cached[1]
        result = _tomorrow_io_weather(garden)
        if result is None:
            raise HTTPException(status_code=502, detail=str(e))
        _weather_cache[garden_id] = (time.time(), result)
        return result

    data  = resp.json()
    cur   = data.get('current', {})
    daily = data.get('daily', {})

    days = []
    for i, d in enumerate(daily.get('time', [])):
        days.append({
            'date':        d,
            'high':        daily['temperature_2m_max'][i],
            'low':         daily['temperature_2m_min'][i],
            'precip_prob': daily['precipitation_probability_max'][i],
            'uv':          daily.get('uv_index_max', [None] * 7)[i],
            'condition':   WMO.get(daily['weather_code'][i], 'Unknown'),
        })
    result = {
        'current': {
            'temp':          cur.get('temperature_2m'),
            'humidity':      cur.get('relative_humidity_2m'),
            'precipitation': cur.get('precipitation'),
            'wind_speed':    cur.get('wind_speed_10m'),
            'condition':     WMO.get(cur.get('weather_code'), 'Unknown'),
        },
        'daily': days,
        'frost': _frost_info(garden),
        'source': 'open-meteo',
    }
    _weather_cache[garden_id] = (time.time(), result)
    return result


def _fetch_weather_for_garden(db: Session, garden_id: int) -> int:
    """Fetch the last 7 days of historical weather for one garden. Returns
    number of days saved.

    Tomorrow.io's recent-history endpoint is the primary source: it gives
    per-garden *observed* rainfall automatically, which is what feeds
    WeatherLog instead of asking the gardener to log rain by hand. The
    Open-Meteo archive (7-day window) is the fallback when Tomorrow.io has
    no key configured or its call fails.
    """
    garden = db.get(Garden, garden_id)
    if not garden or not garden.latitude or not garden.longitude:
        return 0

    rows = _tomorrow_io_history_rows(garden)
    if rows is None:
        end_date   = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=6)
        try:
            resp = http.get('https://archive-api.open-meteo.com/v1/archive', params={
                'latitude':           garden.latitude,
                'longitude':          garden.longitude,
                'start_date':         start_date.isoformat(),
                'end_date':           end_date.isoformat(),
                'daily':              ('precipitation_sum,temperature_2m_max,temperature_2m_min,'
                                       'relative_humidity_2m_mean,et0_fao_evapotranspiration'),
                'temperature_unit':   'fahrenheit',
                'precipitation_unit': 'inch',
                'timezone':           'auto',
            }, timeout=10)
            resp.raise_for_status()
            daily = resp.json().get('daily', {})
            times = daily.get('time', [])
            humidity = daily.get('relative_humidity_2m_mean', [None] * len(times))
            et0      = daily.get('et0_fao_evapotranspiration', [None] * len(times))
            rows = [(date.fromisoformat(d_str),
                     daily['precipitation_sum'][i],
                     daily['temperature_2m_max'][i],
                     daily['temperature_2m_min'][i],
                     humidity[i],
                     et0[i])
                    for i, d_str in enumerate(times)]
        except http.exceptions.RequestException as e:
            logger.warning('[weather] open-meteo archive failed for garden %d '
                           '(tomorrow.io also unavailable): %s', garden_id, e)
            raise

    created = 0
    for d, rainfall, hi, lo, hum, et0_val in rows:
        db.query(WeatherLog).filter_by(garden_id=garden_id, date=d).delete()
        db.add(WeatherLog(
            garden_id=garden_id,
            date=d,
            rainfall_in=rainfall,
            temp_high_f=hi,
            temp_low_f=lo,
            humidity_pct=hum,
            et0_mm=et0_val,
            source='api',
        ))
        created += 1
    db.commit()
    return created


def _tomorrow_io_history_rows(garden: Garden) -> Optional[list]:
    """Yesterday-only backfill from Tomorrow.io recent history (past ~24h).

    Can't match the archive's 7-day window in one call, but run nightly it
    keeps WeatherLog fresh — and is the primary rainfall source (see
    _fetch_weather_for_garden). Fetched in metric units so humidity/ET0 are
    natively %/mm; temp and rainfall are converted to the existing F/inch
    WeatherLog columns.

    Returns list of (date, rainfall_in, temp_high_f, temp_low_f, humidity_pct, et0_mm).
    """
    from ..services import tomorrow_io
    if not tomorrow_io.get_key():
        return None
    try:
        days = tomorrow_io.fetch_history_days(
            garden.latitude, garden.longitude, units='metric')
    except Exception as e:
        logger.warning('[weather] tomorrow.io history failed for garden %d: %s',
                       garden.id, e)
        return None
    rows = []
    for d in days or []:
        day = date.fromisoformat(d['date'])
        if day >= date.today():  # today is a partial day — don't log it
            continue
        precip_mm = d['precip_sum']
        rainfall_in = round(precip_mm / 25.4, 3) if precip_mm is not None else None
        temp_max_f  = round(d['temp_max'] * 9 / 5 + 32, 1) if d['temp_max'] is not None else None
        temp_min_f  = round(d['temp_min'] * 9 / 5 + 32, 1) if d['temp_min'] is not None else None
        rows.append((day, rainfall_in, temp_max_f, temp_min_f, d.get('humidity'), d.get('et0')))
    return rows or None


@monitor(
    monitor_slug='nightly-weather-fetch',
    # Schedule mirrors .github/workflows/scheduled-jobs.yaml, which is what
    # actually triggers this in production (ENABLE_SCHEDULER=0 there, so the
    # APScheduler entry in main.py never fires on the free tier).
    # monitor_config is required — without it Sentry never creates the monitor,
    # and a monitor that doesn't exist can't report MISSED.
    monitor_config={
        'schedule': {'type': 'crontab', 'value': '0 7 * * *'},
        'timezone': 'UTC',
        # Must absorb GitHub Actions cron drift, which is what actually fires
        # this. Scheduled workflows queue behind on-demand jobs and have never
        # started at 07:00: over 12 consecutive days the real start ranged from
        # 08:53 to 10:49 UTC. A 30-minute margin therefore reported MISSED every
        # night on jobs that had run fine, then auto-resolved on the late
        # check-in. 5 hours clears the observed worst case (3h49m) and still
        # opens an issue long before the next night's run.
        'checkin_margin': 300,
        # Longest of the three — one external forecast call per garden.
        'max_runtime': 15,
        'failure_issue_threshold': 1,
        'recovery_threshold': 1,
    },
)
def run_daily_weather_fetch():
    """APScheduler job: fetch weather for every garden that has coordinates."""
    db = SessionLocal()
    try:
        gardens = db.query(Garden).filter(
            Garden.latitude.isnot(None),
            Garden.longitude.isnot(None),
        ).all()
        # Capture id/name up front: after a failed commit the session enters a
        # pending-rollback state, and touching a live ORM object in the except
        # block would itself raise (PendingRollbackError) and escape as a 500.
        targets = [(g.id, g.name) for g in gardens]
        for gid, gname in targets:
            try:
                saved = _fetch_weather_for_garden(db, gid)
                logger.info('[weather] garden %d (%s): %d days saved', gid, gname, saved)
            except Exception:
                db.rollback()
                logger.exception('[weather] garden %d (%s) fetch failed', gid, gname)
    finally:
        db.close()


@router.post('/gardens/{garden_id}/fetch-weather')
def api_fetch_weather_history(garden_id: int,
                              user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    garden = require_garden(db, user, garden_id, 'editor')
    if not garden.latitude or not garden.longitude:
        raise HTTPException(status_code=400, detail='no_location')

    try:
        days_saved = _fetch_weather_for_garden(db, garden_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {'ok': True, 'days_saved': days_saved,
            'rainfall_7d': rainfall_summary(db, garden_id, 7)}


class RainLogBody(BaseModel):
    rainfall_in: float
    entry_date: Optional[str] = None  # YYYY-MM-DD; defaults to today


@router.post('/gardens/{garden_id}/log-rain')
def api_log_rain(garden_id: int, body: RainLogBody,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    require_garden(db, user, garden_id, 'editor')
    log_date = date.fromisoformat(body.entry_date) if body.entry_date else date.today()
    rainfall = max(0.0, min(20.0, body.rainfall_in))

    existing = db.query(WeatherLog).filter_by(garden_id=garden_id, date=log_date).first()
    if existing:
        existing.rainfall_in = rainfall
        existing.source = 'manual'
    else:
        db.add(WeatherLog(garden_id=garden_id, date=log_date, rainfall_in=rainfall, source='manual'))
    db.commit()
    return {'ok': True, 'date': log_date.isoformat(), 'rainfall_in': rainfall}


@router.get('/gardens/{garden_id}/rain-log')
def api_get_rain_log(garden_id: int, days: int = 7,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    require_garden(db, user, garden_id, 'viewer')
    cutoff = date.today() - timedelta(days=days)
    logs = (db.query(WeatherLog)
            .filter(WeatherLog.garden_id == garden_id, WeatherLog.date >= cutoff)
            .order_by(WeatherLog.date.desc())
            .all())
    return [{'date': l.date.isoformat(), 'rainfall_in': l.rainfall_in, 'source': l.source}
            for l in logs]


@router.get('/gardens/{garden_id}/watering-status')
def api_watering_status(garden_id: int,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    from apps.ml_service.app.watering_engine import (
        fetch_forecast_today, get_watering_recommendations,
    )
    garden = require_garden(db, user, garden_id, 'viewer')

    cutoff = date.today() - timedelta(days=7)
    weather_logs = (db.query(WeatherLog)
                    .filter(WeatherLog.garden_id == garden_id,
                            WeatherLog.date >= cutoff)
                    .all())

    forecast_today = None
    if garden.latitude and garden.longitude:
        forecast_today = fetch_forecast_today(garden.latitude, garden.longitude)

    beds = get_watering_recommendations(garden, weather_logs, forecast_today)
    return {
        'garden_id':        garden_id,
        'date':             date.today().isoformat(),
        'has_weather_data': len(weather_logs) > 0,
        'forecast_today':   forecast_today,
        'beds':             beds,
    }
