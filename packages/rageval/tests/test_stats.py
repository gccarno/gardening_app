"""Stats against published worked examples / reference implementations."""
import math

import numpy as np
import pytest
from rageval import stats


def test_wilson_reference_value():
    p, lo, hi = stats.wilson_ci(5, 10)
    assert p == 0.5
    assert lo == pytest.approx(0.2366, abs=1e-4)
    assert hi == pytest.approx(0.7634, abs=1e-4)


def test_wilson_stays_in_unit_interval_at_extremes():
    _, lo, hi = stats.wilson_ci(0, 8)
    assert lo == 0.0 and 0 < hi < 1
    _, lo, hi = stats.wilson_ci(8, 8)
    assert 0 < lo < 1 and hi == 1.0


def test_bootstrap_reproducible_and_contains_mean():
    x = np.random.default_rng(1).normal(0.7, 0.2, 60)
    a = stats.bootstrap_ci(x, seed=42)
    b = stats.bootstrap_ci(x, seed=42)
    assert a == b
    assert a[1] < a[0] < a[2]


def test_paired_bootstrap_detects_consistent_drop():
    base = np.ones(40)
    cand = base.copy()
    cand[:12] = 0     # candidate fails 12 of 40 items baseline passed
    d, lo, hi = stats.paired_bootstrap_diff(base, cand, seed=0)
    assert d == pytest.approx(-0.3)
    assert hi < 0


def test_paired_bootstrap_rejects_length_mismatch():
    with pytest.raises(ValueError):
        stats.paired_bootstrap_diff([1, 0], [1])


def test_mcnemar_exact():
    a = [1] * 10 + [0] * 2 + [1] * 5
    b = [0] * 10 + [1] * 2 + [1] * 5
    a_only, b_only, p = stats.mcnemar_exact(a, b)
    assert (a_only, b_only) == (10, 2)
    assert p == pytest.approx(158 / 4096)


def test_mcnemar_no_discordant_pairs():
    assert stats.mcnemar_exact([1, 0], [1, 0]) == (0, 0, 1.0)


def test_cohen_kappa_wikipedia_example():
    # 50 items: yes/yes 20, A-yes/B-no 5, A-no/B-yes 10, no/no 15 -> kappa 0.4
    r1 = ['y'] * 20 + ['y'] * 5 + ['n'] * 10 + ['n'] * 15
    r2 = ['y'] * 20 + ['n'] * 5 + ['y'] * 10 + ['n'] * 15
    assert stats.cohen_kappa(r1, r2) == pytest.approx(0.4)


def test_cohen_kappa_weighted_matches_sklearn():
    a = [1, 2, 3, 4, 5, 3, 2, 1, 4, 5, 3, 3]
    b = [1, 2, 4, 4, 5, 2, 2, 1, 3, 5, 3, 4]
    assert stats.cohen_kappa(a, b) == pytest.approx(0.5862068965517241)
    assert stats.cohen_kappa(a, b, weights='linear') == pytest.approx(0.7777777777777778)
    assert stats.cohen_kappa(a, b, weights='quadratic') == pytest.approx(0.9047619047619048)


def test_cohen_kappa_degenerate_is_nan():
    assert math.isnan(stats.cohen_kappa(['y'] * 5, ['y'] * 5))


def test_cohen_kappa_drops_missing():
    assert stats.cohen_kappa(['y', 'n', None], ['y', 'n', 'y']) == pytest.approx(1.0)


FLEISS_WIKI = [
    [0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0],
    [2, 2, 8, 1, 1], [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2],
    [6, 5, 2, 1, 0], [0, 2, 2, 3, 7],
]


def test_fleiss_kappa_wikipedia_example():
    assert stats.fleiss_kappa(FLEISS_WIKI) == pytest.approx(0.210, abs=5e-4)


def test_fleiss_kappa_rejects_uneven_rows():
    with pytest.raises(ValueError):
        stats.fleiss_kappa([[2, 1], [1, 1]])


def test_ratings_to_table_and_fleiss_two_raters_binary():
    ratings = [['y', 'y'], ['n', 'n'], ['y', 'n'], ['y', 'y'], [None, 'y']]
    table = stats.ratings_to_table(ratings)
    assert table.shape == (4, 2)
    assert not math.isnan(stats.fleiss_kappa(table))


# Krippendorff (2011) "Computing Krippendorff's alpha-reliability", 4 coders x 12 units
_K = [
    [1, 1, None, 1], [2, 2, 3, 2], [3, 3, 3, 3], [3, 3, 3, 3], [2, 2, 2, 2],
    [1, 2, 3, 4], [4, 4, 4, 4], [1, 1, 2, 1], [2, 2, 2, 2], [None, 5, 5, 5],
    [None, None, 1, 1], [None, 3, None, None],
]


@pytest.mark.parametrize('level,expected', [
    ('nominal', 0.743), ('ordinal', 0.815), ('interval', 0.849),
])
def test_krippendorff_reference_values(level, expected):
    assert stats.krippendorff_alpha(_K, level=level) == pytest.approx(expected, abs=1e-3)


def test_bootstrap_agreement_ci_brackets_point():
    rng = np.random.default_rng(0)
    truth = rng.integers(0, 2, 80)
    r2 = np.where(rng.random(80) < 0.85, truth, 1 - truth)
    rows = list(zip(truth.tolist(), r2.tolist()))
    point, lo, hi = stats.bootstrap_agreement_ci(
        rows, lambda rs: stats.cohen_kappa([a for a, _ in rs], [b for _, b in rs]), seed=3)
    assert lo < point < hi
