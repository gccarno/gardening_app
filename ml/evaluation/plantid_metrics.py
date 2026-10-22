"""
Evaluation metrics for the plant-ID model (see ml/docs/PLANT_ID_MODEL.md).

Accuracy alone isn't enough here: the model sits in front of Claude and only
answers when it is confident, so its *confidence* has to mean something.
Hence calibration (temperature scaling + ECE) and selective prediction
(coverage vs. accuracy, and the threshold that hands off to Claude).

All functions take numpy arrays: `scores`/`logits` are (n, n_classes),
`labels` are class indices, `conf` is the top-1 probability, `correct` is a
bool array of whether the top-1 prediction was right.
"""
import numpy as np


def topk_accuracy(scores: np.ndarray, labels: np.ndarray, k: int) -> float:
    """Fraction of rows whose label is among the k highest scores."""
    k = min(k, scores.shape[1])
    topk = np.argpartition(-scores, k - 1, axis=1)[:, :k]
    return float((topk == labels[:, None]).any(axis=1).mean())


def softmax(logits: np.ndarray, temperature: float) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def _nll(logits: np.ndarray, labels: np.ndarray, temperature: float) -> float:
    p = softmax(logits, temperature)[np.arange(len(labels)), labels]
    return float(-np.log(np.clip(p, 1e-12, None)).mean())


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    """Temperature minimising NLL — a log-spaced grid, then a finer one around the best."""
    grid = np.logspace(-3, 2, 200)
    best = min(grid, key=lambda t: _nll(logits, labels, t))
    fine = np.linspace(best * 0.8, best * 1.25, 100)
    return float(min(fine, key=lambda t: _nll(logits, labels, t)))


def expected_calibration_error(conf: np.ndarray, correct: np.ndarray, n_bins: int = 15) -> float:
    """Weighted mean |accuracy - confidence| over equal-width confidence bins."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # Right-closed bins, with confidence 0 falling in the first.
    idx = np.clip(np.searchsorted(edges, conf, side='left') - 1, 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def coverage_curve(conf: np.ndarray, correct: np.ndarray, thresholds=None) -> list[dict]:
    """For each threshold: share of predictions kept (conf >= t) and their accuracy."""
    if thresholds is None:
        thresholds = np.linspace(0.0, 0.99, 100)
    rows = []
    for t in thresholds:
        keep = conf >= t
        rows.append({
            'threshold': float(t),
            'coverage': float(keep.mean()),
            'selective_accuracy': float(correct[keep].mean()) if keep.any() else None,
        })
    return rows


def choose_threshold(conf: np.ndarray, correct: np.ndarray, target_accuracy: float) -> float | None:
    """Lowest confidence threshold whose kept predictions reach target_accuracy.

    Candidate thresholds are the observed confidences, so the answer is exact
    for this sample. None if no threshold reaches the target.
    """
    order = np.argsort(-conf)
    hits = np.cumsum(correct[order])
    acc = hits / np.arange(1, len(conf) + 1)
    ok = np.nonzero(acc >= target_accuracy)[0]
    if len(ok) == 0:
        return None
    # Largest prefix meeting the target -> lowest threshold.
    return float(conf[order][ok[-1]])
