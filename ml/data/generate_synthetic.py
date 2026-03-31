"""
Generate a synthetic training dataset for the plant recommender.

Run from the project root:
    uv run python ml/data/generate_synthetic.py

Output: ml/data/synthetic_training.csv
Columns: user_zone, sunlight_hours, current_month, soil_ph,
         preferred_types, plant_id, plant_name, plant_type,
         [feature columns], success (0/1 label)
"""

import csv
import json
import os
import random
import sys
from math import ceil
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features.build_features import build_feature_vector, score_plant

# ── Synthetic user profiles ───────────────────────────────────────────────────

ZONES          = list(range(3, 11))                    # USDA zones 3–10
SUNLIGHT_RANGE = (2.0, 10.0)                           # daily sun hours
MONTHS         = list(range(1, 13))                    # 1–12
PH_RANGE       = (5.5, 7.5)
TYPE_OPTIONS   = [
    ['vegetable'],
    ['herb'],
    ['vegetable', 'herb'],
    ['flower'],
    ['vegetable', 'herb', 'flower'],
]

N_USERS = 60
NOISE_STD = 0.12   # Gaussian noise added to rule score before thresholding

# Success threshold: rule score must exceed this (after noise) to label as success
SUCCESS_THRESHOLD = 0.55

RANDOM_SEED = 42

# ── Plant data (loaded from DB or hardcoded seed) ─────────────────────────────

def _load_plants_from_db() -> list[dict]:
    """Try to load PlantLibrary rows from the SQLite DB. Falls back to an empty list."""
    try:
        # Flask app lives in apps/api/; add it to path so models can be imported
        api_path = str(_ROOT / 'apps' / 'api')
        if api_path not in sys.path:
            sys.path.insert(0, api_path)
        from app.main import create_app
        app = create_app()
        with app.app_context():
            from app.db.models import PlantLibrary
            plants = []
            for p in PlantLibrary.query.all():
                plants.append({
                    'id':            p.id,
                    'name':          p.name,
                    'type':          p.type,
                    'min_zone':      p.min_zone,
                    'max_zone':      p.max_zone,
                    'sunlight':      p.sunlight,
                    'soil_ph_min':   p.soil_ph_min,
                    'soil_ph_max':   p.soil_ph_max,
                    'good_neighbors': p.good_neighbors,
                    'difficulty':    p.difficulty,
                    'days_to_harvest': p.days_to_harvest,
                    'fruit_months':  p.fruit_months,
                    'bloom_months':  p.bloom_months,
                    'growth_months': p.growth_months,
                })
            return plants
    except Exception as e:
        print(f'[warn] Could not load from DB ({e}); using fallback seed data.')
        return []


