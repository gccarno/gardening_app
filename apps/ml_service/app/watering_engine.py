"""
Predictive watering engine for the garden assistant.

Combines rainfall history (WeatherLog), plant water requirements (Kc table),
and weather forecast (Open-Meteo) to generate per-bed watering urgency scores
and daily recommendations.

Pure Python — no Flask imports.  All SQLAlchemy objects are passed in by callers.
"""

from datetime import date, timedelta
from math import sqrt

# ── Crop coefficient (Kc) + daily water need lookup ──────────────────────────
# Searched by plant name substring (longest match wins).
# Fallback uses PlantLibrary.water field values: 'Low', 'Moderate', 'High'.

_KC_BY_NAME: list[tuple[str, dict]] = [
    ('tomato',      {'kc': 1.15, 'mm_day': 5.0, 'drought': 'low'}),
    ('pepper',      {'kc': 1.05, 'mm_day': 5.0, 'drought': 'medium'}),
    ('eggplant',    {'kc': 1.05, 'mm_day': 4.0, 'drought': 'medium'}),
    ('cucumber',    {'kc': 1.00, 'mm_day': 5.0, 'drought': 'low'}),
    ('zucchini',    {'kc': 0.95, 'mm_day': 5.0, 'drought': 'medium'}),
    ('squash',      {'kc': 0.95, 'mm_day': 5.0, 'drought': 'medium'}),
    ('pumpkin',     {'kc': 1.00, 'mm_day': 6.0, 'drought': 'medium'}),
    ('melon',       {'kc': 1.00, 'mm_day': 6.0, 'drought': 'medium'}),
    ('lettuce',     {'kc': 1.00, 'mm_day': 3.0, 'drought': 'low'}),
    ('spinach',     {'kc': 1.00, 'mm_day': 3.0, 'drought': 'low'}),
    ('basil',       {'kc': 1.00, 'mm_day': 4.0, 'drought': 'medium'}),
    ('mint',        {'kc': 0.90, 'mm_day': 4.0, 'drought': 'medium'}),
    ('carrot',      {'kc': 0.85, 'mm_day': 3.0, 'drought': 'medium'}),
    ('beet',        {'kc': 0.85, 'mm_day': 3.0, 'drought': 'medium'}),
    ('radish',      {'kc': 0.70, 'mm_day': 2.0, 'drought': 'medium'}),
    ('bean',        {'kc': 1.05, 'mm_day': 5.0, 'drought': 'medium'}),
    ('pea',         {'kc': 1.05, 'mm_day': 4.0, 'drought': 'medium'}),
    ('corn',        {'kc': 1.15, 'mm_day': 6.0, 'drought': 'low'}),
    ('potato',      {'kc': 1.05, 'mm_day': 5.0, 'drought': 'medium'}),
    ('onion',       {'kc': 0.75, 'mm_day': 3.0, 'drought': 'medium'}),
    ('garlic',      {'kc': 0.70, 'mm_day': 3.0, 'drought': 'high'}),
    ('broccoli',    {'kc': 1.00, 'mm_day': 4.0, 'drought': 'low'}),
    ('cabbage',     {'kc': 1.05, 'mm_day': 4.0, 'drought': 'medium'}),
    ('kale',        {'kc': 1.00, 'mm_day': 4.0, 'drought': 'medium'}),
    ('chard',       {'kc': 1.00, 'mm_day': 4.0, 'drought': 'medium'}),
    ('celery',      {'kc': 1.05, 'mm_day': 5.0, 'drought': 'low'}),
    ('strawberry',  {'kc': 0.85, 'mm_day': 4.0, 'drought': 'medium'}),
    ('blueberry',   {'kc': 0.90, 'mm_day': 5.0, 'drought': 'medium'}),
    ('raspberry',   {'kc': 0.90, 'mm_day': 5.0, 'drought': 'medium'}),
    ('herb',        {'kc': 0.80, 'mm_day': 3.0, 'drought': 'high'}),
    ('flower',      {'kc': 0.85, 'mm_day': 3.0, 'drought': 'medium'}),
    ('tree',        {'kc': 0.85, 'mm_day': 4.0, 'drought': 'high'}),
    ('shrub',       {'kc': 0.80, 'mm_day': 3.0, 'drought': 'high'}),
]

