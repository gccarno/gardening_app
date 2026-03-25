"""
Backfill plant images using Wikimedia Commons (primary) and Pexels (fallback).
No rate limit on Wikimedia. Pexels requires PEXELS_API_KEY in .env.
Works for ALL plants including those without a perenual_id.
Run: python backfill_images_wiki.py
"""
import os
import re
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

PEXELS_KEY = os.getenv('PEXELS_API_KEY', '')

WIKI_API = 'https://en.wikipedia.org/w/api.php'
PEXELS_API = 'https://api.pexels.com/v1/search'

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'


def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def wiki_image_url(plant_name):
    """Query Wikipedia for the main image of a plant page. Returns thumbnail URL or None."""
    for query in [plant_name, f'{plant_name} plant']:
        resp = SESSION.get(WIKI_API, params={
            'action': 'query',
            'titles': query,
            'prop': 'pageimages',
            'piprop': 'thumbnail',
            'pithumbsize': 500,
            'pilimit': 1,
            'format': 'json',
            'redirects': 1,
        }, timeout=10)
        resp.raise_for_status()
        pages = resp.json().get('query', {}).get('pages', {})
        for page in pages.values():
            thumb = page.get('thumbnail', {})
            url = thumb.get('source')
            if url:
                # Skip SVGs and icons
                if url.lower().endswith('.svg') or 'icon' in url.lower():
                    continue
                return url
    return None


def pexels_image_url(plant_name):
    """Search Pexels for a plant photo. Returns image URL or None."""
    if not PEXELS_KEY:
        return None
    resp = SESSION.get(PEXELS_API, params={
        'query': f'{plant_name} plant vegetable garden',
        'per_page': 1,
        'orientation': 'square',
    }, headers={'Authorization': PEXELS_KEY}, timeout=10)
    if resp.status_code == 429:
        print('(Pexels rate limit)', end=' ')
        return None
    resp.raise_for_status()
    photos = resp.json().get('photos', [])
    if not photos:
        return None
    # Use medium size (~1200px) for reasonable file size
    return photos[0]['src'].get('medium') or photos[0]['src'].get('original')


def download_image(url, dest_path):
    """Download image from URL to dest_path. Retries on 429 with backoff."""
    for attempt in range(4):
        r = SESSION.get(url, timeout=20, stream=True)
        if r.status_code == 429:
            wait = 10 * (2 ** attempt)
            print(f'(429, waiting {wait}s)', end=' ', flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    raise Exception('Still getting 429 after retries')


def ext_from_url(url):
    path = url.split('?')[0].lower()
    if path.endswith('.png'):
        return '.png'
    if path.endswith('.webp'):
        return '.webp'
    if path.endswith('.gif'):
        return '.jpg'  # save gifs as jpg extension; usually still valid
    return '.jpg'


app = create_app()

with app.app_context():
    static_folder = app.static_folder
    img_dir = os.path.join(static_folder, 'plant_images')
    os.makedirs(img_dir, exist_ok=True)

    todo = (PlantLibrary.query
            .filter(PlantLibrary.image_filename.is_(None))
            .order_by(PlantLibrary.name)
            .all())

    print(f'{len(todo)} plants need images\n')
    if not PEXELS_KEY:
        print('  Note: PEXELS_API_KEY not set -- Pexels fallback disabled\n')

    saved = 0
    for entry in todo:
        print(f'  {entry.name:<25} ... ', end='', flush=True)
        try:
            # --- Try Wikimedia first ---
            url = wiki_image_url(entry.name)
            source = 'wiki'

            # --- Fall back to Pexels ---
            if not url:
                url = pexels_image_url(entry.name)
                source = 'pexels'

            if not url:
                print('no image found (wiki + pexels both empty)')
                continue

            filename = f'{slug(entry.name)}{ext_from_url(url)}'
            dest = os.path.join(img_dir, filename)

            download_image(url, dest)
            entry.image_filename = filename
            db.session.commit()
            saved += 1
            print(f'[{source}] saved as {filename}')

            time.sleep(1.5)  # be polite to Wikimedia upload server

        except Exception as e:
            print(f'ERROR: {e}')

    print(f'\nDone. Saved {saved} images.')
