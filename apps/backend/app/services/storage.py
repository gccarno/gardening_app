"""
Static file storage abstraction.

Writes go to the local `apps/api/static/` tree by default. When the
GCS_STATIC_BUCKET env var is set (cloud deployment, where plant images live
in a PRIVATE Google Cloud Storage bucket), reads/writes go to GCS under the
`static/` prefix instead, authenticated via the service-account key
(GOOGLE_APPLICATION_CREDENTIALS). URL paths (`/static/...`) are unchanged
either way — main.py proxies them from GCS when the local tree is absent.
"""
import os
from functools import lru_cache

from .helpers import STATIC_DIR

GCS_STATIC_BUCKET = os.environ.get('GCS_STATIC_BUCKET')


@lru_cache(maxsize=1)
def _bucket():
    from google.cloud import storage as gcs
    return gcs.Client().bucket(GCS_STATIC_BUCKET)


def save_static(relpath: str, data: bytes) -> None:
    """Save bytes at the given path relative to the static root."""
    if GCS_STATIC_BUCKET:
        _bucket().blob(f'static/{relpath}').upload_from_string(data)
    else:
        dest = STATIC_DIR / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def read_static(relpath: str) -> bytes | None:
    """Return file bytes, or None if the file doesn't exist."""
    if GCS_STATIC_BUCKET:
        blob = _bucket().blob(f'static/{relpath}')
        return blob.download_as_bytes() if blob.exists() else None
    path = STATIC_DIR / relpath
    return path.read_bytes() if path.exists() else None


def delete_static(relpath: str) -> None:
    """Delete a file if it exists; no-op otherwise."""
    if GCS_STATIC_BUCKET:
        blob = _bucket().blob(f'static/{relpath}')
        if blob.exists():
            blob.delete()
    else:
        path = STATIC_DIR / relpath
        if path.exists():
            path.unlink()
