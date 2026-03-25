"""
Add more plants to PlantLibrary from Perenual, stopping on rate limit (429).
Run: python add_more_plants.py
"""
import os
import sys
import time

# Add apps/api to sys.path so the 'app' package is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'api'))

from dotenv import load_dotenv
load_dotenv()

import requests
from app.main import create_app
from app.db.models import db, PlantLibrary

PERENUAL_KEY = os.getenv('PERENUAL_API_KEY', '')
if not PERENUAL_KEY:
    sys.exit('ERROR: PERENUAL_API_KEY not set in .env')

BASE_URL = 'https://perenual.com/api/species-list'

WATER_MAP = {'minimum': 'Low', 'average': 'Moderate', 'frequent': 'High', 'none': 'Low'}

SUNLIGHT_MAP = {
    'full sun': 'Full sun',
    'full_sun': 'Full sun',
    'part shade': 'Partial shade',
    'part_shade': 'Partial shade',
    'partial shade': 'Partial shade',
    'filtered shade': 'Partial shade',
    'full shade': 'Full shade',
    'full_shade': 'Full shade',
}

NEW_PLANTS = [
    # Vegetables
    dict(name='Artichoke',        type='vegetable'),
    dict(name='Brussels Sprouts', type='vegetable'),
    dict(name='Butternut Squash', type='vegetable'),
    dict(name='Bok Choy',         type='vegetable'),
    dict(name='Collard Greens',   type='vegetable'),
    dict(name='Edamame',          type='vegetable'),
    dict(name='Fava Bean',        type='vegetable'),
    dict(name='Kohlrabi',         type='vegetable'),
    dict(name='Lima Bean',        type='vegetable'),
    dict(name='Mustard Greens',   type='vegetable'),
    dict(name='Okra',             type='vegetable'),
    dict(name='Parsnip',          type='vegetable'),
    dict(name='Rhubarb',          type='vegetable'),
    dict(name='Shallot',          type='vegetable'),
    dict(name='Tomatillo',        type='vegetable'),
    dict(name='Turnip',           type='vegetable'),
    dict(name='Scallion',         type='vegetable'),
    dict(name='Radicchio',        type='vegetable'),
    dict(name='Endive',           type='vegetable'),
    dict(name='Acorn Squash',     type='vegetable'),
    # Fruits
    dict(name='Blueberry',        type='fruit'),
    dict(name='Cantaloupe',       type='fruit'),
    dict(name='Raspberry',        type='fruit'),
    dict(name='Blackberry',       type='fruit'),
    dict(name='Fig',              type='fruit'),
    # Herbs
    dict(name='Borage',           type='herb'),
    dict(name='Catnip',           type='herb'),
    dict(name='Chamomile',        type='herb'),
    dict(name='Lemongrass',       type='herb'),
    dict(name='Marjoram',         type='herb'),
    dict(name='Stevia',           type='herb'),
    dict(name='Tarragon',         type='herb'),
    dict(name='Lovage',           type='herb'),
    # Flowers / companions
    dict(name='Calendula',        type='flower'),
    dict(name='Marigold',         type='flower'),
    dict(name='Nasturtium',       type='flower'),
    dict(name='Zinnia',           type='flower'),
]


def search(name):
    resp = requests.get(BASE_URL, params={'key': PERENUAL_KEY, 'q': name, 'page': 1}, timeout=10)
    if resp.status_code == 429:
        raise RateLimitError()
    resp.raise_for_status()
    for item in resp.json().get('data', []):
        common = (item.get('common_name') or '').lower()
        if 'upgrade' in common or 'subscription' in common:
            continue
        return item
    return None


class RateLimitError(Exception):
    pass


def norm_sunlight(val):
    if not val:
        return None
    if isinstance(val, list):
        val = val[0] if val else ''
    return SUNLIGHT_MAP.get(val.lower().strip(), val.title())


def norm_water(val):
    return WATER_MAP.get((val or '').lower())


def sci_name(item):
    names = item.get('scientific_name') or []
    return names[0] if names else None


app = create_app()

with app.app_context():
    added = 0
    skipped = 0
    for p in NEW_PLANTS:
        name = p['name']
        already = PlantLibrary.query.filter(
            db.func.lower(PlantLibrary.name) == name.lower()
        ).first()
        if already:
            print(f'  {name:<22} — already in library, skipping')
            skipped += 1
            continue

        print(f'  {name:<22}', end=' ', flush=True)
        try:
            item = search(name)
            time.sleep(0.4)

            if not item:
                print('— no result, adding with defaults')
                db.session.add(PlantLibrary(name=name, type=p['type']))
                added += 1
                continue

            entry = PlantLibrary(
                name=name,
                scientific_name=sci_name(item),
                perenual_id=item.get('id'),
                type=p['type'],
                sunlight=norm_sunlight(item.get('sunlight')),
                water=norm_water(item.get('watering')),
            )
            db.session.add(entry)
            added += 1
            print(f'✓  id={item.get("id")}  sci={sci_name(item) or "—"}  '
                  f'sun={norm_sunlight(item.get("sunlight")) or "—"}  '
                  f'water={norm_water(item.get("watering")) or "—"}')

        except RateLimitError:
            db.session.commit()
            print(f'\n⚠  Rate limit hit (429). Saved {added} new plants before stopping.')
            sys.exit(0)
        except Exception as e:
            print(f'ERROR: {e}')

    db.session.commit()
    print(f'\nDone. Added {added} new plants, skipped {skipped} already-present.')
