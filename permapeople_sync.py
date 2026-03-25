"""
Bulk-sync Permapeople plant data into PlantLibrary.

- Paginates through all plants on Permapeople API (GET /api/plants)
- Matches to existing PlantLibrary entries by common name or scientific name
- Fills in missing fields (fill-in-blank) and always writes Permapeople-specific fields
- Safe to re-run: never overwrites existing non-null values

Data licensed CC BY-SA 4.0 — https://permapeople.org
Must attribute Permapeople.org and link back in any public display.

Run: python permapeople_sync.py
"""

import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

import requests
from app import create_app
from models import db, PlantLibrary

BASE_URL = 'https://permapeople.org/api'

KEY_ID     = os.getenv('X-Permapeople-Key-Id', '')
KEY_SECRET = os.getenv('X-Permapeople-Key-Secret', '')

if not KEY_ID or not KEY_SECRET:
    sys.exit('ERROR: X-Permapeople-Key-Id and X-Permapeople-Key-Secret must be set in .env')

AUTH_HEADERS = {
    'x-permapeople-key-id': KEY_ID,
    'x-permapeople-key-secret': KEY_SECRET,
}

WATER_MAP = {
    'dry': 'Low',
    'low': 'Low',
    'moist': 'Moderate',
    'medium': 'Moderate',
    'moderate': 'Moderate',
    'average': 'Moderate',
    'wet': 'High',
    'high': 'High',
    'frequent': 'High',
}

SUNLIGHT_MAP = {
    'full sun': 'Full sun',
    'full_sun': 'Full sun',
    'sun': 'Full sun',
    'partial': 'Partial shade',
    'partial sun': 'Partial shade',
    'partial shade': 'Partial shade',
    'part sun': 'Partial shade',
    'part shade': 'Partial shade',
    'dappled': 'Partial shade',
    'shade': 'Full shade',
    'full shade': 'Full shade',
}


def _pp_get(path, params=None):
    """GET from Permapeople API; return parsed JSON or raise."""
    resp = requests.get(f'{BASE_URL}/{path}', params=params, headers=AUTH_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_data(data_array):
    """Convert [{key, value}, ...] to {key: value} dict."""
    return {item['key']: item['value'] for item in (data_array or []) if 'key' in item and 'value' in item}


def norm_water(val):
    if not val:
        return None
    return WATER_MAP.get(val.lower().strip())


def norm_sunlight(val):
    if not val:
        return None
    v = val.lower().strip()
    # Try exact match first, then partial
    if v in SUNLIGHT_MAP:
        return SUNLIGHT_MAP[v]
    for key, mapped in SUNLIGHT_MAP.items():
        if key in v:
            return mapped
    return None


def parse_zone(val):
    """Parse '3-9' or '5' into (min_zone, max_zone) tuple, or (None, None)."""
    if not val:
        return None, None
    val = val.strip()
    if '-' in val:
        parts = val.split('-', 1)
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            return None, None
    try:
        z = int(val)
        return z, z
    except ValueError:
        return None, None


def fetch_all_plants():
    """Paginate through all Permapeople plants using last_id cursor."""
    all_plants = []
    last_id = None
    page = 1

    while True:
        params = {}
        if last_id is not None:
            params['last_id'] = last_id

        try:
            data = _pp_get('plants', params)
        except requests.exceptions.RequestException as e:
            print(f'  ERROR fetching page {page}: {e}')
            break

        plants = data.get('plants', [])
        if not plants:
            break

        all_plants.extend(plants)
        print(f'  Page {page}: {len(plants)} plants fetched (total so far: {len(all_plants)})')

        if len(plants) < 100:
            break  # last page

        last_id = plants[-1]['id']
        page += 1
        time.sleep(0.1)

    return all_plants


app = create_app()

with app.app_context():
    print('=== Permapeople Sync ===\n')

    print('Fetching all plants from Permapeople API…')
    pp_plants = fetch_all_plants()
    print(f'\nTotal fetched: {len(pp_plants)}\n')

    if not pp_plants:
        sys.exit('No plants returned from API. Check credentials and connectivity.')

    # Build lookup indexes from existing library
    library = PlantLibrary.query.all()
    by_name = {e.name.lower(): e for e in library}
    by_sci  = {e.scientific_name.lower(): e for e in library if e.scientific_name}

    matched_count = 0
    fields_updated = 0
    unmatched = []

    for pp in pp_plants:
        name    = (pp.get('name') or '').strip()
        sci     = (pp.get('scientific_name') or '').strip()
        pp_id   = pp.get('id')
        pp_link = pp.get('link') or (f'https://permapeople.org/plants/{pp.get("slug")}' if pp.get('slug') else None)
        desc    = (pp.get('description') or '').strip() or None

        # Match by name, then scientific name
        entry = by_name.get(name.lower()) or (by_sci.get(sci.lower()) if sci else None)

        if not entry:
            unmatched.append(name or sci or f'id={pp_id}')
            continue

        matched_count += 1
        kv = parse_data(pp.get('data', []))

        def fill(field, value):
            """Set field only if currently null; return True if changed."""
            nonlocal fields_updated
            if value and not getattr(entry, field):
                setattr(entry, field, value)
                fields_updated += 1
                return True
            return False

        def always_set(field, value):
            """Always write the value (for new Permapeople-specific fields)."""
            nonlocal fields_updated
            if value:
                setattr(entry, field, value)
                fields_updated += 1

        # Fill-in-blank for existing fields
        fill('scientific_name', sci or None)
        fill('water',    norm_water(kv.get('Water requirement')))
        fill('sunlight', norm_sunlight(kv.get('Light requirement')))
        fill('soil_type', kv.get('Soil type'))

        zone_min, zone_max = parse_zone(kv.get('USDA Hardiness zone'))
        fill('min_zone', zone_min)
        fill('max_zone', zone_max)

        # Always write Permapeople-specific fields
        entry.permapeople_id   = pp_id
        entry.permapeople_link = pp_link
        always_set('permapeople_description', desc)
        always_set('family',       kv.get('Family'))
        always_set('layer',        kv.get('Layer'))
        always_set('edible_parts', kv.get('Edible parts'))

    db.session.commit()

    print('=== Sync Complete ===')
    print(f'Total Permapeople plants fetched : {len(pp_plants)}')
    print(f'Matched to library entries       : {matched_count} / {len(library)}')
    print(f'Fields updated                   : {fields_updated}')
    if unmatched:
        sample = unmatched[:10]
        more = len(unmatched) - len(sample)
        print(f'Unmatched plants ({len(unmatched)} total)      : {", ".join(sample)}' + (f', … +{more} more' if more else ''))
