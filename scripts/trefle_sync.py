"""
Enrich PlantLibrary with Trefle API data.

Trefle (trefle.io) is a botanical plant database with 420k+ species covering
soil pH, temperature, spacing, days to harvest, light/water requirements,
phenology, flower/foliage/fruit characteristics, toxicity, and more.

Strategy:
  - Fill-in-blank only — never overwrites populated fields
  - Idempotent — already-synced plants are skipped unless --force
  - Two API calls per plant: search then detail fetch (for full growth object)
  - --add-new — insert plants found in Trefle but not in library
  - --fetch-images — download Trefle images to disk (no DB insert yet)

Usage:
    python scripts/trefle_sync.py --dry-run                      # preview all plants
    python scripts/trefle_sync.py --plant-id 1 --dry-run
    python scripts/trefle_sync.py                                # live run
    python scripts/trefle_sync.py --add-new                      # also add new plants
    python scripts/trefle_sync.py --plant-id 1 --fetch-images
    python scripts/trefle_sync.py --force                        # re-sync already-synced
    python scripts/trefle_sync.py --limit 5 --dry-run            # safe test on 5 plants
    python scripts/trefle_sync.py --limit 5 --log-level DEBUG    # diagnose field coverage
    python scripts/trefle_sync.py --log-level DEBUG --dry-run    # full diagnostic dry run
    python scripts/trefle_sync.py --log-file /tmp/sync.log       # custom log file

API key: TREFLE_API_KEY in .env
Rate limit: 120 req/min — default --delay 0.6s
"""
import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict

# Ensure stdout can handle Unicode on Windows (cp1252 terminals choke on some plant names)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'backend'))

from dotenv import load_dotenv
load_dotenv()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.db.session import SessionLocal
from app.db.models import PlantLibrary

logger = logging.getLogger('trefle_sync')

_stats_trefle_provided     = defaultdict(int)
_stats_set                 = defaultdict(int)
_stats_skipped_already_set = defaultdict(int)


def _setup_logging(level_name: str, log_file=None) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(sh)
    log_dir = os.path.join(_REPO_ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    fh_path = log_file or os.path.join(log_dir, 'trefle_sync.log')
    fh = logging.FileHandler(fh_path, encoding='utf-8')
    fh.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger.addHandler(fh)


TREFLE_BASE = 'https://trefle.io/api/v1'
API_KEY     = os.getenv('TREFLE_API_KEY', '')

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'


def _make_retry_adapter(total=3):
    retry = Retry(
        total=total,
        read=0,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503],
        respect_retry_after_header=True,
        allowed_methods=['GET'],
    )
    return HTTPAdapter(max_retries=retry)


# ── API helpers ────────────────────────────────────────────────────────────────

def trefle_get(path, params=None, timeout=10):
    """GET a Trefle endpoint. Returns parsed JSON data dict or None."""
    p = dict(params or {})
    p['token'] = API_KEY
    try:
        r = SESSION.get(f'{TREFLE_BASE}{path}', params=p, timeout=timeout)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        logger.debug(
            f'  [api] {path} -> keys: '
            f'{list(data.keys()) if isinstance(data, dict) else type(data).__name__}'
        )
        return data
    except Exception as e:
        logger.warning(f'    API error: {e}')
        return None


def search_species(query):
    """Search Trefle species. Returns list of result dicts or []."""
    resp = trefle_get('/species/search', {'q': query})
    if resp is None:
        return []
    return resp.get('data') or []


def fetch_species_detail(slug):
    """Fetch full species record by slug. Returns attributes dict or None."""
    resp = trefle_get(f'/species/{slug}')
    if resp is None:
        return None
    detail = resp.get('data')
    if detail is not None:
        growth = detail.get('growth') or {}
        logger.debug(
            f'  [detail] {slug}: top-level keys={list(detail.keys())}, '
            f'growth keys={list(growth.keys())}'
        )
    return detail


def best_match(results, entry):
    """Pick the best-matching species from a list of search results.
    Priority: exact common name → exact scientific name → first result."""
    name_lower = entry.name.lower()
    sci_lower  = (entry.scientific_name or '').lower()

    for r in results:
        if (r.get('common_name') or '').lower() == name_lower:
            return r
    for r in results:
        if (r.get('scientific_name') or '').lower() == name_lower:
            return r
    for r in results:
        if sci_lower and (r.get('scientific_name') or '').lower() == sci_lower:
            return r
    return results[0] if results else None


