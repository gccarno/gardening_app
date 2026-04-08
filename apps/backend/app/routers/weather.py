"""
Weather routes: fetch Open-Meteo forecast, fetch/store historical weather, watering status.
"""
from datetime import date, timedelta

import requests as http
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.models import Garden, WeatherLog
from ..db.session import get_db
from ..services.helpers import FROST_DATES, REPO_ROOT, WMO, get_or_404, rainfall_summary

router = APIRouter(prefix='/api', tags=['weather'])


@router.get('/gardens/{garden_id}/weather')
def api_garden_weather(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
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
        raise HTTPException(status_code=502, detail=str(e))

    data  = resp.json()
    cur   = data.get('current', {})
    daily = data.get('daily', {})
    zone_num = ''.join(filter(str.isdigit, garden.usda_zone or ''))
    frost = FROST_DATES.get(zone_num, ('unknown', 'unknown'))

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
    return {
        'current': {
            'temp':          cur.get('temperature_2m'),
            'humidity':      cur.get('relative_humidity_2m'),
            'precipitation': cur.get('precipitation'),
            'wind_speed':    cur.get('wind_speed_10m'),
            'condition':     WMO.get(cur.get('weather_code'), 'Unknown'),
        },
        'daily': days,
        'frost': {'last_spring': frost[0], 'first_fall': frost[1]},
    }


@router.post('/gardens/{garden_id}/fetch-weather')
def api_fetch_weather_history(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    if not garden.latitude or not garden.longitude:
        raise HTTPException(status_code=400, detail='no_location')

    end_date   = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=13)
    try:
        resp = http.get('https://archive-api.open-meteo.com/v1/archive', params={
            'latitude':           garden.latitude,
            'longitude':          garden.longitude,
            'start_date':         start_date.isoformat(),
            'end_date':           end_date.isoformat(),
            'daily':              'precipitation_sum,temperature_2m_max,temperature_2m_min',
            'temperature_unit':   'fahrenheit',
            'precipitation_unit': 'inch',
            'timezone':           'auto',
        }, timeout=10)
        resp.raise_for_status()
        daily = resp.json().get('daily', {})
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    created = 0
    for i, d_str in enumerate(daily.get('time', [])):
        d = date.fromisoformat(d_str)
        db.query(WeatherLog).filter_by(garden_id=garden_id, date=d).delete()
        log = WeatherLog(
            garden_id=garden_id,
            date=d,
            rainfall_in=daily['precipitation_sum'][i],
            temp_high_f=daily['temperature_2m_max'][i],
            temp_low_f=daily['temperature_2m_min'][i],
            source='api',
        )
        db.add(log)
        created += 1
    db.commit()
    return {'ok': True, 'days_saved': created,
            'rainfall_7d': rainfall_summary(db, garden_id, 7)}


@router.get('/gardens/{garden_id}/watering-status')
def api_watering_status(garden_id: int, db: Session = Depends(get_db)):
    from apps.ml_service.app.watering_engine import (
        fetch_forecast_today, get_watering_recommendations,
    )
    garden = get_or_404(db, Garden, garden_id)

    cutoff = date.today() - timedelta(days=14)
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
