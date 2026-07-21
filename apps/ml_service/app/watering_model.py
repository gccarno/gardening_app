"""
Watering model scoring — loads ml/models/watering.pkl if present, predicts
water_mm_today from a feature dict (see ml/features/watering_features.py).

Mirrors apps/ml_service/app/recommender.py's load-once pattern. Returns
None (never raises) when the artifact is missing or fails to load; callers
(watering_engine.get_watering_recommendations) fall back to the
deterministic rule engine in that case — training the model is never
required to run the app.
"""

import pickle
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[3]   # apps/ml_service/app/../../.. → project root
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml.features.watering_features import to_vector

_MODEL_PATH = _PROJECT_ROOT / 'ml' / 'models' / 'watering.pkl'

_model = None
_model_loaded = False


def _load_model():
    global _model, _model_loaded
    if _model_loaded:
        return _model
    _model_loaded = True
    if _MODEL_PATH.exists():
        try:
            with open(_MODEL_PATH, 'rb') as f:
                _model = pickle.load(f)
        except Exception:
            _model = None
    return _model


def predict_water_mm(feature_row: dict) -> float | None:
    """Predict mm of water needed today, or None if no model is available."""
    model = _load_model()
    if model is None:
        return None
    try:
        pred = float(model.predict([to_vector(feature_row)])[0])
    except Exception:
        return None
    return max(0.0, round(pred, 2))
