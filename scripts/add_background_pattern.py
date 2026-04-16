"""
One-time migration: add background_pattern column to garden and garden_bed tables.
Run from the repo root:  python scripts/add_background_pattern.py
"""
import pathlib
import sqlite3

DB_PATH = pathlib.Path(__file__).parents[1] / 'apps' / 'api' / 'instance' / 'garden.db'

stmts = [
    "ALTER TABLE garden ADD COLUMN background_pattern VARCHAR(30)",
    "ALTER TABLE garden_bed ADD COLUMN background_pattern VARCHAR(30)",
]

con = sqlite3.connect(DB_PATH)
for stmt in stmts:
    try:
        con.execute(stmt)
        print(f'OK: {stmt}')
    except Exception as e:
        print(f'Skip (already exists?): {e}')
con.commit()
con.close()
print('Done.')
