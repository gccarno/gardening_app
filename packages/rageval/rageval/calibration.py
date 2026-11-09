"""
Judge calibration against human labels.

For each (judge, criterion) — plus the panel majority — compares the judge's
verdicts with yours on the same answers and reports:

* confusion matrix with the human as ground truth, sensitivity (TPR),
  specificity (TNR), precision, accuracy
* Cohen's kappa with a bootstrap CI (agreement beyond chance)
* pass-rate bias: judge pass rate minus human pass rate on the same items
* ``trusted``: kappa >= threshold on >= min_n labelled items. Only trusted
  criteria may gate a regression.

And ``corrected_pass_rate`` (Rogan-Gladen): a judge with known sensitivity and
specificity over- or under-counts passes in a predictable way, so the true pass
rate can be backed out of the observed one, with a CI that carries the
uncertainty of both the run and the calibration sample.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from rageval import stats
from rageval.judges import (
    JudgeCache,
    judge_records,
    panel_config_hash,
    panel_verdicts,
    rubric_hash,
    verdict_table,
)
from rageval.schema import HumanLabel, RunRecord, from_dict, read_jsonl

PANEL = 'panel'


def confusion(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs = [(human, judge)]; positive = pass."""
    tp = sum(1 for h, j in pairs if h and j)
    fn = sum(1 for h, j in pairs if h and not j)
    fp = sum(1 for h, j in pairs if not h and j)
    tn = sum(1 for h, j in pairs if not h and not j)
    n = len(pairs)

    def ratio(a, b):
        return a / b if b else math.nan

    return {
        'n': n, 'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
        'sensitivity': ratio(tp, tp + fn),
        'specificity': ratio(tn, tn + fp),
        'precision': ratio(tp, tp + fp),
        'accuracy': ratio(tp + tn, n),
        'human_pass_rate': ratio(tp + fn, n),
        'judge_pass_rate': ratio(tp + fp, n),
        'bias': ratio(fp - fn, n),
    }


def judge_vs_human(pairs: list[tuple[bool, bool]], trust_kappa: float = 0.6, min_n: int = 20,
                   seed: int = 0) -> dict:
    out = confusion(pairs)
    if pairs:
        k, lo, hi = stats.bootstrap_agreement_ci(
            pairs, lambda rs: stats.cohen_kappa([h for h, _ in rs], [j for _, j in rs],
                                                labels=[False, True]), seed=seed)
    else:
        k = lo = hi = math.nan
    out.update(kappa=k, kappa_lo=lo, kappa_hi=hi)
    out['trusted'] = bool(len(pairs) >= min_n and not math.isnan(k) and k >= trust_kappa)
    return out


def rogan_gladen(p_obs: float, sens: float, spec: float) -> float:
    denom = sens + spec - 1
    if math.isnan(denom) or denom <= 0:
        return math.nan
    return float(min(1.0, max(0.0, (p_obs + spec - 1) / denom)))


def corrected_pass_rate(observed: list[bool], calib_pairs: list[tuple[bool, bool]],
                        iters: int = 2000, conf: float = 0.95, seed: int = 0
                        ) -> tuple[float, float, float]:
    """Rogan-Gladen corrected pass rate with a bootstrap CI that resamples the
    run's verdicts and the calibration pairs independently."""
    if not observed or not calib_pairs:
        return (math.nan, math.nan, math.nan)
    obs = np.asarray(observed, dtype=float)
    cal = np.asarray(calib_pairs, dtype=bool)

    def est(o, c):
        h, j = c[:, 0], c[:, 1]
        sens = (h & j).sum() / h.sum() if h.sum() else math.nan
        spec = (~h & ~j).sum() / (~h).sum() if (~h).sum() else math.nan
        return rogan_gladen(o.mean(), sens, spec)

    point = est(obs, cal)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(iters):
        v = est(obs[rng.integers(0, len(obs), len(obs))], cal[rng.integers(0, len(cal), len(cal))])
        if not math.isnan(v):
            boots.append(v)
    if not boots:
        return (point, math.nan, math.nan)
    a = (1 - conf) / 2
    return (point, float(np.quantile(boots, a)), float(np.quantile(boots, 1 - a)))


def load_labels(path: Path) -> list[HumanLabel]:
    """Latest label per (item, answer) — relabelling an answer replaces it."""
    latest: dict[tuple[str, str], HumanLabel] = {}
    for lab in read_jsonl(path, HumanLabel):
        latest[(lab.item_id, lab.answer_hash)] = lab
    return list(latest.values())


def calibrate(cfg, client, log=print) -> dict:
    """Judge every labelled answer with the current panel (cache first), compare
    with the human labels, and write ``calibration.json``."""
    from rageval.runner import load_golden
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    labels = [lab for lab in load_labels(cfg.labels_path) if lab.item_id in golden]
    if not labels:
        raise RuntimeError(f'no labels in {cfg.labels_path}; run `rageval label <run>` first')
    records = [from_dict(RunRecord, lab.record) for lab in labels]
    judgments, complete = judge_records(client, records, golden, cfg.panel, cfg.criteria,
                                        JudgeCache(cfg.cache_dir),
                                        cfg.get('judges.temperature', 0.0), log)
    if not complete:
        log('WARNING: judging stopped early (budget); calibration covers only judged labels')
    result = compute_calibration(labels, judgments, cfg.panel, cfg.criteria,
                                 trust_kappa=cfg.get('gate.trust_kappa', 0.6),
                                 min_n=cfg.get('gate.min_labels', 20))
    cfg.calibration_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def compute_calibration(labels: list[HumanLabel], judgments, panel: list[str], criteria: list[str],
                        trust_kappa: float = 0.6, min_n: int = 20) -> dict:
    table = verdict_table(judgments, panel, rubric_hash(criteria))
    results: dict[str, dict[str, dict]] = {}
    for c in criteria:
        results[c] = {}
        for judge in [*panel, PANEL]:
            pairs = []
            for lab in labels:
                h = lab.verdicts.get(c)
                by_judge = table.get((lab.item_id, lab.answer_hash), {})
                j = (panel_verdicts(by_judge, [c])[c] if judge == PANEL
                     else (by_judge.get(judge) or {}).get(c))
                if h is not None and j is not None:
                    pairs.append((bool(h), bool(j)))
            r = judge_vs_human(pairs, trust_kappa, min_n)
            r['pairs'] = pairs
            results[c][judge] = r
    return {
        'panel_hash': panel_config_hash(panel, criteria),
        'panel': panel,
        'criteria': criteria,
        'created_at': datetime.now(UTC).isoformat(),
        'n_labels': len(labels),
        'trust_kappa': trust_kappa,
        'min_n': min_n,
        'results': results,
        'trusted': {c: results[c][PANEL]['trusted'] for c in criteria},
    }


def load_calibration(cfg) -> dict | None:
    p = cfg.calibration_path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def calibration_status(cfg) -> tuple[dict | None, str]:
    """(calibration, status) where status is 'ok', 'missing' or 'stale'."""
    cal = load_calibration(cfg)
    if cal is None:
        return None, 'missing'
    if cal.get('panel_hash') != panel_config_hash(cfg.panel, cfg.criteria):
        return cal, 'stale'
    return cal, 'ok'
