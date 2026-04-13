"""
Sync PlantLibrary nutrition data from USDA FoodData Central API.

Strategy:
  - Iterates through edible PlantLibrary entries (type: vegetable/fruit/herb/mushroom,
    or edible_parts set) in ID order
  - Searches USDA FDC by plant name (falls back to scientific name if no results)
  - Picks best match: Foundation > SR Legacy > Survey (FNDDS)
  - Fetches full nutrient detail and stores 15 key nutrients per 100g
  - Saves usda_fdc_id always; saves/overwrites nutrition JSON only if empty (or --force)
  - Progress tracked in AppSetting('usda_nutrition_sync_cursor') — resumes on next run
  - Stops cleanly on HTTP 429; gracefully handles 500/502/503 with retries

Usage:
    python scripts/usda_nutrition_sync.py --dry-run --limit 3   # smoke test
    python scripts/usda_nutrition_sync.py --limit 50            # process 50 plants
    python scripts/usda_nutrition_sync.py                       # full run (resumes)
    python scripts/usda_nutrition_sync.py --force               # re-process all
    python scripts/usda_nutrition_sync.py --plant-id 42         # single plant debug

API key: USDA_API_KEY in .env
Rate limit: 1,000 req/hr — default --delay 4.0s (~900 req/hr at 2 req/plant)
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_REPO_ROOT / 'apps' / 'backend'))

from dotenv import load_dotenv
load_dotenv()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy import or_
from app.db.session import SessionLocal
from app.db.models import PlantLibrary, AppSetting

# ── Logging ───────────────────────────────────────────────────────────────────

_LOG_DIR = _REPO_ROOT / 'logs'
_LOG_DIR.mkdir(exist_ok=True)
_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
_LOG_FILE = _LOG_DIR / f'usda_nutrition_sync_{_timestamp}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

USDA_BASE      = 'https://api.nal.usda.gov/fdc/v1'
API_KEY        = os.getenv('USDA_API_KEY', '')
SETTING_KEY    = 'usda_nutrition_sync_cursor'
DEFAULT_DELAY  = 4.0
DATATYPE_ORDER = ['Foundation', 'SR Legacy', 'Survey (FNDDS)']
EDIBLE_TYPES   = ['vegetable', 'fruit', 'herb', 'mushroom']

# USDA nutrient ID → nutrition JSON key
NUTRIENT_MAP = {
    1008: 'calories',
    1003: 'protein_g',
    1004: 'fat_g',
    1005: 'carbs_g',
    1079: 'fiber_g',
    2000: 'sugar_g',
    1087: 'calcium_mg',
    1089: 'iron_mg',
    1092: 'potassium_mg',
    1093: 'sodium_mg',
    1162: 'vitamin_c_mg',
    1106: 'vitamin_a_mcg',
    1185: 'vitamin_k_mcg',
    1190: 'folate_mcg',
    1090: 'magnesium_mg',
}

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'


def _make_retry_adapter(total=3):
    retry = Retry(
        total=total,
        read=0,
        backoff_factor=2,
        status_forcelist=[500, 502, 503],  # NOT 429 — handled manually
        respect_retry_after_header=True,
        allowed_methods=['GET', 'POST'],
    )
    return HTTPAdapter(max_retries=retry)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Sync USDA FoodData Central nutrition into PlantLibrary')
    p.add_argument('--dry-run', action='store_true',
                   help='Preview changes without writing to DB')
    p.add_argument('--limit', type=int, default=None,
                   help='Max plants to process this run')
    p.add_argument('--force', action='store_true',
                   help='Re-process plants already synced; overwrite existing nutrition JSON')
    p.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                   help=f'Seconds between HTTP requests (default: {DEFAULT_DELAY})')
    p.add_argument('--plant-id', type=int, default=None,
                   help='Process a single PlantLibrary ID (ignores cursor)')
    return p.parse_args()


# ── Progress cursor ───────────────────────────────────────────────────────────

def get_cursor(db):
    row = db.get(AppSetting, SETTING_KEY)
    return int(row.value) if row and row.value else 0


def set_cursor(db, plant_id, dry_run):
    if dry_run:
        return
    row = db.get(AppSetting, SETTING_KEY)
    if row:
        row.value = str(plant_id)
    else:
        db.add(AppSetting(key=SETTING_KEY, value=str(plant_id)))
    db.commit()


# ── DB query ──────────────────────────────────────────────────────────────────

def build_plant_query(db, force):
    q = db.query(PlantLibrary).filter(
        or_(
            PlantLibrary.type.in_(EDIBLE_TYPES),
            PlantLibrary.edible_parts.isnot(None),
        )
    ).order_by(PlantLibrary.id)
    if not force:
        q = q.filter(PlantLibrary.usda_fdc_id.is_(None))
    return q


# ── USDA API ──────────────────────────────────────────────────────────────────

def search_food(query):
    """POST /foods/search — returns (foods_list, status)."""
    try:
        r = SESSION.post(
            f'{USDA_BASE}/foods/search',
            params={'api_key': API_KEY},
            json={
                'query': query,
                'dataType': DATATYPE_ORDER,
                'pageSize': 10,
            },
            timeout=15,
        )
        if r.status_code == 429:
            return [], 'rate_limit'
        r.raise_for_status()
        data = r.json()
        return data.get('foods', []), 'ok'
    except requests.exceptions.HTTPError as e:
        return [], f'error:{e}'
    except Exception as e:
        return [], f'error:{e}'


def fetch_food_detail(fdc_id):
    """GET /food/{fdc_id} — returns (detail_dict, status)."""
    try:
        r = SESSION.get(
            f'{USDA_BASE}/food/{fdc_id}',
            params={'api_key': API_KEY},
            timeout=15,
        )
        if r.status_code == 429:
            return None, 'rate_limit'
        r.raise_for_status()
        return r.json(), 'ok'
    except requests.exceptions.HTTPError as e:
        return None, f'error:{e}'
    except Exception as e:
        return None, f'error:{e}'


# ── Matching ──────────────────────────────────────────────────────────────────

def pick_best_match(foods, entry):
    """Return the best food from the search results, or None."""
    if not foods:
        return None

    name_lower = (entry.name or '').lower()

    def _score(food):
        dt = food.get('dataType', '')
        try:
            dt_rank = DATATYPE_ORDER.index(dt)
        except ValueError:
            dt_rank = 99
        desc = (food.get('description') or '').lower()
        name_match = 0 if name_lower in desc else 1
        return (dt_rank, name_match)

    return sorted(foods, key=_score)[0]


# ── Nutrient extraction ───────────────────────────────────────────────────────

def extract_nutrients(food_detail):
    """Walk foodNutrients and return flat dict keyed by NUTRIENT_MAP values."""
    result = {}
    for fn in food_detail.get('foodNutrients', []):
        nutrient = fn.get('nutrient', {})
        nid = nutrient.get('id')
        if nid in NUTRIENT_MAP:
            amount = fn.get('amount')
            if amount is not None:
                result[NUTRIENT_MAP[nid]] = round(float(amount), 2)
    return result


def build_nutrition_json(nutrients, fdc_id, data_type):
    """Build the final nutrition dict (all values per 100g)."""
    result = {
        'serving_size':  '100g',
        'calories':      nutrients.get('calories'),
        'protein_g':     nutrients.get('protein_g'),
        'fat_g':         nutrients.get('fat_g'),
        'carbs_g':       nutrients.get('carbs_g'),
        'fiber_g':       nutrients.get('fiber_g'),
        'sugar_g':       nutrients.get('sugar_g'),
        'calcium_mg':    nutrients.get('calcium_mg'),
        'iron_mg':       nutrients.get('iron_mg'),
        'potassium_mg':  nutrients.get('potassium_mg'),
        'sodium_mg':     nutrients.get('sodium_mg'),
        'vitamin_c_mg':  nutrients.get('vitamin_c_mg'),
        'vitamin_a_mcg': nutrients.get('vitamin_a_mcg'),
        'vitamin_k_mcg': nutrients.get('vitamin_k_mcg'),
        'folate_mcg':    nutrients.get('folate_mcg'),
        'magnesium_mg':  nutrients.get('magnesium_mg'),
        'source':        'USDA FoodData Central',
        'fdc_id':        fdc_id,
        'data_type':     data_type,
    }
    # Remove keys with None values (nutrient was absent in USDA response)
    return {k: v for k, v in result.items() if v is not None}


# ── Per-plant processing ──────────────────────────────────────────────────────

def process_plant(db, entry, args, stats):
    """Process one plant. Returns disposition: 'updated'/'not_found'/'error'/'rate_limit'."""
    label = f'[{entry.id}] {entry.name} ({entry.type or "?"})'
    log.info(label)

    # ── Request 1: Search by common name ─────────────────────────────────────
    foods, status = search_food(entry.name)
    time.sleep(args.delay)

    if status == 'rate_limit':
        log.warning('  -> 429 rate limit on search')
        return 'rate_limit'
    if status.startswith('error'):
        log.error('  -> search error: %s', status)
        stats['errors'] += 1
        return 'error'

    # Fallback: try scientific name if common name search returned nothing
    if not foods and entry.scientific_name:
        log.info('  (no results for "%s", retrying with scientific name)', entry.name)
        foods, status = search_food(entry.scientific_name)
        time.sleep(args.delay)
        if status == 'rate_limit':
            log.warning('  -> 429 rate limit on fallback search')
            return 'rate_limit'
        if status.startswith('error'):
            log.error('  -> fallback search error: %s', status)
            stats['errors'] += 1
            return 'error'

    if not foods:
        log.info('  -> no USDA match found')
        stats['not_found'] += 1
        return 'not_found'

    # ── Pick best match ───────────────────────────────────────────────────────
    match = pick_best_match(foods, entry)
    if not match:
        log.info('  -> no usable match in results')
        stats['not_found'] += 1
        return 'not_found'

    fdc_id    = match.get('fdcId')
    data_type = match.get('dataType', '?')
    desc      = match.get('description', '?')
    log.info('  -> matched "%s" (%s, fdcId=%s)', desc, data_type, fdc_id)

    # ── Request 2: Fetch full nutrient detail ─────────────────────────────────
    detail, status = fetch_food_detail(fdc_id)
    time.sleep(args.delay)

    if status == 'rate_limit':
        log.warning('  -> 429 rate limit on detail fetch')
        return 'rate_limit'
    if status.startswith('error') or detail is None:
        log.error('  -> detail fetch error: %s', status)
        stats['errors'] += 1
        return 'error'

    # ── Build nutrition JSON ──────────────────────────────────────────────────
    nutrients      = extract_nutrients(detail)
    nutrition_data = build_nutrition_json(nutrients, fdc_id, data_type)

    should_write_nutrition = not entry.nutrition or args.force

    # ── Log preview ───────────────────────────────────────────────────────────
    cal = nutrition_data.get('calories', '?')
    pro = nutrition_data.get('protein_g', '?')
    fat = nutrition_data.get('fat_g', '?')
    cbh = nutrition_data.get('carbs_g', '?')
    log.info('     cal=%s protein=%sg fat=%sg carbs=%sg (%s)',
             cal, pro, fat, cbh,
             'write' if should_write_nutrition else 'skip — nutrition already set')

    # ── Write to DB ───────────────────────────────────────────────────────────
    if not args.dry_run:
        entry.usda_fdc_id = fdc_id
        if should_write_nutrition:
            entry.nutrition = json.dumps(nutrition_data)
        db.commit()
        set_cursor(db, entry.id, dry_run=False)

    stats['matched'] += 1
    return 'updated'


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        log.error('USDA_API_KEY not set in .env')
        sys.exit(1)

    args = parse_args()

    adapter = _make_retry_adapter()
    SESSION.mount('https://', adapter)
    SESSION.mount('http://', adapter)

    db = SessionLocal()
    try:
        # ── Build plant list ──────────────────────────────────────────────────
        if args.plant_id:
            plants = db.query(PlantLibrary).filter_by(id=args.plant_id).all()
            if not plants:
                log.error('PlantLibrary id=%s not found', args.plant_id)
                sys.exit(1)
        else:
            cursor = get_cursor(db)
            q = build_plant_query(db, args.force)
            if not args.force:
                q = q.filter(PlantLibrary.id > cursor)
            plants = q.all()
            if args.limit:
                plants = plants[:args.limit]

        total = len(plants)
        log.info('USDA Nutrition Sync — %d plants to process', total)
        if args.dry_run:
            log.info('  (DRY RUN — no DB writes)')
        log.info('  delay=%ss  force=%s  limit=%s', args.delay, args.force, args.limit)

        stats = {'matched': 0, 'not_found': 0, 'errors': 0}
        last_id = None

        for entry in plants:
            result = process_plant(db, entry, args, stats)
            if result == 'rate_limit':
                save_id = (last_id or 0)
                log.warning('429 received — saving progress at id=%d and stopping.', save_id)
                set_cursor(db, save_id, args.dry_run)
                break
            last_id = entry.id

        # ── Final stats ───────────────────────────────────────────────────────
        log.info('Done.')
        log.info('  Matched/updated:   %d', stats['matched'])
        log.info('  Not found in USDA: %d', stats['not_found'])
        log.info('  Errors:            %d', stats['errors'])
        log.info('  Total processed:   %d', sum(stats.values()))

        if not args.plant_id:
            cursor_now = get_cursor(db)
            log.info('Next run resumes after PlantLibrary.id = %d', cursor_now)
            log.info("To restart from beginning: delete AppSetting(key='%s') from DB", SETTING_KEY)

    finally:
        db.close()


if __name__ == '__main__':
    main()