_KC_BY_WATER_NEED = {
    'low':      {'kc': 0.60, 'mm_day': 2.0, 'drought': 'high'},
    'moderate': {'kc': 0.85, 'mm_day': 4.0, 'drought': 'medium'},
    'high':     {'kc': 1.10, 'mm_day': 6.0, 'drought': 'low'},
}

_KC_DEFAULT = {'kc': 0.85, 'mm_day': 4.0, 'drought': 'medium'}

# Rain below this threshold (mm) is mostly intercepted — not counted as effective
_EFFECTIVE_RAIN_THRESHOLD_MM = 2.0


# ── Public helpers ────────────────────────────────────────────────────────────

def get_plant_kc(plant_name: str, water_need: str | None = None) -> dict:
    """
    Return Kc data dict for a plant.
    Falls back to water_need category, then default.
    """
    lower = (plant_name or '').lower()
    for keyword, kc_data in _KC_BY_NAME:
        if keyword in lower:
            return dict(kc_data)
    if water_need:
        return dict(_KC_BY_WATER_NEED.get(water_need.lower(), _KC_DEFAULT))
    return dict(_KC_DEFAULT)


def estimate_et0_from_temp(temp_high_f: float | None, temp_low_f: float | None) -> float:
    """
    Estimate daily reference ET0 (mm) from Fahrenheit min/max temperature
    using a simplified Hargreaves-Samani approach.
    Falls back to 3.5 mm/day (typical temperate spring/summer) if temps missing.
    """
    if temp_high_f is None or temp_low_f is None:
        return 3.5
    t_max = (temp_high_f - 32) * 5 / 9
    t_min = (temp_low_f - 32) * 5 / 9
    t_mean = (t_max + t_min) / 2
    t_range = max(0.0, t_max - t_min)
    # Ra approximated as 9 MJ/m^2/day (mid-latitude)
    return max(0.0, round(0.0023 * (t_mean + 17.8) * sqrt(t_range + 0.001) * 9.0, 2))


def days_since_last_watered(bed) -> int:
    """
    Days since any plant in the bed was last watered.
    Returns 999 if never watered.
    """
    today = date.today()
    most_recent = None
    for bp in (bed.bed_plants or []):
        if bp.last_watered:
            if most_recent is None or bp.last_watered > most_recent:
                most_recent = bp.last_watered
    if most_recent is None:
        return 999
    return max(0, (today - most_recent).days)


def _effective_rain_mm(rainfall_in: float | None) -> float:
    if not rainfall_in:
        return 0.0
    mm = rainfall_in * 25.4
    return max(0.0, mm - _EFFECTIVE_RAIN_THRESHOLD_MM)


def calculate_deficit(bed, kc_data: dict, weather_logs: list, lookback_days: int = 7) -> float:
    """
    Calculate soil moisture deficit (mm) over the last lookback_days,
    capped at the number of days since the bed was last watered.

    deficit = sum(ET_actual - effective_rainfall) per day
    ET_actual = ET0 * Kc  (ET0 estimated from stored temp when not explicit)
    """
    dsw = days_since_last_watered(bed)
    effective_days = min(lookback_days, dsw)
    if effective_days <= 0:
        return 0.0

    kc = kc_data.get('kc', 0.85)
    today = date.today()
    log_by_date = {lg.date: lg for lg in weather_logs}

    deficit = 0.0
    for offset in range(1, effective_days + 1):
        d = today - timedelta(days=offset)
        log = log_by_date.get(d)
        if log:
            et0 = estimate_et0_from_temp(log.temp_high_f, log.temp_low_f)
            eff_rain = _effective_rain_mm(log.rainfall_in)
        else:
            et0 = 3.5
            eff_rain = 0.0
        deficit += max(0.0, et0 * kc - eff_rain)

    return round(deficit, 1)


