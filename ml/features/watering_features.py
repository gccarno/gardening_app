"""
Feature encoding for the watering model — shared between training and
serving so a feature row is turned into the exact same numeric vector both
places (training/serving skew is a common, easy-to-miss source of ML bugs).

Pure Python — no DB/FastAPI imports. The *raw* feature computation (querying
WeatherLog, walking bed_plants, calling the forecast APIs) lives in
apps/backend/app/jobs/ml_snapshot.py, since it needs live SQLAlchemy objects
and network calls. That job, the synthetic-data generator, and the snapshot
exporter all produce the same flat dict shape — one key per FEATURE_ORDER
entry. This module turns that dict into the array the model actually sees,
with a single shared definition of what a missing value defaults to.
"""

FEATURE_ORDER = [
    'rain_7d_mm', 'et0_7d_mm', 'temp_high_f', 'temp_low_f', 'humidity_pct',
    'forecast_precip_mm_d0', 'forecast_precip_prob_d0', 'forecast_precip_mm_d1_d2',
    'forecast_temp_max_c', 'days_since_watered', 'maturity_days', 'seedling_frac',
    'kc_avg', 'mm_day_avg', 'sand_pct', 'clay_pct', 'bed_area_m2',
]

# Defaults applied when a feature is missing/None — "unremarkable" mid-range
# conditions, so a missing value doesn't bias the model toward urgent or
# complacent recommendations.
_DEFAULTS = {
    'rain_7d_mm': 0.0, 'et0_7d_mm': 24.5, 'temp_high_f': 75.0, 'temp_low_f': 55.0,
    'humidity_pct': 55.0, 'forecast_precip_mm_d0': 0.0, 'forecast_precip_prob_d0': 20.0,
    'forecast_precip_mm_d1_d2': 0.0, 'forecast_temp_max_c': 24.0, 'days_since_watered': 2,
    'maturity_days': 30, 'seedling_frac': 0.0, 'kc_avg': 0.85, 'mm_day_avg': 4.0,
    'sand_pct': 33.0, 'clay_pct': 33.0, 'bed_area_m2': 3.0,
}


def build_watering_features(feature_row: dict) -> dict:
    """Return a new dict with every FEATURE_ORDER key present, filling
    missing/None/empty values with their default."""
    filled = {}
    for k in FEATURE_ORDER:
        v = feature_row.get(k)
        filled[k] = _DEFAULTS[k] if v is None or v == '' else v
    return filled


def to_vector(feature_row: dict) -> list[float]:
    """Encode a feature dict into the fixed-order numeric vector the model sees."""
    filled = build_watering_features(feature_row)
    return [float(filled[k]) for k in FEATURE_ORDER]
