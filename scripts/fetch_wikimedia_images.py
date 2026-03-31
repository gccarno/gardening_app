"""
Fetch multiple plant images from Wikimedia Commons and iNaturalist.

Uses the Wikimedia Commons API (free, no auth) to search for up to --limit
images per plant, then falls back to iNaturalist if Commons yields nothing.
Detects duplicates by SHA-256 hash before writing to disk.

Usage:
    python scripts/fetch_wikimedia_images.py               # all plants, 3 images each
    python scripts/fetch_wikimedia_images.py --limit 5     # up to 5 per plant
    python scripts/fetch_wikimedia_images.py --plant-id 12 # single plant
    python scripts/fetch_wikimedia_images.py --source wikimedia
    python scripts/fetch_wikimedia_images.py --dry-run     # show URLs, no writes
    python scripts/fetch_wikimedia_images.py --delay 3     # 3s between plants (default 2)
    python scripts/fetch_wikimedia_images.py --retries 8   # more retries on 429 (default 5)

Attribution note:
    Wikimedia Commons images are typically CC-BY-SA 4.0. The script stores the
    artist + license string in PlantLibraryImage.attribution so it can be
    displayed in the UI.

Rate limits:
    iNaturalist: ~60 req/min anonymous. Default --delay 2.0 keeps well under this.
    Wikimedia Commons: very permissive; 1s delay is usually fine.
    The urllib3 Retry adapter automatically honours Retry-After response headers.
"""
import argparse
import hashlib
import os
import re
import sys
import time

# Ensure apps/api is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'api'))

from dotenv import load_dotenv
load_dotenv()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.main import create_app
from app.db.models import db, PlantLibrary, PlantLibraryImage

COMMONS_API  = 'https://commons.wikimedia.org/w/api.php'
INAT_API     = 'https://api.inaturalist.org/v1/taxa'

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'

# Retry adapter is configured after arg parsing so --retries applies;
# a default adapter is set here and replaced in main() with the user's value.
def _make_retry_adapter(total=5):
    retry = Retry(
        total=total,
        backoff_factor=2,              # waits 2, 4, 8, 16, 32s between retries
        status_forcelist=[429, 500, 502, 503],
        respect_retry_after_header=True,  # honours Retry-After header from server
        allowed_methods=['GET'],
    )
    return HTTPAdapter(max_retries=retry)

_adapter = _make_retry_adapter()
SESSION.mount('https://', _adapter)
SESSION.mount('http://', _adapter)


# ── Utilities ──────────────────────────────────────────────────────────────────

def ext_from_url(url):
    path = url.split('?')[0].lower()
    if path.endswith('.png'):  return '.png'
    if path.endswith('.webp'): return '.webp'
    return '.jpg'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def download_bytes(url, timeout=20):
    """Download URL → bytes. The Session's Retry adapter handles 429/5xx automatically,
    including honouring Retry-After headers. Returns None on failure."""
    try:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f'    download error: {e}')
    return None


# ── Wikimedia Commons ──────────────────────────────────────────────────────────

def commons_search_files(query, limit=5):
    """Search Commons for image files matching query. Returns list of file titles."""
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'srnamespace': 6,     # File: namespace
        'srlimit': min(limit * 2, 20),  # fetch extras to allow for filtering
        'format': 'json',
    }
    try:
        r = SESSION.get(COMMONS_API, params=params, timeout=10)
        r.raise_for_status()
        hits = r.json().get('query', {}).get('search', [])
        return [h['title'] for h in hits]
    except Exception as e:
        print(f'    commons search error: {e}')
        return []