def score_urgency(deficit_mm: float, kc_data: dict, forecast_today: dict | None = None) -> int:
    """
    Compute watering urgency score (0–100).

    0–19:  No action needed
    20–49: Consider watering
    50–74: Water today
    75+:   Urgent
    """
    mm_day = kc_data.get('mm_day', 4.0)
    drought = kc_data.get('drought', 'medium')
    max_deficit = mm_day * 3.0  # three dry days at peak need

    score = min(60.0, (deficit_mm / max(max_deficit, 0.1)) * 60.0)

    if forecast_today:
        temp_c = forecast_today.get('temp_max_c') or 20
        wind   = forecast_today.get('wind_kmh') or 10
        prob   = forecast_today.get('precip_prob') or 0
        pmm    = forecast_today.get('precip_mm') or 0

        if temp_c > 35:
            score += 20
        elif temp_c > 30:
            score += 12
        elif temp_c > 25:
            score += 6

        if wind > 40:
            score += 8
        elif wind > 25:
            score += 4

        if prob > 70:
            score -= 30
        elif prob > 50:
            score -= 15
        if pmm > 5:
            score -= 20
        elif pmm > 2:
            score -= 10

    if drought == 'high':
        score *= 0.70
    elif drought == 'low':
        score *= 1.20

    return max(0, min(100, round(score)))


def get_urgency_label(score: int) -> str:
    if score >= 75:
        return 'urgent'
    if score >= 50:
        return 'water_today'
    if score >= 20:
        return 'consider'
    return 'ok'


def get_watering_recommendations(garden, weather_logs: list, forecast_today: dict | None = None) -> list:
    """
    Return per-bed watering recommendations for a garden.

    Args:
        garden:         Garden ORM object (with .beds, .beds[].bed_plants loaded)
        weather_logs:   List of WeatherLog objects for this garden (any date range)
        forecast_today: Optional dict {temp_max_c, wind_kmh, precip_prob, precip_mm}

    Returns:
        List of bed recommendation dicts, sorted by urgency score descending.
    """
    results = []

    for bed in garden.beds:
        plants_in_bed = [bp.plant for bp in bed.bed_plants if bp.plant]
        if not plants_in_bed:
            continue

        # Average Kc across plants in this bed
        kc_list = [
            get_plant_kc(
                p.name,
                (p.library_entry.water if p.library_entry else None),
            )
            for p in plants_in_bed
        ]
        avg_kc = {
            'kc':     round(sum(k['kc']     for k in kc_list) / len(kc_list), 3),
            'mm_day': round(sum(k['mm_day'] for k in kc_list) / len(kc_list), 1),
            'drought': _majority(k['drought'] for k in kc_list),
        }

        deficit = calculate_deficit(bed, avg_kc, weather_logs)
        dsw     = days_since_last_watered(bed)
        score   = score_urgency(deficit, avg_kc, forecast_today)
        label   = get_urgency_label(score)

        # Suggested amount (very rough: mm_day × area × 0.3-0.4 litres/m² scaling)
        area_m2 = (bed.width_ft * bed.height_ft) * 0.0929  # ft² → m²
        amount_L = round(avg_kc['mm_day'] * area_m2 * (1.3 if label == 'urgent' else 1.0))

        rec = {
            'ok':          'Soil moisture looks adequate.',
            'consider':    'Consider watering if the top inch of soil feels dry.',
            'water_today': f'Water today — about {max(amount_L, 1)}L suggested.',
            'urgent':      f'Water immediately — plants may be stressed. About {max(amount_L, 1)}L needed.',
        }[label]

        if forecast_today and (forecast_today.get('precip_prob') or 0) > 60:
            rec += f' ({forecast_today["precip_prob"]}% chance of rain — consider waiting.)'

        results.append({
            'bed_id':             bed.id,
            'bed_name':           bed.name,
            'urgency_score':      score,
            'label':              label,
            'deficit_mm':         deficit,
            'days_since_watered': min(dsw, 99),
            'kc':                 avg_kc['kc'],
            'mm_day':             avg_kc['mm_day'],
            'plants':             [p.name for p in plants_in_bed],
            'recommendation':     rec,
        })

    results.sort(key=lambda x: x['urgency_score'], reverse=True)
    return results


