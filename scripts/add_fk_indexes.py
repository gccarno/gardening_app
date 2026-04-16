"""
One-shot migration: add FK indexes to the existing SQLite database.

SQLAlchemy's index=True on Column() only creates indexes for new tables.
Run this script once against the live DB to add the missing indexes.

Usage:
    uv run python scripts/add_fk_indexes.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'apps' / 'api' / 'instance' / 'garden.db'


INDEXES = [
    # (index_name, table, column)
    ('ix_garden_bed_garden_id',        'garden_bed',    'garden_id'),
    ('ix_plant_library_id',            'plant',         'library_id'),
    ('ix_plant_garden_id',             'plant',         'garden_id'),
    ('ix_bed_plant_bed_id',            'bed_plant',     'bed_id'),
    ('ix_bed_plant_plant_id',          'bed_plant',     'plant_id'),
    ('ix_canvas_plant_garden_id',      'canvas_plant',  'garden_id'),
    ('ix_canvas_plant_library_id',     'canvas_plant',  'library_id'),
    ('ix_canvas_plant_plant_id',       'canvas_plant',  'plant_id'),
    ('ix_task_plant_id',               'task',          'plant_id'),
    ('ix_task_garden_id',              'task',          'garden_id'),
    ('ix_task_bed_id',                 'task',          'bed_id'),
    ('ix_weather_log_garden_id',       'weather_log',   'garden_id'),
]


def main():
    if not DB_PATH.exists():
        print(f'DB not found at {DB_PATH}')
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for idx_name, table, col in INDEXES:
        sql = f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({col})'
        print(f'  {sql}')
        cur.execute(sql)

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
