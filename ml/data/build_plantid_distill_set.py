"""
Unlabelled image set for distilling BioCLIP into a client-sized student
(see ml/docs/PLANT_ID_MODEL.md, stage 5). Distillation needs no labels — the
teacher's embedding of each photo is the target — so any plant photo helps,
and none of the eval set's labels can leak through.

Two sources, both written pre-resized (shortest side 320 px, JPEG q90) so
training isn't bottlenecked on decoding multi-megapixel Wikimedia originals:

  --library   every real (non-AI) library photo
  --inat N    N broad Plantae photos from iNaturalist (research grade,
              CC0 / CC-BY / CC-BY-NC — used for training only, never
              redistributed). Observations in the eval set are excluded.

Resumable: existing files are kept; the iNat cursor is saved.

Run:
    uv run --no-sync python ml/data/build_plantid_distill_set.py --library
    uv run --no-sync python ml/data/build_plantid_distill_set.py --inat 30000
"""
import argparse
import csv
import io
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features.plantid_data import EVAL_CSV, library_manifest  # noqa: E402

DISTILL_DIR = _ROOT / 'ml' / 'data' / 'raw' / 'plantid_distill'
STATE = DISTILL_DIR / 'inat_state.json'
API = 'https://api.inaturalist.org/v1'
HEADERS = {'User-Agent': 'garden-app-plantid-distill/1.0 (personal research; low volume)'}
LICENSES = 'cc0,cc-by,cc-by-nc'
PLANTAE = 47126
SHORT_SIDE = 320


def _save_resized(data_or_path, dest: Path) -> bool:
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = None
    try:
        src = io.BytesIO(data_or_path) if isinstance(data_or_path, bytes) else data_or_path
        img = Image.open(src)
        img.draft('RGB', (SHORT_SIDE * 2, SHORT_SIDE * 2))
        img = ImageOps.exif_transpose(img).convert('RGB')
        scale = SHORT_SIDE / min(img.size)
        if scale < 1:
            img = img.resize((round(img.width * scale), round(img.height * scale)),
                             Image.Resampling.BILINEAR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, 'JPEG', quality=90)
        return True
    except Exception:
        return False


def build_library():
    from apps.backend.app.db.session import SessionLocal
    db = SessionLocal()
    try:
        rows = library_manifest(db)
    finally:
        db.close()
    out = DISTILL_DIR / 'library'
    todo = [r for r in rows if not (out / f'{r["path"].stem}.jpg').exists()]
    print(f'{len(rows)} library photos, {len(todo)} to resize')
    with ThreadPoolExecutor(8) as pool:
        for i, _ in enumerate(pool.map(lambda r: _save_resized(r['path'], out / f'{r["path"].stem}.jpg'), todo), 1):
            if i % 500 == 0:
                print(f'  {i}/{len(todo)}')


def _eval_observations() -> set[str]:
    with EVAL_CSV.open(newline='', encoding='utf-8') as f:
        return {r['inat_observation_id'] for r in csv.DictReader(f)}


def build_inat(target: int):
    out = DISTILL_DIR / 'inat'
    out.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {'id_below': None}
    have = {p.stem for p in out.glob('*.jpg')}
    excluded = _eval_observations()
    print(f'{len(have)} iNat photos already, target {target}, {len(excluded)} eval observations excluded')

    def fetch(item):
        obs_id, url = item
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            return resp.status_code == 200 and _save_resized(resp.content, out / f'{obs_id}.jpg')
        except requests.RequestException:
            return False

    # Photos come from the AWS Open Data bucket (inaturalist-open-data), which is
    # built for bulk reads — only the API calls below are held to ~1 req/s.
    with ThreadPoolExecutor(16) as pool:
        while len(have) < target:
            params = {'taxon_id': PLANTAE, 'quality_grade': 'research', 'photos': 'true',
                      'photo_license': LICENSES, 'per_page': 200, 'order_by': 'id', 'order': 'desc'}
            if state['id_below']:
                params['id_below'] = state['id_below']
            resp = requests.get(f'{API}/observations', params=params, headers=HEADERS, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(30)
                continue
            resp.raise_for_status()
            results = resp.json().get('results', [])
            if not results:
                break
            items = []
            for obs in results:
                oid = str(obs['id'])
                if oid in have or oid in excluded or not obs.get('photos'):
                    continue
                items.append((oid, obs['photos'][0]['url'].replace('/square.', '/medium.')))
            for (oid, _), ok in zip(items, pool.map(fetch, items)):
                if ok:
                    have.add(oid)
            state['id_below'] = min(o['id'] for o in results)
            STATE.write_text(json.dumps(state))
            print(f'  {len(have)}/{target} (cursor id_below={state["id_below"]})')
            time.sleep(1.0)   # iNaturalist asks for ~1 req/s on the API


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--library', action='store_true')
    ap.add_argument('--inat', type=int, default=0, metavar='N')
    args = ap.parse_args()
    if args.library:
        build_library()
    if args.inat:
        build_inat(args.inat)


if __name__ == '__main__':
    main()
