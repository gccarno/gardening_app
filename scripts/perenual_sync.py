"""
Sync PlantLibrary with Perenual API free tier (IDs 1–3000).

Strategy:
  - Iterates through Perenual species IDs 1–3000 sequentially via the details endpoint
  - Matches each to an existing PlantLibrary entry (by perenual_id, scientific_name,
    or common name) — or creates a new entry if no match exists
  - Fill-in-blank for most fields (never overwrites Trefle/Permapeople data)
  - Always-writes Perenual-specific boolean flags (poisonous_to_pets, invasive, etc.)
  - Progress tracked in AppSetting('perenual_sync_next_id') — resumes on next run
  - Stops cleanly on HTTP 429 (100 req/day free tier limit)
  - 100 IDs/day × 30 days = all 3,000 free-tier species

Usage:
    python scripts/perenual_sync.py --dry-run     # preview, no DB writes
    python scripts/perenual_sync.py               # process next 100 IDs
    python scripts/perenual_sync.py --limit 10    # process only 10 IDs (for testing)
    python scripts/perenual_sync.py --force       # re-process already-linked plants

API key: PERENUAL_API_KEY in .env
Rate limit: 100 req/day free tier — default --delay 1.0s, --limit 100
"""
import argparse
import hashlib
import json
import os
import sys
import time

# Windows UTF-8 fix for plant names with diacritics
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'api'))

from dotenv import load_dotenv
load_dotenv()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.main import create_app
from app.db.models import db, PlantLibrary, PlantLibraryImage, AppSetting

API_KEY     = os.getenv('PERENUAL_API_KEY', '')
BASE        = 'https://perenual.com/api'
MAX_FREE_ID = 3000

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'


def _make_retry_adapter(total=3):
    retry = Retry(
        total=total,
        read=0,
        backoff_factor=2,
        status_forcelist=[500, 502, 503],  # NOT 429 — handled manually
        respect_retry_after_header=True,
        allowed_methods=['GET'],
    )
    return HTTPAdapter(max_retries=retry)


# ── API ───────────────────────────────────────────────────────────────────────

def fetch_species(perenual_id):
    """Fetch species details for one ID.
    Returns (data_dict, status) where status is 'ok', 'rate_limit',
    'not_found', 'premium', or 'error:<msg>'."""
    try:
        r = SESSION.get(
            f'{BASE}/species/details/{perenual_id}',
            params={'key': API_KEY},
            timeout=10,
        )
        if r.status_code == 429:
            return None, 'rate_limit'
        if r.status_code == 404:
            return None, 'not_found'
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            msg = str(data.get('message', ''))
            cn  = str(data.get('common_name', ''))
            if 'Upgrade Plans' in msg or 'Upgrade Plans' in cn or 'upgrade' in cn.lower():
                return None, 'premium'
        return data, 'ok'
    except requests.exceptions.HTTPError as e:
        return None, f'error:{e}'
    except Exception as e:
        return None, f'error:{e}'


# ── Normalizers ───────────────────────────────────────────────────────────────

SUNLIGHT_MAP = {
    'full sun':       'Full sun',
    'full_sun':       'Full sun',
    'part shade':     'Partial shade',
    'part_shade':     'Partial shade',
    'partial shade':  'Partial shade',
    'filtered shade': 'Partial shade',
    'sun-part_shade': 'Partial sun',
    'part sun/shade': 'Partial sun',
    'full shade':     'Full shade',
    'full_shade':     'Full shade',
}
WATER_MAP = {
    'minimum':  'Low',
    'average':  'Moderate',
    'frequent': 'High',
    'none':     'Low',
}
TYPE_MAP = {
    'vegetable': 'vegetable',
    'herb':      'herb',
    'fruit':     'fruit',
    'tree':      'tree',
    'shrub':     'tree',
    'flower':    'flower',
    'vine':      'plant',
    'succulent': 'plant',
    'cactus':    'plant',
    'grass':     'plant',
    'fern':      'plant',
    'moss':      'plant',
    'aquatic':   'plant',
}
SEASON_MONTHS = {
    'spring': [3, 4, 5],
    'summer': [6, 7, 8],
    'fall':   [9, 10, 11],
    'autumn': [9, 10, 11],
    'winter': [12, 1, 2],
}


def _norm_sunlight(sunlight):
    if not sunlight:
        return None
    if isinstance(sunlight, list):
        sunlight = sunlight[0] if sunlight else ''
    return SUNLIGHT_MAP.get(str(sunlight).lower().strip(), str(sunlight).title() if sunlight else None)


