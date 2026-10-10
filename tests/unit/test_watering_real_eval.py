"""Pure-logic tests for the real-outcome watering evaluation harness."""
from datetime import date, timedelta

from ml.evaluation.watering_real_eval import (
    MIN_DATE, day_bootstrap_diff, prepare, score,
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
