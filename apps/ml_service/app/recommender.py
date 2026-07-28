"""
Plant recommender scoring engine.

Uses rule-based scoring (build_features.py) by default.
If ml/models/recommender.pkl exists, uses the trained sklearn model instead.
"""

import pickle
import sys
from pathlib import Path

# Make ml.features importable from wherever this module is called
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[3]   # apps/ml_service/app/../../.. → project root
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml.features.build_features import build_feature_vector, score_plant, top_reason

_MODEL_PATH = _PROJECT_ROOT / 'ml' / 'models' / 'recommender.pkl'
_FEATURE_ORDER = [
    'zone_match', 'season_match', 'sunlight_match',
    'soil_ph_match', 'difficulty', 'type_preference', 'companion_bonus',
]

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


def recommend(plants: list, context: dict, top_n: int = 5) -> list:
    """
    Score all plants and return top_n sorted by predicted success score.

    Parameters
    ----------
    plants : list of dicts
        Serialised PlantLibrary rows. Each dict must include at minimum 'id', 'name'.
    context : dict
        Garden and preference context. Recognised keys:
          zone (int|str), sunlight_hours (float), current_month (int),
          soil_ph (float|None), current_plant_names (list[str]),
          preferred_types (list[str])
    top_n : int
        Maximum number of recommendations to return.

    Returns
    -------
    list of dicts: {plant_id, name, type, score, reason, image_filename}
    """
    if not plants:
        return []

    model = _load_model()
    feature_vectors = [build_feature_vector(p, context) for p in plants]

    # One predict_proba over every row, not one call per plant. The library is
    # ~9,999 rows in production and the per-row version spent minutes of CPU on
    # sklearn call overhead alone -- enough to pin the free instance's CPU cap
    # and time the request out. A failure now falls the whole batch back to
    # rule scoring rather than just the offending row; the model either loads
    # and works or it doesn't, so per-row recovery bought nothing.
    scores = None
    if model is not None:
        X = [[fv.get(f, 0.0) for f in _FEATURE_ORDER] for fv in feature_vectors]
        try:
            scores = [float(row[1]) for row in model.predict_proba(X)]
        except Exception:
            scores = None
    if scores is None:
        scores = [score_plant(p, context) for p in plants]

    results = [
        {
            'plant_id':       plant.get('id'),
            'name':           plant.get('name'),
            'type':           plant.get('type'),
            'score':          round(score, 3),
            'reason':         top_reason(fv, context),
            'image_filename': plant.get('image_filename'),
        }
        for plant, fv, score in zip(plants, feature_vectors, scores)
    ]

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]
