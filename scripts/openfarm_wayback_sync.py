"""
Enrich PlantLibrary with OpenFarm data via the Wayback Machine.

OpenFarm (openfarm.cc) was a CC0-licensed crowd-sourced gardening database.
Its API servers were shut down in April 2025, but a decade of responses were
archived by the Wayback Machine. This script queries the CDX index to find
those snapshots, downloads the JSON, and fills in missing fields on existing
PlantLibrary entries.

Strategy:
  - Fill-in-blank only — never overwrites populated fields
  - Idempotent — safe to re-run; already-synced plants are skipped unless --force
  - --add-new — off by default; pass to insert crops found in OpenFarm that
    don't match any existing library entry

Usage:
    python scripts/openfarm_wayback_sync.py               # all plants
    python scripts/openfarm_wayback_sync.py --dry-run     # preview, no writes
    python scripts/openfarm_wayback_sync.py --plant-id 5  # single plant
    python scripts/openfarm_wayback_sync.py --add-new     # also add new plants
    python scripts/openfarm_wayback_sync.py --force       # re-fetch even if synced
    python scripts/openfarm_wayback_sync.py --delay 2.0   # slower rate (default 1.5)

Data license: CC0 (Public Domain) — https://github.com/openfarmcc/OpenFarm
"""
import argparse
import json
import os
import sys
import time
import urllib.parse

# Ensure apps/api is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'api'))

from dotenv import load_dotenv
load_dotenv()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.main import create_app
from app.db.models import db, PlantLibrary

CDX_API    = 'https://web.archive.org/cdx/search/cdx'
WAYBACK    = 'https://web.archive.org/web'

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'


def _make_retry_adapter(total=5):
    retry = Retry(
        total=total,
        read=0,            # don't retry on read timeouts — fail fast
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503],
        respect_retry_after_header=True,
        allowed_methods=['GET'],
    )
    return HTTPAdapter(max_retries=retry)


# ── CDX / Wayback helpers ──────────────────────────────────────────────────────

def cdx_find_snapshot(query_url):
    """Return (timestamp, original_url) for the most-recent 200 snapshot of
    query_url, or None if not archived."""
    params = {
        'url':      query_url,
        'output':   'json',
        'fl':       'timestamp,original',
        'filter':   'statuscode:200',
        'limit':    1,
        'collapse': 'urlkey',
    }
    try:
        r = SESSION.get(CDX_API, params=params, timeout=8)
        r.raise_for_status()
        rows = r.json()
        if len(rows) < 2:  # first row is headers; need at least one data row
            return None
        ts, orig = rows[1]
        return ts, orig
    except Exception as e:
        print(f'    CDX error: {e}')
        return None


def wayback_fetch_json(timestamp, original_url):
    """Fetch a Wayback Machine snapshot and return parsed JSON, or None."""
    # if_ modifier returns raw content without the Wayback toolbar HTML
    url = f'{WAYBACK}/{timestamp}if_/{original_url}'
    try:
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'    fetch error: {e}')
        return None


# ── OpenFarm query helpers ─────────────────────────────────────────────────────

def _openfarm_filter_url(query):
    """Build an OpenFarm crops search URL for the given query string."""
    encoded = urllib.parse.quote(query)
    return f'openfarm.cc/api/v1/crops?filter={encoded}'


def find_archived_crops(entry, delay):
    """Try to find an archived OpenFarm search result for this plant.
    Returns parsed JSON data list or None."""
    queries = []
    queries.append(entry.name)
    if entry.scientific_name:
        queries.append(entry.scientific_name)

    for q in queries:
        url = _openfarm_filter_url(q)
        snap = cdx_find_snapshot(url)
        time.sleep(delay / 2)
        if not snap:
            continue
        ts, orig = snap
        data = wayback_fetch_json(ts, orig)
        time.sleep(delay / 2)
        if not data:
            continue
        crops = data.get('data', [])
        if crops:
            return crops, q
    return None, None


def best_match(crops, entry):
    """Pick the best-matching crop from a list of OpenFarm results.
    Priority: exact name match ->scientific name match ->first result."""
    name_lower = entry.name.lower()
    sci_lower  = (entry.scientific_name or '').lower()

    for crop in crops:
        attrs = crop.get('attributes', {})
        if attrs.get('name', '').lower() == name_lower:
            return crop
    for crop in crops:
        attrs = crop.get('attributes', {})
        if sci_lower and attrs.get('binomial_name', '').lower() == sci_lower:
            return crop
    return crops[0] if crops else None


