"""
GCS restore job for garden.db.

Downloads {prefix}/latest.db.gz from GCS, verifies SHA-256 against stored
metadata, and atomically replaces the local database.  Safe to call from the
admin endpoint and from the CLI wrapper in scripts/gcs_restore.py.

Environment variables: same as gcs_backup.py (GCS_BUCKET_NAME,
GCS_BACKUP_PREFIX, GARDEN_DB_PATH, GOOGLE_APPLICATION_CREDENTIALS).
"""

import gzip
import logging
import os
import shutil
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Reuse constants and helpers from the backup module — single source of truth.
from .gcs_backup import _BUCKET_NAME, _PREFIX, _DB_PATH, _sha256_file


def run_restore(dry_run: bool = False) -> dict:
    """
    Download latest.db.gz from GCS and replace the local DB.

    Returns a dict with:
      status:  'ok' | 'skipped' | 'error'
      message: human-readable description
    """
    if not _BUCKET_NAME:
        msg = 'GCS_BUCKET_NAME not set — skipping restore.'
        log.warning('[gcs_restore] %s', msg)
        return {'status': 'error', 'message': msg}

    try:
        from google.cloud import storage  # noqa: PLC0415
    except ImportError:
        msg = 'google-cloud-storage not installed. Run: uv sync'
        log.error('[gcs_restore] %s', msg)
        return {'status': 'error', 'message': msg}

    client = storage.Client()
    bucket = client.bucket(_BUCKET_NAME)
    latest_name = f'{_PREFIX}/latest.db.gz'

    blob = bucket.blob(latest_name)
    try:
        blob.reload()
    except Exception as exc:
        msg = f'Could not find {latest_name} in bucket {_BUCKET_NAME}: {exc}'
        log.error('[gcs_restore] %s', msg)
        return {'status': 'error', 'message': msg}

    stored_sha256 = (blob.metadata or {}).get('sha256')
    size_mb = (blob.size or 0) / (1024 * 1024)
    log.info('[gcs_restore] Found %s (%.1f MB, stored sha256=%s)', latest_name, size_mb,
             (stored_sha256 or 'none')[:12])

    # Write temp files alongside the DB so os.replace() is always same-filesystem.
    db_dir = _DB_PATH.parent
    db_dir.mkdir(parents=True, exist_ok=True)

    gz_tmp_path = None
    db_tmp_path = None
    try:
        # Download the compressed blob to a sibling temp file.
        gz_fd, gz_tmp = tempfile.mkstemp(dir=db_dir, suffix='.db.gz.tmp')
        os.close(gz_fd)
        gz_tmp_path = Path(gz_tmp)

        log.info('[gcs_restore] Downloading %s …', latest_name)
        blob.download_to_filename(str(gz_tmp_path))

        # Decompress to another sibling temp file.
        db_fd, db_tmp = tempfile.mkstemp(dir=db_dir, suffix='.db.tmp')
        os.close(db_fd)
        db_tmp_path = Path(db_tmp)

        with gzip.open(gz_tmp_path, 'rb') as f_in, open(db_tmp_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Verify SHA-256 of the decompressed snapshot.
        actual_sha256 = _sha256_file(db_tmp_path)
        if stored_sha256 and actual_sha256 != stored_sha256:
            msg = f'SHA-256 mismatch: got {actual_sha256[:12]}… expected {stored_sha256[:12]}…'
            log.error('[gcs_restore] %s', msg)
            return {'status': 'error', 'message': msg}

        log.info('[gcs_restore] SHA-256 verified: %s…', actual_sha256[:12])

        if dry_run:
            msg = f'[dry-run] Would replace {_DB_PATH} with {latest_name} (sha256={actual_sha256[:12]}…)'
            log.info('[gcs_restore] %s', msg)
            return {'status': 'skipped', 'message': msg}

        # Atomic replace.
        os.replace(str(db_tmp_path), str(_DB_PATH))
        db_tmp_path = None  # replaced, don't delete in finally
        log.info('[gcs_restore] Replaced %s with restored DB.', _DB_PATH)

        # Flush the SQLAlchemy connection pool so new connections open the restored file.
        try:
            from ..db.session import engine
            engine.dispose()
            log.info('[gcs_restore] SQLAlchemy connection pool flushed.')
        except Exception as exc:
            log.warning('[gcs_restore] Could not dispose engine: %s', exc)

        msg = f'Restored {_DB_PATH} from {latest_name} (sha256={actual_sha256[:12]}…)'
        log.info('[gcs_restore] Done. %s', msg)
        return {'status': 'ok', 'message': msg}

    except Exception as exc:
        msg = f'Restore failed: {exc}'
        log.exception('[gcs_restore] %s', msg)
        return {'status': 'error', 'message': msg}

    finally:
        for tmp in (gz_tmp_path, db_tmp_path):
            if tmp is not None and tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
