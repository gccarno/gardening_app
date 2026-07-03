"""
Shared pytest fixtures for garden app tests.

Uses standard SQLAlchemy with an in-memory SQLite database — no Flask context needed.
"""
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.backend.app.db.models import (
    Base, Garden, GardenBed, GardenMember, Plant, BedPlant, PlantLibrary,
    Task, User, WeatherLog,
)


@pytest.fixture
def engine():
    # Function-scoped so commits from endpoints under test can't leak between
    # tests. StaticPool keeps the single in-memory DB shared across sessions.
    e = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    """Provide a clean SQLAlchemy session that rolls back after each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def user(db):
    """Default authenticated test user (owner of the `garden` fixture)."""
    from apps.backend.app.services.auth import hash_password
    u = User(email='test@example.com', display_name='Test',
             password_hash=hash_password('password123'))
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def client(db, user):
    """FastAPI TestClient wired to the test database session, logged in
    as the `user` fixture.

    Instantiated without a context manager so the app lifespan (migrations,
    scheduler) never runs.
    """
    from fastapi.testclient import TestClient
    from apps.backend.app.main import app
    from apps.backend.app.db.session import get_db
    from apps.backend.app.services.auth import get_current_user

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


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
def garden(db, user):
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
    db.add(GardenMember(garden_id=g.id, user_id=user.id, role='owner'))
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
