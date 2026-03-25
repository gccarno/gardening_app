"""
One-time script: supplement PlantLibrary with Perenual data.
- Adds scientific_name + fills missing sunlight/water for all 34 existing plants
- Adds 10 new plants from Perenual
Run: python supplement_library.py
"""
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

import requests
from app import create_app
from models import db, PlantLibrary

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
    dict(name='Strawberry',   type='fruit'),
    dict(name='Lavender',     type='herb'),
    dict(name='Sunflower',    type='flower'),
    dict(name='Sweet Potato', type='vegetable'),
    dict(name='Asparagus',    type='vegetable'),
    dict(name='Watermelon',   type='fruit'),
    dict(name='Leek',         type='vegetable'),
    dict(name='Celery',       type='vegetable'),
    dict(name='Fennel',       type='herb'),
    dict(name='Lemon Balm',   type='herb'),
]


def search(name):
    """Return first non-upgrade Perenual result for name, or None."""
    resp = requests.get(BASE_URL, params={'key': PERENUAL_KEY, 'q': name, 'page': 1}, timeout=10)
    resp.raise_for_status()
    for item in resp.json().get('data', []):
        common = (item.get('common_name') or '').lower()
        if 'upgrade' in common or 'subscription' in common:
            continue
        return item
    return None


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
    # ── Update existing 34 plants ──────────────────────────────────────────
    existing = PlantLibrary.query.order_by(PlantLibrary.name).all()
    print(f'Supplementing {len(existing)} existing plants…\n')

    for plant in existing:
        print(f'  {plant.name:<20}', end=' ', flush=True)
        try:
            item = search(plant.name)
            time.sleep(0.4)
            if not item:
                print('— no result')
                continue

            changed = []
            sci = sci_name(item)
            if sci and not plant.scientific_name:
                plant.scientific_name = sci
                changed.append(f'sci={sci}')

            sun = norm_sunlight(item.get('sunlight'))
            if sun and not plant.sunlight:
                plant.sunlight = sun
                changed.append(f'sun={sun}')

            water = norm_water(item.get('watering'))
            if water and not plant.water:
                plant.water = water
                changed.append(f'water={water}')

            print('✓ ' + (', '.join(changed) if changed else 'already complete'))
        except Exception as e:
            print(f'ERROR: {e}')

    db.session.commit()
    print('\nExisting plants saved.\n')

    # ── Add 10 new plants ─────────────────────────────────────────────────
    print(f'Adding {len(NEW_PLANTS)} new plants…\n')

    for p in NEW_PLANTS:
        name = p['name']
        already = PlantLibrary.query.filter(
            db.func.lower(PlantLibrary.name) == name.lower()
        ).first()
        if already:
            print(f'  {name:<20} — already in library, skipping')
            continue

        print(f'  {name:<20}', end=' ', flush=True)
        try:
            item = search(name)
            time.sleep(0.4)
            if not item:
                print('— no result, adding with defaults')
                db.session.add(PlantLibrary(name=name, type=p['type']))
                continue

            sci = sci_name(item)
            sun = norm_sunlight(item.get('sunlight'))
            water = norm_water(item.get('watering'))
            cycle = item.get('cycle')

            entry = PlantLibrary(
                name=name,
                scientific_name=sci,
                type=p['type'] or cycle,
                sunlight=sun,
                water=water,
            )
            db.session.add(entry)
            print(f'✓  sci={sci or "—"}  sun={sun or "—"}  water={water or "—"}')
        except Exception as e:
            print(f'ERROR: {e}')

    db.session.commit()
    print('\nDone.')
