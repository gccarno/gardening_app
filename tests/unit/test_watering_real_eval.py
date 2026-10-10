"""Pure-logic tests for the real-outcome watering evaluation harness."""
from datetime import date, timedelta

from ml.evaluation.watering_real_eval import (
    MIN_DATE, checkin_items, day_bootstrap_diff, prepare, score, score_checkins,
)


def _row(day_offset, watered, pred, deficit=0.0, rain=0.0, **kw):
    return {'snapshot_date': MIN_DATE + timedelta(days=day_offset),
            'watered_next_day': watered, 'model_pred_mm': pred,
            'rule_deficit_mm': deficit, 'mm_day_avg': 4.0,
            'rain_next_day_mm': rain, **kw}


def test_prepare_drops_unlabelled_and_pre_fix_rows():
    rows = [_row(0, True, 5.0),
            _row(1, None, 5.0),
            {**_row(0, True, 5.0), 'snapshot_date': date(2026, 7, 30)}]
    assert len(prepare(rows)) == 1


def test_rain_credit_flag_and_calls():
    r = prepare([_row(0, True, 5.0, deficit=20.0, rain=8.0)])[0]
    assert r['rain_credited'] is True
    assert r['calls']['model'] is True      # 5.0 mm > 1.5 mm cutoff
    assert r['calls']['rule'] is True       # big deficit -> score >= 50
    assert r['calls']['never_water'] is False


def test_rule_call_is_recomputed_not_read_from_stored_rule_score():
    # A contaminated stored rule_score of 99 must be ignored.
    r = prepare([_row(0, False, 5.0, deficit=0.0, rule_score=99)])[0]
    assert r['calls']['rule'] is False


def test_baselines_on_imbalanced_labels():
    rows = prepare([_row(i, i < 2, 0.0) for i in range(10)])  # 2 of 10 positive
    assert score(rows, 'never_water')['accuracy'] == 0.8
    assert score(rows, 'never_water')['balanced_accuracy'] == 0.5
    assert score(rows, 'always_water')['accuracy'] == 0.2


def test_bootstrap_identical_predictors_diff_is_zero():
    rows = prepare([_row(i, i % 2 == 0, 5.0, deficit=20.0) for i in range(12)])
    point, lo, hi = day_bootstrap_diff(rows, 'model', 'rule', iters=200)
    assert point == 0 and lo == 0 and hi == 0


def test_bucket_call_is_attached_to_every_row():
    r = prepare([_row(0, True, 5.0, rain_7d_mm=0.0, et0_7d_mm=35.0, days_since_watered=7,
                      kc_avg=1.0)])[0]
    assert r['calls']['bucket'] is True   # a week of 5 mm/day ET with no rain


def test_score_checkins_orders_depletion_by_reading():
    items = [{'level': 'dry', 'depletion_frac': 0.8, 'water_today': True},
             {'level': 'ok', 'depletion_frac': 0.3, 'water_today': False},
             {'level': 'wet', 'depletion_frac': 0.0, 'water_today': True}]
    s = score_checkins(items)
    assert s['agreement'] == 2 / 3
    assert s['mean_depletion_frac']['dry'] > s['mean_depletion_frac']['ok'] > s['mean_depletion_frac']['wet']


def test_checkin_replay_skips_rain_credited_waterings(db, garden, bed, plant_in_bed):
    """Rain is already in WeatherLog; a rain-credited WateringEvent must not also
    refill the bucket. A hand-watering must."""
    from apps.backend.app.db.models import SoilMoistureCheckin, WateringEvent, WeatherLog
    today = date.today()
    for i in range(1, 15):
        db.add(WeatherLog(garden_id=garden.id, date=today - timedelta(days=i),
                          rainfall_in=0.0, et0_mm=5.0, source='api'))
    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id, event_date=today - timedelta(days=1),
                         amount='light', source='rain'))
    db.add(SoilMoistureCheckin(garden_id=garden.id, bed_id=bed.id, check_date=today, level='dry'))
    db.flush()
    dry = checkin_items(db)[0]
    assert dry['depletion_frac'] > 0.5

    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id, event_date=today - timedelta(days=1),
                         amount='moderate', source='user'))
    db.flush()
    assert checkin_items(db)[0]['depletion_frac'] < dry['depletion_frac']