def commons_image_info(file_titles):
    """Fetch imageinfo (URL + attribution) for a list of File: titles.
    Returns list of dicts: {title, url, ext, attribution}"""
    if not file_titles:
        return []
    params = {
        'action': 'query',
        'titles': '|'.join(file_titles[:10]),
        'prop': 'imageinfo',
        'iiprop': 'url|extmetadata',
        'iiurlwidth': 600,
        'format': 'json',
    }
    try:
        r = SESSION.get(COMMONS_API, params=params, timeout=10)
        r.raise_for_status()
        pages = r.json().get('query', {}).get('pages', {})
    except Exception as e:
        print(f'    commons imageinfo error: {e}')
        return []

    results = []
    for page in pages.values():
        title = page.get('title', '')
        for ii in page.get('imageinfo', []):
            url = ii.get('thumburl') or ii.get('url', '')
            if not url:
                continue
            lower = url.lower()
            # Skip SVGs, GIFs, icons, logos
            if any(lower.endswith(s) for s in ('.svg', '.gif')):
                continue
            if any(kw in lower for kw in ('icon', 'logo', 'symbol', 'map')):
                continue
            meta = ii.get('extmetadata', {})
            artist = meta.get('Artist', {}).get('value', '')
            # Strip HTML tags from artist string
            artist = re.sub(r'<[^>]+>', '', artist).strip()
            license_name = meta.get('LicenseShortName', {}).get('value', '')
            attribution = ' / '.join(filter(None, [artist, license_name])) or None
            results.append({
                'title': title,
                'url': url,
                'ext': ext_from_url(url),
                'attribution': attribution,
                'source': 'wikimedia',
                'source_url': url,
            })
    return results


def fetch_wikimedia(entry, limit):
    """Return up to `limit` candidate image dicts for this plant from Wikimedia Commons."""
    queries = []
    if entry.scientific_name:
        queries.append(entry.scientific_name)
    queries.append(f'{entry.name} plant')

    titles = []
    seen_titles = set()
    for q in queries:
        for t in commons_search_files(q, limit):
            if t not in seen_titles:
                seen_titles.add(t)
                titles.append(t)
        if len(titles) >= limit * 2:
            break

    candidates = commons_image_info(titles)
    return candidates[:limit]


# ── iNaturalist ────────────────────────────────────────────────────────────────

def fetch_inaturalist(entry, limit):
    """Return up to `limit` candidate image dicts from iNaturalist taxa photos."""
    query = entry.scientific_name or entry.name
    try:
        r = SESSION.get(INAT_API, params={'q': query, 'rank': 'species', 'per_page': 1}, timeout=10)
        r.raise_for_status()
        results = r.json().get('results', [])
    except Exception as e:
        print(f'    iNaturalist error: {e}')
        return []

    candidates = []
    for taxon in results[:1]:
        photos = taxon.get('taxon_photos', [])
        if not photos:
            dp = taxon.get('default_photo')
            if dp:
                photos = [{'photo': dp}]
        for tp in photos[:limit]:
            photo = tp.get('photo', {})
            url = photo.get('medium_url') or photo.get('url', '')
            if not url:
                continue
            url = url.replace('square', 'medium')
            attr = photo.get('attribution', '') or None
            candidates.append({
                'url': url,
                'ext': ext_from_url(url),
                'attribution': attr,
                'source': 'inaturalist',
                'source_url': url,
            })
    return candidates[:limit]


# ── Core save logic ────────────────────────────────────────────────────────────

