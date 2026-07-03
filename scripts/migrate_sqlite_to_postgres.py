"""
One-time data migration: copy every table from the local SQLite database to a
target database (Neon Postgres).

Usage:
    uv run python scripts/migrate_sqlite_to_postgres.py --target "postgresql+psycopg://USER:PASS@HOST/dbname?sslmode=require"

Options:
    --source PATH   SQLite file (default: apps/api/instance/garden.db)
    --target URL    Target SQLAlchemy URL (or set DATABASE_URL env var)
    --chunk N       Insert batch size (default 1000)

Behaviour:
    * Creates the schema on the target from the current models.
    * Refuses to run if any target table already has rows (idempotence guard).
    * Copies tables in FK-dependency order.
    * Resets Postgres sequences afterwards so new INSERTs don't collide.
"""
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine, func, insert, select, text  # noqa: E402

from apps.backend.app.db.models import Base  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(REPO_ROOT / 'apps' / 'api' / 'instance' / 'garden.db'))
    parser.add_argument('--target', default=os.environ.get('DATABASE_URL'))
    parser.add_argument('--chunk', type=int, default=1000)
    args = parser.parse_args()

    if not args.target:
        print('ERROR: no target — pass --target or set DATABASE_URL')
        return 1
    if args.target.startswith('sqlite') and args.source in args.target:
        print('ERROR: target must differ from source')
        return 1
    if not Path(args.source).exists():
        print(f'ERROR: source DB not found: {args.source}')
        return 1

    src_engine = create_engine(f'sqlite:///{args.source}')
    dst_engine = create_engine(args.target)

    print(f'Source: {args.source}')
    print(f'Target: {dst_engine.url.render_as_string(hide_password=True)}')

    # 1. Create schema on target
    Base.metadata.create_all(dst_engine)

    tables = Base.metadata.sorted_tables  # FK-dependency order

    # 2. Idempotence guard
    with dst_engine.connect() as dst:
        for table in tables:
            count = dst.execute(select(func.count()).select_from(table)).scalar()
            if count:
                print(f'ERROR: target table "{table.name}" already has {count} rows — aborting.')
                print('Drop/empty the target database (or use a fresh Neon branch) and retry.')
                return 1

    # 3. Copy rows table by table
    with src_engine.connect() as src, dst_engine.begin() as dst:
        for table in tables:
            # Only copy columns that exist in the source DB (older DBs may
            # lack recently added columns; defaults fill the rest).
            src_cols = {
                row[1] for row in src.execute(text(f'PRAGMA table_info("{table.name}")'))
            }
            if not src_cols:
                print(f'  {table.name}: not in source, skipped')
                continue
            cols = [c for c in table.columns if c.name in src_cols]
            rows = src.execute(select(*cols)).mappings().all()
            for i in range(0, len(rows), args.chunk):
                chunk = [dict(r) for r in rows[i:i + args.chunk]]
                if chunk:
                    dst.execute(insert(table), chunk)
            print(f'  {table.name}: {len(rows)} rows')

    # 4. Reset sequences (Postgres only)
    if dst_engine.dialect.name == 'postgresql':
        with dst_engine.begin() as dst:
            for table in tables:
                pk_cols = [c for c in table.primary_key.columns
                           if c.autoincrement is not False and c.type.python_type is int]
                for pk in pk_cols:
                    dst.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk.name}'), "
                        f"COALESCE((SELECT MAX({pk.name}) FROM \"{table.name}\"), 0) + 1, false)"
                    ))
        print('Sequences reset.')

    print('Done. Verify row counts, then point DATABASE_URL at the target.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