# ── Scale converters ───────────────────────────────────────────────────────────

def _light_to_sunlight(v):
    if v is None:
        return None
    if v <= 3:
        return 'Partial shade'
    if v <= 6:
        return 'Partial sun'
    return 'Full sun'


def _humidity_to_water(v):
    if v is None:
        return None
    if v <= 3:
        return 'Low'
    if v <= 6:
        return 'Moderate'
    return 'High'


def _texture_to_soil_type(v):
    if v is None:
        return None
    if v <= 2:
        return 'Clay'
    if v <= 5:
        return 'Loam'
    if v <= 7:
        return 'Sandy loam'
    return 'Sandy/Rocky'


def _c_to_f(c):
    if c is None:
        return None
    return round(float(c) * 9 / 5 + 32)


def _cm_to_in(cm):
    if cm is None:
        return None
    return max(1, round(float(cm) / 2.54))


def _join_array(arr):
    if not arr:
        return None
    return ', '.join(str(x) for x in arr if x is not None)


def _get_nested(d, *keys):
    """Safely traverse nested dicts: _get_nested(d, 'growth', 'spread', 'cm')"""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


# ── Field merge ────────────────────────────────────────────────────────────────

def _blank(val):
    return val is None or str(val).strip() == ''


def merge_fields(entry, species, dry_run):
    """Fill-in-blank merge of Trefle species data into a PlantLibrary entry.
    Returns list of (field, value, note) tuples for changed fields."""
    g     = species.get('growth') or {}
    specs = species.get('specifications') or {}
    changes = []

    def _set(field, value, note=''):
        if value is None:
            logger.debug(f'    {field}: null in Trefle response')
            return
        _stats_trefle_provided[field] += 1
        current = getattr(entry, field, None)
        # For booleans, treat None as blank but don't treat False as blank
        if isinstance(value, bool):
            if current is None:
                _stats_set[field] += 1
                changes.append((field, value, note))
                if not dry_run:
                    setattr(entry, field, value)
            else:
                _stats_skipped_already_set[field] += 1
                logger.debug(f'    {field}: already set, skipping')
            return
        if _blank(current):
            _stats_set[field] += 1
            changes.append((field, value, note))
            if not dry_run:
                setattr(entry, field, value)
        else:
            _stats_skipped_already_set[field] += 1
            logger.debug(f'    {field}: already set ({str(current)[:40]!r}), skipping')

    # ── Core / taxonomy ────────────────────────────────────────────────────
    _set('scientific_name', species.get('scientific_name') or None)
    _set('family',          species.get('family') or None)
    _set('genus',           species.get('genus') or None)

    edible_val = species.get('edible')
    if edible_val is not None:
        _set('edible', bool(edible_val))

    # ── Growing conditions ─────────────────────────────────────────────────
    _set('sunlight', _light_to_sunlight(g.get('light')),
         note=f'from light={g.get("light")}')
    _set('water', _humidity_to_water(g.get('soil_humidity')),
         note=f'from soil_humidity={g.get("soil_humidity")}')
    _set('soil_type', _texture_to_soil_type(g.get('soil_texture')),
         note=f'from soil_texture={g.get("soil_texture")}')

    _set('soil_ph_min', g.get('ph_minimum'))
    _set('soil_ph_max', g.get('ph_maximum'))

    min_c = _get_nested(g, 'minimum_temperature', 'deg_c')
    max_c = _get_nested(g, 'maximum_temperature', 'deg_c')
    _set('temp_min_f', _c_to_f(min_c), note=f'from {min_c}C')
    _set('temp_max_f', _c_to_f(max_c), note=f'from {max_c}C')

    hz_min = species.get('hardiness_zone_united_states_min')
    hz_max = species.get('hardiness_zone_united_states_max')
    logger.debug(
        f'    hardiness zone raw: min={hz_min!r}, max={hz_max!r} | '
        f'zone-related keys: {[k for k in species if "zone" in k.lower() or "hardi" in k.lower()]}'
    )
    _set('min_zone', hz_min)
    _set('max_zone', hz_max)

    # spacing: prefer row_spacing, fall back to spread
    rs_cm = _get_nested(g, 'row_spacing', 'cm')
    sp_cm = _get_nested(g, 'spread', 'cm')
    if rs_cm is not None:
        _set('spacing_in', _cm_to_in(rs_cm), note=f'from row_spacing={rs_cm}cm')
    elif sp_cm is not None:
        _set('spacing_in', _cm_to_in(sp_cm), note=f'from spread={sp_cm}cm')

    _set('days_to_harvest', g.get('days_to_harvest'))

    edible_parts = species.get('edible_part')
    if isinstance(edible_parts, list):
        _set('edible_parts', _join_array(edible_parts))

    _set('notes', g.get('sowing') or None)
    _set('permapeople_description', g.get('description') or None)

    # ── New Trefle fields ──────────────────────────────────────────────────
    # toxicity, ligneous_type, growth_* and height are under 'specifications'
    _set('toxicity',          specs.get('toxicity') or None)

    dur = species.get('duration')
    _set('duration', _join_array(dur) if isinstance(dur, list) else dur or None)

    _set('ligneous_type',     specs.get('ligneous_type') or None)
    _set('growth_habit',      specs.get('growth_habit') or None)
    _set('growth_form',       specs.get('growth_form') or None)
    _set('growth_rate',       specs.get('growth_rate') or None)
    _set('nitrogen_fixation', specs.get('nitrogen_fixation') or None)
    _set('observations',      species.get('observations') or None)

    veg = species.get('vegetable')
    if veg is not None:
        _set('vegetable', bool(veg))

    avg_h = _get_nested(specs, 'average_height', 'cm')
    max_h = _get_nested(specs, 'maximum_height', 'cm')
    _set('average_height_cm', int(avg_h) if avg_h is not None else None)
    _set('maximum_height_cm', int(max_h) if max_h is not None else None)

    _set('spread_cm',             int(sp_cm) if sp_cm is not None else None)
    _set('row_spacing_cm',        int(rs_cm) if rs_cm is not None else None)

    rd_cm = _get_nested(g, 'minimum_root_depth', 'cm')
    _set('minimum_root_depth_cm', int(rd_cm) if rd_cm is not None else None)

    _set('soil_nutriments',    g.get('soil_nutriments'))
    _set('soil_salinity',      g.get('soil_salinity'))
    _set('atmospheric_humidity', g.get('atmospheric_humidity'))

    p_min = _get_nested(g, 'minimum_precipitation', 'mm')
    p_max = _get_nested(g, 'maximum_precipitation', 'mm')
    _set('precipitation_min_mm', int(p_min) if p_min is not None else None)
    _set('precipitation_max_mm', int(p_max) if p_max is not None else None)

    bm = g.get('bloom_months')
    fm = g.get('fruit_months')
    gm = g.get('growth_months')
    _set('bloom_months',  json.dumps(bm) if isinstance(bm, list) else None)
    _set('fruit_months',  json.dumps(fm) if isinstance(fm, list) else None)
    _set('growth_months', json.dumps(gm) if isinstance(gm, list) else None)

    flower  = species.get('flower') or {}
    foliage = species.get('foliage') or {}
    fos     = species.get('fruit_or_seed') or {}

    fc = flower.get('color')
    _set('flower_color', _join_array(fc) if isinstance(fc, list) else fc or None)
    if flower.get('conspicuous') is not None:
        _set('flower_conspicuous', bool(flower['conspicuous']))

    fol_c = foliage.get('color')
    _set('foliage_color',   _join_array(fol_c) if isinstance(fol_c, list) else fol_c or None)
    _set('foliage_texture', foliage.get('texture') or None)
    if foliage.get('leaf_retention') is not None:
        _set('leaf_retention', bool(foliage['leaf_retention']))

    fr_c = fos.get('color')
    _set('fruit_color', _join_array(fr_c) if isinstance(fr_c, list) else fr_c or None)
    _set('fruit_shape', fos.get('shape') or None)
    if fos.get('conspicuous') is not None:
        _set('fruit_conspicuous', bool(fos['conspicuous']))
    if fos.get('seed_persistence') is not None:
        _set('seed_persistence', bool(fos['seed_persistence']))

    return changes


