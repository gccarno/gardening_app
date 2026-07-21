"""
Bootstrap synthetic training data for the watering model.

Before any real garden has logged real outcomes, this generates labeled
examples for `water_mm_today` from the same soil-moisture-deficit physics
the rule engine (apps/ml_service/app/watering_engine.py) uses — applied
directly to sampled feature combinations rather than walking ORM objects,
since this needs to run with no live DB. Once real MlWateringSnapshot rows
accumulate, ml/data/export_watering_snapshots.py provides the real training
signal alongside (eventually instead of) this. See ml/docs/WATERING_MODEL.md,
step 3, for why this bootstrap approach was chosen.

Run:
    uv run python ml/data/generate_watering_synthetic.py
"""
import csv
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features.watering_features import FEATURE_ORDER

OUT_PATH = _ROOT / 'ml' / 'data' / 'watering_synthetic.csv'
RANDOM_SEED = 42
N_SAMPLES = 6000

# Plausible value ranges per feature. Sampled independently and uniformly at
# random per row (not a full grid product — with 17 features that would be
# billions of combinations) so the dataset covers the input space broadly.
_RANGES = {
    'rain_7d_mm':               [0, 5, 15, 30, 60],
    'et0_7d_mm':                [10, 20, 30, 45],
    'temp_high_f':              [60, 75, 85, 95, 105],
    'temp_low_f':               [45, 55, 65, 75],
    'humidity_pct':             [30, 50, 70, 90],
    'forecast_precip_mm_d0':    [0, 2, 10, 25],
    'forecast_precip_prob_d0':  [0, 30, 60, 90],
    'forecast_precip_mm_d1_d2': [0, 5, 20],
    'forecast_temp_max_c':      [18, 25, 33, 40],
    'days_since_watered':       [0, 1, 2, 4, 7],
    'maturity_days':            [7, 21, 45, 90],
    'seedling_frac':            [0.0, 0.5, 1.0],
    'kc_avg':                   [0.6, 0.85, 1.05, 1.2],
    'mm_day_avg':               [2.0, 4.0, 5.0, 6.0],
    'sand_pct':                 [15, 33, 50],
    'clay_pct':                 [15, 33, 50],
    'bed_area_m2':              [1.5, 3.0, 6.0],
}


def _label(row: dict) -> float:
    """Physics-based target: mm of water needed today, mirroring the rule
    engine's deficit calculation (soil moisture debt minus effective rain,
    adjusted by upcoming forecast rain, temperature, and plant maturity)."""
    days = min(row['days_since_watered'], 7)
    et0_per_day = row['et0_7d_mm'] / 7 if row['et0_7d_mm'] else 3.5
    demand = days * et0_per_day * row['kc_avg']

    effective_rain = max(0.0, row['rain_7d_mm'] - 2.0 * days)  # ~2mm/day interception
    deficit = max(0.0, demand - effective_rain)

    # Rain expected soon reduces today's need — the model's whole point
    # relative to the rule engine, which only looks at today's forecast.
    upcoming = row['forecast_precip_mm_d0'] + row['forecast_precip_mm_d1_d2']
    deficit *= max(0.25, 1 - 0.04 * upcoming)

    # Hot days raise evaporative demand a bit beyond what ET0 already implies.
    if row['temp_high_f'] > 75:
        deficit *= 1 + min(0.4, (row['temp_high_f'] - 75) / 100)

    # Seedlings dry out faster (shallow roots) — raises urgency; the
    # shallow-but-frequent *scheduling* itself is applied at serving time
    # (see ml/docs/WATERING_MODEL.md, step 4), not learned here.
    deficit *= 1 + 0.3 * row['seedling_frac']

    return max(0.0, deficit)


def generate(n_samples: int = N_SAMPLES) -> list[dict]:
    random.seed(RANDOM_SEED)
    rows = []
    for _ in range(n_samples):
        row = {k: random.choice(v) for k, v in _RANGES.items()}
        label = _label(row) + random.gauss(0, 0.5)
        row['water_mm_today'] = round(max(0.0, min(40.0, label)), 2)
        rows.append(row)
    return rows


def main():
    rows = generate()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_ORDER + ['water_mm_today'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'Generated {len(rows)} synthetic rows -> {OUT_PATH}')


if __name__ == '__main__':
    main()