def _norm_water(watering):
    return WATER_MAP.get((watering or '').lower().strip())


def _norm_type(type_str):
    return TYPE_MAP.get((type_str or '').lower().strip(), 'plant')


def _first(lst):
    if isinstance(lst, list):
        return lst[0] if lst else None
    return lst or None


def _to_bool(val):
    """Convert int/bool/None to bool/None. 0→False, 1+→True, None→None."""
    if val is None:
        return None
    return bool(val)


# ── Fill-in-blank merge ───────────────────────────────────────────────────────

def _blank(val):
    return val is None or str(val).strip() == ''


def merge_fill(entry, data, dry_run):
    """Fill-in-blank fields from Perenual. Returns list of (field, value) tuples."""
    changes = []

    def _set(field, value):
        if value is None:
            return
        current = getattr(entry, field, None)
        # Booleans: treat None as blank, False as populated
        if isinstance(value, bool):
            if current is None:
                changes.append((field, value))
                if not dry_run:
                    setattr(entry, field, value)
            return
        if _blank(current):
            changes.append((field, value))
            if not dry_run:
                setattr(entry, field, value)

    _set('scientific_name', _first(data.get('scientific_name')) or None)
    _set('family',          data.get('family') or None)
    _set('sunlight',        _norm_sunlight(data.get('sunlight')))
    _set('water',           _norm_water(data.get('watering')))
    _set('growth_rate',     data.get('growth_rate') or None)
    _set('difficulty',      data.get('care_level') or None)
    _set('notes',           data.get('description') or None)
    _set('duration',        data.get('cycle') or None)

    # Hardiness zones (hardiness can be a dict {min, max} or a list)
    hardiness = data.get('hardiness') or {}
    if isinstance(hardiness, list):
        hardiness = hardiness[0] if hardiness else {}
    if isinstance(hardiness, dict):
        for zone_field, zone_key in [('min_zone', 'min'), ('max_zone', 'max')]:
            raw = hardiness.get(zone_key)
            if raw is not None:
                try:
                    _set(zone_field, int(str(raw).split('-')[0].strip()))
                except (ValueError, TypeError):
                    pass

    # Soil type
    soil_list = data.get('soil') or []
    if soil_list:
        _set('soil_type', ', '.join(str(s) for s in soil_list if s))

    # Height from dimensions
    dim = data.get('dimensions') or {}
    max_val_raw = dim.get('max_value')
    if max_val_raw is not None:
        try:
            max_val = float(max_val_raw)
            unit = str(dim.get('unit', '')).lower()
            if 'ft' in unit or 'feet' in unit:
                max_val = max_val * 30.48
            elif unit in ('m', 'meter', 'meters', 'metre', 'metres'):
                max_val = max_val * 100
            _set('maximum_height_cm', int(max_val))
        except (ValueError, TypeError):
            pass

    # Edible parts
    edible_parts = []
    if data.get('edible_fruit'):
        edible_parts.append('fruit')
    if data.get('edible_leaf'):
        edible_parts.append('leaves')
    if edible_parts:
        _set('edible_parts', ', '.join(edible_parts))

    # Pruning months
    pm = data.get('pruning_month') or []
    if pm:
        _set('pruning_months', json.dumps(pm))

    # Bloom months from flowering_season
    fs = (data.get('flowering_season') or '').lower().strip()
    if fs in SEASON_MONTHS:
        _set('bloom_months', json.dumps(SEASON_MONTHS[fs]))

    return changes


# ── Always-write Perenual fields ──────────────────────────────────────────────

def write_perenual_fields(entry, data, dry_run):
    """Write Perenual-specific fields regardless of existing value."""
    changes = []

    def _write(field, value):
        if value is None:
            return
        changes.append((field, value))
        if not dry_run:
            setattr(entry, field, value)

    # Boolean flags
    for field, key in [
        ('poisonous_to_pets',   'poisonous_to_pets'),
        ('poisonous_to_humans', 'poisonous_to_humans'),
        ('drought_tolerant',    'drought_tolerant'),
        ('salt_tolerant',       'salt_tolerant'),
        ('thorny',              'thorny'),
        ('invasive',            'invasive'),
        ('rare',                'rare'),
        ('tropical',            'tropical'),
        ('indoor',              'indoor'),
        ('cuisine',             'cuisine'),
        ('medicinal',           'medicinal'),
    ]:
        _write(field, _to_bool(data.get(key)))

    # JSON arrays
    attracts = data.get('attracts') or []
    if attracts:
        _write('attracts', json.dumps(attracts))

    propagation = data.get('propagation') or []
    if propagation:
        _write('propagation_methods', json.dumps(propagation))

    # String fields
    for field, key in [
        ('harvest_season',  'harvest_season'),
        ('harvest_method',  'harvest_method'),
        ('fruiting_season', 'fruiting_season'),
    ]:
        val = data.get(key) or None
        if val:
            _write(field, val)

    return changes


