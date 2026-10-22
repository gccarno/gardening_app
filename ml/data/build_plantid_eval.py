"""
Build the held-out evaluation set for the plant-ID model (see
ml/docs/PLANT_ID_MODEL.md, stage 3/6).

The library's own photos can't be the test set: they're what the model's
prototypes are built from. Instead this pulls *real-world* photos from
iNaturalist — research-grade observations, CC0 / CC-BY only — for a random
sample of library species, one photo per observation so a test species isn't
five shots of the same plant.

Labels are species, not library entries: many library rows are cultivars that
share a scientific name (23 rows are Capsicum annuum), and no photo can tell
them apart. `species_key` is the normalised scientific name.

Leakage guards: photos whose SHA-256 matches a plant_library_image.file_hash,
or whose iNaturalist photo id appears in a library source_url, are dropped.

Resumable — species already in the CSV are skipped, downloaded files are kept.
Requires DATABASE_URL (reads the live DB, read-only).

Run:
    uv run python ml/data/build_plantid_eval.py                 # 300 species x 5
    uv run python ml/data/build_plantid_eval.py --species 50    # smaller
"""
import argparse
import csv
import hashlib
import random
import re
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features.plantid_data import EVAL_CSV as CSV_PATH, species_key  # noqa: E402

IMG_DIR = _ROOT / 'ml' / 'data' / 'raw' / 'plantid_eval'
API = 'https://api.inaturalist.org/v1'
HEADERS = {'User-Agent': 'garden-app-plantid-eval/1.0 (personal research; low volume)'}
LICENSES = 'cc0,cc-by'
MIN_LIBRARY_IMAGES = 3   # species need enough library photos to form a prototype
CROP_MIN_ENTRIES = 3
SEED = 42
FIELDS = ['species_key', 'scientific_name', 'inat_taxon_id', 'inat_observation_id',
          'inat_photo_id', 'path', 'license', 'attribution', 'observed_on', 'is_crop']


