"""
Admin utility endpoints (local use only — no auth).
"""
import logging

from fastapi import APIRouter

from ..jobs.gcs_restore import run_restore

log = logging.getLogger(__name__)

router = APIRouter(prefix='/api/admin', tags=['admin'])


@router.post('/restore-from-gcs')
def restore_from_gcs(dry_run: bool = False):
    """
    Download latest.db.gz from GCS and hot-swap the local SQLite database.

    After os.replace(), new SQLAlchemy connections open the restored file.
    For heavy write traffic, stop the backend first and use the CLI script.

    Query param: ?dry_run=true to preview without replacing.
    """
    log.info('[admin] restore-from-gcs requested (dry_run=%s)', dry_run)
    return run_restore(dry_run=dry_run)