# ── Image save ────────────────────────────────────────────────────────────────

def save_image(entry, url, img_dir, dry_run):
    """Download image, deduplicate by hash, save to disk + DB."""
    if not url or 'Upgrade Plans' in str(url):
        return None
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        img_bytes = r.content
        fhash = hashlib.sha256(img_bytes).hexdigest()

        if PlantLibraryImage.query.filter_by(file_hash=fhash).first():
            return None  # duplicate

        ct  = r.headers.get('content-type', '')
        ext = '.png' if 'png' in ct else '.webp' if 'webp' in ct else '.jpg'
        count = PlantLibraryImage.query.filter_by(
            plant_library_id=entry.id, source='perenual'
        ).count()
        filename = f'{entry.id}_perenual_{count + 1}{ext}'

        if dry_run:
            return filename

        dest = os.path.join(img_dir, filename)
        with open(dest, 'wb') as f:
            f.write(img_bytes)

        has_primary = PlantLibraryImage.query.filter_by(
            plant_library_id=entry.id, is_primary=True
        ).first() is not None
        db.session.add(PlantLibraryImage(
            plant_library_id=entry.id,
            filename=filename,
            source='perenual',
            source_url=url,
            file_hash=fhash,
            is_primary=not has_primary,
        ))
        return filename
    except Exception as e:
        print(f'      [image] error: {e}')
        return None


# ── Match existing plant ───────────────────────────────────────────────────────

def find_existing(perenual_id, sci_name, common_name):
    """Look up a matching PlantLibrary entry. Returns entry or None."""
    if perenual_id:
        found = PlantLibrary.query.filter_by(perenual_id=perenual_id).first()
        if found:
            return found
    if sci_name:
        found = PlantLibrary.query.filter(
            db.func.lower(PlantLibrary.scientific_name) == sci_name.lower()
        ).first()
        if found:
            return found
    if common_name:
        found = PlantLibrary.query.filter(
            db.func.lower(PlantLibrary.name) == common_name.lower()
        ).first()
        if found:
            return found
    return None


# ── Create new entry ──────────────────────────────────────────────────────────

def create_new(data, img_dir, dry_run):
    """Create a new PlantLibrary entry from Perenual species data."""
    name = (data.get('common_name') or '').strip()
    if not name:
        return None
    sci = _first(data.get('scientific_name')) or None
    typ = _norm_type(data.get('type'))

    if dry_run:
        print(f'      [dry-run] would create: {name!r} (type={typ}, sci={sci})')
        return None

    entry = PlantLibrary(
        name=name,
        scientific_name=sci,
        type=typ,
        perenual_id=data.get('id'),
        family=data.get('family') or None,
    )
    db.session.add(entry)
    db.session.flush()  # assign entry.id before saving image

    merge_fill(entry, data, dry_run=False)
    write_perenual_fields(entry, data, dry_run=False)

    img = data.get('default_image') or {}
    url = img.get('small_url') or img.get('thumbnail')
    if url:
        fname = save_image(entry, url, img_dir, dry_run=False)
        if fname:
            print(f'      [image] saved {fname}')

    db.session.commit()
    return entry


# ── AppSetting helpers ────────────────────────────────────────────────────────

def get_next_id():
    row = AppSetting.query.get('perenual_sync_next_id')
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            pass
    return 1


def set_next_id(next_id, dry_run):
    if dry_run:
        return
    row = AppSetting.query.get('perenual_sync_next_id')
    if row:
        row.value = str(next_id)
    else:
        db.session.add(AppSetting(key='perenual_sync_next_id', value=str(next_id)))
    db.session.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description='Sync PlantLibrary with Perenual free tier (IDs 1–3000)'
    )
    p.add_argument('--dry-run',  action='store_true',
                   help='Preview changes without writing to DB')
    p.add_argument('--force',    action='store_true',
                   help='Re-process plants that already have perenual_id set')
    p.add_argument('--delay',    type=float, default=1.0,
                   help='Seconds between requests (default 1.0)')
    p.add_argument('--limit',    type=int, default=100,
                   help='Max API calls per run (default 100 = daily free limit)')
    return p.parse_args()


