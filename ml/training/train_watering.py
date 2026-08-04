"""
Train the watering model: predicts water_mm_today from the feature vector
in ml/features/watering_features.py.

Run from the project root:
    uv run python ml/training/train_watering.py

Steps:
  1. Load ml/data/watering_synthetic.csv (generate it first if missing),
     plus ml/data/watering_snapshots.csv if it exists (real flywheel data,
     see ml/data/export_watering_snapshots.py).
  2. Encode features with ml.features.watering_features.to_vector.
  3. 5-fold CV comparing Ridge vs GradientBoostingRegressor — start simple,
     only prefer the more complex model if it actually wins.
  4. Pick whichever wins on decision accuracy (not raw MAE — see
     ml/docs/WATERING_MODEL.md, step 6).
  5. Retrain the winner on the full dataset, save ml/models/watering.pkl.
"""
import csv
import pickle
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

from ml.evaluation.metrics_history import append_run
from ml.evaluation.watering_metrics import evaluate
from ml.features.watering_features import FEATURE_ORDER, to_vector

SYNTHETIC_PATH = _ROOT / 'ml' / 'data' / 'watering_synthetic.csv'
SNAPSHOTS_PATH = _ROOT / 'ml' / 'data' / 'watering_snapshots.csv'
MODEL_DIR      = _ROOT / 'ml' / 'models'
MODEL_PATH     = MODEL_DIR / 'watering.pkl'

N_FOLDS = 5
RANDOM_SEED = 42

# Evaluation gate (Burkov step 6/7): a coin-flip-plus-margin floor. When real
# snapshot data with a rule_score is present, the gate compares against the
# rule engine's own call instead — see ml/docs/WATERING_MODEL.md §6.
GATE_MIN_DECISION_ACCURACY = 0.55


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_data() -> tuple[np.ndarray, np.ndarray, list]:
    rows = load_rows(SYNTHETIC_PATH)
    if not rows:
        raise FileNotFoundError(
            f'{SYNTHETIC_PATH} not found. Run ml/data/generate_watering_synthetic.py first.'
        )
    rows += load_rows(SNAPSHOTS_PATH)  # real flywheel data, once it exists

    X = np.array([to_vector(r) for r in rows])
    y = np.array([float(r['water_mm_today']) for r in rows])
    rule_scores = [float(r['rule_score']) if r.get('rule_score') not in (None, '') else None
                  for r in rows]
    return X, y, rule_scores


def cross_validate(X: np.ndarray, y: np.ndarray, rule_scores: list) -> dict:
    kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    results = {'ridge': [], 'gbr': []}

    for fold, (train_idx, test_idx) in enumerate(kf.split(X), 1):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        rs_te = [rule_scores[i] for i in test_idx]

        for name, model in (
            ('ridge', Ridge(alpha=1.0)),
            ('gbr', GradientBoostingRegressor(n_estimators=100, random_state=RANDOM_SEED)),
        ):
            model.fit(X_tr, y_tr)
            preds = model.predict(X_te)
            metrics = evaluate(list(y_te), list(preds), rs_te)
            results[name].append(metrics)
            print(f'  Fold {fold} [{name}]: ' + '  '.join(f'{k}={v:.3f}' for k, v in metrics.items()))

    return {name: {k: sum(f[k] for f in folds) / len(folds) for k in folds[0]}
            for name, folds in results.items()}


def main():
    print('Loading training data…')
    X, y, rule_scores = load_data()
    n_with_rule = sum(1 for r in rule_scores if r is not None)
    print(f'Dataset: {len(X)} rows ({n_with_rule} with a real rule_score)')
    print(f'Features ({len(FEATURE_ORDER)}): {FEATURE_ORDER}')

    print(f'\nRunning {N_FOLDS}-fold cross-validation (Ridge vs GradientBoostingRegressor)…')
    avg = cross_validate(X, y, rule_scores)
    print('\nAverage metrics:')
    for name, metrics in avg.items():
        print(f'  {name}: ' + '  '.join(f'{k}={v:.4f}' for k, v in metrics.items()))

    winner = max(avg, key=lambda n: avg[n]['decision_accuracy'])
    print(f'\nWinner: {winner} (higher decision_accuracy)')

    winner_metrics = avg[winner]
    gate_label = 'decision_accuracy_vs_rule' if 'decision_accuracy_vs_rule' in winner_metrics else 'decision_accuracy'
    gate_value = winner_metrics[gate_label]
    print(f'\nEvaluation gate: {gate_label}={gate_value:.4f} (must be >= {GATE_MIN_DECISION_ACCURACY})')
    gate_passed = gate_value >= GATE_MIN_DECISION_ACCURACY

    append_run('watering', winner_metrics, {
        'model_type': winner,
        'n_rows': len(X),
        'n_with_rule': n_with_rule,
        'gate_metric': gate_label,
        'gate_passed': gate_passed,
    })

    if not gate_passed:
        print('GATE FAILED — not saving model.')
        sys.exit(1)

    print('\nTraining final model on full dataset…')
    model = (Ridge(alpha=1.0) if winner == 'ridge'
            else GradientBoostingRegressor(n_estimators=100, random_state=RANDOM_SEED))
    model.fit(X, y)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    print(f'Model saved -> {MODEL_PATH}')


if __name__ == '__main__':
    main()
