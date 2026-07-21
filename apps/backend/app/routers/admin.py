"""
Admin utility endpoints.

The job endpoints (run-weather-fetch, run-backup) exist so an external cron
(GitHub Actions — .github/workflows/scheduled-jobs.yaml) can trigger the
nightly work when the app runs on a free-tier host that spins down when idle
(the request itself wakes the host and the Neon database). They are guarded
by a shared secret: set the JOB_TOKEN env var on the server and send it as an
X-Job-Token header. When JOB_TOKEN is unset (local dev), the check is skipped.
"""
import logging
import os
import secrets

from fastapi import APIRouter, Header, HTTPException

from ..jobs.gcs_restore import run_restore
from .weather import run_daily_weather_fetch

log = logging.getLogger(__name__)

router = APIRouter(prefix='/api/admin', tags=['admin'])


def _check_job_token(x_job_token: str | None) -> None:
    expected = os.environ.get('JOB_TOKEN')
    if not expected:
        return  # local dev — no token configured
    if not x_job_token or not secrets.compare_digest(x_job_token, expected):
        raise HTTPException(status_code=401, detail='invalid job token')


@router.post('/run-weather-fetch')
def run_weather_fetch(x_job_token: str | None = Header(default=None)):
    """Fetch historical weather for all gardens (normally a 2 AM cron job)."""
    _check_job_token(x_job_token)
    log.info('[admin] run-weather-fetch triggered')
    run_daily_weather_fetch()
    return {'ok': True}


@router.post('/run-ml-snapshot')
def run_ml_snapshot_endpoint(x_job_token: str | None = Header(default=None)):
    """Backfill watering-model training labels, snapshot today's features,
    and prune WeatherLog/WateringEvent to 7 days (normally right after the
    weather fetch, part of the 2 AM cron)."""
    _check_job_token(x_job_token)
    from ..jobs.ml_snapshot import run_ml_snapshot
    log.info('[admin] run-ml-snapshot triggered')
    return run_ml_snapshot()


@router.post('/run-backup')
def run_backup_endpoint(x_job_token: str | None = Header(default=None)):
    """Run the nightly backup job (normally a 3 AM cron job)."""
    _check_job_token(x_job_token)
    from ..jobs.gcs_backup import run_backup
    log.info('[admin] run-backup triggered')
    run_backup()
    return {'ok': True}


@router.post('/test-weather-providers')
def test_weather_providers(lat: float | None = None, lon: float | None = None,
                           x_job_token: str | None = Header(default=None)):
    """
    Probe alternative weather APIs from this host's egress IP and report
    status/latency/available fields per provider. Driven remotely by
    scripts/test_weather_providers.py to test from Render's shared IPs.
    """
    _check_job_token(x_job_token)
    from ..services.weather_probes import run_all_probes
    log.info('[admin] test-weather-providers triggered (lat=%s lon=%s)', lat, lon)
    return run_all_probes(lat, lon)


@router.post('/restore-from-gcs')
def restore_from_gcs(dry_run: bool = False,
                     x_job_token: str | None = Header(default=None)):
    """
    Download latest.db.gz from GCS and hot-swap the local SQLite database.

    After os.replace(), new SQLAlchemy connections open the restored file.
    For heavy write traffic, stop the backend first and use the CLI script.

    Query param: ?dry_run=true to preview without replacing.
    """
    _check_job_token(x_job_token)
    log.info('[admin] restore-from-gcs requested (dry_run=%s)', dry_run)
    return run_restore(dry_run=dry_run)