_FALLBACK_PLANTS = [
    {'id': 1,  'name': 'Tomato',        'type': 'vegetable', 'min_zone': 3, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 6.8, 'good_neighbors': '["Basil","Carrot"]',  'difficulty': 'Moderate', 'days_to_harvest': 70,  'fruit_months': '[7,8,9]',    'bloom_months': '[6,7]',   'growth_months': '[5,6,7,8,9]'},
    {'id': 2,  'name': 'Basil',         'type': 'herb',      'min_zone': 4, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Tomato","Pepper"]', 'difficulty': 'Easy',     'days_to_harvest': 30,  'fruit_months': None,         'bloom_months': '[7,8]',   'growth_months': '[5,6,7,8]'},
    {'id': 3,  'name': 'Lettuce',       'type': 'vegetable', 'min_zone': 4, 'max_zone': 9,  'sunlight': 'Partial shade', 'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Carrot","Radish"]', 'difficulty': 'Easy',     'days_to_harvest': 45,  'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10,11]'},
    {'id': 4,  'name': 'Carrot',        'type': 'vegetable', 'min_zone': 3, 'max_zone': 10, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 6.8, 'good_neighbors': '["Lettuce","Onion"]', 'difficulty': 'Moderate', 'days_to_harvest': 70,  'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,6,7,8,9,10]'},
    {'id': 5,  'name': 'Zucchini',      'type': 'vegetable', 'min_zone': 4, 'max_zone': 10, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.5, 'good_neighbors': '["Basil","Dill"]',    'difficulty': 'Easy',     'days_to_harvest': 50,  'fruit_months': '[6,7,8,9]',  'bloom_months': '[6,7,8]', 'growth_months': '[5,6,7,8,9]'},
    {'id': 6,  'name': 'Kale',          'type': 'vegetable', 'min_zone': 2, 'max_zone': 9,  'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.5, 'good_neighbors': '["Beet","Celery"]',   'difficulty': 'Easy',     'days_to_harvest': 55,  'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10,11]'},
    {'id': 7,  'name': 'Cucumber',      'type': 'vegetable', 'min_zone': 4, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Dill","Radish"]',   'difficulty': 'Moderate', 'days_to_harvest': 55,  'fruit_months': '[7,8,9]',    'bloom_months': '[6,7,8]', 'growth_months': '[5,6,7,8,9]'},
    {'id': 8,  'name': 'Radish',        'type': 'vegetable', 'min_zone': 2, 'max_zone': 10, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Carrot","Lettuce"]', 'difficulty': 'Easy',    'days_to_harvest': 25,  'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10]'},
    {'id': 9,  'name': 'Mint',          'type': 'herb',      'min_zone': 3, 'max_zone': 11, 'sunlight': 'Partial shade', 'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Tomato","Cabbage"]', 'difficulty': 'Easy',    'days_to_harvest': 30,  'fruit_months': None,         'bloom_months': '[6,7,8]', 'growth_months': '[4,5,6,7,8,9]'},
    {'id': 10, 'name': 'Bell Pepper',   'type': 'vegetable', 'min_zone': 5, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 6.8, 'good_neighbors': '["Basil","Carrot"]',  'difficulty': 'Moderate', 'days_to_harvest': 75,  'fruit_months': '[7,8,9]',    'bloom_months': '[6,7]',   'growth_months': '[5,6,7,8,9]'},
    {'id': 11, 'name': 'Sunflower',     'type': 'flower',    'min_zone': 2, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.5, 'good_neighbors': '["Cucumber","Corn"]',  'difficulty': 'Easy',    'days_to_harvest': 80,  'fruit_months': '[8,9,10]',   'bloom_months': '[7,8,9]', 'growth_months': '[4,5,6,7,8,9]'},
    {'id': 12, 'name': 'Spinach',       'type': 'vegetable', 'min_zone': 3, 'max_zone': 9,  'sunlight': 'Partial shade', 'soil_ph_min': 6.5, 'soil_ph_max': 7.5, 'good_neighbors': '["Strawberry","Pea"]', 'difficulty': 'Easy',    'days_to_harvest': 40,  'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10,11]'},
]


def generate_dataset(plants: list[dict], n_users: int = N_USERS, seed: int = RANDOM_SEED) -> list[dict]:
    rng = random.Random(seed)
    rows = []

    for _ in range(n_users):
        zone   = rng.choice(ZONES)
        sun    = round(rng.uniform(*SUNLIGHT_RANGE), 1)
        month  = rng.choice(MONTHS)
        ph     = round(rng.uniform(*PH_RANGE), 1)
        prefs  = rng.choice(TYPE_OPTIONS)
        # A few currently-growing plants (randomly sampled)
        n_current = rng.randint(0, 3)
        current_names = [p['name'] for p in rng.sample(plants, min(n_current, len(plants)))]

        context = {
            'zone':                zone,
            'sunlight_hours':      sun,
            'current_month':       month,
            'soil_ph':             ph,
            'preferred_types':     prefs,
            'current_plant_names': current_names,
        }

        for plant in plants:
            fv = build_feature_vector(plant, context)
            rule_score = score_plant(plant, context)
            noisy_score = rule_score + rng.gauss(0, NOISE_STD)
            success = 1 if noisy_score >= SUCCESS_THRESHOLD else 0

            row = {
                'user_zone':           zone,
                'sunlight_hours':      sun,
                'current_month':       month,
                'soil_ph':             ph,
                'preferred_types':     json.dumps(prefs),
                'plant_id':            plant['id'],
                'plant_name':          plant['name'],
                'plant_type':          plant.get('type', ''),
                **{f'feat_{k}': round(v, 4) for k, v in fv.items()},
                'rule_score':          round(rule_score, 4),
                'success':             success,
            }
            rows.append(row)

    return rows


def main():
    print('Loading plant data…')
    plants = _load_plants_from_db()
    if not plants:
        print(f'Using {len(_FALLBACK_PLANTS)} fallback plants.')
        plants = _FALLBACK_PLANTS

    print(f'Generating dataset: {N_USERS} users × {len(plants)} plants = {N_USERS * len(plants)} rows')
    rows = generate_dataset(plants)

    out_path = Path(__file__).parent / 'synthetic_training.csv'
    if rows:
        fieldnames = list(rows[0].keys())
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    pos = sum(r['success'] for r in rows)
    print(f'Saved {len(rows)} rows to {out_path}')
    print(f'Class balance: {pos} positive ({100*pos/len(rows):.1f}%), {len(rows)-pos} negative')


if __name__ == '__main__':
    main()
