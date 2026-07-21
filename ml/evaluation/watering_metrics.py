"""
Evaluation metrics for the watering regression model.

The metric that actually matters for this product isn't raw error — it's
whether the model's water/no-water call is right (and, once real data
exists, whether it agrees with or improves on the rule engine's own call).
See ml/docs/WATERING_MODEL.md, step 6.
"""
import math


def mae(y_true: list, y_pred: list) -> float:
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / len(y_true)


def rmse(y_true: list, y_pred: list) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y_true, y_pred)) / len(y_true))


def decision_accuracy(y_true: list, y_pred: list, threshold: float = 1.5) -> float:
    """Fraction of rows where predicted and true water/no-water calls agree
    at the given mm threshold (roughly the rule engine's 'consider' cutoff)."""
    agree = sum((a > threshold) == (b > threshold) for a, b in zip(y_true, y_pred))
    return agree / len(y_true)


def decision_accuracy_vs_rule(y_pred: list, rule_scores: list,
                              threshold: float = 1.5, rule_cutoff: int = 50) -> float | None:
    """Fraction of rows where the model's water/no-water call agrees with the
    deterministic rule engine's own call (rule_score >= rule_cutoff). None
    when no row has a rule_score (e.g. purely synthetic data)."""
    pairs = [(p, r) for p, r in zip(y_pred, rule_scores) if r is not None]
    if not pairs:
        return None
    agree = sum((p > threshold) == (r >= rule_cutoff) for p, r in pairs)
    return agree / len(pairs)


def evaluate(y_true: list, y_pred: list, rule_scores: list | None = None,
            threshold: float = 1.5) -> dict:
    out = {
        'mae':               mae(y_true, y_pred),
        'rmse':               rmse(y_true, y_pred),
        'decision_accuracy':  decision_accuracy(y_true, y_pred, threshold),
    }
    if rule_scores is not None:
        vs_rule = decision_accuracy_vs_rule(y_pred, rule_scores, threshold)
        if vs_rule is not None:
            out['decision_accuracy_vs_rule'] = vs_rule
    return out
