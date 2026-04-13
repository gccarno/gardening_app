"""
Shared pytest fixtures for garden app tests.

Uses standard SQLAlchemy with an in-memory SQLite database — no Flask context needed.
"""
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.backend.app.db.models import (
    Base, Garden, GardenBed, Plant, BedPlant, PlantLibrary, Task, WeatherLog,
)


@pytest.fixture(scope='session')
def engine():
    e = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture
def db(engine):
    """Provide a clean SQLAlchemy session that rolls back after each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def library_plant(db):
    p = PlantLibrary(
        name='Tomato',
        type='vegetable',
        spacing_in=24,
        sunlight='Full sun',
        water='Moderate',
        days_to_germination=7,
        days_to_harvest=70,
        sow_indoor_weeks=6,
        transplant_offset=0,
        direct_sow_offset=2,
        good_neighbors=json.dumps(['Basil', 'Carrot', 'Marigold']),
        bad_neighbors=json.dumps(['Fennel', 'Brassica']),
    )
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def garden(db):
    g = Garden(
        name='Test Garden',
        usda_zone='5b',
        last_frost_date=date(2026, 4, 15),
        latitude=41.8,
        longitude=-87.6,
        city='Chicago',
        state='IL',
    )
    db.add(g)
    db.flush()
    return g


@pytest.fixture
def bed(db, garden):
    b = GardenBed(
        name='Raised Bed A',
        garden_id=garden.id,
        width_ft=4.0,
        height_ft=8.0,
    )
    db.add(b)
    db.flush()
    # Refresh garden to pick up the new bed in its .beds relationship
    db.refresh(garden)
    return b


@pytest.fixture
def plant_in_bed(db, garden, bed, library_plant):
    p = Plant(
        name='Tomato',
        type='vegetable',
        garden_id=garden.id,
        library_id=library_plant.id,
        planted_date=date.today(),
        status='growing',
    )
    db.add(p)
    db.flush()
    bp = BedPlant(bed_id=bed.id, plant_id=p.id)
    db.add(bp)
    db.flush()
    db.refresh(garden)
    db.refresh(bed)
    return p


@pytest.fixture
def upcoming_task(db, garden):
    t = Task(
        title='Water tomatoes',
        task_type='watering',
        due_date=date.today() + timedelta(days=5),
        garden_id=garden.id,
        completed=False,
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def weather_log(db, garden):
    w = WeatherLog(
        garden_id=garden.id,
        date=date.today() - timedelta(days=2),
        rainfall_in=0.4,
        temp_high_f=72.0,
        temp_low_f=55.0,
        source='manual',
    )
    db.add(w)
    db.flush()
    return w