def _get(path: str, **params) -> dict:
    for attempt in range(4):
        resp = requests.get(f'{API}{path}', params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        time.sleep(1.0)   # iNaturalist asks for ~1 req/s
        return resp.json()
    resp.raise_for_status()
    return {}


def _library_species(db) -> tuple[list[str], set[str], set[str], set[str]]:
    """Return (eligible species keys, crop species keys, known image hashes,
    library iNat photo ids).

    "Crop" = a species with >= CROP_MIN_ENTRIES library rows, or any row typed
    vegetable/herb. PlantLibrary.type is NULL for ~89% of rows, so cultivar
    count is the main proxy for a garden crop (Capsicum annuum has 23 rows,
    wild species have one); the typed rows are the hand-curated originals
    and catch crops like tomato that have few cultivar rows.
    """
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT p.scientific_name, count(*) AS n
        FROM plant_library p
        JOIN plant_library_image i ON i.plant_library_id = p.id
        WHERE i.source <> 'ai-generated' AND coalesce(p.scientific_name, '') <> ''
        GROUP BY p.scientific_name
    """)).all()
    counts: dict[str, int] = {}
    for sci, n in rows:
        counts[species_key(sci)] = counts.get(species_key(sci), 0) + n
    # Library rows per species, photographed or not — the cultivar count.
    entries: dict[str, int] = {}
    typed: set[str] = set()
    for sci, ptype in db.execute(text(
            "SELECT scientific_name, type FROM plant_library WHERE coalesce(scientific_name, '') <> ''")):
        entries[species_key(sci)] = entries.get(species_key(sci), 0) + 1
        if ptype in ('vegetable', 'herb'):
            typed.add(species_key(sci))
    # Mojibake names (e.g. a mangled hybrid ×) can't be matched to a taxon.
    eligible = sorted(k for k, n in counts.items()
                      if n >= MIN_LIBRARY_IMAGES and k.isascii() and ' ' in k)

    hashes = {h for (h,) in db.execute(text('SELECT file_hash FROM plant_library_image'))}
    photo_ids = set()
    for (url,) in db.execute(text(
            "SELECT source_url FROM plant_library_image WHERE source_url LIKE '%inaturalist%'")):
        photo_ids.update(re.findall(r'photos/(\d+)', url or ''))
    crops = {k for k in eligible if entries[k] >= CROP_MIN_ENTRIES or k in typed}
    return eligible, crops, hashes, photo_ids


# Library names like 'Brassica oleracea capitata' are varieties on iNaturalist,
# which spells them 'Brassica oleracea var. capitata'.
_RANKS = ('species', 'hybrid', 'subspecies', 'variety', 'form')


def _strip_rank(name: str) -> str:
    return re.sub(r'\b(var|subsp|ssp|f)\.\s*', '', name)


def _taxon_id(name: str) -> int | None:
    data = _get('/taxa', q=name, is_active='true', per_page=5)
    for t in data.get('results', []):
        if t.get('rank') in _RANKS and species_key(_strip_rank(t['name'])) == name:
            return t['id']
    return None


def _fetch_species(name: str, per_species: int, hashes: set[str], lib_photo_ids: set[str]) -> list[dict]:
    taxon = _taxon_id(name)
    if taxon is None:
        return []
    data = _get('/observations', taxon_id=taxon, quality_grade='research',
                photo_license=LICENSES, photos='true', per_page=per_species * 3,
                order_by='votes')
    rows = []
    for obs in data.get('results', []):
        photo = next((p for p in obs.get('photos', [])
                      if (p.get('license_code') or '') in LICENSES.split(',')), None)
        if photo is None or str(photo['id']) in lib_photo_ids:
            continue
        url = photo['url'].replace('/square.', '/medium.')
        dest = IMG_DIR / f"{photo['id']}.jpg"
        if not dest.exists():
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                continue
            if hashlib.sha256(resp.content).hexdigest() in hashes:
                continue
            dest.write_bytes(resp.content)
            time.sleep(0.5)
        rows.append({
            'species_key': name,
            'scientific_name': obs['taxon']['name'],
            'inat_taxon_id': taxon,
            'inat_observation_id': obs['id'],
            'inat_photo_id': photo['id'],
            'path': dest.relative_to(_ROOT).as_posix(),
            'license': photo['license_code'],
            'attribution': photo.get('attribution', ''),
            'observed_on': obs.get('observed_on') or '',
        })
        if len(rows) == per_species:
            break
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--species', type=int, default=300)
    ap.add_argument('--per-species', type=int, default=5)
    args = ap.parse_args()

    from apps.backend.app.db.session import SessionLocal
    db = SessionLocal()
    try:
        eligible, crops, hashes, lib_photo_ids = _library_species(db)
    finally:
        db.close()
    print(f'{len(eligible)} eligible species ({len(crops)} crops), {len(hashes)} library hashes')

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if CSV_PATH.exists():
        with CSV_PATH.open(newline='', encoding='utf-8') as f:
            done = {r['species_key'] for r in csv.DictReader(f)}

    # Crops first so the garden-relevant slice is fully represented, then a
    # random fill from the rest of the library.
    rng = random.Random(SEED)
    crop_order = sorted(crops)
    rest = [k for k in eligible if k not in crops]
    rng.shuffle(crop_order)
    rng.shuffle(rest)
    order = crop_order + rest
    new_file = not CSV_PATH.exists()
    with CSV_PATH.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for name in order:
            if len(done) >= args.species:
                break
            if name in done:
                continue
            try:
                rows = _fetch_species(name, args.per_species, hashes, lib_photo_ids)
            except requests.RequestException as exc:
                print(f'  {name}: {exc}')
                continue
            # Only keep species with a full quota — keeps per-species weight equal.
            if len(rows) < args.per_species:
                print(f'  {name}: only {len(rows)} usable photos, skipped')
                continue
            for r in rows:
                r['is_crop'] = int(name in crops)
            writer.writerows(rows)
            f.flush()
            done.add(name)
            print(f'[{len(done)}/{args.species}] {name}')

    # Re-derive is_crop for every row, so rows written by an earlier run under
    # a different crop definition stay consistent.
    with CSV_PATH.open(newline='', encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))
    for r in all_rows:
        r['is_crop'] = int(r['species_key'] in crops)
    with CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f'done — {len(done)} species in {CSV_PATH.relative_to(_ROOT)}')


if __name__ == '__main__':
    main()