# ── Field merge ────────────────────────────────────────────────────────────────

def _blank(val):
    return val is None or str(val).strip() == ''


def merge_fields(entry, crop, dry_run):
    """Apply OpenFarm crop attributes to entry using fill-in-blank.
    Returns list of (field, new_value) changes applied."""
    attrs   = crop.get('attributes', {})
    changes = []

    def _set(field, value, note=''):
        if value is None:
            return
        if _blank(getattr(entry, field, None)):
            changes.append((field, value, note))
            if not dry_run:
                setattr(entry, field, value)
        else:
            print(f'      {field}: already set, skipping')

    # Direct string fields
    _set('scientific_name', attrs.get('binomial_name') or None)
    _set('sunlight',        attrs.get('sun_requirements') or None)

    # Days to harvest (integer)
    dtm = attrs.get('days_to_maturity')
    if dtm is not None:
        try:
            _set('days_to_harvest', int(dtm))
        except (ValueError, TypeError):
            pass

    # Spacing — prefer spread, fallback to row_spacing (cm ->inches)
    for cm_field in ('spread', 'row_spacing'):
        cm_val = attrs.get(cm_field)
        if cm_val is not None:
            try:
                inches = round(float(cm_val) / 2.54)
                if inches > 0:
                    _set('spacing_in', inches, f'from {cm_field}={cm_val}cm')
                    break
            except (ValueError, TypeError):
                pass

    # Min temperature (°C ->°F)
    min_c = attrs.get('minimum_temperature')
    if min_c is not None:
        try:
            min_f = round(float(min_c) * 9 / 5 + 32)
            _set('temp_min_f', min_f, f'from {min_c}°C')
        except (ValueError, TypeError):
            pass

    # Description ->permapeople_description (shared "description" slot)
    desc = attrs.get('description') or None
    if desc:
        _set('permapeople_description', desc)

    # Sowing method ->appended to notes
    sow = attrs.get('sowing_method') or None
    if sow and _blank(entry.notes):
        _set('notes', sow, 'sowing_method')

    # Companion plants ->good_neighbors JSON array
    companions = attrs.get('companions') or []
    if companions and _blank(entry.good_neighbors):
        names = []
        for c in companions:
            n = c.get('name') or (c.get('attributes', {}) or {}).get('name')
            if n:
                names.append(n)
        if names:
            _set('good_neighbors', json.dumps(names), f'{len(names)} companions')

    return changes


# ── New plant creation ─────────────────────────────────────────────────────────

def create_from_openfarm(crop, dry_run):
    """Create a new PlantLibrary entry from an OpenFarm crop dict."""
    attrs = crop.get('attributes', {})
    name  = attrs.get('name', '').strip()
    if not name:
        return None
    if dry_run:
        print(f'    [dry-run] would add new plant: {name}')
        return None

    entry = PlantLibrary(
        name           = name,
        scientific_name= attrs.get('binomial_name') or None,
        sunlight       = attrs.get('sun_requirements') or None,
        days_to_harvest= int(attrs['days_to_maturity']) if attrs.get('days_to_maturity') else None,
        openfarm_id    = str(crop.get('id', '')),
        openfarm_slug  = name.lower().replace(' ', '-'),
    )
    spread = attrs.get('spread') or attrs.get('row_spacing')
    if spread:
        try:
            entry.spacing_in = round(float(spread) / 2.54)
        except (ValueError, TypeError):
            pass
    min_c = attrs.get('minimum_temperature')
    if min_c is not None:
        try:
            entry.temp_min_f = round(float(min_c) * 9 / 5 + 32)
        except (ValueError, TypeError):
            pass
    db.session.add(entry)
    db.session.commit()
    print(f'    [added] {name} (OpenFarm id={crop.get("id")})')
    return entry


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Sync PlantLibrary with OpenFarm via Wayback Machine')
    p.add_argument('--plant-id', type=int, default=None, help='Process single plant by library ID')
    p.add_argument('--dry-run',  action='store_true',    help='Print changes without writing')
    p.add_argument('--add-new',  action='store_true',    help='Add plants found in OpenFarm but not in library')
    p.add_argument('--force',    action='store_true',    help='Re-fetch even if openfarm_id already set')
    p.add_argument('--delay',    type=float, default=0.5,
                   help='Seconds between Wayback Machine requests (default 0.5)')
    p.add_argument('--retries',  type=int,   default=5,
                   help='Max retries per request (default 5)')
    return p.parse_args()