def main():
    if not API_KEY:
        print('ERROR: PERENUAL_API_KEY not set in .env')
        sys.exit(1)

    args = parse_args()

    adapter = _make_retry_adapter(3)
    SESSION.mount('https://', adapter)
    SESSION.mount('http://',  adapter)

    flask_app = create_app()
    with flask_app.app_context():
        img_dir = os.path.join(flask_app.static_folder, 'plant_images')
        os.makedirs(img_dir, exist_ok=True)

        start_id = get_next_id()

        if start_id > MAX_FREE_ID:
            print('All 3,000 free-tier species have been processed.')
            print('To restart, set AppSetting perenual_sync_next_id to 1.')
            return

        end_id = min(start_id + args.limit, MAX_FREE_ID + 1)

        print(f'Processing Perenual IDs {start_id}–{end_id - 1}  '
              f'[dry_run={args.dry_run}, force={args.force}, '
              f'limit={args.limit}, delay={args.delay}s]\n')

        n_matched = n_added = n_premium = n_not_found = n_errors = n_updated = 0
        next_start = start_id

        for pid in range(start_id, end_id):
            print(f'[{pid}/{MAX_FREE_ID}]', end=' ', flush=True)

            data, status = fetch_species(pid)
            time.sleep(args.delay)

            if status == 'rate_limit':
                print('RATE LIMIT (429) — stopping.')
                set_next_id(pid, args.dry_run)
                break

            if status == 'not_found':
                print('not found')
                n_not_found += 1
                next_start = pid + 1
                continue

            if status == 'premium':
                print('premium-only, skipping')
                n_premium += 1
                next_start = pid + 1
                continue

            if status.startswith('error'):
                print(f'ERROR: {status}')
                n_errors += 1
                next_start = pid + 1
                continue

            common_name = (data.get('common_name') or '').strip()
            sci_name    = _first(data.get('scientific_name')) or ''
            print(f'{common_name!r}', end=' ', flush=True)

            entry = find_existing(pid, sci_name, common_name)

            if entry is None:
                name_for_new = (data.get('common_name') or '').strip()
                if not name_for_new:
                    print('→ skipped (no common_name)')
                    next_start = pid + 1
                    continue
                new_entry = create_new(data, img_dir, args.dry_run)
                if args.dry_run:
                    print(f'→ would add {name_for_new!r}')
                    n_added += 1
                elif new_entry:
                    print(f'→ added (library_id={new_entry.id})')
                    n_added += 1
                next_start = pid + 1
                continue

            # Existing plant — check if already fully synced
            if entry.perenual_id and not args.force:
                print(f'→ already synced (library_id={entry.id}), skipping')
                n_matched += 1
                next_start = pid + 1
                continue

            print(f'→ matched (library_id={entry.id})')

            try:
                fill_changes     = merge_fill(entry, data, args.dry_run)
                perenual_changes = write_perenual_fields(entry, data, args.dry_run)
                all_changes      = fill_changes + perenual_changes

                for field, value in all_changes:
                    print(f'      {field}: {str(value)[:70]}')

                if not all_changes:
                    print('      (no new fields)')

                # Image
                img = data.get('default_image') or {}
                url = img.get('small_url') or img.get('thumbnail')
                if url:
                    fname = save_image(entry, url, img_dir, args.dry_run)
                    if fname:
                        print(f'      [image] {fname}')

                if not args.dry_run:
                    entry.perenual_id = pid
                    db.session.commit()

                n_matched += 1
                if all_changes:
                    n_updated += 1

            except Exception as e:
                print(f'      ERROR: {e}')
                db.session.rollback()
                n_errors += 1

            next_start = pid + 1

        else:
            # Loop finished without break (no rate limit hit)
            set_next_id(next_start, args.dry_run)

        print(f'\nDone. '
              f'Matched: {n_matched} ({n_updated} updated)  '
              f'Added: {n_added}  '
              f'Premium/not-found: {n_premium + n_not_found}  '
              f'Errors: {n_errors}')
        print(f'Next run starts at ID: {next_start}')


if __name__ == '__main__':
    main()
