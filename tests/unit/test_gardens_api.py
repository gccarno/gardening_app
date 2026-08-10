"""Garden CRUD + dashboard endpoint tests.

External ZIP/frost lookups are monkeypatched — tests must never hit the network.
"""
from datetime import date, timedelta

import pytest

from apps.backend.app.routers import gardens as gardens_router
from apps.backend.app.db.models import Plant, Task


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(gardens_router, '_apply_zip', lambda garden, zip_code: None)
    monkeypatch.setattr(gardens_router, '_apply_frost', lambda garden, zip_code: None)


def test_create_garden(client):
    r = client.post('/api/gardens', json={'name': 'Backyard'})
    assert r.status_code == 200
    data = r.json()
    assert data['name'] == 'Backyard'
    assert data['unit'] == 'ft'


def test_list_gardens(client, garden):
    r = client.get('/api/gardens')
    assert r.status_code == 200
    assert any(g['id'] == garden.id for g in r.json())


def test_get_garden_404(client):
    assert client.get('/api/gardens/99999').status_code == 404


def test_update_garden(client, garden):
    r = client.put(f'/api/gardens/{garden.id}', json={
        'name': 'Renamed', 'watering_frequency_days': 3,
        'last_frost_date': '2026-04-20',
    })
    assert r.status_code == 200
    data = r.json()
    assert data['name'] == 'Renamed'
    assert data['watering_frequency_days'] == 3
    assert data['last_frost_date'] == '2026-04-20'


def test_delete_garden(client, garden):
    assert client.delete(f'/api/gardens/{garden.id}').json()['ok'] is True
    assert client.get(f'/api/gardens/{garden.id}').status_code == 404


def test_delete_garden_clears_watering_rows(client, db, garden, bed):
    """A watered garden must still delete.

    Only WeatherLog was cleared here; watering_event and ml_watering_snapshot
    have the same NOT NULL garden_id with no cascade, so they raised a
    ForeignKeyViolation 500 on Postgres. SQLite does not enforce FKs here, so
    assert the rows are gone rather than relying on the IntegrityError.
    """
    from datetime import date

    from apps.backend.app.db.models import MlWateringSnapshot, WateringEvent

    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id,
                         event_date=date.today(), amount='light', source='user'))
    db.add(MlWateringSnapshot(garden_id=garden.id, bed_id=bed.id,
                              snapshot_date=date.today()))
    db.flush()

    assert client.delete(f'/api/gardens/{garden.id}').json()['ok'] is True
    assert db.query(WateringEvent).filter_by(garden_id=garden.id).count() == 0
    assert db.query(MlWateringSnapshot).filter_by(garden_id=garden.id).count() == 0


def test_default_garden_setting(client, garden):
    assert client.get('/api/settings/default-garden').json()['garden_id'] is None
    client.post('/api/settings/default-garden', json={'garden_id': garden.id})
    assert client.get('/api/settings/default-garden').json()['garden_id'] == garden.id
    # E2E teardown restores a "no default" state through this same path.
    client.post('/api/settings/default-garden', json={'garden_id': None})
    assert client.get('/api/settings/default-garden').json()['garden_id'] is None


def test_default_garden_setting_ignores_unreachable_garden(client, garden):
    """A default pointing at a garden the caller can't reach reads back as None.

    The setting is global and was returned unvalidated, so after an E2E run left
    it on a since-deleted garden the mobile dashboard — which does
    `defaultId ?: gardens.first()` — sent every request to a 404 instead of
    falling back to a garden the user actually has.
    """
    client.post('/api/settings/default-garden', json={'garden_id': garden.id})
    client.delete(f'/api/gardens/{garden.id}')
    assert client.get('/api/settings/default-garden').json()['garden_id'] is None


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_dashboard_metrics(client, db, garden, bed):
    db.add(Plant(name='Tomato', garden_id=garden.id, status='growing'))
    db.add(Plant(name='Basil', garden_id=garden.id, status='planning'))
    db.add(Task(title='Overdue', garden_id=garden.id, completed=False,
                due_date=date.today() - timedelta(days=2)))
    db.add(Task(title='Soon', garden_id=garden.id, completed=False,
                due_date=date.today() + timedelta(days=2)))
    db.flush()

    r = client.get(f'/api/dashboard?garden_id={garden.id}')
    assert r.status_code == 200
    m = r.json()['metrics']
    assert m['bed_count'] == 1
    assert m['plant_count'] == 2
    # Regression: used to count status == 'active' which never matches
    assert m['plants_active'] == 1
    assert m['task_count'] == 2
    assert m['overdue_tasks'] == 1


def test_dashboard_upcoming_and_hint(client, garden, upcoming_task):
    r = client.get(f'/api/dashboard?garden_id={garden.id}')
    data = r.json()
    assert data['upcoming_tasks'][0]['title'] == 'Water tomatoes'
    assert data['season'] in ('Winter', 'Spring', 'Summer', 'Fall')
    assert data['hint_action']


def test_quick_task_autotitle(client, garden):
    r = client.post(f'/api/gardens/{garden.id}/quick-task', json={'task_type': 'weeding'})
    assert r.status_code == 200
    task_id = r.json()['task_id']
    t = client.get(f'/api/tasks/{task_id}').json()
    assert t['title'] == f'Weed {garden.name}'


def test_bulk_care_water(client, db, garden, plant_in_bed):
    r = client.post(f'/api/gardens/{garden.id}/bulk-care', json={'action': 'water'})
    assert r.status_code == 200
    assert r.json()['updated'] == 1
    db.expire_all()
    assert plant_in_bed.last_watered == date.today()
    assert plant_in_bed.bed_plants[0].last_watered == date.today()


def test_bulk_care_invalid_action(client, garden):
    r = client.post(f'/api/gardens/{garden.id}/bulk-care', json={'action': 'burn'})
    assert r.status_code == 400


def test_annotations_roundtrip(client, garden):
    shapes = [{'type': 'rect', 'x': 1, 'y': 2}]
    client.post(f'/api/gardens/{garden.id}/annotations', json={'shapes': shapes})
    assert client.get(f'/api/gardens/{garden.id}/annotations').json()['shapes'] == shapes
