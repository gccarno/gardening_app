"""
Nightly forecast archive: record what each weather provider predicts for the
next several days, so forecast accuracy can later be measured against the
observed WeatherLog rows (see WeatherForecastArchive).

Both providers are archived every night, regardless of which one currently
drives the app. That is the point: it is the only way to learn which is more
accurate for this location.
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from ..db.models import WeatherForecastArchive

logger = logging.getLogger(__name__)


def _open_meteo_days(lat: float, lon: float) -> list[dict]:
    from apps.ml_service.app.watering_engine import fetch_7day_forecast
    return [{
        'date':        d['date'],
        'precip_mm':   d.get('precip_mm'),
        'precip_prob': d.get('precip_prob'),
        'temp_max_c':  d.get('temp_max_c'),
        'temp_min_c':  d.get('temp_min_c'),
        'wind_kmh':    d.get('wind_kmh'),
        'et0_mm':      d.get('et0_mm'),
    } for d in fetch_7day_forecast(lat, lon) or []]


def _tomorrow_io_days(lat: float, lon: float) -> list[dict]:
    from . import tomorrow_io
    out = []
    for d in tomorrow_io.fetch_forecast_days(lat, lon, units='metric') or []:
        wind_ms = d.get('wind_max')  # metric wind is m/s
        out.append({
            'date':        d['date'],
            'precip_mm':   d.get('precip_sum'),
            'precip_prob': d.get('precip_prob'),
            'temp_max_c':  d.get('temp_max'),
            'temp_min_c':  d.get('temp_min'),
            'wind_kmh':    round(wind_ms * 3.6, 1) if wind_ms is not None else None,
            'et0_mm':      d.get('et0'),
        })
    return out


_PROVIDERS = {'open-meteo': _open_meteo_days, 'tomorrow-io': _tomorrow_io_days}


def archive_forecasts(db: Session, garden_id: int, lat: float, lon: float) -> int:
    """Store today's forecast from every provider. Returns rows written.

    Re-running on the same day replaces that day's rows, so the job is
    idempotent. One provider failing never blocks the other, and this never
    raises: the archive is a side channel and must not cost the nightly
    weather fetch its real job.
    """
    fetched = date.today()
    written = 0
    for provider, fetch in _PROVIDERS.items():
        try:
            days = fetch(lat, lon)
        except Exception as e:
            logger.warning('[forecast_archive] %s failed for garden %d: %s', provider, garden_id, e)
            continue
        # Skip the past: Open-Meteo's local date can lag the server's UTC date.
        days = [d for d in days if d.get('date') and date.fromisoformat(d['date']) >= fetched]
        if not days:
            continue
        try:
            db.query(WeatherForecastArchive).filter_by(
                garden_id=garden_id, fetched_date=fetched, provider=provider).delete()
            for d in days:
                target = date.fromisoformat(d['date'])
                db.add(WeatherForecastArchive(
                    garden_id=garden_id, fetched_date=fetched, target_date=target,
                    lead_days=(target - fetched).days, provider=provider,
                    precip_mm=d['precip_mm'], precip_prob=d['precip_prob'],
                    temp_max_c=d['temp_max_c'], temp_min_c=d['temp_min_c'],
                    wind_kmh=d['wind_kmh'], et0_mm=d['et0_mm'],
                ))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception('[forecast_archive] saving %s failed for garden %d', provider, garden_id)
            continue
        written += len(days)
    return written
