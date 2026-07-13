"""
Upload ONE image per plant (the primary) to the private GCS static bucket,
optionally downscaled to cut storage and transfer costs.

Why not a .zip? JPEGs are already compressed — zipping them saves ~1% — and
packing images into an archive would force the app to download the whole
archive to show one picture, defeating lazy loading. Instead each image is a
separate object, the app fetches an image only when it is displayed (lazy
load), and long-lived Cache-Control headers make browsers / the Android app
keep a local copy so each image transfers from the bucket at most once per
device. Downscaling to --max-px (default 800, plenty for the UI) is what
actually shrinks the bill: ~5.6 GB of originals become well under 1 GB.

Non-primary gallery images are NOT uploaded — in the cloud the library detail
gallery will only show the primary image. Locally nothing changes (the app
serves the full on-disk tree when it exists).

Usage:
    uv run python scripts/upload_primary_images_gcs.py --bucket garden_app_static --dry-run
    uv run python scripts/upload_primary_images_gcs.py --bucket garden_app_static
    uv run python scripts/upload_primary_images_gcs.py --bucket garden_app_static --no-resize

Requires GOOGLE_APPLICATION_CREDENTIALS pointing at the service-account JSON
key (see DEPLOYMENT.md section 2), or `gcloud auth application-default login`.
"""

import argparse
import io
import logging
import sys
from pathlib import Path

# Bootstrap: add repo root to sys.path so the app package is importable.
_REPO_ROOT = Path(__file__).parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [upload_images] %(levelname)s %(message)s')
log = logging.getLogger(__name__)

from apps.backend.app.db.models import PlantLibrary  # noqa: E402
from apps.backend.app.db.session import SessionLocal  # noqa: E402

STATIC_DIR = _REPO_ROOT / 'apps' / 'api' / 'static'
CACHE_CONTROL = 'public, max-age=31536000, immutable'  # filenames are unique; content never changes


def local_path(filename: str) -> Path:
    """Mirror the web app's plantImageUrl(): bare names live in plant_images/."""
    return STATIC_DIR / filename if '/' in filename else STATIC_DIR / 'plant_images' / filename


def blob_name(filename: str) -> str:
    return f'static/{filename}' if '/' in filename else f'static/plant_images/{filename}'


def maybe_downscale(data: bytes, max_px: int) -> bytes:
    """Downscale so the longest side is max_px. Returns original bytes if the
    image is already small enough or in a format we don't re-encode."""
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
    except Exception:
        return data
    if fmt not in ('JPEG', 'PNG') or max(img.size) <= max_px:
        return data
    img.thumbnail((max_px, max_px))
    out = io.BytesIO()
    if fmt == 'JPEG':
        img.convert('RGB').save(out, 'JPEG', quality=82, optimize=True)
    else:
        img.save(out, 'PNG', optimize=True)
    return out.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description='Upload one (primary) image per plant to GCS.')
    parser.add_argument('--bucket', required=True, help='Bucket name, e.g. garden_app_static')
    parser.add_argument('--max-px', type=int, default=800, help='Longest side after downscale (default 800)')
    parser.add_argument('--no-resize', action='store_true', help='Upload original bytes untouched')
    parser.add_argument('--dry-run', action='store_true', help='Report what would be uploaded; no writes')
    args = parser.parse_args()

    db = SessionLocal()
    filenames = [f for (f,) in db.query(PlantLibrary.image_filename)
                 .filter(PlantLibrary.image_filename.isnot(None)).distinct()]
    db.close()
    log.info('%d plants with a primary image', len(filenames))

    from google.cloud import storage as gcs
    bucket = gcs.Client().bucket(args.bucket)
    existing = {b.name for b in bucket.list_blobs(prefix='static/')}
    log.info('%d objects already in gs://%s/static/', len(existing), args.bucket)

    uploaded = skipped = missing = 0
    total_bytes = 0
    for i, filename in enumerate(sorted(filenames), 1):
        name = blob_name(filename)
        if name in existing:
            skipped += 1
            continue
        src = local_path(filename)
        if not src.exists():
            missing += 1
            log.warning('missing on disk: %s', src)
            continue
        data = src.read_bytes()
        if not args.no_resize:
            data = maybe_downscale(data, args.max_px)
        total_bytes += len(data)
        if not args.dry_run:
            blob = bucket.blob(name)
            blob.cache_control = CACHE_CONTROL
            blob.upload_from_string(data)
        uploaded += 1
        if i % 250 == 0:
            log.info('progress: %d/%d (%.1f MB so far)', i, len(filenames), total_bytes / 1e6)

    verb = 'would upload' if args.dry_run else 'uploaded'
    log.info('done: %s %d images (%.1f MB), %d already present, %d missing on disk',
             verb, uploaded, total_bytes / 1e6, skipped, missing)


if __name__ == '__main__':
    main()
