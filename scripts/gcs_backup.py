"""
CLI wrapper for the GCS database backup job.

Usage:
    uv run python scripts/gcs_backup.py              # real backup
    uv run python scripts/gcs_backup.py --dry-run    # log what would happen, no uploads
"""

import argparse
import logging
import sys
from pathlib import Path

# Bootstrap: add repo root to sys.path so the app package is importable.
_REPO_ROOT = Path(__file__).parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / '.env')

# Configure logging before importing the job module (which grabs the logger at
# import time).  Writes to both stdout and logs/gcs_backup.log.
_LOG_DIR = _REPO_ROOT / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [gcs_backup] %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_DIR / 'gcs_backup.log', encoding='utf-8'),
    ],
)

from apps.backend.app.jobs.gcs_backup import run_backup  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description='Back up garden.db to Google Cloud Storage.')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Log what would happen without uploading or deleting anything.',
    )
    args = parser.parse_args()
    run_backup(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