def save_image_for_entry(entry, candidate, img_dir, dry_run):
    """Download + save one candidate image for entry. Returns True on success."""
    url = candidate['url']
    source = candidate['source']
    ext = candidate['ext']
    attribution = candidate.get('attribution')
    source_url = candidate.get('source_url', url)

    img_bytes = download_bytes(url)
    if not img_bytes:
        return False

    fhash = sha256_bytes(img_bytes)

    if dry_run:
        print(f'    [dry-run] {source}: {url[:80]}')
        return True

    # Check for duplicate hash globally
    existing = PlantLibraryImage.query.filter_by(file_hash=fhash).first()
    if existing:
        print(f'    [duplicate] hash matches existing image {existing.filename}', flush=True)
        return False

    count = PlantLibraryImage.query.filter_by(
        plant_library_id=entry.id, source=source
    ).count()
    filename = f'{entry.id}_{source}_{count + 1}{ext}'
    dest = os.path.join(img_dir, filename)
    with open(dest, 'wb') as f:
        f.write(img_bytes)

    has_primary = PlantLibraryImage.query.filter_by(
        plant_library_id=entry.id, is_primary=True
    ).first() is not None
    is_primary = not has_primary

    db.session.add(PlantLibraryImage(
        plant_library_id=entry.id,
        filename=filename,
        source=source,
        source_url=source_url,
        attribution=attribution,
        file_hash=fhash,
        is_primary=is_primary,
    ))
    if is_primary:
        entry.image_filename = filename
    db.session.commit()
    print(f'    [{source}] saved {filename}', flush=True)
    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Fetch plant images from public sources')
    p.add_argument('--limit', type=int, default=3, help='Max new images per plant (default: 3)')
    p.add_argument('--plant-id', type=int, default=None, help='Process single plant by ID')
    p.add_argument('--source', choices=['wikimedia', 'inaturalist', 'all'], default='all')
    p.add_argument('--dry-run', action='store_true', help='Show URLs without downloading')
    p.add_argument('--delay', type=float, default=2.0,
                   help='Seconds to wait between plants (default: 2.0). '
                        'iNaturalist allows ~60 req/min; keep >= 1.5 to avoid 429s.')
    p.add_argument('--retries', type=int, default=5,
                   help='Max retries per request when rate-limited (default: 5). '
                        'Uses exponential backoff and honours Retry-After headers.')
    p.add_argument('--start-after', type=str, default=None,
                   help='Skip all plants whose name sorts before or equal to this value '
                        '(case-insensitive). Use to resume after an interruption, e.g. '
                        '"--start-after \\"Solander\'s Geranium\\"". '
                        'The named plant itself is included.')
    return p.parse_args()


def main():
    args = parse_args()

    # Apply --retries to the Session adapter
    adapter = _make_retry_adapter(args.retries)
    SESSION.mount('https://', adapter)
    SESSION.mount('http://', adapter)

    flask_app = create_app()
    with flask_app.app_context():
        img_dir = os.path.join(flask_app.static_folder, 'plant_images')
        os.makedirs(img_dir, exist_ok=True)

        if args.plant_id:
            plants = PlantLibrary.query.filter_by(id=args.plant_id).all()
        elif args.start_after:
            plants = PlantLibrary.query.filter(
                PlantLibrary.name >= args.start_after
            ).order_by(PlantLibrary.name).all()
        else:
            plants = PlantLibrary.query.order_by(PlantLibrary.name).all()

        print(f'{len(plants)} plant(s) to process  '
              f'[source={args.source}, limit={args.limit}, '
              f'delay={args.delay}s, retries={args.retries}, dry_run={args.dry_run}]\n')

        total_added = 0
        total_dupes = 0
        total_errors = 0

        for entry in plants:
            existing_count = len(entry.images)
            needed = args.limit - existing_count
            if needed <= 0 and not args.dry_run:
                print(f'  {entry.name:<28} already has {existing_count} image(s), skipping')
                continue

            print(f'  {entry.name:<28} ({existing_count} existing)', flush=True)

            candidates = []
            if args.source in ('wikimedia', 'all'):
                candidates += fetch_wikimedia(entry, args.limit)
            if args.source in ('inaturalist', 'all') and len(candidates) < args.limit:
                remaining = args.limit - len(candidates)
                candidates += fetch_inaturalist(entry, remaining)

            if not candidates:
                print(f'    no candidates found')
                continue

            added = 0
            for cand in candidates:
                if added >= needed and not args.dry_run:
                    break
                ok = save_image_for_entry(entry, cand, img_dir, args.dry_run)
                if ok:
                    added += 1
                    total_added += 1
                else:
                    total_dupes += 1
                time.sleep(args.delay / 2)  # brief pause between images within a plant

            time.sleep(args.delay)  # full pause between plants

        print(f'\nDone. Added: {total_added}  Duplicates skipped: {total_dupes}  Errors: {total_errors}')


if __name__ == '__main__':
    main()