def main():
    args = parse_args()

    adapter = _make_retry_adapter(args.retries)
    SESSION.mount('https://', adapter)
    SESSION.mount('http://',  adapter)

    flask_app = create_app()
    with flask_app.app_context():
        if args.plant_id:
            plants = PlantLibrary.query.filter_by(id=args.plant_id).all()
        else:
            plants = PlantLibrary.query.order_by(PlantLibrary.name).all()

        print(f'{len(plants)} plant(s) to process  '
              f'[dry_run={args.dry_run}, add_new={args.add_new}, '
              f'force={args.force}, delay={args.delay}s]\n')

        n_updated = n_skipped = n_no_snap = n_no_match = n_errors = n_added = 0

        for entry in plants:
            # Skip if already synced (unless --force)
            if entry.openfarm_id and not args.force:
                print(f'  {entry.name:<30} already synced (id={entry.openfarm_id}), skipping')
                n_skipped += 1
                continue

            print(f'  {entry.name:<30}', end='', flush=True)
            t0 = time.time()

            try:
                crops, matched_query = find_archived_crops(entry, args.delay)
            except Exception as e:
                print(f' ERROR: {e}  ({time.time()-t0:.1f}s)')
                n_errors += 1
                time.sleep(args.delay)
                continue

            if not crops:
                print(f' -> no snapshot  ({time.time()-t0:.1f}s)')
                n_no_snap += 1
                time.sleep(args.delay)
                continue

            crop = best_match(crops, entry)
            if not crop:
                print(f' -> no match  ({time.time()-t0:.1f}s)')
                n_no_match += 1
                time.sleep(args.delay)
                continue

            crop_id   = str(crop.get('id', ''))
            crop_name = crop.get('attributes', {}).get('name', '?')
            print(f' -> matched "{crop_name}" (id={crop_id})  ({time.time()-t0:.1f}s)')

            changes = merge_fields(entry, crop, args.dry_run)

            for field, value, note in changes:
                display = str(value)[:60]
                suffix  = f'  [{note}]' if note else ''
                print(f'      {field}: {display}{suffix}')

            if not args.dry_run:
                entry.openfarm_id   = crop_id
                entry.openfarm_slug = crop_name.lower().replace(' ', '-')
                db.session.commit()

            if changes:
                n_updated += 1
            else:
                print('      (no new fields to fill)')

            time.sleep(args.delay)

        # Optional: scan OpenFarm for plants not in the library
        if args.add_new:
            print('\n--- Scanning for new plants in OpenFarm ---')
            # Common crops to check that might not be in the library yet
            known_names = {p.name.lower() for p in PlantLibrary.query.all()}
            candidates = [
                'Artichoke', 'Asparagus', 'Bok Choy', 'Brussels Sprouts',
                'Butternut Squash', 'Celery', 'Chicory', 'Cilantro', 'Chives',
                'Collard Greens', 'Endive', 'Fennel', 'Horseradish', 'Kohlrabi',
                'Leek', 'Mustard Greens', 'Parsnip', 'Rutabaga', 'Sorrel',
                'Summer Squash', 'Tomatillo', 'Turnip', 'Watercress', 'Winter Squash',
            ]
            for name in candidates:
                if name.lower() in known_names:
                    continue
                print(f'  {name:<30}', end='', flush=True)
                try:
                    url  = _openfarm_filter_url(name)
                    snap = cdx_find_snapshot(url)
                    time.sleep(args.delay / 2)
                    if not snap:
                        print(' ->no snapshot')
                        continue
                    data = wayback_fetch_json(snap[0], snap[1])
                    time.sleep(args.delay / 2)
                    if not data or not data.get('data'):
                        print(' ->no data')
                        continue
                    crop = data['data'][0]
                    new_entry = create_from_openfarm(crop, args.dry_run)
                    if new_entry:
                        n_added += 1
                        known_names.add(name.lower())
                except Exception as e:
                    print(f' ERROR: {e}')
                    n_errors += 1
                time.sleep(args.delay)

        print(f'\nDone.  Updated: {n_updated}  Already synced: {n_skipped}  '
              f'No snapshot: {n_no_snap}  No match: {n_no_match}  '
              f'Added: {n_added}  Errors: {n_errors}')


if __name__ == '__main__':
    main()