# ── Image fetch (disk only, no DB insert) ─────────────────────────────────────

def fetch_images_to_disk(entry, species, img_dir, dry_run):
    """Download Trefle images to static/plant_images/. No DB rows created."""
    images = species.get('images') or {}
    saved = 0
    for category, items in images.items():
        if not isinstance(items, list):
            continue
        for n, img in enumerate(items, 1):
            url = img.get('image_url') or img.get('url')
            if not url:
                continue
            fname = f'trefle_{entry.id}_{category}_{n}.jpg'
            dest  = os.path.join(img_dir, fname)
            if os.path.exists(dest):
                logger.debug(f'      [image] {fname} already exists, skipping')
                continue
            if dry_run:
                logger.info(f'      [image-dry] would save {fname}  ({url[:60]})')
                saved += 1
                continue
            try:
                r = SESSION.get(url, timeout=15)
                r.raise_for_status()
                with open(dest, 'wb') as f:
                    f.write(r.content)
                logger.info(f'      [image] saved {fname}')
                saved += 1
            except Exception as e:
                logger.error(f'      [image] error {fname}: {e}')
    return saved


# ── New plant creation ─────────────────────────────────────────────────────────

def create_from_trefle(session, species, dry_run):
    """Create a new PlantLibrary entry from a Trefle species dict."""
    name = (species.get('common_name') or species.get('scientific_name') or '').strip()
    if not name:
        return None
    if dry_run:
        logger.info(f'    [dry-run] would add: {name}')
        return None
    entry = PlantLibrary(
        name            = name,
        scientific_name = species.get('scientific_name') or None,
        family          = species.get('family') or None,
        trefle_id       = species.get('id'),
        trefle_slug     = species.get('slug'),
    )
    session.add(entry)
    session.flush()
    merge_fields(entry, species, dry_run=False)
    session.commit()
    logger.info(f'    [added] {name} (trefle id={species.get("id")})')
    return entry


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Sync PlantLibrary with Trefle API')
    p.add_argument('--plant-id',     type=int,   default=None)
    p.add_argument('--dry-run',      action='store_true')
    p.add_argument('--force',        action='store_true',
                   help='Re-sync even if trefle_id already set')
    p.add_argument('--add-new',      action='store_true',
                   help='Add plants found in Trefle but not in library')
    p.add_argument('--fetch-images', action='store_true',
                   help='Download Trefle images to disk (no DB insert)')
    p.add_argument('--delay',        type=float, default=0.6,
                   help='Seconds between requests (default 0.6; limit is 120/min)')
    p.add_argument('--limit',        type=int,   default=None,
                   help='Process only the first N plants (useful for testing)')
    p.add_argument('--log-level',    default='INFO',
                   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                   help='Logging verbosity (default: INFO)')
    p.add_argument('--log-file',     default=None,
                   help='Write logs to this path (default: logs/trefle_sync.log)')
    return p.parse_args()


