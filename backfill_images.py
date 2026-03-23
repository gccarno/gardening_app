"""
Run this script to download missing plant images from Perenual.
Safe to re-run — skips plants that already have a local image.
Run: python backfill_images.py
"""
import os, time, sqlite3, requests
from dotenv import load_dotenv
load_dotenv()

KEY = os.getenv('PERENUAL_API_KEY')
if not KEY:
    raise SystemExit('PERENUAL_API_KEY not set in .env')

IMG_DIR = os.path.join(os.path.dirname(__file__), 'static', 'plant_images')
os.makedirs(IMG_DIR, exist_ok=True)

conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'instance', 'garden.db'))
plants = conn.execute(
    'SELECT id, name, perenual_id FROM plant_library '
    'WHERE perenual_id IS NOT NULL AND image_filename IS NULL ORDER BY name'
).fetchall()

if not plants:
    print('All images already downloaded.')
    conn.close()
    raise SystemExit(0)

print(f'Downloading images for {len(plants)} plants...\n')
downloaded = 0

for db_id, name, perenual_id in plants:
    print(f'  {name:<22}', end=' ', flush=True)
    r = requests.get(
        f'https://perenual.com/api/species/details/{perenual_id}',
        params={'key': KEY}, timeout=10
    )
    time.sleep(0.4)

    if r.status_code == 429:
        print('RATE LIMIT reached — run again tomorrow.')
        break
    if not r.ok:
        print(f'HTTP {r.status_code}, skipping')
        continue

    data = r.json()
    img = data.get('default_image') or {}
    url = img.get('small_url') or img.get('thumbnail')

    if not url or 'Upgrade Plans' in str(url):
        print('no image available')
        continue

    try:
        img_r = requests.get(url, timeout=10, stream=True)
        img_r.raise_for_status()
        ct = img_r.headers.get('content-type', '')
        ext = '.png' if 'png' in ct else '.webp' if 'webp' in ct else '.jpg'
        filename = f'{perenual_id}{ext}'
        with open(os.path.join(IMG_DIR, filename), 'wb') as f:
            for chunk in img_r.iter_content(8192):
                f.write(chunk)
        conn.execute('UPDATE plant_library SET image_filename=? WHERE id=?', (filename, db_id))
        conn.commit()
        print(f'saved {filename}')
        downloaded += 1
    except Exception as e:
        print(f'download error: {e}')

conn.close()
print(f'\nDone. {downloaded} images saved.')
remaining = len(plants) - downloaded
if remaining:
    print(f'{remaining} remaining — run again tomorrow.')
