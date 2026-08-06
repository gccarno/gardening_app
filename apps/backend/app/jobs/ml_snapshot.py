"""
Nightly ML snapshot job for the watering-model flywheel.

Three steps, run in this order (see admin.run_ml_snapshot and
ml/docs/WATERING_MODEL.md, step 3):
  1. Backfill labels for snapshots whose "next day" has fully elapsed and
     been recorded — did each bed get watered, and how much rain fell? That
     is D-2 and older, not yesterday; see _backfill_labels.
  2. Compute today's feature snapshot per bed: the features the watering
     model sees, plus what the rule engine (and, once trained, the model)
     currently recommend.
  3. Prune WeatherLog / WateringEvent rows older than 7 days.

Order matters: label backfill and the new snapshot both read from
WeatherLog/WateringEvent, so pruning has to happen last.  MlWateringSnapshot
itself is never pruned — it's the accumulating training/monitoring store.

This job must also run *after* the nightly weather fetch, which is what
writes yesterday's WeatherLog row and credits rain-as-watering events — both
of which step 1 reads.
"""
import logging
from datetime import date, timedelta

from sentry_sdk.crons import monitor
from sqlalchemy.orm import Session

from ..db.models import Garden, MlWateringSnapshot, WateringEvent, WeatherLog
from ..db.session import SessionLocal

log = logging.getLogger(__name__)

_RETENTION_DAYS = 7


def _backfill_labels(db: Session, garden_id: int) -> int:
    """Label snapshots whose "next day" has fully elapsed *and* been recorded.

    The window starts at D-2, not D-1. A snapshot taken on day D asks "was this
    bed watered on D+1, and did it rain?" — neither is knowable while D+1 is
    still running. This job fires around 04:00 local, so labelling yesterday's
    snapshot meant asking whether the gardener had watered in the four hours
    since midnight (answer: never) and reading a WeatherLog row for today that
    by design is never written (weather.py skips today as a partial day). Both
    labels were therefore constant: 66 rows, 0 positives, every rain figure
    0.0mm — including across 2.03in of rain on 2026-08-02.

    Labels every still-unlabelled snapshot back to the retention edge rather
    than exactly D-2, so a missed night is recoverable instead of leaving a
    permanent null (2026-08-01 is one).
    """
    today = date.today()
    newest = today - timedelta(days=2)                    # its next day (D-1) is complete
    oldest = today - timedelta(days=_RETENTION_DAYS)      # older source rows are pruned
    snapshots = (db.query(MlWateringSnapshot)
                 .filter(MlWateringSnapshot.garden_id == garden_id,
                         MlWateringSnapshot.snapshot_date <= newest,
                         MlWateringSnapshot.snapshot_date >= oldest,
                         MlWateringSnapshot.watered_next_day.is_(None))
                 .all())
    if not snapshots:
        return 0

    rain_by_date = {lg.date: (lg.rainfall_in or 0) * 25.4 for lg in
                    db.query(WeatherLog).filter(WeatherLog.garden_id == garden_id,
                                                WeatherLog.date >= oldest).all()}
    events_by_bed_date = {}
    for ev in (db.query(WateringEvent)
               .filter(WateringEvent.garden_id == garden_id,
                       WateringEvent.event_date >= oldest)
               .all()):
        if ev.bed_id:
            events_by_bed_date.setdefault((ev.bed_id, ev.event_date), ev)

    for snap in snapshots:
        outcome_date = snap.snapshot_date + timedelta(days=1)
        ev = events_by_bed_date.get((snap.bed_id, outcome_date))
        snap.watered_next_day = ev is not None
        snap.watered_amount = ev.amount if ev else None
        snap.rain_next_day_mm = rain_by_date.get(outcome_date, 0.0)
    return len(snapshots)


def _predict_mm(feature_row: dict) -> tuple[float | None, bool]:
    try:
        from apps.ml_service.app.watering_model import predict_water_mm
    except Exception:
        return None, False
    try:
        pred = predict_water_mm(feature_row)
    except Exception:
        log.exception('[ml_snapshot] model prediction failed')
        return None, False
    return pred, pred is not None