def main():
    args = parse_args()
    _setup_logging(args.log_level, args.log_file)

    if not API_KEY:
        logger.error('ERROR: TREFLE_API_KEY not set in .env')
        sys.exit(1)

    adapter = _make_retry_adapter(3)
    SESSION.mount('https://', adapter)
    SESSION.mount('http://',  adapter)

    img_dir = os.path.join(_REPO_ROOT, 'apps', 'api', 'static', 'plant_images')
    os.makedirs(img_dir, exist_ok=True)

    db = SessionLocal()
    try:
        if args.plant_id:
            plants = db.query(PlantLibrary).filter_by(id=args.plant_id).all()
        else:
            plants = db.query(PlantLibrary).order_by(PlantLibrary.name).all()

        if args.limit is not None:
            plants = plants[:args.limit]

        logger.info(
            f'{len(plants)} plant(s) to process  '
            f'[dry_run={args.dry_run}, add_new={args.add_new}, '
            f'force={args.force}, fetch_images={args.fetch_images}, '
            f'delay={args.delay}s]\n'
        )

        n_updated = n_skipped = n_no_match = n_errors = n_added = 0

        for entry in plants:
            if entry.trefle_id and not args.force:
                logger.info(f'  {entry.name:<32} already synced (id={entry.trefle_id}), skipping')
                n_skipped += 1
                continue

            t0 = time.time()

            # Search
            results = search_species(entry.name)
            time.sleep(args.delay)

            if not results and entry.scientific_name:
                results = search_species(entry.scientific_name)
                time.sleep(args.delay)

            if not results:
                logger.info(f'  {entry.name:<32} -> no match  ({time.time()-t0:.1f}s)')
                n_no_match += 1
                continue

            match = best_match(results, entry)
            if not match:
                logger.info(f'  {entry.name:<32} -> no match  ({time.time()-t0:.1f}s)')
                n_no_match += 1
                continue

            # Fetch full detail for growth sub-object
            slug = match.get('slug', '')
            detail = fetch_species_detail(slug) if slug else None
            time.sleep(args.delay)

            if detail is None:
                logger.warning(
                    f'  {entry.name}: detail fetch failed for slug={slug!r} — '
                    f'falling back to search result. Growth fields (sunlight, water, '
                    f'soil, temp, spacing, days_to_harvest, etc.) will all be null.'
                )
                species = match
            else:
                species = detail

            trefle_id   = species.get('id')
            trefle_name = species.get('common_name') or species.get('scientific_name', '?')
            logger.info(
                f'  {entry.name:<32} -> matched "{trefle_name}" '
                f'(id={trefle_id})  ({time.time()-t0:.1f}s)'
            )

            try:
                changes = merge_fields(entry, species, args.dry_run)

                for field, value, note in changes:
                    display = str(value)[:60]
                    suffix  = f'  [{note}]' if note else ''
                    logger.info(f'      {field}: {display}{suffix}')

                if not changes:
                    logger.debug('      (no new fields to fill)')

                if not args.dry_run:
                    entry.trefle_id   = trefle_id
                    entry.trefle_slug = slug
                    db.commit()

                if args.fetch_images:
                    fetch_images_to_disk(entry, species, img_dir, args.dry_run)

                if changes:
                    n_updated += 1

            except Exception as e:
                logger.error(f'      ERROR during merge: {e}')
                db.rollback()
                n_errors += 1

        # --add-new: try common garden plants not yet in library
        if args.add_new:
            logger.info('\n--- Scanning for new plants ---')
            known = {p.name.lower() for p in db.query(PlantLibrary).all()}
            candidates = [
                'Artichoke', 'Asparagus', 'Bok Choy', 'Brussels Sprouts',
                'Butternut Squash', 'Celery', 'Chicory', 'Chives', 'Collard Greens',
                'Endive', 'Fennel', 'Horseradish', 'Kohlrabi', 'Leek',
                'Mustard Greens', 'Parsnip', 'Rutabaga', 'Sorrel',
                'Summer Squash', 'Tomatillo', 'Turnip', 'Watercress', 'Winter Squash',
            ]
            for name in candidates:
                if name.lower() in known:
                    continue
                results = search_species(name)
                time.sleep(args.delay)
                if not results:
                    logger.info(f'  {name:<32} -> no match')
                    continue
                match = best_match(results, type('_', (), {'name': name, 'scientific_name': None})())
                if not match:
                    logger.info(f'  {name:<32} -> no match')
                    continue
                slug   = match.get('slug', '')
                detail = fetch_species_detail(slug) if slug else None
                time.sleep(args.delay)
                species = detail if detail else match
                tname   = species.get('common_name') or name
                logger.info(f'  {name:<32} -> {tname}')
                new_entry = create_from_trefle(db, species, args.dry_run)
                if new_entry:
                    n_added += 1
                    known.add(name.lower())

    finally:
        db.close()

    # Field coverage summary
    all_fields = sorted(
        set(_stats_trefle_provided) | set(_stats_set) | set(_stats_skipped_already_set)
    )
    if all_fields:
        logger.info('\n── Field coverage (Trefle → this run) ─────────────────')
        logger.info(f'  {"Field":<30} {"Provided":>9} {"Set":>8} {"AlreadySet":>11}')
        logger.info(f'  {"-"*30} {"-"*9} {"-"*8} {"-"*11}')
        for f in all_fields:
            logger.info(
                f'  {f:<30} {_stats_trefle_provided[f]:>9} '
                f'{_stats_set[f]:>8} {_stats_skipped_already_set[f]:>11}'
            )

    logger.info(
        f'\nDone.  Updated: {n_updated}  Already synced: {n_skipped}  '
        f'No match: {n_no_match}  Added: {n_added}  Errors: {n_errors}'
    )


if __name__ == '__main__':
    main()
