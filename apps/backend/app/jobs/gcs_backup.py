"""
GCS backup job for garden.db.

Uploads a gzip-compressed SQLite snapshot to Google Cloud Storage only when
the database has actually changed (hash-based conditional upload).  Safe to
call from APScheduler threads and from the CLI wrapper in scripts/gcs_backup.py.

Environment variables:
  GCS_BUCKET_NAME              Required.  Name of the GCS bucket.
  GCS_BACKUP_PREFIX            Optional.  Object prefix (default: garden_db).
  GARDEN_DB_PATH               Optional.  Override DB path (mirrors session.py).
  GOOGLE_APPLICATION_CREDENTIALS  Path to a service-account key JSON file.
                               Consumed automatically by google-auth; no manual
                               reading needed.
"""

import gzip
import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', '')
_PREFIX      = os.environ.get('GCS_BACKUP_PREFIX', 'garden_db')
_KEEP_DAILY  = 7
_KEEP_WEEKLY = 4

# Mirror the path logic in apps/backend/app/db/session.py
# parents[3] = apps/  →  apps/api/instance/garden.db
_DEFAULT_DB = Path(__file__).parents[3] / 'api' / 'instance' / 'garden.db'
_DB_PATH    = Path(os.environ.get('GARDEN_DB_PATH') or _DEFAULT_DB)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _snapshot_db(src: Path, dest: Path) -> None:
    """Create a consistent online backup of `src` at `dest` via sqlite3 API."""
    src_conn  = sqlite3.connect(str(src))
    dest_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()


def _sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of `path`, reading in 1 MB chunks."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _get_last_hash(bucket, blob_name: str) -> str | None:
    """
    Return the sha256 stored in the object's custom metadata, or None if the
    object does not exist or has no hash.  Costs 1 Class B read operation.
    """
    blob = bucket.blob(blob_name)
    try:
        blob.reload()
    except Exception:
        return None
    meta = blob.metadata or {}
    return meta.get('sha256')


def _compress_gz(src: Path, dest: Path) -> None:
    """Gzip-compress `src` into `dest`."""
    with open(src, 'rb') as f_in, gzip.open(dest, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)


def _upload(
    bucket,
    gz_path: Path,
    sha256: str,
    versioned_name: str,
    latest_name: str,
    dry_run: bool,
) -> None:
    """Upload `gz_path` as both the versioned blob and the `latest` pointer."""
    size_mb = gz_path.stat().st_size / (1024 * 1024)
    metadata = {'sha256': sha256}

    if dry_run:
        log.info('[dry-run] Would upload %s (%.1f MB, sha256=%s…)', versioned_name, size_mb, sha256[:12])
        log.info('[dry-run] Would update %s pointer.', latest_name)
        return

    versioned_blob = bucket.blob(versioned_name)
    versioned_blob.metadata = metadata
    versioned_blob.upload_from_filename(str(gz_path), content_type='application/gzip')
    log.info('[upload] %s (%.1f MB, sha256=%s…)', versioned_name, size_mb, sha256[:12])

    latest_blob = bucket.blob(latest_name)
    latest_blob.metadata = metadata
    latest_blob.upload_from_filename(str(gz_path), content_type='application/gzip')
    log.info('[upload] Updated %s pointer.', latest_name)


def _apply_retention(bucket, dry_run: bool) -> None:
    """
    Keep the newest _KEEP_DAILY versioned backups, plus one backup per ISO week
    for the most recent _KEEP_WEEKLY distinct weeks.  Delete everything else.
    Never touches `latest.db.gz`.
    """
    prefix = f'{_PREFIX}/garden_'
    blobs  = list(bucket.list_blobs(prefix=prefix))

    # Parse timestamps from names like garden_db/garden_2026-04-15T03-00.db.gz
    dated = []
    for blob in blobs:
        stem = blob.name  # e.g. garden_db/garden_2026-04-15T03-00.db.gz
        try:
            ts_str = stem.split('garden_', 1)[1].replace('.db.gz', '')
            dt = datetime.strptime(ts_str, '%Y-%m-%dT%H-%M').replace(tzinfo=timezone.utc)
            dated.append((dt, blob))
        except (IndexError, ValueError):
            continue  # skip unparseable names

    dated.sort(key=lambda x: x[0], reverse=True)  # newest first

    keep   = set()
    weekly = {}  # iso_week -> blob_name of the one we keep

    for i, (dt, blob) in enumerate(dated):
        if i < _KEEP_DAILY:
            keep.add(blob.name)
            continue
        week_key = dt.isocalendar()[:2]  # (year, week)
        if len(weekly) < _KEEP_WEEKLY and week_key not in weekly:
            weekly[week_key] = blob.name
            keep.add(blob.name)

    kept    = 0
    deleted = 0
    for dt, blob in dated:
        if blob.name in keep:
            kept += 1
        else:
            if dry_run:
                log.info('[dry-run] Would delete %s (beyond retention window)', blob.name)
            else:
                blob.delete()
                log.info('[retention] Deleted %s (beyond retention window)', blob.name)
            deleted += 1

    log.info('[retention] Kept %d versioned backup(s); deleted %d.', kept, deleted)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_backup(dry_run: bool = False) -> None:
    """
    Orchestrate a full backup cycle.  Called by APScheduler (3 AM daily) and
    by scripts/gcs_backup.py for manual runs.

    Exits early (warning only) if GCS_BUCKET_NAME is not configured so the
    server starts normally in dev environments without GCS credentials.
    """
    if not _BUCKET_NAME:
        log.warning('[gcs_backup] GCS_BUCKET_NAME not set — skipping backup.')
        return

    if not _DB_PATH.exists():
        log.error('[gcs_backup] DB not found at %s — skipping backup.', _DB_PATH)
        return

    try:
        from google.cloud import storage  # noqa: PLC0415 — lazy import
    except ImportError:
        log.error('[gcs_backup] google-cloud-storage not installed. Run: uv sync')
        return

    client = storage.Client()
    bucket = client.bucket(_BUCKET_NAME)

    now           = datetime.now(tz=timezone.utc)
    versioned_name = f'{_PREFIX}/garden_{now.strftime("%Y-%m-%dT%H-%M")}.db.gz'
    latest_name    = f'{_PREFIX}/latest.db.gz'

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path    = Path(tmp)
        snapshot    = tmp_path / 'garden.db'
        gz_snapshot = tmp_path / 'garden.db.gz'

        # 1. Create consistent snapshot
        log.info('[gcs_backup] Snapshotting %s …', _DB_PATH)
        _snapshot_db(_DB_PATH, snapshot)

        # 2. Compute hash of snapshot
        sha256 = _sha256_file(snapshot)
        log.debug('[gcs_backup] Snapshot sha256=%s', sha256)

        # 3. Check last uploaded hash — skip if unchanged
        last_hash = _get_last_hash(bucket, latest_name)
        if last_hash and last_hash == sha256:
            log.info('[skip] DB unchanged (sha256 matches last upload); no backup needed.')
            return

        # 4. Compress
        _compress_gz(snapshot, gz_snapshot)

        # 5. Upload versioned + latest
        _upload(bucket, gz_snapshot, sha256, versioned_name, latest_name, dry_run)

        # 6. Enforce retention policy
        if not dry_run:
            _apply_retention(bucket, dry_run=False)
        else:
            _apply_retention(bucket, dry_run=True)

    log.info('[gcs_backup] Done.')