def _snapshot_garden(db: Session, garden: Garden) -> int:
    from apps.ml_service.app.watering_engine import fetch_forecast_window, get_watering_recommendations

    cutoff = date.today() - timedelta(days=_RETENTION_DAYS)
    weather_logs = (db.query(WeatherLog)
                    .filter(WeatherLog.garden_id == garden.id, WeatherLog.date >= cutoff)
                    .all())

    forecast_today, precip_d1_d2 = None, None
    if garden.latitude and garden.longitude:
        forecast_today, precip_d1_d2 = fetch_forecast_window(garden.latitude, garden.longitude)

    recs_by_bed = {r['bed_id']: r for r in
                   get_watering_recommendations(garden, weather_logs, forecast_today, precip_d1_d2)}
    rain_7d_mm = sum((lg.rainfall_in or 0) * 25.4 for lg in weather_logs)
    et0_vals = [lg.et0_mm for lg in weather_logs if lg.et0_mm is not None]
    et0_7d_mm = round(sum(et0_vals), 1) if et0_vals else None
    latest_log = max(weather_logs, key=lambda lg: lg.date, default=None)

    today = date.today()
    saved = 0
    for bed in garden.beds:
        rec = recs_by_bed.get(bed.id)
        if rec is None:
            continue  # bed has no plants — nothing to score

        plants_in_bed = [bp.plant for bp in bed.bed_plants if bp.plant]
        maturity = [(today - p.planted_date).days for p in plants_in_bed if p.planted_date]
        stages = [bp.stage or 'seedling' for bp in bed.bed_plants if bp.plant]
        seedling_frac = (sum(1 for s in stages if s == 'seedling') / len(stages)) if stages else None
        area_m2 = (bed.width_ft or 0) * (bed.height_ft or 0) * 0.0929

        feature_row = {
            'rain_7d_mm':               round(rain_7d_mm, 1),
            'et0_7d_mm':                et0_7d_mm,
            'temp_high_f':              latest_log.temp_high_f if latest_log else None,
            'temp_low_f':               latest_log.temp_low_f if latest_log else None,
            'humidity_pct':             latest_log.humidity_pct if latest_log else None,
            'forecast_precip_mm_d0':    (forecast_today or {}).get('precip_mm'),
            'forecast_precip_prob_d0':  (forecast_today or {}).get('precip_prob'),
            'forecast_precip_mm_d1_d2': precip_d1_d2,
            'forecast_temp_max_c':      (forecast_today or {}).get('temp_max_c'),
            'days_since_watered':       rec['days_since_watered'],
            'maturity_days':            round(sum(maturity) / len(maturity)) if maturity else None,
            'seedling_frac':            seedling_frac,
            'kc_avg':                   rec['kc'],
            'mm_day_avg':               rec['mm_day'],
            'sand_pct':                 bed.sand_pct,
            'clay_pct':                 bed.clay_pct,
            'bed_area_m2':              round(area_m2, 2),
        }
        model_pred_mm, model_used = _predict_mm(feature_row)

        existing = db.query(MlWateringSnapshot).filter_by(
            garden_id=garden.id, bed_id=bed.id, snapshot_date=today).first()
        if existing:
            db.delete(existing)
            db.flush()

        db.add(MlWateringSnapshot(
            garden_id=garden.id, bed_id=bed.id, snapshot_date=today,
            rule_deficit_mm=rec['deficit_mm'], rule_score=rec['urgency_score'],
            model_pred_mm=model_pred_mm, model_used=model_used,
            **feature_row,
        ))
        saved += 1
    return saved


def _prune_operational_tables(db: Session) -> None:
    cutoff = date.today() - timedelta(days=_RETENTION_DAYS)
    db.query(WeatherLog).filter(WeatherLog.date < cutoff).delete(synchronize_session=False)
    db.query(WateringEvent).filter(WateringEvent.event_date < cutoff).delete(synchronize_session=False)


@monitor(
    monitor_slug='nightly-ml-snapshot',
    # Schedule mirrors .github/workflows/scheduled-jobs.yaml. This job feeds the
    # watering-model flywheel, so a silent stop means training data quietly
    # stops accruing — exactly the failure MISSED detection exists to catch.
    monitor_config={
        'schedule': {'type': 'crontab', 'value': '0 7 * * *'},
        'timezone': 'UTC',
        # 5h, not 30m: absorbs GitHub Actions cron drift (see weather.py).
        'checkin_margin': 300,
        'max_runtime': 10,        # DB-only work, no external calls
        'failure_issue_threshold': 1,
        'recovery_threshold': 1,
    },
)
def run_ml_snapshot() -> dict:
    """APScheduler/admin job: backfill labels, snapshot today, prune. Order matters."""
    db = SessionLocal()
    try:
        gardens = db.query(Garden).filter(
            Garden.latitude.isnot(None), Garden.longitude.isnot(None),
        ).all()

        backfilled = 0
        for g in gardens:
            try:
                backfilled += _backfill_labels(db, g.id)
            except Exception:
                log.exception('[ml_snapshot] label backfill failed for garden %d', g.id)
        db.commit()

        snapshotted = 0
        for g in gardens:
            try:
                snapshotted += _snapshot_garden(db, g)
            except Exception:
                log.exception('[ml_snapshot] snapshot failed for garden %d', g.id)
        db.commit()

        _prune_operational_tables(db)
        db.commit()

        log.info('[ml_snapshot] backfilled=%d snapshotted=%d gardens=%d',
                 backfilled, snapshotted, len(gardens))
        return {'backfilled': backfilled, 'snapshotted': snapshotted, 'gardens': len(gardens)}
    finally:
        db.close()
