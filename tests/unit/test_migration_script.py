"""Round-trip test for scripts/migrate_sqlite_to_postgres.py (sqlite → sqlite)."""
import sys
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from apps.backend.app.db.models import Base, Garden, GardenBed, Plant, BedPlant, Task
from scripts.migrate_sqlite_to_postgres import main as migrate_main


def _seed_source(path):
    engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    g = Garden(name='Src Garden', usda_zone='6a')
    s.add(g)
    s.flush()
    b = GardenBed(name='Bed', garden_id=g.id, width_ft=4, height_ft=8)
    p = Plant(name='Tomato', garden_id=g.id, status='growing', planted_date=date.today())
    s.add_all([b, p])
    s.flush()
    s.add(BedPlant(bed_id=b.id, plant_id=p.id, grid_x=0, grid_y=0))
    s.add(Task(title='Water', garden_id=g.id))
    s.commit()
    s.close()
    engine.dispose()


def _run(source, target_url, monkeypatch):
    monkeypatch.setattr(sys, 'argv', [
        'migrate', '--source', str(source), '--target', target_url,
    ])
    return migrate_main()


def test_round_trip(tmp_path, monkeypatch):
    source = tmp_path / 'src.db'
    target = tmp_path / 'dst.db'
    _seed_source(source)

    assert _run(source, f'sqlite:///{target}', monkeypatch) == 0

    engine = create_engine(f'sqlite:///{target}')
    with engine.connect() as conn:
        for table_name, expected in [('garden', 1), ('garden_bed', 1),
                                     ('plant', 1), ('bed_plant', 1), ('task', 1)]:
            table = Base.metadata.tables[table_name]
            assert conn.execute(select(func.count()).select_from(table)).scalar() == expected
        garden_table = Base.metadata.tables['garden']
        row = conn.execute(select(garden_table)).mappings().first()
        assert row['name'] == 'Src Garden'
    engine.dispose()


def test_refuses_nonempty_target(tmp_path, monkeypatch):
    source = tmp_path / 'src.db'
    target = tmp_path / 'dst.db'
    _seed_source(source)
    _seed_source(target)  # target already has data

    assert _run(source, f'sqlite:///{target}', monkeypatch) == 1


def test_missing_source_fails(tmp_path, monkeypatch):
    assert _run(tmp_path / 'nope.db', f'sqlite:///{tmp_path / "dst.db"}', monkeypatch) == 1