# ── Weather fetch helpers (used by chat tools) ────────────────────────────────

def fetch_forecast_today(lat: float, lon: float) -> dict | None:
    """Fetch today's forecast from Open-Meteo (metric). Returns None on failure."""
    try:
        import requests
        resp = requests.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': lat, 'longitude': lon,
            'daily': (
                'temperature_2m_max,precipitation_probability_max,'
                'precipitation_sum,wind_speed_10m_max'
            ),
            'temperature_unit': 'celsius',
            'wind_speed_unit': 'kmh',
            'precipitation_unit': 'mm',
            'forecast_days': 1,
            'timezone': 'auto',
        }, timeout=6)
        resp.raise_for_status()
        d = resp.json().get('daily', {})
        if not d.get('time'):
            return None
        return {
            'date':       d['time'][0],
            'temp_max_c': _idx(d.get('temperature_2m_max'), 0),
            'wind_kmh':   _idx(d.get('wind_speed_10m_max'), 0),
            'precip_prob': _idx(d.get('precipitation_probability_max'), 0),
            'precip_mm':  _idx(d.get('precipitation_sum'), 0),
        }
    except Exception:
        return None


def fetch_7day_forecast(lat: float, lon: float) -> list | None:
    """
    Fetch 7-day daily forecast from Open-Meteo (metric, includes ET0).
    Returns list of dicts or None on failure.
    """
    try:
        import requests
        resp = requests.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': lat, 'longitude': lon,
            'daily': (
                'temperature_2m_max,temperature_2m_min,'
                'precipitation_probability_max,precipitation_sum,'
                'wind_speed_10m_max,et0_fao_evapotranspiration,weather_code'
            ),
            'temperature_unit': 'celsius',
            'wind_speed_unit': 'kmh',
            'precipitation_unit': 'mm',
            'forecast_days': 7,
            'timezone': 'auto',
        }, timeout=8)
        resp.raise_for_status()
        d = resp.json().get('daily', {})
        dates = d.get('time', [])
        return [
            {
                'date':        dates[i],
                'temp_max_c':  _idx(d.get('temperature_2m_max'), i),
                'temp_min_c':  _idx(d.get('temperature_2m_min'), i),
                'precip_prob': _idx(d.get('precipitation_probability_max'), i),
                'precip_mm':   _idx(d.get('precipitation_sum'), i),
                'wind_kmh':    _idx(d.get('wind_speed_10m_max'), i),
                'et0_mm':      _idx(d.get('et0_fao_evapotranspiration'), i),
                'condition':   _WMO.get(_idx(d.get('weather_code'), i), 'Unknown'),
            }
            for i in range(len(dates))
        ]
    except Exception:
        return None


# ── Private utilities ─────────────────────────────────────────────────────────

def _idx(lst, i, default=None):
    if lst and i < len(lst):
        return lst[i]
    return default


def _majority(iterable):
    counts = {}
    for v in iterable:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get, default='medium')


_WMO = {
    0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
    45: 'Fog', 48: 'Icy fog',
    51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
    61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
    71: 'Light snow', 73: 'Snow', 75: 'Heavy snow',
    80: 'Light showers', 81: 'Showers', 82: 'Heavy showers',
    95: 'Thunderstorm', 96: 'Thunderstorm w/ hail',
}
