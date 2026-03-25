"""
Backfill plant images from Perenual for all library entries that have a
perenual_id but no local image. Stops cleanly on 429 rate limit.
Run: python backfill_images.py
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

BASE = 'https://perenual.com/api'


def get_details(perenual_id):
    resp = requests.get(f'{BASE}/species/details/{perenual_id}',
                        params={'key': PERENUAL_KEY}, timeout=10)
    if resp.status_code == 429:
        return None, 'rate_limit'
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and 'Upgrade Plans' in str(data.get('message', '')):
        return None, 'upgrade'
    return data, None


def download_image(perenual_id, url, static_folder):
    filename = f'{perenual_id}.jpg'
    dest = os.path.join(static_folder, 'plant_images', filename)
    if os.path.exists(dest):
        return filename
    r = requests.get(url, timeout=15, stream=True)
    r.raise_for_status()
    content_type = r.headers.get('content-type', '')
    ext = '.png' if 'png' in content_type else '.webp' if 'webp' in content_type else '.jpg'
    filename = f'{perenual_id}{ext}'
    dest = os.path.join(static_folder, 'plant_images', filename)
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return filename


app = create_app()

with app.app_context():
    static_folder = app.static_folder
    os.makedirs(os.path.join(static_folder, 'plant_images'), exist_ok=True)

    todo = (PlantLibrary.query
            .filter(PlantLibrary.perenual_id.isnot(None),
                    PlantLibrary.image_filename.is_(None))
            .order_by(PlantLibrary.name)
            .all())

    print(f'{len(todo)} plants need images\n')

    saved = 0
    for entry in todo:
        print(f'  {entry.name:<25} (id={entry.perenual_id}) ... ', end='', flush=True)
        try:
            data, err = get_details(entry.perenual_id)
            time.sleep(0.4)

            if err == 'rate_limit':
                print('RATE LIMIT (429) - stopping.')
                print(f'\nSaved {saved} images before hitting the limit.')
                sys.exit(0)

            if err == 'upgrade':
                print('upgrade-only, skipping')
                continue

            if not data:
                print('no data, skipping')
                continue

            img = data.get('default_image') or {}
            url = img.get('small_url') or img.get('thumbnail')
            if not url or 'Upgrade Plans' in str(url):
                print('no image available')
                continue

            filename = download_image(entry.perenual_id, url, static_folder)
            entry.image_filename = filename
            db.session.commit()
            saved += 1
            print(f'saved as {filename}')

        except Exception as e:
            print(f'ERROR: {e}')

    print(f'\nDone. Saved {saved} images.')
