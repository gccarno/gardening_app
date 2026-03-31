"""
Train the plant recommender model.

Run from the project root:
    uv run python ml/training/train_recommender.py

Steps:
  1. Load ml/data/synthetic_training.csv (generate it first if missing)
  2. Build feature matrix
  3. Train GradientBoostingClassifier with 5-fold cross-validation
  4. Print precision@5, recall@5, NDCG@5 per fold
  5. Retrain on full dataset and save model to ml/models/recommender.pkl
"""

import csv
import pickle
import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder

from ml.evaluation.metrics import evaluate_recommendations

DATA_PATH  = _ROOT / 'ml' / 'data' / 'synthetic_training.csv'
MODEL_DIR  = _ROOT / 'ml' / 'models'
MODEL_PATH = MODEL_DIR / 'recommender.pkl'

FEATURE_COLS = [
    'feat_zone_match',
    'feat_season_match',
    'feat_sunlight_match',
    'feat_soil_ph_match',
    'feat_difficulty',
    'feat_type_preference',
    'feat_companion_bonus',
]

N_FOLDS = 5
RANDOM_SEED = 42


def load_data(path: Path) -> tuple[np.ndarray, np.ndarray, list]:
    """Load CSV and return (X, y, plant_ids)."""
    if not path.exists():
        raise FileNotFoundError(
            f'{path} not found. Run ml/data/generate_synthetic.py first.'
        )
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    X = np.array([[float(r[c]) for c in FEATURE_COLS] for r in rows])
    y = np.array([int(r['success']) for r in rows])
    plant_ids = [r['plant_id'] for r in rows]
    return X, y, plant_ids


def cross_validate(X: np.ndarray, y: np.ndarray, plant_ids: list) -> dict:
    """Run stratified k-fold CV and return averaged metrics."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    all_metrics = []
    k = 5  # precision/recall/NDCG @k

    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), 1):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        ids_te = [plant_ids[i] for i in test_idx]

        clf = GradientBoostingClassifier(n_estimators=100, random_state=RANDOM_SEED)
        clf.fit(X_tr, y_tr)

        proba = clf.predict_proba(X_te)[:, 1]
        ranked_ids = [pid for _, pid in sorted(zip(proba, ids_te), reverse=True)]
        relevant   = [pid for pid, label in zip(ids_te, y_te) if label == 1]

        metrics = evaluate_recommendations(ranked_ids, relevant, k=k)
        all_metrics.append(metrics)
        print(f'  Fold {fold}: ' + '  '.join(f'{m}={v:.3f}' for m, v in metrics.items()))

    avg = {m: sum(f[m] for f in all_metrics) / N_FOLDS for m in all_metrics[0]}
    return avg


def train_final(X: np.ndarray, y: np.ndarray) -> GradientBoostingClassifier:
    clf = GradientBoostingClassifier(n_estimators=100, random_state=RANDOM_SEED)
    clf.fit(X, y)
    return clf


def save_model(clf, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(clf, f)
    print(f'Model saved -> {path}')


def main():
    print(f'Loading data from {DATA_PATH}…')
    X, y, plant_ids = load_data(DATA_PATH)
    print(f'Dataset: {len(X)} rows, {y.sum()} positive ({100*y.mean():.1f}%)')
    print(f'Features: {FEATURE_COLS}')

    print(f'\nRunning {N_FOLDS}-fold cross-validation…')
    avg_metrics = cross_validate(X, y, plant_ids)
    print('\nAverage metrics:')
    for m, v in avg_metrics.items():
        print(f'  {m} = {v:.4f}')

    print('\nTraining final model on full dataset…')
    clf = train_final(X, y)

    print('\nFeature importances:')
    for name, imp in sorted(zip(FEATURE_COLS, clf.feature_importances_), key=lambda x: -x[1]):
        bar = '#' * int(imp * 40)
        print(f'  {name:<30} {imp:.4f}  {bar}')

    save_model(clf, MODEL_PATH)


if __name__ == '__main__':
    main()
