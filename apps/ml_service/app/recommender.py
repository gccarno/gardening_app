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
    results = []

    for plant in plants:
        fv = build_feature_vector(plant, context)

        if model is not None:
            X = [[fv.get(f, 0.0) for f in _FEATURE_ORDER]]
            try:
                score = float(model.predict_proba(X)[0][1])
            except Exception:
                score = score_plant(plant, context)
        else:
            score = score_plant(plant, context)

        results.append({
            'plant_id':       plant.get('id'),
            'name':           plant.get('name'),
            'type':           plant.get('type'),
            'score':          round(score, 3),
            'reason':         top_reason(fv, context),
            'image_filename': plant.get('image_filename'),
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]
