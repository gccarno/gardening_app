"""
Statistics for small eval sets: confidence intervals, paired tests, and
inter-rater agreement.

Pure numpy plus the stdlib on purpose: no scipy/sklearn, so the package stays
light enough to install anywhere an eval runs.

Conventions
-----------
* Every interval is returned as ``(point, lo, hi)``.
* Degenerate agreement (every rating in one category, so chance agreement is 1)
  makes kappa/alpha undefined. Those return ``nan``, never a made-up 1.0 or 0.0;
  reports render nan as "n/a".
* Bootstraps take a ``seed`` and are exactly reproducible for a given seed.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from statistics import NormalDist

import numpy as np


def _z(conf: float) -> float:
    return NormalDist().inv_cdf(0.5 + conf / 2)


# ── Intervals ────────────────────────────────────────────────────────────────

def wilson_ci(successes: int, n: int, conf: float = 0.95) -> tuple[float, float, float]:
    """Wilson score interval for a proportion. Behaves at p=0/1 and small n,
    where the normal approximation produces intervals outside [0, 1]."""
    if n == 0:
        return (math.nan, math.nan, math.nan)
    p = successes / n
    z = _z(conf)
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(
    values: Sequence[float],
    stat: Callable[[np.ndarray], float] = np.mean,
    iters: int = 2000,
    conf: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI of ``stat`` over ``values``. NaNs are dropped."""
    x = np.asarray(values, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (math.nan, math.nan, math.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(iters, len(x)))
    boots = np.array([stat(x[i]) for i in idx])
    alpha = (1 - conf) / 2
    return (float(stat(x)), float(np.quantile(boots, alpha)), float(np.quantile(boots, 1 - alpha)))


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    iters: int = 2000,
    conf: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """CI of mean(b - a) over paired items (b = candidate, a = baseline).

    Resampling the *pairs* keeps the per-item correlation, which is what makes a
    paired comparison far tighter than comparing two independent means. Pairs
    where either side is NaN are dropped.
    """
    a_ = np.asarray(a, dtype=float)
    b_ = np.asarray(b, dtype=float)
    if a_.shape != b_.shape:
        raise ValueError(f'paired arrays differ in length: {a_.shape} vs {b_.shape}')
    keep = ~(np.isnan(a_) | np.isnan(b_))
    return bootstrap_ci(b_[keep] - a_[keep], iters=iters, conf=conf, seed=seed)


def mcnemar_exact(a: Sequence[int], b: Sequence[int]) -> tuple[int, int, float]:
    """Exact (binomial) McNemar test on paired binary outcomes.

    Returns ``(n_a_only, n_b_only, two_sided_p)`` where ``n_a_only`` counts items
    baseline passed and candidate failed. Only discordant pairs carry
    information; the exact form is right for the small counts an eval produces.
    """
    a_ = np.asarray(a, dtype=int)
    b_ = np.asarray(b, dtype=int)
    a_only = int(np.sum((a_ == 1) & (b_ == 0)))
    b_only = int(np.sum((a_ == 0) & (b_ == 1)))
    n = a_only + b_only
    if n == 0:
        return (a_only, b_only, 1.0)
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return (a_only, b_only, min(1.0, 2 * tail))


# ── Agreement ────────────────────────────────────────────────────────────────

def percent_agreement(r1: Sequence, r2: Sequence) -> float:
    pairs = [(x, y) for x, y in zip(r1, r2) if x is not None and y is not None]
    if not pairs:
        return math.nan
    return sum(x == y for x, y in pairs) / len(pairs)


def cohen_kappa(
    r1: Sequence,
    r2: Sequence,
    weights: str | None = None,
    labels: Sequence | None = None,
) -> float:
    """Cohen's kappa for two raters. ``weights`` = None, 'linear' or 'quadratic'
    (weighted forms treat ``labels`` as ordered). Items either rater skipped
    (None) are dropped."""
    pairs = [(x, y) for x, y in zip(r1, r2) if x is not None and y is not None]
    if not pairs:
        return math.nan
    cats = list(labels) if labels is not None else sorted({v for p in pairs for v in p})
    k = len(cats)
    pos = {c: i for i, c in enumerate(cats)}
    obs = np.zeros((k, k))
    for x, y in pairs:
        obs[pos[x], pos[y]] += 1
    obs /= obs.sum()
    exp = np.outer(obs.sum(axis=1), obs.sum(axis=0))
    i, j = np.indices((k, k))
    if weights is None:
        w = (i != j).astype(float)
    elif weights == 'linear':
        w = np.abs(i - j) / max(k - 1, 1)
    elif weights == 'quadratic':
        w = ((i - j) / max(k - 1, 1)) ** 2
    else:
        raise ValueError(f'unknown weights: {weights!r}')
    denom = float((w * exp).sum())
    if denom == 0:
        return math.nan
    return 1 - float((w * obs).sum()) / denom


def fleiss_kappa(table: np.ndarray | Sequence[Sequence[int]]) -> float:
    """Fleiss' kappa from an items x categories count table. Every row must sum
    to the same number of raters."""
    t = np.asarray(table, dtype=float)
    n_raters = t.sum(axis=1)
    if len(t) == 0 or not np.allclose(n_raters, n_raters[0]) or n_raters[0] < 2:
        raise ValueError('fleiss_kappa needs >= 2 ratings per item and the same count on every item')
    n = n_raters[0]
    p_i = ((t * t).sum(axis=1) - n) / (n * (n - 1))
    p_bar = p_i.mean()
    p_j = t.sum(axis=0) / t.sum()
    p_e = float((p_j ** 2).sum())
    if p_e == 1:
        return math.nan
    return float((p_bar - p_e) / (1 - p_e))


def ratings_to_table(ratings: Sequence[Sequence], labels: Sequence | None = None) -> np.ndarray:
    """items x raters ratings -> items x categories counts (for fleiss_kappa).
    Items with any missing (None) rating are dropped: Fleiss needs a fixed count."""
    rows = [r for r in ratings if all(v is not None for v in r)]
    cats = list(labels) if labels is not None else sorted({v for r in rows for v in r})
    pos = {c: i for i, c in enumerate(cats)}
    table = np.zeros((len(rows), len(cats)))
    for i, r in enumerate(rows):
        for v in r:
            table[i, pos[v]] += 1
    return table


def krippendorff_alpha(
    ratings: Sequence[Sequence],
    level: str = 'nominal',
) -> float:
    """Krippendorff's alpha over items x raters, None = missing.

    Unlike Fleiss, it tolerates missing ratings and any number of raters, and
    has ordinal/interval forms for 1-5 style scores. ``level`` is 'nominal',
    'ordinal' or 'interval' (ordinal and interval need numeric values).
    """
    units = [[v for v in r if v is not None] for r in ratings]
    units = [u for u in units if len(u) >= 2]
    if not units:
        return math.nan
    cats = sorted({v for u in units for v in u})
    k = len(cats)
    pos = {c: i for i, c in enumerate(cats)}
    o = np.zeros((k, k))
    for u in units:
        m = len(u)
        for a in range(m):
            for b in range(m):
                if a != b:
                    o[pos[u[a]], pos[u[b]]] += 1 / (m - 1)
    n_c = o.sum(axis=1)
    n = n_c.sum()

    if level == 'nominal':
        d2 = 1 - np.eye(k)
    elif level == 'interval':
        v = np.asarray(cats, dtype=float)
        d2 = (v[:, None] - v[None, :]) ** 2
    elif level == 'ordinal':
        d2 = np.zeros((k, k))
        for c in range(k):
            for kk in range(k):
                lo, hi = min(c, kk), max(c, kk)
                d2[c, kk] = (n_c[lo:hi + 1].sum() - (n_c[c] + n_c[kk]) / 2) ** 2
    else:
        raise ValueError(f'unknown level: {level!r}')

    d_o = (o * d2).sum() / n
    d_e = (np.outer(n_c, n_c) * d2).sum() / (n * (n - 1))
    if d_e == 0:
        return math.nan
    return float(1 - d_o / d_e)


def bootstrap_agreement_ci(
    ratings: Sequence[Sequence],
    fn: Callable[[list], float],
    iters: int = 1000,
    conf: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Bootstrap CI for any agreement statistic, resampling *items* (rows).
    ``fn`` takes an items x raters list. Resamples where ``fn`` is undefined
    (nan) are skipped."""
    rows = list(ratings)
    if not rows:
        return (math.nan, math.nan, math.nan)
    point = fn(rows)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(iters):
        idx = rng.integers(0, len(rows), size=len(rows))
        try:
            v = fn([rows[i] for i in idx])
        except ValueError:
            continue
        if not math.isnan(v):
            boots.append(v)
    if not boots:
        return (point, math.nan, math.nan)
    alpha = (1 - conf) / 2
    return (point, float(np.quantile(boots, alpha)), float(np.quantile(boots, 1 - alpha)))
