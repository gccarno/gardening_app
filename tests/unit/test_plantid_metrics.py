"""Unit tests for ml/evaluation/plantid_metrics.py."""
import numpy as np
import pytest

from ml.evaluation.plantid_metrics import (
    choose_threshold,
    coverage_curve,
    expected_calibration_error,
    fit_temperature,
    softmax,
    topk_accuracy,
)


def test_topk_accuracy_counts_label_within_top_k():
    scores = np.array([
        [0.9, 0.1, 0.0],   # top1 = 0
        [0.2, 0.3, 0.5],   # top1 = 2, top2 = {2, 1}
        [0.05, 0.8, 0.15],  # top1 = 1, top2 = {1, 2}
    ])
    labels = np.array([0, 1, 0])
    assert topk_accuracy(scores, labels, 1) == pytest.approx(1 / 3)
    assert topk_accuracy(scores, labels, 2) == pytest.approx(2 / 3)
    assert topk_accuracy(scores, labels, 3) == pytest.approx(1.0)


def test_softmax_rows_sum_to_one_and_temperature_sharpens():
    logits = np.array([[1.0, 2.0, 3.0]])
    p1 = softmax(logits, 1.0)
    p_sharp = softmax(logits, 0.1)
    assert p1.sum() == pytest.approx(1.0)
    assert p_sharp[0, 2] > p1[0, 2]


def test_ece_is_zero_when_confidence_matches_accuracy():
    # 10 predictions at confidence 0.7, 7 correct -> perfectly calibrated bin.
    conf = np.full(10, 0.7)
    correct = np.array([1] * 7 + [0] * 3, dtype=bool)
    assert expected_calibration_error(conf, correct, n_bins=10) == pytest.approx(0.0)


def test_ece_measures_overconfidence():
    conf = np.full(10, 0.9)
    correct = np.array([1] * 5 + [0] * 5, dtype=bool)
    assert expected_calibration_error(conf, correct, n_bins=10) == pytest.approx(0.4)


def test_fit_temperature_recovers_scale_of_overconfident_logits():
    rng = np.random.default_rng(0)
    n, k = 2000, 20
    true_logits = rng.normal(0, 1.5, size=(n, k))
    probs = softmax(true_logits, 1.0)
    labels = np.array([rng.choice(k, p=p) for p in probs])
    # Logits scaled up 4x are overconfident; the fitted T should undo it.
    t = fit_temperature(true_logits * 4.0, labels)
    assert 3.0 < t < 5.0


def test_coverage_curve_and_threshold_choice():
    conf = np.array([0.95, 0.9, 0.8, 0.6, 0.4, 0.2])
    correct = np.array([1, 1, 1, 0, 1, 0], dtype=bool)
    curve = coverage_curve(conf, correct, thresholds=[0.0, 0.5, 0.85])
    by_t = {round(r['threshold'], 2): r for r in curve}
    assert by_t[0.0]['coverage'] == pytest.approx(1.0)
    assert by_t[0.5]['coverage'] == pytest.approx(4 / 6)
    assert by_t[0.5]['selective_accuracy'] == pytest.approx(3 / 4)
    assert by_t[0.85]['selective_accuracy'] == pytest.approx(1.0)
    # Lowest threshold whose selective accuracy reaches the target.
    assert choose_threshold(conf, correct, target_accuracy=0.9) == pytest.approx(0.8)


def test_choose_threshold_returns_none_when_target_unreachable():
    conf = np.array([0.9, 0.8])
    correct = np.array([0, 0], dtype=bool)
    assert choose_threshold(conf, correct, target_accuracy=0.5) is None
