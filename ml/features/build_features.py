"""
Feature engineering for the plant recommender system.

Pure Python — no Flask or SQLAlchemy dependencies.
Accepts plant dicts (serialised PlantLibrary rows) and a context dict describing
the user's garden and preferences.
"""

import json
from math import ceil
from datetime import datetime

# USDA zone → (last_spring_frost, first_fall_frost) as "Mon DD" strings
_FROST_DATES = {
    '1':  ('Jun 15', 'Aug 15'),
    '2':  ('Jun 1',  'Sep 1'),
    '3':  ('May 15', 'Sep 15'),
    '4':  ('May 1',  'Oct 1'),
    '5':  ('Apr 15', 'Oct 15'),
    '6':  ('Apr 1',  'Oct 31'),
    '7':  ('Mar 15', 'Nov 15'),
    '8':  ('Feb 15', 'Dec 1'),
    '9':  ('Jan 31', 'Dec 15'),
    '10': ('rare',   'rare'),
    '11': ('none',   'none'),
    '12': ('none',   'none'),
    '13': ('none',   'none'),
}

_MONTH_ABBR = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,  'May': 5,  'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}

# Feature weights used for the rule-based composite score
WEIGHTS = {
    'zone_match':      0.30,
    'season_match':    0.25,
    'sunlight_match':  0.20,
    'soil_ph_match':   0.10,
    'difficulty':      0.10,
    'type_preference': 0.05,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_frost_month(frost_str: str) -> int:
    """Parse 'Nov 15' → 11. Returns 12 for 'rare'/'none' (no frost concern)."""
    if not frost_str or frost_str in ('rare', 'none'):
        return 12
    parts = frost_str.split()
    return _MONTH_ABBR.get(parts[0], 12) if parts else 12


def _parse_zone(zone_str) -> int | None:
    """Parse '7a' / '7b' / '7' / 7 → 7 (int). Returns None if invalid."""
    if zone_str is None:
        return None
    digits = ''.join(c for c in str(zone_str) if c.isdigit())
    try:
        return int(digits[:2] if len(digits) > 1 else digits)
    except (ValueError, TypeError):
        return None


_MONTH_NAME_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _parse_json_list(val) -> list:
    """Parse a JSON array string or Python list into a list of ints.
    Handles both integer arrays [6, 7] and month-name arrays ['jun', 'jul'].
    Returns [] if invalid or empty."""
    if val is None:
        return []
    if isinstance(val, list):
        raw = val
    else:
        try:
            raw = json.loads(val)
            if not isinstance(raw, list):
                return []
        except (json.JSONDecodeError, TypeError):
            return []
    result = []
    for item in raw:
        if isinstance(item, int):
            result.append(item)
            continue
        s = str(item).strip().lower()
        if s in _MONTH_NAME_MAP:
            result.append(_MONTH_NAME_MAP[s])
        else:
            try:
                result.append(int(s))
            except (ValueError, TypeError):
                pass  # skip unrecognised values
    return result


# ── Individual feature functions ──────────────────────────────────────────────

def zone_match_score(plant: dict, context: dict) -> float:
    """1.0 = zone in range, 0.5 = 1 zone off or unknown, 0.0 = 2+ zones off."""
    garden_zone = _parse_zone(context.get('zone'))
    pmin = plant.get('min_zone')
    pmax = plant.get('max_zone')
    if garden_zone is None or pmin is None or pmax is None:
        return 0.5
    if pmin <= garden_zone <= pmax:
        return 1.0
    distance = max(pmin - garden_zone, garden_zone - pmax)
    return 0.5 if distance == 1 else 0.0


def sunlight_match_score(plant: dict, context: dict) -> float:
    """Compare plant sunlight need to available garden sun hours."""
    hours = context.get('sunlight_hours', 6)
    plant_sun = (plant.get('sunlight') or '').lower()

    if 'full' in plant_sun:
        plant_need = 'full'
    elif 'partial' in plant_sun or 'part' in plant_sun:
        plant_need = 'partial'
    elif 'shade' in plant_sun:
        plant_need = 'shade'
    else:
        return 0.5

    if hours >= 6:
        garden_sun = 'full'
    elif hours >= 3:
        garden_sun = 'partial'
    else:
        garden_sun = 'shade'

    if plant_need == garden_sun:
        return 1.0
    rank = {'full': 2, 'partial': 1, 'shade': 0}
    diff = abs(rank.get(plant_need, 1) - rank.get(garden_sun, 1))
    return max(0.0, 1.0 - 0.5 * diff)


def season_match_score(plant: dict, context: dict) -> float:
    """
    1.0 if it is viable to plant now and harvest before first fall frost.

    Logic:
      1. Derive target months from fruit_months → bloom_months → growth_months.
      2. earliest_plant_month = min(target) - months_to_harvest
         → planting now must be no earlier than this (current_month >= earliest_plant_month).
      3. projected_harvest_month = current_month + months_to_harvest
         → must be no later than first_fall_frost_month + 1.
    """
    current_month = context.get('current_month', datetime.now().month)
    zone_str = str(_parse_zone(context.get('zone')) or 7)

    frost_info = _FROST_DATES.get(zone_str, ('unknown', 'unknown'))
    fall_frost_month = _parse_frost_month(frost_info[1])

    days_to_harvest = plant.get('days_to_harvest') or 60
    months_to_harvest = ceil(days_to_harvest / 30)

    # Choose target season
    target = (
        _parse_json_list(plant.get('fruit_months')) or
        _parse_json_list(plant.get('bloom_months')) or
        _parse_json_list(plant.get('growth_months'))
    )

    if not target:
        # No month data — use simple frost-window check only
        projected = current_month + months_to_harvest
        return 1.0 if projected <= fall_frost_month + 1 else 0.0

    # Part 1: is it early enough to plant so the plant is ready by its target season?
    earliest_plant_month = min(target) - months_to_harvest
    if current_month < earliest_plant_month:
        return 0.0

    # Part 2: will harvest complete before first fall frost (+ 30-day buffer)?
    projected_harvest_month = current_month + months_to_harvest
    if projected_harvest_month > fall_frost_month + 1:
        return 0.0

    return 1.0


def soil_ph_match_score(plant: dict, context: dict) -> float:
    """1.0 = pH in range, 0.5 = within 0.5 units or unknown, 0.0 = >0.5 outside."""
    soil_ph = context.get('soil_ph')
    pmin = plant.get('soil_ph_min')
    pmax = plant.get('soil_ph_max')
    if soil_ph is None or pmin is None or pmax is None:
        return 0.5
    if pmin <= soil_ph <= pmax:
        return 1.0
    distance = max(pmin - soil_ph, soil_ph - pmax)
    return 0.5 if distance <= 0.5 else 0.0


def difficulty_score(plant: dict, _context: dict) -> float:
    """Easy=1.0, Moderate=0.5, Hard=0.0, unknown=0.5."""
    d = (plant.get('difficulty') or '').lower()
    return {'easy': 1.0, 'moderate': 0.5, 'hard': 0.0}.get(d, 0.5)


def companion_bonus(plant: dict, context: dict) -> float:
    """0.2 if plant is listed as a good neighbor of any current garden plant."""
    current = {n.lower() for n in context.get('current_plant_names', [])}
    if not current:
        return 0.0
    for neighbor in _parse_json_list(plant.get('good_neighbors')):
        if isinstance(neighbor, str) and neighbor.lower() in current:
            return 0.2
    return 0.0


def type_preference_score(plant: dict, context: dict) -> float:
    """1.0 if plant.type matches user preferences, 0.5 otherwise."""
    prefs = [t.lower() for t in context.get('preferred_types', [])]
    if not prefs:
        return 0.5
    return 1.0 if (plant.get('type') or '').lower() in prefs else 0.5


# ── Public API ────────────────────────────────────────────────────────────────

def build_feature_vector(plant: dict, context: dict) -> dict:
    """Return a dict of named feature values, each in [0, 1] (companion may be 0 or 0.2)."""
    return {
        'zone_match':      zone_match_score(plant, context),
        'season_match':    season_match_score(plant, context),
        'sunlight_match':  sunlight_match_score(plant, context),
        'soil_ph_match':   soil_ph_match_score(plant, context),
        'difficulty':      difficulty_score(plant, context),
        'type_preference': type_preference_score(plant, context),
        'companion_bonus': companion_bonus(plant, context),
    }


def score_plant(plant: dict, context: dict) -> float:
    """Weighted sum of features + companion bonus. Returns float in [0, ~1.2]."""
    fv = build_feature_vector(plant, context)
    base = sum(WEIGHTS.get(k, 0.0) * v for k, v in fv.items() if k != 'companion_bonus')
    return round(base + fv['companion_bonus'], 4)


def top_reason(fv: dict, context: dict) -> str:
    """Return a short human-readable explanation based on the feature vector."""
    parts = []
    if fv.get('zone_match', 0) == 1.0 and context.get('zone'):
        parts.append(f"Zone {context['zone']} match")
    if fv.get('season_match', 0) == 1.0:
        parts.append('good planting timing')
    if fv.get('sunlight_match', 0) == 1.0:
        parts.append('sunlight match')
    if fv.get('companion_bonus', 0) > 0:
        parts.append('companion plant')
    if fv.get('difficulty', 0) == 1.0:
        parts.append('beginner-friendly')
    if parts:
        return 'Good match: ' + ', '.join(parts)
    if fv.get('season_match', 0) == 0.0:
        return 'Check planting timing for your zone'
    if fv.get('zone_match', 0) == 0.0:
        return 'Marginal zone fit — check hardiness'
    return 'See plant details for care tips'
