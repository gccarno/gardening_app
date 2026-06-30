"""
CLI wrapper for the GCS database restore job.

Usage:
    uv run python scripts/gcs_restore.py              # real restore
    uv run python scripts/gcs_restore.py --dry-run    # log what would happen, no downloads
"""

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / '.env')

_LOG_DIR = _REPO_ROOT / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [gcs_restore] %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_DIR / 'gcs_restore.log', encoding='utf-8'),
    ],
)

from apps.backend.app.jobs.gcs_restore import run_restore  # noqa: E402

log = logging.getLogger('gcs_restore')


def main() -> None:
    parser = argparse.ArgumentParser(description='Restore garden.db from Google Cloud Storage.')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Log what would happen without downloading or replacing anything.',
    )
    args = parser.parse_args()

    if not args.dry_run:
        log.warning(
            'Stop the FastAPI backend before restoring to avoid write conflicts. '
            'Use --dry-run to preview first.'
        )

    result = run_restore(dry_run=args.dry_run)
    log.info('Result: %s — %s', result['status'], result['message'])

    if result['status'] == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
